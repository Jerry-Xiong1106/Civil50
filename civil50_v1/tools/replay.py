"""Record isolated workflow replays. Scripted mode tests transport, never answer quality."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
def rows(path): return [json.loads(l) for l in path.read_text().splitlines()]
def keyed(path): return {r['task_id']:r for r in rows(path)}
def log(path,obj):
    with path.open('a') as f:f.write(json.dumps(obj,ensure_ascii=False)+'\n')
def say(path,who,text):
    with path.open('a') as f:f.write('**'+who+'**\n\n'+text+'\n\n')
def settled(client,path):
    deadline=time.monotonic()+300
    while time.monotonic()<deadline:
        r=client.get(path);r.raise_for_status();d=r.json()
        if not d['pending']:return d
        time.sleep(.04 if isinstance(client,TestClient) else .5)
    raise TimeoutError('等待 API 状态转换超时')
def scripted(directory,task,flow,hidden):
    from backend.agent.factory import build_runner
    from backend.agent.model.llm import ScriptedLLM,tool_call
    from backend.agent.runtime.store import RunStore
    from backend.api.conversations import Conversations
    from backend.api.app import create_app
    from backend.case import CaseService,SQLiteCaseRepository
    from backend.common.schemas import RunConfig
    script=[]
    for f in hidden['facts']:
        script.append(tool_call('ask_user',kind='material_request',questions=[{'question_id':f['fact_id'],'text':f['accepted_question_examples'][-1]}]))
    script.append(tool_call('finish',answer='接口测试：已接收本轮材料。'))
    if flow['route']!='consultation':
        for pos,step in enumerate(flow['states']):
            script.append(tool_call('confirm_step',step_id=step,summary='接口演练',answer='接口测试：'+step+' 步骤确认。'))
            if pos==0 and flow['revise_first']:
                script.append(tool_call('confirm_step',step_id=step,summary='修改后确认',answer='接口测试：已分列记载和待核事项。'))
        script.append(tool_call('finish',answer='接口测试：路线步骤已走完。'))
    service=CaseService(SQLiteCaseRepository(directory/'cases.sqlite3'))
    runner=build_runner(llm=ScriptedLLM(script),case_service=service,real_statutes=False,dotenv=None,store=RunStore(directory/'runs'),config=RunConfig()).runner
    return TestClient(create_app(Conversations(runner,service),token='offline-test'),headers={'Authorization':'Bearer offline-test'})

def run(client,task,flow,hidden,mats,out,offline):
    transcript=out/'transcript.md'
    say(transcript,'运行条件','脚本模型，结果仅验证接口。' if offline else '实际配置的服务模型，待人工评审。')
    trace=out/'trace.jsonl'
    response=client.post('/api/conversations',json={'title':task['task_id']});response.raise_for_status()
    cid=response.json()['conversation_id'];path='/api/conversations/'+cid
    def post(action,payload):
        req=dict(request_id=uuid4().hex,**payload)
        log(trace,dict(action=action,conversation_id=cid,request=req))
        for attempt in range(2):
            try:
                r=client.post(path+'/'+action,json=req);break
            except (httpx.TimeoutException,httpx.NetworkError):
                if attempt:raise
        log(trace,dict(http_status=r.status_code,receipt=r.json()));r.raise_for_status()
        return settled(client,path)
    message=task['initial_input']+'\n'+task['user_goal']+'\n'+'\n'.join(task['output_requirements'])
    say(transcript,'用户',message);state=post('messages',dict(text=message))
    selected=False;revised=False;expect_step=None;sent=set();uploaded={}
    for turn in range(flow['budget']):
        log(trace,dict(turn=turn,state=state))
        run=state['run']
        if expect_step:
            assert state['route_progress']['current_step']==expect_step,'修订后步骤已跳转'
            expect_step=None
        if run['status']=='completed':
            final=run['final'];say(transcript,'助手',final['answer'])
            if selected or flow['route']=='consultation':
                if selected and not all(s['status']=='completed' for s in state['route_progress']['steps']):
                    raise RuntimeError('运行已停，指定路线尚有步骤未完成')
                artifacts=[]
                for o in state['outputs']:
                    aid=o.get('artifact_id')
                    if aid:
                        a=client.get(path+'/artifacts/'+aid);a.raise_for_status()
                        (out/Path(aid).name).write_bytes(a.content);artifacts.append(aid)
                if not offline and flow['route']=='litigation' and not artifacts:raise RuntimeError('诉讼准备缺少可下载成果')
                return dict(conversation_id=cid,last_run_id=run['run_id'],status='protocol_completed' if offline else 'endpoint_pending_review',materials_uploaded=len(uploaded),artifacts=artifacts)
            selected=True;say(transcript,'用户选择路线',flow['route'])
            state=post('route',dict(route=flow['route']));continue
        if run['status']!='waiting_user':raise RuntimeError(str(run.get('error') or run['status']))
        wait=run['wait']; assert wait['wait_id']
        if wait.get('message'):say(transcript,'助手',wait['message'])
        if wait['kind']=='step_confirmation':
            step=wait['step_id'];assert step and step==state['route_progress']['current_step'] and wait.get('message')
            modify=flow['revise_first'] and not revised
            if not offline:
                print(step,wait['message']); print('回车确认，输入修订意见可要求修改。')
                instruction=input().strip()
                modify=bool(instruction) or modify
            if modify:
                revised=True;expect_step=step
                reply=dict(step_decision='revise',text=instruction if not offline and instruction else '请分开写已经确认和还要核实的事项。')
            else:reply=dict(step_decision='done')
            say(transcript,'模拟用户确认',json.dumps(reply,ensure_ascii=False))
            state=post('messages',dict(wait_id=wait['wait_id'],reply=reply));continue
        answers={};files=[]
        for q in wait['questions']:
            say(transcript,'助手追问',q['text'])
            matches=[i for i,f in enumerate(flow['facts']) if f['intent'] in q['text']]
            if not offline and not matches:
                print(q['text'],[(i+1,f['intent']) for i,f in enumerate(flow['facts'])])
                choice=input('选择实际问到的事项编号（空格分隔），泛问或范围外按回车：').split()
                matches=[int(s)-1 for s in choice if s in ('1','2')]
            notes=[]
            for i in matches:
                fact=hidden['facts'][i]; notes.append(fact['response']);sent.add(fact['fact_id'])
                if wait['kind']=='material_request':
                    mat=mats[i];p=ROOT/mat['path']
                    assert hashlib.sha256(p.read_bytes()).hexdigest()==mat['sha256']
                    if i not in uploaded:
                        u=client.post(path+'/files',files={'file':(p.name,p.read_bytes(),'text/plain')});u.raise_for_status();rec=u.json()
                        assert rec['content_sha256']==mat['sha256'];log(trace,dict(upload=rec,locator='L3',material_id=mat['material_id']))
                        uploaded[i]={k:rec[k] for k in ('file_id','file_version')}
                    if uploaded[i] not in files:files.append(uploaded[i])
            answers[q['question_id']]=' '.join(notes) or flow['fallback']
            say(transcript,'模拟用户',answers[q['question_id']])
        state=post('messages',dict(wait_id=wait['wait_id'],reply=dict(answers=answers or {},**({} if answers else {'text':flow['fallback']})),attachments=files))
    raise RuntimeError('逐案交互预算已耗尽')

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--out',required=True,type=Path)
    ap.add_argument('--api',help='真实本地 CivRA 服务根地址；默认用脚本模型测试接口')
    ap.add_argument('--case',action='append');ap.add_argument('--civra',type=Path,default=ROOT.parent/'CivRA')
    args=ap.parse_args();sys.path.insert(0,str(args.civra.resolve()))
    from fastapi.testclient import TestClient
    import httpx
    tasks=keyed(ROOT/'development/tasks.jsonl')|keyed(ROOT/'private/heldout-draft/tasks.jsonl')
    flows=keyed(ROOT/'private/workflow.jsonl');h=keyed(ROOT/'private/hidden.jsonl');m=rows(ROOT/'private/materials.jsonl')
    args.out.mkdir(parents=True,exist_ok=False)
    failures=0
    for tid in args.case or sorted(tasks):
        out=args.out/tid;out.mkdir()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                client=(httpx.Client(base_url=args.api,headers={'Authorization':'Bearer '+os.environ['CIVRA_API_TOKEN']},timeout=60) if args.api else scripted(Path(tmp),tasks[tid],flows[tid],h[tid]))
                with client:res=run(client,tasks[tid],flows[tid],h[tid],[r for r in m if r['task_id']==tid],out,not args.api)
                if not args.api:
                    import shutil
                    shutil.copytree(Path(tmp)/'runs',out/'runtime')
        except Exception as exc:
            failures+=1;res=dict(status='failed',reason=str(exc),error_type=type(exc).__name__)
        log(args.out/'summary.jsonl',dict(task_id=tid,**res))
    print('Failures:',failures);sys.exit(bool(failures))

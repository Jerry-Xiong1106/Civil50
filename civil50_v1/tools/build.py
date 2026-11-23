"""Rebuild authored evaluation tables from the pinned local source selections."""
from pathlib import Path
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from decimal import Decimal

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / 'private'
UP = P / 'upstream'
read = lambda p: json.loads(p.read_text(encoding='utf8'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p, s):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding='utf8')
def lines(p, rows):
    save(p, ''.join(json.dumps(x, ensure_ascii=False)+'\n' for x in rows))
def table(p, rows, fields=None):
    with p.open('w', newline='', encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=fields or list(rows[0])); w.writeheader();w.writerows(rows)

origins=read(UP/'origins.json')
selection={l.split('|')[0]:l.split('|')[1:] for l in (P/'selections.txt').read_text().splitlines()}
groups=[
 ('tort','交通事故','case_cn_0006 2-25 2-30 4-99 8-27 8-35 8-37 8-84 9-47 8-q 2-71 3-12 4-40 5-53','CNLCMCNCLLCCNM',3),
 ('lending','民间借贷','0-18 1-38 1-71 2-42 2-94 3-30 4-63 5-0 5-38 6-88 7-35 8-99 9-77','MLCNCLNCLMCNL',3),
 ('contract','买卖合同','case_cn_0007 1-59 2-39 3-98 4-47 6-59 6-76 7-2 7-23 7-55 7-90 7-98 8-62','CLNCMCLNMCMLC',2),
 ('leasing','租赁','case_cn_0020 0-96 1-28 3-17 3-37 5-14 6-28 7-97 1-83 4-4','CMCNCMCNCM',2)]
route_names=dict(C='consultation',N='negotiation',M='mediation',L='litigation')
route_zh=dict(C='咨询',N='协商',M='调解',L='诉讼准备')
steps=dict(C=['answer'],N=['prepare','communicate','perform'],M=['channel','participate','result'],L=['jurisdiction','evidence','draft','submit'])
products=dict(C='列出能确认的事实、尚缺的依据和下一步。',N='整理一份双方可以核对的协商方案和履行清单。',M='准备一份调解陈述、材料清单及结果核对表。',L='整理管辖待核事项、证据目录、起诉状草稿和提交清单。')
DL={
 'case_cn_0006':('对方全责，但保险公司不认可我住院这么久，怎么把这两件事说清？','事故责任','住院必要性','分别核对责任认定与长期住院的医学记录。'),
 'case_cn_0007':('平台上买的电动车品牌跟宣传不一样，我该找谁，需要什么证据？','交易相对方','品牌差异','查清店铺与平台的交易角色，品牌差异本身不足以认定假冒。'),
 'case_cn_0020':('商铺没能开业，想复盘保证金和消防手续，应该先查哪些材料？','租约及保证金','消防整改','区分商铺备案与主体建筑验收，核对受托招商与保证金流向。')}
source_records=[]
case_rows=[]
rubrics=[]
acc=defaultdict(list)
index=[json.loads(l) for l in (P/'index.jsonl').read_text().splitlines()]
# Local comparison provisions are explicitly versioned, including for historical matters.
cc=[i for i in index if i['law_title']=='中华人民共和国民法典']
def law(n):
    assert len(cc)==1260
    return cc[n-1]
law_numbers=[
 [1179,509,1184,1184,None,None,None,None,1179,None,None,None,None,None],
 [551,561,679,679,667,1064,496,670,680,679,675,680,675],
 [1197,626,566,626,628,585,628,595,595,626,626,626,628],
 [708,509,733,721,722,585,733,509,563,730]]
full=set('2-25 4-99 3-98 7-55 7-35'.split())
conflict=set('5-38 7-98 5-14 4-4 7-90 5-0 6-88'.split())
missing=set('8-37 8-84 8-27 8-q 3-30 8-99'.split())
outside=set('2-71 3-12 4-40 5-53'.split())
case_comps=dict(tort='8-98',lending='4-49',contract='7-60',leasing='5-94')
comparisons={}
for k in [*case_comps.values(), "7-11", "8-56", "3-84"]:
    v=read(UP/(k+'.json'))
    comparisons[k]=dict(candidate_id=v['CaseId'],cause=v['CaseCause'],passage=v['JudgeReason'],origin=origins[k],field='JudgeReason')
lines(P/'case_candidates.jsonl',comparisons.values())
seq=0
for group_idx,(domain,label,keys,codes,dev_count) in enumerate(groups):
    assert len(keys.split())==len(codes)
    for j,(k,code) in enumerate(zip(keys.split(),codes)):
        seq+=1
        tid=f'civil50-{seq:03}'; dev=j<dev_count
        route=route_names[code]; origin=origins[k]; rawfile=UP/(k+'.json'); raw=read(rawfile)
        dl=k in DL
        sid=raw['id' if dl else 'CaseId']
        case_dir=P/'cases'/tid; fixtures=case_dir/'materials'
        case_dir.mkdir(parents=True,exist_ok=True)
        base=dict(task_id=tid,dataset_version='civil50_v1')
        url='https://github.com/'+origin['publisher']+'/blob/'+origin['commit']+'/'+origin['path']
        if dl: url+='#L'+origin['pointer'].split(':')[1]
        if dl:
            opening,t1,t2,anchor=DL[k]
            entries=[(title,f['client_belief'],'facts/'+str(i)+'/client_belief',f['client_belief']) for i,(title,f) in enumerate(zip([t1,t2],raw['facts']))]
            result='\n'.join(f['fact_id']+' '+f['court_record'] for f in raw['facts'][:2])
            historical=[];cause='上游未列案由'
        else:
            opening,t1,n1,a1,t2,n2,a2,anchor=selection[k]
            entries=[]
            for title,note,needle in [(t1,n1,a1),(t2,n2,a2)]:
                field=next(x for x in ('JudgeAccusation','JudgeReason','JudgeResult') if needle in raw[x])
                entries.append((title,note,field,needle))
            result=raw['JudgeResult'];historical=raw['LegalBasis'];cause='、'.join(raw['CaseCause'])
        coverage=('事实材料冲突' if k in conflict else '关键事实待补' if k in missing else '专项保险法依据库外' if k in outside else '就指定核账问题材料充分' if k in full else '部分法律覆盖')
        task=dict(**base,source_case_id=sid,split='development' if dev else 'final_test',phase='pilot' if dev else 'formal',task_type='interactive',domain=domain,tags=[label],initial_input=opening,user_goal=products[code],output_requirements=['请逐项注明信息来自哪份材料，列明仍需核实的内容。'],selected_route=None,materials=[],provenance='deidentified_public_case',source_reference=url)
        acc['dev' if dev else 'held'].append(task)
        facts=[];links=[];items=[];qrels=[];md=[]
        for ix,(title,note,field,needle) in enumerate(entries,1):
            fid='F'+str(ix);mid='M'+str(ix);iid=tid+'-i'+str(ix)
            file=fixtures/('note-'+str(ix)+'.txt')
            save(file,'咨询材料摘记（评测改编）\n'+('当事人自述' if dl else '案卷内容整理')+'\n'+note+'\n')
            source=raw
            for part in field.split('/'):source=source[int(part)] if isinstance(source,list) else source[part]
            start=source.index(needle)
            ref=dict(field=field,start=start,end=start+len(needle),quote=needle)
            material=dict(task_id=tid,material_id=mid,version='1',visibility='on_request',type='匿名案情摘记',path=str(file.relative_to(ROOT)),sha256=sha(file),locator='第3行',support=note,limit='仅反映来源记载；原始凭证未随案取得。',origin=ref,invented_fields=[],adaptation='编辑转述，模拟上传文件')
            acc['materials'].append(material)
            ask=f'关于{title}，当时的情况或记录是怎样的？'
            facts.append(dict(fact_id=fid,disclosure_condition='明确询问'+title,accepted_question_examples=[ask,'有关于'+title+'的记录吗？'],response=note))
            scores=dict(item_id='S'+str(ix),dimension='evidence',description=f'追问并准确使用{title}记录',zero='遗漏该问题，或把摘记说成已经查验的原始凭证。',one='询问了'+title+'，但没有说明答复来源或后续作用。',two=note+' 须说明其来源和证明范围。',applicable_modes=['agent'],required_for_success=True,evidence_refs=[mid+'@1:L3',fid])
            items.append(scores)
            amounts=[]
            for m in re.finditer(r'(\d+(?:\.\d+)?)\s*(万?)元',note):
                amounts.append(dict(surface=m.group(),value=str(Decimal(m[1])*(10000 if m[2] else 1)),currency='CNY',nature=title,approximate=bool(re.search('约|近',note[max(0,m.start()-2):m.start()]))))
            links.append(dict(task_id=tid,issue_id=iid,user_goal=opening,fact_id=fid,issue=title,disclosure='on_intent',source_status='上游当事人理解' if dl else ('裁判说理记载' if field=='JudgeReason' else '案卷记载，按原段区分诉称与查明'),material_id=mid,material_version='1',locator='L3',source_ref=ref,amounts=amounts,item_id=scores['item_id'],gold_anchor=anchor,coverage=coverage))
            md+=[f'**追问 {ix}**　{ask}',f'模拟答复　{note}',f'按请求上传 [摘记 {ix}](materials/{file.name})，核对第 3 行。评审定位为 `{field}` 的字符 [{start}, {start+len(needle)})。']
        lnum=law_numbers[group_idx][j]
        refs=[]
        if lnum:
            art=law(lnum);refs=[art['provision_id']]
            qrels.append(dict(task_id=tid,issue_id=links[-1]['issue_id'],kind='statute',source_id=refs[0],grade=1,role='本地版本对照；须先核实事件日期与时间效力',passage=art['text'],page=art['page_start'],version=art['publication_date']))
        cmp=comparisons[case_comps[domain]]
        case_grade=1 if k in ('2-71','3-12','4-40','5-53','2-94','7-2','1-59','3-98','4-47','7-90','3-17','5-14','1-28','3-37') else 0
        difference={'tort':'对照案讨论车主保险利益与免责提示，不能确定本案事故责任、损失或主体资格。','lending':'对照案的借条源于货款转化，本案须另查实际借款交付及还款约定。','contract':'对照案凭欠条认定孜然货款，不能证明本案供货、后续结算或退款金额。','leasing':'对照案从租赁欠款扣除已付款并审查违约金，本案的租期和退还条件须单独核对。'}[domain]
        qrels.append(dict(task_id=tid,issue_id=links[-1]['issue_id'],kind='case',source_id=cmp['candidate_id'],grade=case_grade,role='离线辅助对照' if case_grade else '离线干扰项',passage=cmp['passage'],difference=difference))
        if k in ('7-2','4-40'):
            near=comparisons['4-49' if k=='7-2' else '8-98']
            qrels=[r for r in qrels if r['source_id']!=near['candidate_id']]
            qrels.append(dict(task_id=tid,issue_id=links[-1]['issue_id'],kind='case',source_id=near['candidate_id'],grade=2,role='专项核心对照，评审侧候选',passage=near['passage'],difference='两案均需审查借据背后的货款。对照案另有双方将其转为借贷的协商。' if k=='7-2' else '均涉及车损险免责及提示义务。须区分不同保单、具体免责事由和提示证据。'))
        acc['qrels']+=qrels
        for m,dim,desc,part,sufficient in [
          ('3','behavior','取得两份摘记并按步骤确认','取得部分材料','实际上传、可定位，逐次确认路线步骤或交付咨询答复。'),
          ('4','citation','说明依据与适用限制','给出一般规定，未说明版本','区分原案援引与本地语料版本；专项依据缺失时说明所需来源。'),
          ('7','citation','核对实际检索上下文与争点','仅记录检索候选，未核对实际送入模型的段落。','逐项记录实际候选与模型上下文；说明命中段落能支持的主张及缺失的专项依据。'),
          ('5','guidance','区分原件、摘记与待核事项','提及摘记但未说明能证明什么','分别引用两份材料第3行；不对未到手的原件作真实性判断。'),
          ('6','task_outcome',anchor,'仅复述两项材料，未解决二者的关系。',anchor+' '+products[code])]:
            items.append(dict(item_id='S'+m,dimension=dim,description=desc,zero='遗漏该项或给出与记录相反的结论。',one=part,two=sufficient,applicable_modes=['agent'],required_for_success=True,evidence_refs=['M1@1:L3','M2@1:L3']))
        hidden=dict(**base,facts=facts,route_choice=None if code=='C' else route)
        gold=dict(**base,review_status='draft',reviewed_by=[],key_facts=[f['response'] for f in facts],acceptable_outputs=[anchor,products[code]],prohibited_inventions=['虚构签收、付款、立案或调解结果','把诉称作为已查验凭证','将个案裁判直接套用于未知事实'],authority_refs=refs,scoring_items=items)
        acc['hidden'].append(hidden);acc['gold'].append(gold);acc['issues']+=links
        revise=j%2==1
        workflow=dict(task_id=tid,route=route,budget=20,revise_first=revise,states=steps[code],facts=[dict(intent=t,fact_id='F'+str(i),material_id='M'+str(i)) for i,t in enumerate([t1,t2],1)],fallback='我目前只能提供已有摘记，其他情况还要核实。',completion=products[code],external_status='未模拟付款、签署或受理。')
        acc['workflow'].append(workflow)
        dated=[]
        dated_fields=({'facts/'+str(i)+'/court_record':f['court_record'] for i,f in enumerate(raw['facts'])} if dl else {'JudgeAccusation':raw['JudgeAccusation']})
        for field_name,body in dated_fields.items():
            for match in re.finditer(r'(?:19|20)\d{2}年\d{1,2}月\d{1,2}日',body):
                if match[0] not in [a['date'] for a in dated]:
                    dated.append(dict(date=match[0],field=field_name,start=match.start(),context=body[max(0,match.start()-16):match.end()+18]))
        source_records.append(dict(task_id=tid,source_case_id=sid,upstream_key=k,source=origin['publisher'],original_cause=cause,url=url,commit=origin['commit'],pointer=origin['pointer'],upstream_sha256=origin['file_sha256'],local_file=str(rawfile.relative_to(ROOT)),local_sha256=sha(rawfile),jurisdiction='中国大陆',event_date_mentions='、'.join(a['date'] for a in dated),date_context=json.dumps(dated,ensure_ascii=False),decision_date='上游无独立日期字段',access_date='2026-11-22',checked_by='Codex（制作时核对上游）',court_original_check='未逐案独立核验',license='CC BY 4.0（数据）' if dl else '仓库 MIT；第三方裁判文本授权未单列',acquisition='官方 Git 仓库固定提交，本地提取记录'))
        case_rows.append(dict(task_id=tid,family=sid,scenario=label,source=origin['publisher'],source_cause=cause,allocation='开发' if dev else '封存候选',endpoint=route,coverage=coverage,materials=2,review='待独立复核',case_file=str((case_dir/'README.md').relative_to(ROOT))))
        rubric_tables='\n'.join(f"|{i['item_id']}|{i['description']}|{i['two']}|{i['one']}|{i['zero']}|" for i in items)
        lawtext='\n'.join(refs) or '本题专项法或历史程序依据未建立直接库内对应。'
        history='\n'.join('* '+a.get('law','')+a.get('terms','') for a in historical) or '上游未提供结构化原判法条字段。'
        mdroute=' → '.join(steps[code])
        save(case_dir/'README.md',f'# {tid} · {opening}\n\n{label} · {route_zh[code]} · {case_rows[-1]["allocation"]} · {coverage}\n\n## 预期交互\n\n当事人开场　{opening}\n\n期望成果　{products[code]}\n\n'+'\n\n'.join(md)+f'\n\n泛问或超出材料范围时答「{workflow["fallback"]}」。只在问到相应事项时披露该条。\n\n路线步骤　{mdroute}。'+('首次交付后要求明确区分证实与待核项，重新交付后确认。' if revise else '收到完整交付后确认。')+f'\n\n## 评审依据\n\n{anchor}\n\n来源标识　{sid} · {origin["pointer"]}。 [上游固定版本]({url}) · [本地来源记录](../../upstream/{k}.json)\n\n裁判主文或上游事实校准（仅评审可见）\n\n{result}\n\n原始记录的依据\n\n{history}\n\n本地版本对照\n\n{lawtext}\n\n|项|目标|充分 2|部分 1|错误或遗漏 0|\n|---|---|---|---|---|\n{rubric_tables}\n\n## 实测\n\n[脚本模型接口回放](../../../results/protocol/{tid}/transcript.md) · [请求、状态及回执](../../../results/protocol/{tid}/trace.jsonl)。真实生成模型未运行。\n')
assert Counter(r['endpoint'] for r in case_rows)==dict(consultation=20,negotiation=10,mediation=10,litigation=10)
table(P/'sources.csv',source_records);table(P/'coverage.csv',case_rows)
lines(ROOT/'development/tasks.jsonl',acc['dev']);lines(P/'heldout-draft/tasks.jsonl',acc['held'])
for name in ['hidden','gold','issues','materials','workflow','qrels']:lines(P/(name+'.jsonl'),acc[name])
for name in ['hidden','gold']:
    ids={r['task_id'] for r in acc['dev']};lines(P/('development-'+name+'.jsonl'),(r for r in acc[name] if r['task_id'] in ids))
table(ROOT/'results/case_summary.csv',[dict(task_id=r['task_id'],endpoint=r['endpoint'],run_state='未运行模型',score='',run_id='') for r in case_rows])
for name,header in [('item_scores','run_id,task_id,item_id,label,score,evidence,reviewer'),('retrieval_hits','run_id,task_id,query,source_id,rank'),('failures','run_id,task_id,step_id,reason')]:
    table(ROOT/'results'/(name+'.csv'),[],header.split(','))
save(P/'目录.md','# 评审目录\n\n|案件|场景|用途|终点|开场|\n|---|---|---|---|---|\n'+'\n'.join(f"|[{r['task_id']}](cases/{r['task_id']}/README.md)|{r['scenario']}|{r['allocation']}|{r['endpoint']}|{t['initial_input']}|" for r,t in zip(case_rows,sorted(acc['dev']+acc['held'],key=lambda x:x['task_id'])))+'\n')

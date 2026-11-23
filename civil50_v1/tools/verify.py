"""Verify from disk, optionally re-extracting records from both official Git checkouts."""
import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
import sys

R=Path(__file__).resolve().parents[1];P=R/'private'
def rows(p):return [json.loads(s) for s in p.read_text().splitlines()]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def check_source(row,record):
    if 'sha256' in record:
        x=dict(record);h=x.pop('sha256')
        assert hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()==h
    if args.upstream:
        src=Path(args.upstream['milecut' if 'CaseId' in record else 'dlawbench'])/row['path']
        assert digest(src)==row['file_sha256']
        loc=row['pointer']
        if loc.startswith('line:'): extracted=json.loads(src.read_text().splitlines()[int(loc[5:])-1])
        else:
            extracted=json.loads(src.read_text())
            for key in loc[1:].split('/'):extracted=extracted[key]
        assert extracted==record
def validate_material(mat,raw,data):
    assert hashlib.sha256(data).hexdigest()==mat['sha256']
    assert data.decode().splitlines()[2]==mat['support']
    ori=mat['origin']
    for key in ori['field'].split('/'):raw=raw[int(key)] if isinstance(raw,list) else raw[key]
    assert raw[ori['start']:ori['end']]==ori['quote']
def validate_ref(q,index):
    if q['kind']=='statute':
        v=index[q['source_id']];assert q['passage']==v['text'] and q['page']==v['page_start'] and q['version']==v['publication_date']
def check_wait(d):
    assert d['run']['status']=='waiting_user' and d['run']['wait']['wait_id']

ap=argparse.ArgumentParser();ap.add_argument('--civra',type=Path,default=R.parent/'CivRA');ap.add_argument('--milecut');ap.add_argument('--dlawbench')
args=ap.parse_args();assert bool(args.milecut)==bool(args.dlawbench);args.upstream=vars(args).copy() if args.milecut else None
sys.path.insert(0,str(args.civra.resolve()))
from evaluation.schemas.tasks import PublicTask,GoldTask,HiddenTask,validate_bundle
dev=rows(R/'development/tasks.jsonl');held=rows(P/'heldout-draft/tasks.jsonl')
tasks={t['task_id']:t for t in dev+held}
assert len(dev)==10 and len(held)==40 and len(tasks)==50
assert len(set(t['source_case_id'] for t in tasks.values()))==50
for t in tasks.values():
    visible=PublicTask.model_validate(t).to_model_input()
    assert set(visible)=={'initial_input','user_goal','selected_route','materials','output_requirements'} and not visible['materials'] and visible['selected_route'] is None
assert Counter(t['domain'] for t in dev)==dict(tort=3,lending=3,contract=2,leasing=2)
assert Counter(t['domain'] for t in held)==dict(tort=11,lending=10,contract=11,leasing=8)
validate_bundle(R/'development/tasks.jsonl',P/'development-hidden.jsonl',P/'development-gold.jsonl')
for name,model in [('gold',GoldTask),('hidden',HiddenTask)]:
    layer=rows(P/(name+'.jsonl'));assert len(layer)==50 and {v['task_id'] for v in layer}==tasks.keys()
    for v in layer:model.model_validate(v);assert v['dataset_version']==tasks[v['task_id']]['dataset_version']
sources=list(csv.DictReader((P/'sources.csv').open(encoding='utf-8-sig')))
assert len(sources)==50 and {s['task_id'] for s in sources}==tasks.keys()
origins=json.loads((P/'upstream/origins.json').read_text());raws={}
for k,o in origins.items():check_source(o,json.loads((P/'upstream'/(k+'.json')).read_text()))
for s in sources:
    p=R/s['local_file'];assert digest(p)==s['local_sha256'];raw=json.loads(p.read_text());raws[s['task_id']]=raw
    assert s['source_case_id']==raw.get('id',raw.get('CaseId'))==tasks[s['task_id']]['source_case_id']
assert len({re.sub(r'\s','',v.get('JudgeAccusation',v.get('opening',''))) for v in raws.values()})==50
mats=rows(P/'materials.jsonl');assert Counter(m['task_id'] for m in mats)=={tid:2 for tid in tasks}
for m in mats:validate_material(m,raws[m['task_id']],(R/m['path']).read_bytes())
index={v['provision_id']:v for v in rows(P/'index.jsonl')};assert len(index)==1690
candidates={v['candidate_id']:v for v in rows(P/'case_candidates.jsonl')};assert not set(candidates)&{v['source_case_id'] for v in tasks.values()}
qrels=rows(P/'qrels.jsonl')
for q in qrels:
    validate_ref(q,index)
    if q['kind']=='case':assert candidates[q['source_id']]['passage']==q['passage']
for t in tasks:
    for path in (P/'cases'/t/'README.md',):
        for target in re.findall(r'\]\(([^)]+)\)',path.read_text()):
            if not target.startswith('https://'):assert (path.parent/target).is_file(),target
wf=rows(P/'workflow.jsonl');assert Counter(w['route'] for w in wf)==dict(consultation=20,negotiation=10,mediation=10,litigation=10)
protocol=rows(R/'results/protocol/summary.jsonl')
assert len(protocol)==50 and {v['task_id'] for v in protocol}==tasks.keys()
for v in protocol:
    assert v['status']=='protocol_completed' and v['materials_uploaded']==2,v
    events=rows(R/'results/protocol'/v['task_id']/'trace.jsonl')
    waits=[e['state'] for e in events if e.get('state',{}).get('run',{}).get('wait')]
    for state in waits:check_wait(state)
    resume={e['request']['wait_id'] for e in events if 'wait_id' in e.get('request',{})}
    assert resume=={s['run']['wait']['wait_id'] for s in waits}
uploads=rows(R/'results/upload-smoke.jsonl');assert len(uploads)==100 and len({u['conversation_id'] for u in uploads})==50
byid={(m['task_id'],m['material_id']):m for m in mats}
for u in uploads:assert u['http_status']==201 and u['receipt']['content_sha256']==byid[u['task_id'],u['material_id']]['sha256']
def reject(fn):
    try:fn()
    except (AssertionError,KeyError,FileNotFoundError):return
    raise AssertionError('故障注入未拦截')
m=mats[0];data=(R/m['path']).read_bytes()
reject(lambda:validate_material(m,raws[m['task_id']],data+'金额增加1元'.encode()))
reject(lambda:validate_material(m,raws[m['task_id']],(R/(m['path']+'.missing')).read_bytes()))
q=next(q for q in qrels if q['kind']=='statute');reject(lambda:validate_ref(dict(q,source_id=next(iter(index))),index))
reject(lambda:check_wait({'run':{'status':'completed','final':{'answer':'请问还款了吗？'}}}))
print(json.dumps(dict(case_families=50,development=10,heldout_drafts=40,upstream_records=len(origins),checked_against_original_files=bool(args.upstream),located_materials=100,index_provisions=len(index),protocol_replays=50,independent_upload_receipts=100,negative_checks=4,live_model_scores=0),ensure_ascii=False,indent=2))

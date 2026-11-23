"""Create the single-file reviewer database and paired offline lookup probes."""
from pathlib import Path
import json
import csv
import hashlib
import re
import sqlite3
import tempfile
import os
from collections import Counter

R=Path(__file__).resolve().parents[1];P=R/'private'
def rows(p):return [json.loads(l) for l in p.read_text().splitlines()]
def dump(x):return json.dumps(x,ensure_ascii=False)
def save(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def table(name):return list(csv.DictReader((P/name).open(encoding='utf-8-sig')))
index=rows(P/'index.jsonl')
probes=[]
for tid,article in [('civil50-018','第六百七十九条'),('civil50-030','第五百六十六条'),('civil50-047','第七百三十三条')]:
    entry=next(x for x in index if x['law_title']=='中华人民共和国民法典' and x['article_no']==article)
    source=entry['provision_id']
    for condition,excluded in [('完整快照',[]),('移除指定条文',[source])]:
        view={x['provision_id']:x for x in index if x['provision_id'] not in excluded}
        probes.append(dict(task_id=tid,query='请在给定索引中核对民法典'+article+'的原文，并说明它能否直接作为原案当时的依据。',condition=condition,exclude=excluded,source_id=source,index_count=len(view),exact_lookup_found=source in view,core_text=entry['text'] if source in view else None,scope='离线按稳定ID定位；模型检索表现待测。'))
assert sum(p['exact_lookup_found'] for p in probes)==3
save(P/'paired_probes.json',probes)
weights={'事实追问':{'weight':20,'items':['S1','S2']},'流程与工具':{'weight':15,'items':['S3']},'检索与上下文':{'weight':20,'items':['S7']},'引用与不确定性':{'weight':20,'items':['S4','S5']},'最终交付':{'weight':25,'items':['S6']}}
save(P/'weights.json',weights)
cases=table('coverage.csv')
fd,tmp=tempfile.mkstemp(dir=P,suffix='.sqlite3');os.close(fd)
try:
    with sqlite3.connect(tmp) as db:
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('CREATE TABLE cases(task_id TEXT PRIMARY KEY,family TEXT UNIQUE NOT NULL,scenario TEXT,allocation TEXT,endpoint TEXT,opening TEXT,case_file TEXT)')
        tasks=rows(R/'development/tasks.jsonl')+rows(P/'heldout-draft/tasks.jsonl')
        opens={r['task_id']:r['initial_input'] for r in tasks}
        db.executemany('INSERT INTO cases VALUES(?,?,?,?,?,?,?)',[(r['task_id'],r['family'],r['scenario'],r['allocation'],r['endpoint'],opens[r['task_id']],r['case_file']) for r in cases])
        for name,values in [('tasks',tasks),('sources',table('sources.csv')),('probes',probes),*[(k,rows(P/(k+'.jsonl'))) for k in ['hidden','gold','issues','materials','workflow','qrels']]]:
            db.execute(f'CREATE TABLE {name}(task_id TEXT NOT NULL REFERENCES cases, record TEXT NOT NULL CHECK(json_valid(record)))')
            db.execute(f'CREATE INDEX {name}_by_case ON {name}(task_id)')
            db.executemany(f'INSERT INTO {name} VALUES(?,?)',[(r['task_id'],dump(r)) for r in values])
        db.execute('CREATE TABLE source_texts(task_id TEXT PRIMARY KEY REFERENCES cases,record TEXT NOT NULL)')
        db.execute('CREATE TABLE fact_dates(task_id TEXT REFERENCES cases,field TEXT,char_start INTEGER,literal TEXT,context TEXT)')
        for r in table('sources.csv'):
            doc=json.loads((R/r['local_file']).read_text())
            db.execute('INSERT INTO source_texts VALUES(?,?)',(r['task_id'],dump(doc)))
            fields={k:doc[k] for k in ['JudgeAccusation','JudgeReason','JudgeResult'] if k in doc}
            for i,f in enumerate(doc.get('facts',[])):fields[f'facts/{i}/court_record']=f['court_record']
            for k,txt in fields.items():
                for m in re.finditer(r'(?:19|20)\d{2}年\d{1,2}月\d{1,2}日',txt):
                    db.execute('INSERT INTO fact_dates VALUES(?,?,?,?,?)',(r['task_id'],k,m.start(),m[0],txt[max(0,m.start()-18):m.end()+30]))
        db.execute('CREATE TABLE attachments(task_id TEXT REFERENCES cases,material_id TEXT,sha256 TEXT,body BLOB,PRIMARY KEY(task_id,material_id))')
        for m in rows(P/'materials.jsonl'):
            data=(R/m['path']).read_bytes();assert hashlib.sha256(data).hexdigest()==m['sha256']
            db.execute('INSERT INTO attachments VALUES(?,?,?,?)',(m['task_id'],m['material_id'],m['sha256'],data))
        for name,col,values in [('statutes','provision_id',index),('case_candidates','candidate_id',rows(P/'case_candidates.jsonl'))]:
            db.execute(f'CREATE TABLE {name}({col} TEXT PRIMARY KEY,record TEXT)')
            db.executemany(f'INSERT INTO {name} VALUES(?,?)',[(v[col],dump(v)) for v in values])
        assert db.execute('PRAGMA integrity_check').fetchone()==('ok',)
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
    os.replace(tmp,P/'civil50.sqlite3')
finally:
    if os.path.exists(tmp):os.unlink(tmp)
print('Database verified:',len(cases),'cases and',len(probes),'probe configurations')

"""Exercise the real, isolated CivRA ASGI conversation and upload endpoints locally."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile

root=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser()
ap.add_argument('--civra',type=Path,default=root.parent/'CivRA')
ap.add_argument('--out',type=Path,required=True)
args=ap.parse_args()
sys.path.insert(0,str(args.civra.resolve()))
from fastapi.testclient import TestClient
from backend.api.app import create_app

materials=[json.loads(l) for l in (root/'private/materials.jsonl').read_text().splitlines()]
tasks=sorted(set(m['task_id'] for m in materials))
args.out.parent.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory() as data, args.out.open('x') as out:
    os.environ['CIVRA_API_DATA_DIR']=data
    token=secrets.token_urlsafe(32)
    with TestClient(create_app(token=token),headers={'Authorization':'Bearer '+token}) as client:
        for tid in tasks:
            session=client.post('/api/conversations',json={'title':tid})
            session.raise_for_status()
            cid=session.json()['conversation_id']
            path='/api/conversations/'+cid
            for material in [m for m in materials if m['task_id']==tid]:
                p=root/material['path']
                response=client.post(path+'/files',files={'file':(p.name,p.read_bytes(),'text/plain')})
                response.raise_for_status()
                record=response.json()
                assert record['content_sha256']==material['sha256']
                snapshot=client.get(path);snapshot.raise_for_status()
                assert record['file_id'] in [f['file_id'] for f in snapshot.json()['files']]
                out.write(json.dumps(dict(task_id=tid,conversation_id=cid,material_id=material['material_id'],http_status=response.status_code,receipt=record),ensure_ascii=False)+'\n')
print(len(tasks),'conversations;',len(materials),'verified uploads')

#!/usr/bin/env python3
"""Export a checked current-file snapshot, excluding credentials and Git history."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
from check_repository import ROOT, included, inspect

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    out=args.output.resolve()
    sidecar=out.with_name(out.name+'.sha256')
    if out.exists() or sidecar.exists():
        parser.error('Output already exists; never overwrite a prior snapshot.')
    result=inspect()
    if not result['passed']:
        print(json.dumps(result,indent=2)); return 1
    members=[p for p in sorted(ROOT.rglob('*')) if p.is_file() and included(p) and p.resolve()!=out]
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in members}
    out.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(out,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for p in members: z.write(p,str(p.relative_to(ROOT)))
        z.writestr('SNAPSHOT_CHECKSUMS.json',json.dumps(hashes,indent=2)+'\n')
    with zipfile.ZipFile(out) as z:
        if z.testzip() is not None or not all(hashlib.sha256(z.read(n)).hexdigest()==h for n,h in hashes.items()):
            raise ValueError('Snapshot checksum verification failed')
    digest=hashlib.sha256(out.read_bytes()).hexdigest()
    with sidecar.open('x',encoding='utf-8') as stream:
        stream.write(digest+'  '+out.name+'\n')
    print(json.dumps({'path':str(out),'files':len(members),'bytes':out.stat().st_size,
                      'sha256':digest,'checksum_file':str(sidecar),'archive_verified':True}))
    return 0

if __name__=='__main__': raise SystemExit(main())

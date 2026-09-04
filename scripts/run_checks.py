#!/usr/bin/env python3
"""Run the saved regression suites and persist commands, logs and source identity."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys

ROOT=Path(__file__).resolve().parent.parent

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    run=args.output or ROOT/'experiments/local'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ_checks')
    run=run.resolve()
    if run.exists() and any(run.iterdir()):
        parser.error('Run directory is not empty; use a new run ID.')
    run.mkdir(parents=True,exist_ok=True)
    report={'utc':datetime.now(timezone.utc).isoformat(),'python':sys.version,'platform':platform.platform(),
            'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
              for d in ['src','tests','benchmarks'] for p in sorted((ROOT/d).rglob('*.py'))},'checks':[]}
    commands=[('inventory',[sys.executable,'scripts/check_repository.py']),
              ('regression',[sys.executable,'-m','unittest','discover','-s','tests','-p','test_*.py','-v'])]
    for name,cmd in commands:
        result=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=180)
        log=result.stdout+result.stderr
        (run/(name+'.log')).write_text(log,encoding='utf-8')
        report['checks'].append({'name':name,'command':cmd,'exit_code':result.returncode,'log':name+'.log'})
        print(name, 'PASS' if result.returncode==0 else 'FAIL',flush=True)
        if result.returncode:
            break
    report['passed']=len(report['checks'])==2 and all(x['exit_code']==0 for x in report['checks'])
    (run/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Results:',run)
    return 0 if report['passed'] else 1

if __name__=='__main__':
    raise SystemExit(main())

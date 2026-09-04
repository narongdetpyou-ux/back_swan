#!/usr/bin/env python3
"""Check artifact inventory and obvious accidental secrets without printing values."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parent.parent
SKIP = {'.git', '.venv', 'venv', '__pycache__', '.pytest_cache', 'build', 'dist', 'backups'}
KEY_PATTERN = re.compile(rb'\bsk-(?:proj-)?[A-Za-z0-9_-]{40,}\b')

def included(path):
    rel = path.relative_to(ROOT)
    return not any(x in SKIP or x.endswith('.egg-info') for x in rel.parts) and not any(
        rel.is_relative_to(Path(p)) for p in ('experiments/local', 'artifacts/local', 'data/private'))

def inspect():
    errors, files = [], []
    for p in sorted(ROOT.rglob('*')):
        if not p.is_file() or not included(p):
            continue
        name = str(p.relative_to(ROOT))
        data = p.read_bytes()
        files.append(p)
        if not data:
            errors.append(name+': empty file')
        if p.name == 'openai-api-key.txt' or (p.name.startswith('.env') and p.name != '.env.example'):
            errors.append(name+': prohibited credential filename')
        if KEY_PATTERN.search(data):
            errors.append(name+': possible credential content (value withheld)')
        if p.suffix == '.zip':
            with zipfile.ZipFile(p) as z:
                for entry in z.infolist():
                    if entry.is_dir():
                        continue
                    parts = Path(entry.filename).parts
                    if Path(entry.filename).is_absolute() or '..' in parts or 'openai-api-key.txt' in parts:
                        errors.append(name+': unsafe archive member')
                        continue
                    if entry.file_size > 100_000_000:
                        errors.append(name+': oversized archive member')
                        continue
                    if KEY_PATTERN.search(z.read(entry)):
                        errors.append(name+': possible credential in archive (value withheld)')
    manifest = ROOT/'data/manifests/recovered_files.json'
    if manifest.exists():
        for row in json.loads(manifest.read_text())['files']:
            p = ROOT/row['path']
            if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != row['sha256']:
                errors.append(row['path']+': recovered source checksum mismatch')
    return {'files_checked':len(files),'errors':errors,'passed':not errors,
            'scope':'Current deliverable and contained ZIP files; heuristic secret detection, not Git-history cleanup.'}

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--manifest', action='store_true')
    args=parser.parse_args()
    result=inspect()
    print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(not result['passed'])

"""Standard-library run provenance; no detector logic or external storage access."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time
import uuid


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def run_id(version, purpose):
    for value in (version, purpose):
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', value):
            raise ValueError('Version and purpose must be lowercase alphanumeric/hyphen labels.')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    return f'{stamp}_{version}_{purpose}_{uuid.uuid4().hex[:8]}'


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def source_hashes(root):
    return {p.relative_to(root).as_posix(): sha256(p)
            for folder in ('src', 'tests', 'benchmarks', 'scripts', 'configs')
            for p in sorted((root / folder).rglob('*'))
            if p.is_file() and p.suffix in ('.py', '.json') and '__pycache__' not in p.parts}


def git_identity(root):
    # An exported snapshot must not inherit a surrounding workspace's Git HEAD.
    if not (root / '.git').exists():
        return {'commit': None, 'dirty': None, 'reason': 'snapshot_without_git_metadata'}
    try:
        commit = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'],
                                         text=True, stderr=subprocess.DEVNULL, timeout=10).strip()
        status = subprocess.check_output(['git', '-C', str(root), 'status', '--porcelain'],
                                         text=True, stderr=subprocess.DEVNULL, timeout=10)
        return {'commit': commit, 'dirty': bool(status), 'reason': None}
    except (OSError, subprocess.SubprocessError):
        return {'commit': None, 'dirty': None, 'reason': 'git_metadata_unavailable'}


class RunRecord:
    """Reserve a new directory and finalize manifest even on ordinary exceptions.

    SIGKILL/power loss leaves status=running: never interpret this as success.
    Exception messages and environment variable values are deliberately not saved.
    """
    def __init__(self, root, version, purpose, output=None, metadata=None):
        self.root = Path(root).resolve()
        identifier = run_id(version, purpose)
        self.path = Path(output).resolve() if output is not None else self.root / 'experiments/local' / identifier
        self.manifest = {
            'schema_version': 1, 'run_id': identifier, 'directory_name': self.path.name,
            'model_version': version, 'purpose': purpose, 'status': 'running',
            'started_at_utc': utc_now(), 'ended_at_utc': None,
            'command': [sys.executable, *sys.argv], 'cwd': str(Path.cwd()),
            'git': git_identity(self.root), 'source_sha256': source_hashes(self.root),
            'environment': {'python': sys.version, 'platform': platform.platform(),
                            'machine': platform.machine(), 'processor': platform.processor() or None,
                            'logical_cpu_count': os.cpu_count()},
            'metadata': metadata or {}, 'details': {}, 'artifacts': {},
        }
        json.dumps(self.manifest, allow_nan=False)  # Validate before reserving directory.
        self.outcome = 'completed'  # Completion does not certify model acceptance.
        self.started = time.monotonic()
        self.path.mkdir(parents=True, exist_ok=False)
        self.checkpoint()

    def checkpoint(self):
        temporary = self.path / '.manifest.tmp'
        temporary.write_text(json.dumps(self.manifest, ensure_ascii=False, indent=2,
                                        allow_nan=False) + '\n', encoding='utf-8')
        temporary.replace(self.path / 'manifest.json')

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.manifest['ended_at_utc'] = utc_now()
        self.manifest['elapsed_seconds'] = time.monotonic() - self.started
        self.manifest['status'] = 'failed' if exc_type else self.outcome
        self.manifest['failure_type'] = exc_type.__name__ if exc_type else None
        self.manifest['source_unchanged'] = source_hashes(self.root) == self.manifest['source_sha256']
        if not self.manifest['source_unchanged']:
            self.manifest['status'] = 'failed'
        self.manifest['artifacts'] = {
            p.relative_to(self.path).as_posix(): {'bytes': p.stat().st_size, 'sha256': sha256(p)}
            for p in sorted(self.path.rglob('*')) if p.is_file() and not p.is_symlink()
            and p.name not in ('manifest.json', '.manifest.tmp')}
        self.checkpoint()
        return False

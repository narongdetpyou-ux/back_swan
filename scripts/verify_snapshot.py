#!/usr/bin/env python3
"""Verify snapshot transport checksum and every member; optionally restore safely."""
import argparse
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import zipfile
from experiment_record import sha256


def verify(archive, checksum):
    archive, checksum = Path(archive), Path(checksum)
    parts = checksum.read_text(encoding='utf-8').strip().split(maxsplit=1)
    if len(parts) != 2 or parts[1] != archive.name or sha256(archive) != parts[0]:
        raise ValueError('Archive checksum/name mismatch')
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        if len(names) != len(set(names)):
            raise ValueError('Duplicate archive members')
        for entry in z.infolist():
            name = PurePosixPath(entry.filename)
            if (name.is_absolute() or name.as_posix() != entry.filename or '..' in name.parts or '\\' in entry.filename
                    or ':' in entry.filename or entry.is_dir()
                    or stat.S_ISLNK(entry.external_attr >> 16)):
                raise ValueError('Unsafe archive member')
            if entry.file_size > 100_000_000:
                raise ValueError('Oversized archive member')
        if sum(x.file_size for x in z.infolist()) > 1_000_000_000:
            raise ValueError('Archive exceeds 1 GB uncompressed verification limit')
        hashes = json.loads(z.read('SNAPSHOT_CHECKSUMS.json'))
        if set(names) != set(hashes) | {'SNAPSHOT_CHECKSUMS.json'}:
            raise ValueError('Manifest does not cover exactly all snapshot files')
        import hashlib
        for name, expected in hashes.items():
            if hashlib.sha256(z.read(name)).hexdigest() != expected:
                raise ValueError('Snapshot member checksum mismatch: ' + name)
    return {'files': len(hashes), 'sha256': parts[0], 'verified': True}


def restore(archive, destination, checksum):
    # Never overwrite or merge with an existing directory.
    verify(archive, checksum)
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(archive) as z:
        for entry in z.infolist():
            target = destination / entry.filename
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(entry) as source, target.open('xb') as output:
                shutil.copyfileobj(source, output)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('archive', type=Path)
    parser.add_argument('--checksum', type=Path)
    parser.add_argument('--restore-to', type=Path, help='New, nonexistent directory')
    args = parser.parse_args()
    result = verify(args.archive, args.checksum or args.archive.with_name(args.archive.name + '.sha256'))
    if args.restore_to:
        restore(args.archive, args.restore_to, args.checksum or args.archive.with_name(args.archive.name + '.sha256'))
        result['restored_to'] = str(args.restore_to.resolve())
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

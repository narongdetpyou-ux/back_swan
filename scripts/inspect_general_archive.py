#!/usr/bin/env python3
"""Read a Black Swan ZIP without executing or extracting its contents."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile

PREVIOUS_SHA256 = "730472506e90712731589d6633203bd964bdace67d67f26ba5676625b1bc8cb1"
MAX_ARCHIVE_BYTES = 20_000_000
MAX_EXPANDED_BYTES = 100_000_000
MAX_SOURCE_BYTES = 512_000
MAX_FILE_BYTES = 64_000
MAX_ENTRIES = 10_000
# A bounded heuristic, not a guarantee that every sensitive value is detected.
SENSITIVE = re.compile(
    rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{40,}\b"
    rb"|-----BEGIN (?:[A-Z]+ )*PRIVATE KEY-----"
)

def is_source(path):
    parts = path.parts
    return (
        path.name == "AGENTS.md"
        or (path.suffix == ".py" and any(
            x in parts for x in ("black_swan_general", "tests", "experiments")))
        or path.name in (
            "NEXT_EXPERIMENT.md", "lab.py", "run_user_experiments.py",
            "pyproject.toml", "requirements.txt")
    )

def inspect_archive(archive):
    archive = Path(archive)
    if archive.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("Archive exceeds the byte limit.")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    inventory, sources, omitted = [], [], []
    source_bytes = 0
    names = set()
    with zipfile.ZipFile(archive) as bundle:
        entries = bundle.infolist()
        if len(entries) > MAX_ENTRIES:
            raise ValueError("Archive has too many entries.")
        if sum(x.file_size for x in entries) > MAX_EXPANDED_BYTES:
            raise ValueError("Archive exceeds the expanded byte limit.")
        for entry in sorted(entries, key=lambda x: x.filename):
            path = PurePosixPath(entry.filename)
            if (path.is_absolute() or ".." in path.parts
                    or "\\" in entry.filename or "\x00" in entry.filename
                    or any(":" in part for part in path.parts)):
                raise ValueError("Archive contains an unsafe member name.")
            normalized = str(path)
            if normalized in names:
                raise ValueError("Archive contains duplicate member names.")
            names.add(normalized)
            if stat.S_ISLNK(entry.external_attr >> 16):
                raise ValueError("Archive contains a symbolic link.")
            if entry.flag_bits & 1:
                raise ValueError("Encrypted entries cannot be inspected.")
            if entry.is_dir():
                continue
            inventory.append({"path": entry.filename, "bytes": entry.file_size})
            if not is_source(path):
                continue
            if entry.file_size > MAX_FILE_BYTES or source_bytes + entry.file_size > MAX_SOURCE_BYTES:
                omitted.append({"path": entry.filename, "reason": "text_size_limit"})
                continue
            raw = bundle.read(entry)
            if SENSITIVE.search(raw):
                omitted.append({"path": entry.filename, "reason": "possible_sensitive_content"})
                continue
            try:
                content = raw.decode("utf-8")
            except UnicodeDecodeError:
                omitted.append({"path": entry.filename, "reason": "not_utf8"})
                continue
            source_bytes += len(raw)
            sources.append({"path": entry.filename,
                            "sha256": hashlib.sha256(raw).hexdigest(),
                            "content": content})
    return {
        "status": "inspected",
        "archive_name": archive.name,
        "archive_sha256": digest,
        "matches_previously_reviewed_archive": digest == PREVIOUS_SHA256,
        "core_executed": False,
        "inventory": inventory,
        "source_files": sources,
        "omitted_source_files": omitted,
        "scope": "Archive structure and selected UTF-8 source only; no extraction, imports, or Core tests.",
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    if not args.archive.is_file():
        print(json.dumps({"status": "awaiting_archive",
                          "archive_path": str(args.archive),
                          "core_executed": False}))
        return 0
    try:
        report = inspect_archive(args.archive)
    except (OSError, ValueError, zipfile.BadZipFile, RuntimeError) as exc:
        # Do not print member contents or exception text from an unreviewed archive.
        print(json.dumps({"status": "inspection_failed",
                          "error_type": type(exc).__name__,
                          "core_executed": False}))
        return 1
    print(json.dumps(report, ensure_ascii=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

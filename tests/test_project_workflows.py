"""Filesystem-only checks for experiment provenance and snapshot restoration."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from experiment_record import RunRecord, git_identity, run_id, sha256
from verify_snapshot import verify, restore
import run_checks


class RunRecordTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'src').mkdir()
        (self.root / 'src/example.py').write_text('value = 1\n')

    def test_unique_safe_names(self):
        names = {run_id('v8', 'quality-check') for _ in range(100)}
        self.assertEqual(len(names), 100)
        self.assertTrue(all('_v8_quality-check_' in n for n in names))
        with self.assertRaises(ValueError):
            run_id('v8', '../escape')

    def test_success_records_artifact_and_source_hashes(self):
        with RunRecord(self.root, 'v8', 'test') as record:
            (record.path / 'result.json').write_text('{"ok": true}\n')
        manifest = json.loads((record.path / 'manifest.json').read_text())
        self.assertEqual(manifest['status'], 'completed')
        self.assertTrue(manifest['source_unchanged'])
        self.assertEqual(manifest['source_sha256']['src/example.py'], sha256(self.root / 'src/example.py'))
        self.assertEqual(manifest['artifacts']['result.json']['sha256'], sha256(record.path / 'result.json'))
        self.assertIsNone(manifest['git']['commit'])
        self.assertIsNotNone(manifest['ended_at_utc'])

    def test_failed_run_preserves_partial_evidence_without_exception_message(self):
        with self.assertRaises(RuntimeError):
            with RunRecord(self.root, 'v8', 'test') as record:
                (record.path / 'partial.json').write_text('{}')
                raise RuntimeError('sensitive exception text')
        manifest = json.loads((record.path / 'manifest.json').read_text())
        self.assertEqual(manifest['status'], 'failed')
        self.assertEqual(manifest['failure_type'], 'RuntimeError')
        self.assertIn('partial.json', manifest['artifacts'])
        self.assertNotIn('sensitive exception text', json.dumps(manifest))

    def test_existing_directory_never_overwritten(self):
        with self.assertRaises(FileExistsError):
            RunRecord(self.root, 'v8', 'test', output=self.root / 'src')
        self.assertEqual((self.root / 'src/example.py').read_text(), 'value = 1\n')

    def test_source_mutation_marks_failed(self):
        with RunRecord(self.root, 'v8', 'test') as record:
            (self.root / 'src/example.py').write_text('value = 2\n')
        self.assertFalse(record.manifest['source_unchanged'])
        self.assertEqual(record.manifest['status'], 'failed')

    def test_snapshot_does_not_inherit_parent_git_commit(self):
        with patch('experiment_record.subprocess.check_output') as command:
            self.assertEqual(git_identity(self.root)['reason'], 'snapshot_without_git_metadata')
            command.assert_not_called()

    def test_timeout_is_finalized_as_failure(self):
        with self.assertRaises(subprocess.TimeoutExpired):
            with RunRecord(self.root, 'v8', 'regression') as record:
                with patch('run_checks.subprocess.run', side_effect=subprocess.TimeoutExpired('test', 180)):
                    run_checks.run_checks(record)
        self.assertEqual(record.manifest['failure_type'], 'TimeoutExpired')
        self.assertEqual(record.manifest['status'], 'failed')

    def test_nonzero_check_exit_marks_failed(self):
        with RunRecord(self.root, 'v8', 'regression') as record:
            with patch('run_checks.subprocess.run', return_value=subprocess.CompletedProcess(['test'], 1, 'failed', '')):
                self.assertEqual(run_checks.run_checks(record), 1)
        self.assertEqual(record.manifest['status'], 'failed')
        self.assertFalse(record.manifest['details']['checks_passed'])


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.archive = self.root / 'snapshot.zip'
        self.checksum = self.root / 'snapshot.zip.sha256'

    def make_archive(self, name='src/example.py', bad_hash=False, extra=False):
        content = b'value = 1\n'
        with zipfile.ZipFile(self.archive, 'w') as z:
            z.writestr(name, content)
            z.writestr('SNAPSHOT_CHECKSUMS.json', json.dumps({name: '0' * 64 if bad_hash else hashlib.sha256(content).hexdigest()}))
            if extra:
                z.writestr('unlisted.txt', 'unexpected')
        self.checksum.write_text(sha256(self.archive) + '  ' + self.archive.name + '\n')

    def test_verify_and_restore(self):
        self.make_archive()
        self.assertTrue(verify(self.archive, self.checksum)['verified'])
        destination = self.root / 'restored'
        restore(self.archive, destination, self.checksum)
        self.assertEqual((destination / 'src/example.py').read_bytes(), b'value = 1\n')
        with self.assertRaises(FileExistsError):
            restore(self.archive, destination, self.checksum)

    def test_tampered_transport_is_rejected(self):
        self.make_archive()
        self.checksum.write_text('0' * 64 + '  snapshot.zip\n')
        with self.assertRaises(ValueError):
            verify(self.archive, self.checksum)

    def test_wrong_internal_hash_is_rejected(self):
        self.make_archive(bad_hash=True)
        with self.assertRaises(ValueError):
            verify(self.archive, self.checksum)

    def test_path_traversal_is_rejected_before_restore(self):
        self.make_archive(name='../escape.txt')
        destination = self.root / 'restored'
        with self.assertRaises(ValueError):
            restore(self.archive, destination, self.checksum)
        self.assertFalse(destination.exists())

    def test_unlisted_file_is_rejected(self):
        self.make_archive(extra=True)
        with self.assertRaises(ValueError):
            verify(self.archive, self.checksum)


if __name__ == '__main__':
    unittest.main()

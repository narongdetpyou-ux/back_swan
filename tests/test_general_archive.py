from pathlib import Path
import importlib.util
import json
import stat
import tempfile
import unittest
from unittest import mock
import zipfile

SCRIPT = Path(__file__).resolve().parents[1]/"scripts/inspect_general_archive.py"
spec = importlib.util.spec_from_file_location("general_archive_inspector", SCRIPT)
inspector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inspector)

class ArchiveInspectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.archive = Path(self.tmp.name)/"input.zip"

    def make_archive(self, rows):
        with zipfile.ZipFile(self.archive, "w") as archive:
            for name, content in rows:
                archive.writestr(name, content)

    def test_reads_selected_source_without_executing_it(self):
        source = "raise RuntimeError('This must never execute')\n"
        self.make_archive([
            ("project/src/black_swan_general/verifier.py", source),
            ("project/docs/NEXT_EXPERIMENT.md", "Review the next experiment."),
            ("project/datasets/labels.jsonl", '{"answer":1}\n'),
        ])
        report = inspector.inspect_archive(self.archive)
        self.assertEqual(report["status"], "inspected")
        self.assertFalse(report["core_executed"])
        self.assertEqual(len(report["inventory"]), 3)
        self.assertEqual(len(report["source_files"]), 2)
        self.assertEqual(report["source_files"][1]["content"], source)

    def test_modified_archive_is_reported_as_different(self):
        self.make_archive([("project/lab.py", "pass\n")])
        report = inspector.inspect_archive(self.archive)
        self.assertFalse(report["matches_previously_reviewed_archive"])
        self.assertEqual(len(report["archive_sha256"]), 64)

    def test_path_traversal_is_rejected(self):
        self.make_archive([("../project/lab.py", "pass\n")])
        with self.assertRaises(ValueError):
            inspector.inspect_archive(self.archive)

    def test_duplicate_path_is_rejected(self):
        self.make_archive([("project/lab.py", "pass\n"),
                           ("project/./lab.py", "pass\n")])
        with self.assertRaises(ValueError):
            inspector.inspect_archive(self.archive)

    def test_symlink_is_rejected(self):
        entry = zipfile.ZipInfo("project/lab.py")
        entry.create_system = 3
        entry.external_attr = (stat.S_IFLNK | 0o777) << 16
        self.make_archive([(entry, "/outside")])
        with self.assertRaises(ValueError):
            inspector.inspect_archive(self.archive)

    def test_expanded_size_limit_is_enforced(self):
        self.make_archive([("project/lab.py", "long contents")])
        with mock.patch.object(inspector, "MAX_EXPANDED_BYTES", 4):
            with self.assertRaises(ValueError):
                inspector.inspect_archive(self.archive)

    def test_possible_secret_content_is_not_returned(self):
        value = "sk-" + "A" * 50
        self.make_archive([("project/lab.py", value)])
        report = inspector.inspect_archive(self.archive)
        self.assertEqual(report["source_files"], [])
        self.assertEqual(report["omitted_source_files"][0]["reason"],
                         "possible_sensitive_content")
        self.assertNotIn(value, json.dumps(report))

    def test_all_agent_instructions_are_included(self):
        self.make_archive([
            ("project/AGENTS.md", "Project instructions"),
            ("project/src/AGENTS.md", "Source instructions"),
        ])
        report = inspector.inspect_archive(self.archive)
        self.assertEqual(len(report["source_files"]), 2)

if __name__ == "__main__":
    unittest.main()

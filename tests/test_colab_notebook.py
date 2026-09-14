"""Behavioral regression tests execute the notebook's actual orchestration cell.

The experiment subprocess is controlled in these tests. They do not execute
black_swan_general or certify the earlier 45-test run.
"""
from contextlib import redirect_stdout
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock
import io
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile

NOTEBOOK = Path(__file__).resolve().parents[1] / "notebooks/Black_Swan_Colab_Verified.ipynb"
EXPECTED_CHECKS = (
    "reviewed_probe_contracts", "graph_traversals_actually_executed",
    "actual_object_cycle_rejected", "next_request_recovers",
    "learning_gate_passed", "numeric_answers_correct",
    "numeric_first_choice_improves", "old_regression_answer_count_preserved",
    "old_regression_automatic_errors_not_increased",
    "memory_frozen_for_holdout", "regression_tests_passed",
)

def passing_summary():
    return {"all_checks_passed": True,
            "checks": {name: True for name in EXPECTED_CHECKS}}

def cell_source(cell):
    value = cell["source"]
    return "".join(value) if isinstance(value, list) else value

class NotebookRunContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
        self.cells = {cell["id"]: cell for cell in self.notebook["cells"]}
        self.ns = dict(Path=Path, datetime=datetime, timezone=timezone,
                       json=json, sys=sys, subprocess=subprocess,
                       zipfile=zipfile, ROOT=self.root)
        if "code-run-guard" in self.cells:
            self.execute_cell("code-run-guard")

    def execute_cell(self, cell_id):
        source = cell_source(self.cells[cell_id])
        with redirect_stdout(io.StringIO()):
            exec(compile(source, f"{NOTEBOOK.name}:{cell_id}", "exec"), self.ns)

    def run_experiment(self, report, returncode=0):
        def complete(command, **kwargs):
            run_dir = Path(command[command.index("--output") + 1])
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "summary.json").write_text(
                json.dumps(report), encoding="utf-8")
            return subprocess.CompletedProcess(
                command, returncode, stdout="controlled stdout\n",
                stderr="controlled stderr\n")
        with mock.patch.object(subprocess, "run", side_effect=complete):
            self.execute_cell("code-04")

    def test_passing_report_is_usable(self):
        self.run_experiment(passing_summary())
        self.assertEqual(self.ns["summary"], passing_summary())
        self.assertTrue((self.ns["RUN_DIR"] / "summary.json").is_file())

    def test_nonzero_exit_stops_run(self):
        with self.assertRaises(RuntimeError):
            self.run_experiment(passing_summary(), returncode=2)

    def test_false_summary_stops_run(self):
        report = passing_summary()
        report["all_checks_passed"] = False
        with self.assertRaises(RuntimeError):
            self.run_experiment(report)

    def test_failed_gate_cannot_hide_behind_true_summary(self):
        report = passing_summary()
        report["checks"]["learning_gate_passed"] = False
        with self.assertRaises(RuntimeError):
            self.run_experiment(report)

    def test_missing_required_check_stops_run(self):
        report = passing_summary()
        del report["checks"]["memory_frozen_for_holdout"]
        with self.assertRaises(RuntimeError):
            self.run_experiment(report)

    def test_numeric_truth_is_not_boolean_evidence(self):
        report = passing_summary()
        report["all_checks_passed"] = 1
        with self.assertRaises(RuntimeError):
            self.run_experiment(report)

    def test_missing_check_container_stops_run(self):
        with self.assertRaises(RuntimeError):
            self.run_experiment({"all_checks_passed": True})

    def test_empty_check_container_stops_run(self):
        with self.assertRaises(RuntimeError):
            self.run_experiment({"all_checks_passed": True, "checks": {}})

    def test_non_boolean_individual_check_stops_run(self):
        report = passing_summary()
        report["checks"]["memory_frozen_for_holdout"] = "true"
        with self.assertRaises(RuntimeError):
            self.run_experiment(report)

    def test_new_failing_check_is_not_ignored(self):
        report = passing_summary()
        report["checks"]["future_regression"] = False
        with self.assertRaises(RuntimeError):
            self.run_experiment(report)

    def test_extra_successful_check_is_compatible(self):
        report = passing_summary()
        report["checks"]["future_regression"] = True
        self.run_experiment(report)
        self.assertEqual(self.ns["require_verified_run"](), self.ns["RUN_DIR"])

    def test_results_unavailable_before_first_success(self):
        with self.assertRaises(RuntimeError):
            self.ns["require_verified_run"]()

    def test_failed_rerun_revokes_previous_success_and_blocks_memory(self):
        self.run_experiment(passing_summary())
        previous = self.ns["require_verified_run"]()
        report = passing_summary()
        report["all_checks_passed"] = False
        with self.assertRaises(RuntimeError):
            self.run_experiment(report)
        self.assertTrue((previous / "summary.json").is_file())
        self.assertIsNone(self.ns["RUN_DIR"])
        self.assertIsNone(self.ns["summary"])
        with self.assertRaises(RuntimeError):
            self.ns["require_verified_run"]()
        from types import ModuleType, SimpleNamespace
        core = ModuleType("black_swan_general")
        core.BlackSwanGeneralEngine = mock.Mock()
        core_io = ModuleType("black_swan_general.io")
        core_io.load_release = mock.Mock()
        core_io.request_from_dict = lambda value: value
        cases = ModuleType("experiments.cases")
        cases.recurrence_case = lambda *args: SimpleNamespace(request={})
        with mock.patch.dict(sys.modules, {
            "black_swan_general": core, "black_swan_general.io": core_io,
            "experiments.cases": cases,
        }):
            for cell_id in ("code-09", "code-13"):
                with self.subTest(cell=cell_id), self.assertRaises(RuntimeError):
                    self.execute_cell(cell_id)
        core_io.load_release.assert_not_called()

    def test_timeout_revokes_success_and_preserves_diagnostics(self):
        self.run_experiment(passing_summary())
        error = subprocess.TimeoutExpired(
            cmd=["controlled-runner"], timeout=600,
            output=b"partial output\n", stderr=b"partial error\n")
        with mock.patch.object(subprocess, "run", side_effect=error):
            with self.assertRaisesRegex(RuntimeError, "timed out"):
                self.execute_cell("code-04")
        with self.assertRaises(RuntimeError):
            self.ns["require_verified_run"]()
        run = self.ns["CANDIDATE_RUN_DIR"]
        self.assertEqual((run/"notebook_stdout.log").read_text(), "partial output\n")
        self.assertEqual((run/"notebook_stderr.log").read_text(), "partial error\n")

    def test_missing_summary_cannot_reuse_success(self):
        self.run_experiment(passing_summary())
        completed = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        with mock.patch.object(subprocess, "run", return_value=completed):
            with self.assertRaises(RuntimeError):
                self.execute_cell("code-04")
        with self.assertRaises(RuntimeError):
            self.ns["require_verified_run"]()

    def test_malformed_summary_is_rejected(self):
        def malformed(command, **kwargs):
            run = Path(command[command.index("--output") + 1])
            run.mkdir(parents=True)
            (run/"summary.json").write_text("{invalid")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        with mock.patch.object(subprocess, "run", side_effect=malformed):
            with self.assertRaises(RuntimeError):
                self.execute_cell("code-04")
        with self.assertRaises(RuntimeError):
            self.ns["require_verified_run"]()

    def test_changed_summary_is_rejected_before_use(self):
        self.run_experiment(passing_summary())
        path = self.ns["RUN_DIR"]/"summary.json"
        report = passing_summary()
        report["all_checks_passed"] = False
        path.write_text(json.dumps(report))
        with self.assertRaisesRegex(RuntimeError, "changed"):
            self.ns["require_verified_run"]()

    def test_deleted_summary_is_rejected_before_use(self):
        self.run_experiment(passing_summary())
        (self.ns["RUN_DIR"]/"summary.json").unlink()
        with self.assertRaises(RuntimeError):
            self.ns["require_verified_run"]()

    def test_full_subprocess_logs_are_preserved(self):
        with self.assertRaises(RuntimeError):
            self.run_experiment(passing_summary(), returncode=3)
        run = self.ns["CANDIDATE_RUN_DIR"]
        self.assertEqual((run/"notebook_stdout.log").read_text(), "controlled stdout\n")
        self.assertEqual((run/"notebook_stderr.log").read_text(), "controlled stderr\n")

    def test_changed_archive_stops_before_extraction(self):
        archive = self.root/"Black_Swan_Colab_Review_2026-09-14.zip"
        archive.write_bytes(b"wrong archive")
        with mock.patch.object(Path, "cwd", return_value=self.root):
            with mock.patch.object(zipfile, "ZipFile") as extract:
                with self.assertRaisesRegex(RuntimeError, "ZIP"):
                    self.execute_cell("code-02")
                extract.assert_not_called()

    def test_matching_archive_digest_is_accepted(self):
        import hashlib
        archive = self.root/"fixture.zip"
        archive.write_bytes(b"controlled archive bytes")
        expected = hashlib.sha256(archive.read_bytes()).hexdigest()
        self.assertEqual(self.ns["verify_archive"](archive, expected), expected)

    def test_failed_run_exports_diagnostics_with_false_status_and_checksum(self):
        with self.assertRaises(RuntimeError):
            self.run_experiment(passing_summary(), returncode=3)
        self.execute_cell("code-17")
        self.assert_export_status(False)

    def test_successful_run_exports_true_status_and_checksum(self):
        self.run_experiment(passing_summary())
        self.execute_cell("code-17")
        self.assert_export_status(True)

    def assert_export_status(self, expected):
        import hashlib
        path = self.ns["EVIDENCE_ZIP"]
        with zipfile.ZipFile(path) as archive:
            status = json.loads(archive.read("notebook_export_status.json"))
            self.assertIs(status["verified"], expected)
            self.assertIn("notebook_stderr.log", archive.namelist())
        sidecar = Path(str(path)+".sha256").read_text().split()[0]
        self.assertEqual(sidecar, hashlib.sha256(path.read_bytes()).hexdigest())

    def test_all_code_cells_compile(self):
        for cell in self.notebook["cells"]:
            if cell["cell_type"] == "code":
                with self.subTest(cell=cell["id"]):
                    compile(cell_source(cell), cell["id"], "exec")

    def test_no_historical_outputs_are_presented_as_new_results(self):
        self.assertNotIn("black_swan_validation", self.notebook["metadata"])
        for cell in self.notebook["cells"]:
            if cell["cell_type"] == "code":
                with self.subTest(cell=cell["id"]):
                    self.assertEqual(cell["outputs"], [])
                    self.assertIsNone(cell["execution_count"])

if __name__ == "__main__":
    unittest.main()

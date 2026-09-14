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

if __name__ == "__main__":
    unittest.main()

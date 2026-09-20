import json
from pathlib import Path
import unittest

from scripts.validate_real_world_dataset import validate_manifest

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"


class RealWorldDatasetContractTests(unittest.TestCase):
    def load(self, name):
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

    def test_valid_manifest_passes(self):
        self.assertEqual(validate_manifest(self.load("real_world_manifest_valid.json")), [])

    def test_time_overlap_is_rejected(self):
        errors = validate_manifest(self.load("real_world_manifest_overlap_invalid.json"))
        self.assertIn("splits: baseline overlaps calibration", errors)

    def test_labels_must_be_hidden_and_independent(self):
        doc = self.load("real_world_manifest_valid.json")
        doc["labels_hidden_from_engine"] = False
        doc["inputs"]["labels"]["independent_of_predictions"] = False
        errors = validate_manifest(doc)
        self.assertIn("labels_hidden_from_engine: must be true", errors)
        self.assertIn("inputs.labels.independent_of_predictions: must be true", errors)

    def test_unknown_metric_is_rejected(self):
        doc = self.load("real_world_manifest_valid.json")
        doc["metric_contract"]["selected_metrics"].append("invented_metric")
        doc["metric_contract"]["source_mapping"]["invented_metric"] = "x"
        errors = validate_manifest(doc)
        self.assertTrue(any("unknown metrics invented_metric" in x for x in errors))

    def test_missing_provenance_is_rejected(self):
        doc = self.load("real_world_manifest_valid.json")
        doc["inputs"]["raw"]["provenance"] = ""
        errors = validate_manifest(doc)
        self.assertIn("inputs.raw.provenance: must be non-empty", errors)

    def test_private_identifiers_must_not_be_committed(self):
        doc = self.load("real_world_manifest_valid.json")
        doc["privacy"]["direct_identifiers_in_git"] = True
        errors = validate_manifest(doc)
        self.assertIn("privacy.direct_identifiers_in_git: must be false", errors)


if __name__ == "__main__":
    unittest.main()

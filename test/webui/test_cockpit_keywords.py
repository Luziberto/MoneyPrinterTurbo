import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

if "streamlit" not in sys.modules:
    sys.modules["streamlit"] = MagicMock()

from app.models.schema import CollectorKeyword, NormalizedCollectorKeywords
from webui import cockpit_keywords


class TestCockpitKeywords(unittest.TestCase):
    def test_coerce_editor_rows_accepts_list_of_dicts(self):
        rows = [{"term": "tokyo street", "weight": 1.0}]
        self.assertEqual(cockpit_keywords._coerce_editor_rows(rows), rows)

    def test_coerce_editor_rows_accepts_dataframe(self):
        frame = pd.DataFrame(
            [
                {"term": "tokyo street", "weight": 1.0},
                {"term": "japan train", "weight": 0.8},
            ]
        )
        normalized = cockpit_keywords._normalized_from_rows(
            cockpit_keywords._coerce_editor_rows(frame)
        )
        self.assertEqual(len(normalized.keywords), 2)
        self.assertEqual(normalized.keywords[0].term, "tokyo street")
        self.assertEqual(normalized.keywords[1].weight, 0.8)

    def test_coerce_editor_rows_returns_empty_for_unknown_type(self):
        self.assertEqual(cockpit_keywords._coerce_editor_rows("tokyo, japan"), [])


class TestCockpitKeywordsPackageStore(unittest.TestCase):
    def _rich_terms(self) -> NormalizedCollectorKeywords:
        return NormalizedCollectorKeywords(
            keywords=[
                CollectorKeyword(
                    term="tokyo street",
                    weight=1.0,
                    visual_intent="Mostra a rua principal.",
                    alternatives=["Tokyo city street"],
                    required_concepts=["Tokyo", "street"],
                    optional_concepts=["urban"],
                ),
                CollectorKeyword(
                    term="japan train",
                    weight=0.8,
                    visual_intent="Mostra o trem japonês.",
                    alternatives=["Japanese train"],
                    required_concepts=["Japan", "train"],
                    optional_concepts=["commuters"],
                ),
            ],
            has_explicit_weights=True,
        )

    def test_editing_weight_preserves_visual_package(self):
        with patch.object(cockpit_keywords.st, "session_state", {}):
            cockpit_keywords.set_normalized_video_terms(self._rich_terms())

            # Simulate the grid editor changing only the weight of a row.
            cockpit_keywords.st.session_state[cockpit_keywords.EDITOR_WIDGET_KEY] = [
                {"term": "tokyo street", "weight": 0.5},
                {"term": "japan train", "weight": 0.8},
            ]

            payloads = cockpit_keywords.payloads_for_params()

        self.assertEqual(payloads[0]["weight"], 0.5)
        self.assertEqual(payloads[0]["visual_intent"], "Mostra a rua principal.")
        self.assertEqual(payloads[0]["alternatives"], ["Tokyo city street"])
        self.assertEqual(payloads[0]["required_concepts"], ["Tokyo", "street"])
        self.assertEqual(payloads[0]["optional_concepts"], ["urban"])
        self.assertEqual(payloads[1]["visual_intent"], "Mostra o trem japonês.")

    def test_new_term_falls_back_to_compat_defaults(self):
        with patch.object(cockpit_keywords.st, "session_state", {}):
            cockpit_keywords.set_normalized_video_terms(self._rich_terms())

            # Row with a brand-new term typed by hand in the grid.
            cockpit_keywords.st.session_state[cockpit_keywords.EDITOR_WIDGET_KEY] = [
                {"term": "tokyo street", "weight": 1.0},
                {"term": "mount fuji sunrise", "weight": 0.6},
            ]

            payloads = cockpit_keywords.payloads_for_params()

        new_term = next(p for p in payloads if p["term"] == "mount fuji sunrise")
        self.assertEqual(new_term["visual_intent"], "")
        self.assertEqual(new_term["alternatives"], [])
        self.assertEqual(new_term["required_concepts"], ["mount", "fuji", "sunrise"])
        self.assertEqual(new_term["optional_concepts"], [])


if __name__ == "__main__":
    unittest.main()

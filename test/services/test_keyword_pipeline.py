import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.models.schema import CollectorKeyword
from app.utils.keyword_pipeline import (
    apply_paragraph_weights,
    merge_dedupe_rank_keywords,
    paragraph_keyword_weight,
    split_script_paragraphs,
)


class TestKeywordPipeline(unittest.TestCase):
    def test_split_script_paragraphs_on_blank_lines(self):
        script = "Paragraph one.\n\nParagraph two.\n\nParagraph three."
        self.assertEqual(split_script_paragraphs(script), [
            "Paragraph one.",
            "Paragraph two.",
            "Paragraph three.",
        ])

    def test_merge_dedupe_keeps_highest_weight(self):
        merged = merge_dedupe_rank_keywords(
            [
                CollectorKeyword(term="Tokyo commuters", weight=0.7),
                CollectorKeyword(term="tokyo commuters", weight=0.9),
                CollectorKeyword(term="Shinkansen platform", weight=1.0),
            ]
        )
        self.assertEqual([item.term for item in merged], ["Shinkansen platform", "Tokyo commuters"])
        self.assertEqual(merged[1].weight, 0.9)

    def test_apply_paragraph_weights_orders_by_narrative_position(self):
        ranked = apply_paragraph_weights(
            [
                [
                    CollectorKeyword(term="Japanese train station", weight=1.0),
                    CollectorKeyword(term="Shinkansen platform", weight=1.0),
                ],
                [
                    CollectorKeyword(term="Railway control room", weight=1.0),
                    CollectorKeyword(term="Japanese railway staff", weight=1.0),
                ],
            ]
        )
        self.assertEqual(ranked[0].term, "Japanese train station")
        self.assertGreater(ranked[0].weight, ranked[-1].weight)

    def test_paragraph_keyword_weight_decreases_with_position(self):
        self.assertGreater(
            paragraph_keyword_weight(0, 0),
            paragraph_keyword_weight(2, 1),
        )


if __name__ == "__main__":
    unittest.main()

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.models.schema import VideoAspect, normalize_collector_keywords


class TestVideoAspect(unittest.TestCase):
    def test_to_resolution_known_aspects(self):
        self.assertEqual(VideoAspect.landscape.to_resolution(), (1920, 1080))
        self.assertEqual(VideoAspect.portrait.to_resolution(), (1080, 1920))
        self.assertEqual(VideoAspect.square.to_resolution(), (1080, 1080))

    def test_to_resolution_rejects_unsupported_value(self):
        with self.assertRaises(ValueError):
            VideoAspect.to_resolution("4:5")


class TestNormalizeCollectorKeywords(unittest.TestCase):
    def test_parses_weighted_ui_string_tokens(self):
        normalized = normalize_collector_keywords(
            "tokyo street (0.8), japan train (1), plain term"
        )
        self.assertTrue(normalized.has_explicit_weights)
        self.assertEqual(len(normalized.keywords), 3)
        self.assertEqual(normalized.keywords[0].term, "tokyo street")
        self.assertAlmostEqual(normalized.keywords[0].weight, 0.8)
        self.assertEqual(normalized.keywords[1].term, "japan train")
        self.assertAlmostEqual(normalized.keywords[1].weight, 1.0)
        self.assertEqual(normalized.keywords[2].term, "plain term")
        self.assertAlmostEqual(normalized.keywords[2].weight, 1.0)

    def test_weighted_ui_string_tokens_get_compat_defaults(self):
        normalized = normalize_collector_keywords("tokyo street (0.8)")
        keyword = normalized.keywords[0]
        self.assertEqual(keyword.visual_intent, "")
        self.assertEqual(keyword.alternatives, [])
        self.assertEqual(keyword.required_concepts, ["tokyo", "street"])
        self.assertEqual(keyword.optional_concepts, [])

    def test_parses_structured_dict_list(self):
        normalized = normalize_collector_keywords(
            [
                {"term": "tokyo street", "weight": 0.75},
                {"term": "japan train", "weight": 1.0},
            ]
        )
        self.assertTrue(normalized.has_explicit_weights)
        dumped = [keyword.model_dump() for keyword in normalized.keywords]
        self.assertEqual([d["term"] for d in dumped], ["tokyo street", "japan train"])
        self.assertEqual([d["weight"] for d in dumped], [0.75, 1.0])
        # Legacy {term, weight}-only dicts get compat-filled required_concepts.
        self.assertEqual(dumped[0]["required_concepts"], ["tokyo", "street"])
        self.assertEqual(dumped[0]["visual_intent"], "")
        self.assertEqual(dumped[0]["alternatives"], [])
        self.assertEqual(dumped[0]["optional_concepts"], [])

    def test_parses_rich_visual_package_dict_list(self):
        normalized = normalize_collector_keywords(
            [
                {
                    "term": "Japanese children cleaning classroom",
                    "weight": 1.0,
                    "visual_intent": "Mostrar crianças japonesas limpando a sala de aula.",
                    "alternatives": ["students cleaning classroom Japan", "Japanese school cleaning"],
                    "required_concepts": ["Japanese", "children", "cleaning", "classroom"],
                    "optional_concepts": ["school", "students"],
                }
            ]
        )
        keyword = normalized.keywords[0]
        self.assertEqual(keyword.visual_intent, "Mostrar crianças japonesas limpando a sala de aula.")
        self.assertEqual(
            keyword.alternatives,
            ["students cleaning classroom Japan", "Japanese school cleaning"],
        )
        self.assertEqual(
            keyword.required_concepts, ["Japanese", "children", "cleaning", "classroom"]
        )
        self.assertEqual(keyword.optional_concepts, ["school", "students"])

    def test_alternatives_are_capped_and_deduplicated(self):
        normalized = normalize_collector_keywords(
            [
                {
                    "term": "tokyo street",
                    "weight": 1.0,
                    "alternatives": [
                        "a", "b", "a", "c", "d", "e", "f", "g", "h",
                    ],
                }
            ]
        )
        self.assertEqual(
            normalized.keywords[0].alternatives, ["a", "b", "c", "d", "e", "f"]
        )


if __name__ == "__main__":
    unittest.main()

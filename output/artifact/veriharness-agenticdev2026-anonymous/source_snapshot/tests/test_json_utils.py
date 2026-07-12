import unittest

from autoresearch.json_utils import extract_json_object


class JsonUtilsTests(unittest.TestCase):
    def test_extracts_fenced_json(self):
        self.assertEqual(extract_json_object('```json\n{"a": 1}\n```'), {"a": 1})

    def test_extracts_from_preamble(self):
        self.assertEqual(extract_json_object('done\n{"a": [1, 2]}'), {"a": [1, 2]})


if __name__ == "__main__":
    unittest.main()

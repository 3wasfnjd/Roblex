import sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import fix_map  # noqa: E402


class FixMapTests(unittest.TestCase):
    def test_numeric_references_decode_exactly(self):
        # &#133; must stay U+0085 (html.unescape would turn it into "…")
        self.assertEqual(fix_map.decode_refs("&#216;&#167;&#133;&amp;"), "Ø§\u0085&")

    def test_double_encoded_arabic_is_repaired(self):
        stored = "انضمي".encode("utf-8").decode("latin-1")
        self.assertEqual(fix_map.unmojibake(stored), "انضمي")
        self.assertEqual(fix_map.unmojibake("♡".encode("utf-8").decode("latin-1")), "♡")

    def test_correct_text_is_left_alone(self):
        self.assertIsNone(fix_map.unmojibake("انضمي"))
        self.assertIsNone(fix_map.unmojibake("Boulevard"))
        self.assertIsNone(fix_map.unmojibake(""))

    def test_fix_text_rewrites_only_text_properties(self):
        xml = ('<string name="Name">&#216;&#167;</string>'
               '<string name="ActionText">&#216;&#167;&#217;&#134;</string>')
        out, n = fix_map.fix_text(xml)
        self.assertEqual(n, 1)
        self.assertIn('<string name="ActionText">ان</string>', out)
        self.assertIn('<string name="Name">&#216;&#167;</string>', out)


if __name__ == "__main__":
    unittest.main()

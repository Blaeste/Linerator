"""The French of Linerator: every text of t() and N_() translated, with the same {fields}."""

import ast
import json
import string
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "liner"

def texts():
	"""The first argument of each t() and N_() written as a string in liner/."""
	found = set()
	for path in ROOT.rglob("*.py"):
		for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
			if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("t", "N_")
					and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
				found.add(node.args[0].value)
	return found

def fields(text):
	return sorted(name for _, name, _, _ in string.Formatter().parse(text) if name)

class TestFrench(unittest.TestCase):

	def setUp(self):
		self.catalog = json.loads((ROOT / "locales" / "fr.json").read_text(encoding="utf-8"))

	def test_every_text_is_translated(self):
		missing = sorted(text for text in texts() if not self.catalog.get(text))
		self.assertEqual(missing, [])

	def test_the_same_fields(self):
		wrong = [text for text in texts() if self.catalog.get(text) and fields(self.catalog[text]) != fields(text)]
		self.assertEqual(wrong, [])

	def test_no_translation_left_over(self):
		known = texts()
		self.assertEqual(sorted(key for key in self.catalog if not key.startswith("_") and key not in known), [])

	def test_no_field_named_text(self):
		"""t(text, **fields): a field called text would clash with it."""
		self.assertEqual([text for text in texts() if "text" in fields(text)], [])

class TestLongLines(unittest.TestCase):

	def test_the_size_of_a_line_cut_in_french(self):
		from liner import i18n
		from liner.judge import shown
		self.addCleanup(i18n.set_language, "en")
		i18n.set_language("fr")
		self.assertIn("(50 octets)", shown(b"x" * 50))

if __name__ == "__main__":
	unittest.main()

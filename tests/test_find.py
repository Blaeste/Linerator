"""The get_next_line projects of the student, found in the home folder: a folder with get_next_line.c."""

import json
import tempfile
import unittest
from pathlib import Path

from liner.find import iter_projects, last_project, looks_like_project, remember_project

class TestFind(unittest.TestCase):

	def setUp(self):
		folder = tempfile.TemporaryDirectory()
		self.addCleanup(folder.cleanup)
		self.home = Path(folder.name)

	def project(self, relative, name="get_next_line.c"):
		path = self.home / relative
		path.mkdir(parents=True)
		(path / name).write_text("")
		return path

	def test_a_folder_with_get_next_line_c(self):
		self.assertTrue(looks_like_project(self.project("a")))
		self.assertFalse(looks_like_project(self.project("b", "ft_printf.c")))
		self.assertFalse(looks_like_project(self.home))

	def test_the_nearest_first_and_not_in_hidden_folders(self):
		deep = self.project("42/common/get_next_line")
		near = self.project("gnl")
		self.project(".trash/get_next_line")
		self.project("a/b/c/d/e/get_next_line")
		self.assertEqual(list(iter_projects(self.home)), [near, deep])

	def test_the_last_project_is_kept_with_the_other_settings(self):
		settings = self.home / "settings.json"
		settings.write_text(json.dumps({"language": "fr", "testers": {"pushterator": {"project": "/p"}}}))
		self.assertIsNone(last_project(settings))
		remember_project("/home/me/gnl", settings)
		self.assertEqual(last_project(settings), "/home/me/gnl")
		data = json.loads(settings.read_text())
		self.assertEqual((data["language"], data["testers"]["pushterator"]), ("fr", {"project": "/p"}))

if __name__ == "__main__":
	unittest.main()

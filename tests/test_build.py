"""The test program built with the files of the student, for each BUFFER_SIZE, and run."""

import tempfile
import unittest
from pathlib import Path

from liner.build import Builder
from liner.run import run_program
from tests.fakes import make_project

class BuildTestCase(unittest.TestCase):

	def setUp(self):
		folder = tempfile.TemporaryDirectory()
		self.addCleanup(folder.cleanup)
		self.folder = Path(folder.name)

class TestTheBuild(BuildTestCase):

	def test_one_program_for_each_buffer_size(self):
		builder = Builder(make_project(self.folder), self.folder / "build")
		program, error = builder.build(42)
		self.assertIsNone(error)
		other, _ = builder.build(1)
		self.assertNotEqual(program, other)
		self.assertTrue(program.is_file())

	def test_without_buffer_size(self):
		program, error = Builder(make_project(self.folder), self.folder / "build").build(None)
		self.assertIsNone(error)

	def test_a_warning_is_an_error(self):
		project = make_project(self.folder)
		with (project / "get_next_line_utils.c").open("a") as utils:
			utils.write("int\tunused(void)\n{\n\tint\tx;\n\treturn (0);\n}\n")
		program, error = Builder(project, self.folder / "build").build(42)
		self.assertIsNone(program)
		self.assertIn("unused", error)

	def test_the_bonus_files(self):
		builder = Builder(make_project(self.folder, bonus=True), self.folder / "build", bonus=True)
		program, error = builder.build(42)
		self.assertIsNone(error)

class TestTheRun(BuildTestCase):

	def test_the_bytes_of_the_lines(self):
		program, _ = Builder(make_project(self.folder), self.folder / "build").build(42)
		path = self.folder / "f.txt"
		path.write_bytes(b"h\xc3\xa9llo\nlast")
		run = run_program(program, ["lines", str(path)])
		self.assertIn(b"L 7\nh\xc3\xa9llo\n\n", run.stdout)
		self.assertTrue(run.stdout.rstrip().endswith(b"!P"))

	def test_the_standard_input(self):
		program, _ = Builder(make_project(self.folder), self.folder / "build").build(42)
		run = run_program(program, ["lines", "-"], stdin=b"a\nb\n")
		self.assertTrue(run.stdout.startswith(b"L 2\na\n\n"))

if __name__ == "__main__":
	unittest.main()

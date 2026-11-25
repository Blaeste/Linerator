"""The project: its files at the root, the header, the build with and without BUFFER_SIZE, what is forbidden."""

import stat
import tempfile
import unittest
from pathlib import Path

from liner.project import Workspace, check_project
from tests.fakes import make_project

GOOD_README = """*This project has been created as part of the 42 curriculum by alice.*

## Description
Reads a file one line at a time.

## Instructions
cc -Wall -Wextra -Werror -D BUFFER_SIZE=42 get_next_line.c get_next_line_utils.c main.c

## Resources
man 2 read. AI was used to review the README.

## Algorithm
A static buffer keeps what was read after the newline, for the next call.
"""

def fake_norminette(folder, output, code):
	path = Path(folder) / "norminette"
	path.write_text(f"#!/bin/sh\necho '{output}'\nexit {code}\n")
	path.chmod(path.stat().st_mode | stat.S_IXUSR)
	return path

class ProjectTestCase(unittest.TestCase):

	def setUp(self):
		folder = tempfile.TemporaryDirectory()
		self.addCleanup(folder.cleanup)
		self.folder = Path(folder.name)

	def project(self, mode="good", bonus=False):
		project = make_project(self.folder / "p", mode, bonus=bonus)
		(project / "README.md").write_text(GOOD_README)
		return project

	def checks(self, project, norminette=None):
		workspace = Workspace(project)
		self.addCleanup(workspace.cleanup)
		result = check_project(workspace, norminette=norminette or str(self.folder / "none"))
		return {check.key: check for check in result.checks}

class TestTheFiles(ProjectTestCase):

	def test_a_project_that_follows_the_subject(self):
		checks = self.checks(self.project())
		for key in ("files.mandatory", "header.prototype", "build.with_buffer_size", "build.without_buffer_size",
				"code.libft", "code.globals"):
			self.assertEqual(checks[key].status, "OK", (key, checks[key].detail))
		self.assertEqual(checks["files.bonus"].status, "SKIP")
		self.assertEqual(checks["norm"].status, "SKIP")

	def test_a_missing_file(self):
		project = self.project()
		(project / "get_next_line_utils.c").unlink()
		checks = self.checks(project)
		self.assertEqual(checks["files.mandatory"].status, "KO")
		self.assertIn("get_next_line_utils.c", checks["files.mandatory"].detail)

	def test_no_prototype_in_the_header(self):
		project = self.project()
		(project / "get_next_line.h").write_text("#ifndef GET_NEXT_LINE_H\n# define GET_NEXT_LINE_H\n#endif\n")
		self.assertEqual(self.checks(project)["header.prototype"].status, "KO")

	def test_the_libft_used(self):
		project = self.project()
		(project / "libft").mkdir()
		self.assertEqual(self.checks(project)["code.libft"].status, "KO")

	def test_the_bonus_files_and_their_statics(self):
		checks = self.checks(self.project(bonus=True))
		self.assertEqual(checks["files.bonus"].status, "OK")
		self.assertEqual(checks["bonus.static"].status, "OK", checks["bonus.static"].detail)
		checks = self.checks(make_project(self.folder / "two", "two_statics", bonus=True))
		self.assertEqual(checks["bonus.static"].status, "KO")

	def test_functions_of_the_libc_that_are_not_allowed(self):
		"""The fake reads with stdio: fdopen, getc... are not read, malloc and free."""
		checks = self.checks(self.project())
		self.assertEqual(checks["code.externals"].status, "KO")
		self.assertIn("fdopen", checks["code.externals"].detail)
		checks = self.checks(make_project(self.folder / "lseek", "reads_all"))
		self.assertIn("lseek", checks["code.externals"].detail)

	def test_the_norm(self):
		checks = self.checks(self.project(), norminette=str(fake_norminette(self.folder, "Error!", 1)))
		self.assertEqual(checks["norm"].status, "KO")

class TestTheBuild(ProjectTestCase):

	def test_a_warning_breaks_the_build(self):
		project = self.project()
		with (project / "get_next_line_utils.c").open("a") as utils:
			utils.write("int\tunused(void)\n{\n\tint\tx;\n\treturn (0);\n}\n")
		checks = self.checks(project)
		self.assertEqual(checks["build.with_buffer_size"].status, "KO")
		self.assertIn("unused", checks["build.with_buffer_size"].detail)

	def test_buffer_size_needed(self):
		project = self.project()
		source = (project / "get_next_line.c").read_text().replace("#ifndef BUFFER_SIZE\n# define BUFFER_SIZE 42\n#endif\n", "")
		(project / "get_next_line.c").write_text(source + "\nint\tsize(void)\n{\n\treturn (BUFFER_SIZE);\n}\n")
		checks = self.checks(project)
		self.assertEqual(checks["build.with_buffer_size"].status, "OK")
		self.assertEqual(checks["build.without_buffer_size"].status, "KO")

class TestTheReadme(ProjectTestCase):

	def checks_with(self, readme):
		project = self.project()
		if readme is None:
			(project / "README.md").unlink()
		else:
			(project / "README.md").write_text(readme)
		return self.checks(project)

	def test_a_good_readme(self):
		checks = self.checks_with(GOOD_README)
		for key in ("readme.exists", "readme.first_line", "readme.sections", "readme.ai", "readme.algorithm"):
			self.assertEqual(checks[key].status, "OK", (key, checks[key].detail))

	def test_no_readme(self):
		self.assertEqual(self.checks_with(None)["readme.exists"].status, "KO")

	def test_the_first_line_not_in_italics(self):
		checks = self.checks_with(GOOD_README.replace("*This project", "This project", 1))
		self.assertEqual(checks["readme.first_line"].status, "KO")

	def test_a_section_missing(self):
		checks = self.checks_with(GOOD_README.replace("## Instructions", "## How"))
		self.assertEqual(checks["readme.sections"].status, "KO")
		self.assertIn("Instructions", checks["readme.sections"].detail)

	def test_no_ai_and_no_algorithm(self):
		readme = GOOD_README.replace("AI was used to review the README.", "").split("## Algorithm")[0]
		checks = self.checks_with(readme)
		self.assertEqual(checks["readme.ai"].status, "WARN")
		self.assertEqual(checks["readme.algorithm"].status, "WARN")

if __name__ == "__main__":
	unittest.main()

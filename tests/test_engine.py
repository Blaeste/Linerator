"""The whole run, its JSON for 42pal, its report and the command line, with the fake get_next_line."""

import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from liner.engine import test_project
from liner.report import Stream, failing_sizes, to_dict
from tests.fakes import make_project
from tests.test_project import GOOD_README

ROOT = Path(__file__).resolve().parent.parent

class EngineTestCase(unittest.TestCase):

	def setUp(self):
		folder = tempfile.TemporaryDirectory()
		self.addCleanup(folder.cleanup)
		self.folder = Path(folder.name)

	def project(self, mode="good", bonus=False):
		project = make_project(self.folder / mode, mode, bonus=bonus)
		(project / "README.md").write_text(GOOD_README)
		return project

class TestTheRun(EngineTestCase):

	def test_the_events_in_order(self):
		events = []
		report = test_project(self.project(), norminette="", steps=("fds",), on_event=lambda kind, data:
			events.append((kind, data)))
		kinds = [kind for kind, _ in events]
		self.assertEqual(kinds[0], "start")
		self.assertEqual(events[1], ("step", {"step": "subject"}))
		self.assertIn("check", kinds)
		self.assertLess(kinds.index("plan"), kinds.index("test"))
		plans = [data for kind, data in events if kind == "plan"]
		self.assertEqual(len(plans), 1)
		self.assertEqual(plans[0]["tests"], 3)
		self.assertEqual(plans[0]["suites"], [{"key": "fds", "name": "file descriptors", "group": "The other tests",
			"label": "file descriptors", "tests": 3}])
		self.assertEqual(kinds.count("test"), 3)
		self.assertEqual(len(report.results), 3)
		self.assertIsNone(report.error)

	def test_a_folder_that_does_not_exist(self):
		report = test_project(self.folder / "nowhere")
		self.assertIn("Folder not found", report.error[0])
		self.assertFalse(report.passed)

	def test_files_missing(self):
		project = self.project()
		(project / "get_next_line.c").unlink()
		report = test_project(project, norminette="")
		self.assertIn("not at the root", report.error[0])
		self.assertEqual(report.results, [])

	def test_a_build_that_fails(self):
		project = self.project()
		(project / "get_next_line_utils.c").write_text("int\tbroken(void)\n{\n\treturn (x);\n}\n")
		report = test_project(project, norminette="")
		self.assertIn("does not compile", report.error[0])
		self.assertIn("x", report.error[1])

	def test_the_bonus_tested_when_its_files_are_there(self):
		report = test_project(self.project(bonus=True), norminette="", steps=("bonus",))
		self.assertEqual({result.suite for result in report.results}, {"bonus"})
		report = test_project(self.project(mode="leaks"), norminette="", steps=("bonus",))
		self.assertEqual(report.results, [])

	def test_the_workspace_kept(self):
		report = test_project(self.project(), norminette="", steps=("fds",), keep=True)
		self.addCleanup(report.workspace.cleanup)
		self.assertTrue((report.workspace.path / "get_next_line.c").is_file())

class TestFewerMallocs(EngineTestCase):

	def test_a_second_plan_with_the_mallocs_counted(self):
		events = []
		test_project(self.project(), norminette="", steps=("malloc_failures",), on_event=lambda kind, data:
			events.append((kind, data)))
		plans = [data for kind, data in events if kind == "plan"]
		self.assertEqual([plan["tests"] for plan in plans], [20, 5])
		self.assertEqual(plans[-1]["suites"][0]["tests"], 5)

class TestTheJson(EngineTestCase):

	def test_format_1(self):
		report = test_project(self.project("leaks"), norminette="", steps=("lines",))
		data = to_dict(report)
		self.assertEqual((data["format"], data["tester"]), (1, "linerator"))
		self.assertEqual(set(data), {"format", "tester", "version", "lang", "seed", "log", "error", "notes",
			"conformity", "tests", "suites"})
		# The name and the row of each suite, for 42pal: BUFFER_SIZE=1 rather than buffer_1.
		self.assertEqual(data["suites"][0], {"key": "buffer_1", "name": "BUFFER_SIZE=1", "group": "BUFFER_SIZE",
			"label": "1", "tests": 16})
		self.assertEqual(data["suites"][-1]["label"], "default")
		self.assertTrue(any(test["status"] == "LEAK" for test in data["tests"]))
		self.assertIn("BUFFER_SIZE", data["notes"][0])
		self.assertEqual(failing_sizes(report.results)[0], "1")

	def test_the_stream(self):
		out = io.StringIO()
		Stream(out)("plan", {"tests": 3})
		self.assertEqual(json.loads(out.getvalue()), {"event": "plan", "tests": 3})

class TestTheCommandLine(EngineTestCase):

	def run_linerator(self, *args):
		return subprocess.run([str(ROOT / "linerator"), *args], capture_output=True, text=True, cwd="/",
			env={"PATH": "/usr/bin:/bin", "PAL42_LANG": "en", "HOME": str(self.folder)})

	def test_the_plain_report(self):
		done = self.run_linerator(str(self.project()), "--plain", "--no-color", "--no-norm", "--only", "fds,stdin",
			"--json", str(self.folder / "out.json"))
		# The fake reads with stdio: the functions it uses fail the project, never the tests.
		self.assertEqual(done.returncode, 1, done.stderr)
		self.assertIn("file descriptors", done.stdout)
		self.assertIn("standard input", done.stdout)
		self.assertIn("not an oracle", done.stdout)
		data = json.loads((self.folder / "out.json").read_text())
		self.assertTrue(all(test["status"] == "PASS" for test in data["tests"]), data["tests"])

	def test_the_stream_option(self):
		done = self.run_linerator(str(self.project()), "--stream", "--no-norm", "--only", "fds")
		events = [json.loads(line)["event"] for line in done.stdout.splitlines()]
		self.assertEqual(events[0], "start")
		self.assertEqual(events.count("test"), 3)

	def test_a_wrong_folder(self):
		done = self.run_linerator(str(self.folder / "nowhere"), "--plain", "--json", str(self.folder / "out.json"))
		self.assertEqual(done.returncode, 2)
		self.assertIn("Folder not found", json.loads((self.folder / "out.json").read_text())["error"]["title"])

	def test_a_wrong_step(self):
		done = self.run_linerator("--only", "nothing")
		self.assertEqual(done.returncode, 2)
		self.assertIn("unknown step", done.stderr)

if __name__ == "__main__":
	unittest.main()

"""The full screen: the logo and the folder, then the run live, then the report; the visualizer."""

import asyncio
import functools
import tempfile
import threading
import unittest
from pathlib import Path

import liner.cli  # noqa: F401  (puts vendor/ in Python's path)
from liner.cli.tui import HomeScreen, LineratorApp, RunScreen
from liner.engine import Report
from liner.judge import Result
from liner.project import Check
from tests.fakes import make_project
from tests.test_project import GOOD_README

OPTIONS = dict(seed=5, timeout=10, norminette="", steps=("fds", "stdin"))

def screen_test(method):
	"""Run an async test with asyncio.run (IsolatedAsyncioTestCase makes textual slow)."""
	@functools.wraps(method)
	def run(self):
		asyncio.run(method(self))
	return run

def log_text(screen):
	return "\n".join(line.text for line in screen.query_one("#log").lines)

def rendered(widget):
	return str(widget.render())

class TuiTestCase(unittest.TestCase):

	def setUp(self):
		folder = tempfile.TemporaryDirectory()
		self.addCleanup(folder.cleanup)
		self.folder = Path(folder.name)
		self.project = make_project(self.folder, "good")
		(self.project / "README.md").write_text(GOOD_README)
		self.settings = self.folder / "settings.json"

	def app(self, folder=None, run=None, options=OPTIONS):
		app = LineratorApp(options, folder=folder, projects_root=self.folder, settings=self.settings, run=run)
		app.animation_level = "none"
		return app

	async def wait(self, pilot, condition, what, tries=400):
		for _ in range(tries):
			await pilot.pause(0.05)
			if condition():
				return
		self.fail(f"never: {what}")

	async def wait_report(self, pilot):
		await self.wait(pilot, lambda: isinstance(pilot.app.screen, RunScreen) and not pilot.app.screen.busy
			and pilot.app.screen.report is not None, "the report")
		return pilot.app.screen

class TestHome(TuiTestCase):

	@screen_test
	async def test_the_logo_and_the_project_found(self):
		app = self.app()
		async with app.run_test(size=(110, 40)) as pilot:
			screen = app.screen
			self.assertIsInstance(screen, HomeScreen)
			self.assertTrue(screen.query(".logo"))
			await self.wait(pilot, lambda: any(path == self.project for _, path in screen.entry_labels()), "found")

	@screen_test
	async def test_the_disclaimer_at_the_bottom(self):
		app = self.app()
		async with app.run_test(size=(110, 40)) as pilot:
			await pilot.pause()
			self.assertIn("not an oracle", rendered(app.screen.query_one(".disclaimer")))

	@screen_test
	async def test_escape_quits(self):
		app = self.app()
		async with app.run_test(size=(110, 40)) as pilot:
			await pilot.press("escape")
			await pilot.pause()
		self.assertFalse(app.is_running)

class TestTheRun(TuiTestCase):

	@screen_test
	async def test_the_project_chosen_runs_then_the_report(self):
		app = self.app()
		async with app.run_test(size=(110, 40)) as pilot:
			screen = app.screen
			await self.wait(pilot, lambda: any(path == self.project for _, path in screen.entry_labels()), "found")
			await pilot.press("down", "enter")
			run = await self.wait_report(pilot)
			text = log_text(run)
			self.assertIn("file descriptors", text)
			self.assertIn("The prototype of get_next_line", text)
			self.assertIn("✗ KO", rendered(run.query_one("#header")))
			self.assertIn("The other tests", rendered(run.query_one("#sizes")))

	@screen_test
	async def test_a_folder_given_runs_at_once_and_is_kept(self):
		app = self.app(folder=self.project)
		async with app.run_test(size=(110, 40)) as pilot:
			await self.wait_report(pilot)
		from liner.find import last_project
		self.assertEqual(last_project(self.settings), str(self.project))

	@screen_test
	async def test_r_runs_again_and_f_chooses_another_folder(self):
		app = self.app(folder=self.project)
		async with app.run_test(size=(110, 40)) as pilot:
			run = await self.wait_report(pilot)
			first = run.report
			await pilot.press("r")
			await self.wait(pilot, lambda: run.report is not first and not run.busy, "again")
			await pilot.press("f")
			await pilot.pause()
			self.assertIsInstance(app.screen, HomeScreen)

class TestLive(TuiTestCase):

	@screen_test
	async def test_what_comes_shows_at_once(self):
		release = threading.Event()
		self.addCleanup(release.set)

		def run(folder, on_event):
			on_event("start", {"tester": "linerator", "version": "1", "lang": "en"})
			on_event("step", {"step": "subject"})
			on_event("check", {"key": "code.externals", "group": "Code", "label": "Only read, malloc and free",
				"status": "KO", "detail": "not allowed: lseek"})
			on_event("plan", {"tests": 4, "suites": [{"key": "buffer_1", "name": "BUFFER_SIZE=1", "group": "BUFFER_SIZE",
				"label": "1", "tests": 4}]})
			on_event("step", {"step": "tests"})
			on_event("phase", {"phase": "lines"})
			on_event("test", {"name": "buffer_1/few_lines", "status": "PASS", "detail": "5 lines", "ms": 1})
			on_event("test", {"name": "buffer_1/long_line", "status": "LEAK", "detail": "1 block left", "ms": 1})
			release.wait(10)
			return Report(checks=[Check("code.externals", "Code", "Only read, malloc and free", "KO")],
				results=[Result("buffer_1/long_line", "LEAK", "1 block left")], project=folder)

		app = self.app(folder=self.project, run=run)
		async with app.run_test(size=(110, 40)) as pilot:
			await self.wait(pilot, lambda: isinstance(app.screen, RunScreen)
				and "2/4" in rendered(app.screen.query_one("#activity")), "the counter")
			screen = app.screen
			self.assertIn("1 KO", rendered(screen.query_one("#activity")))
			text = log_text(screen)
			self.assertIn("not allowed: lseek", text)
			self.assertIn("1 block left", text)
			# The failure live with the name of its suite, like 42pal shows it.
			self.assertIn("BUFFER_SIZE=1 · long_line", text)
			self.assertIn("1/2", rendered(screen.query_one("#sizes")))
			self.assertTrue(screen.busy)
			release.set()
			await self.wait_report(pilot)

class TestTheVisualizer(TuiTestCase):

	@screen_test
	async def test_v_plays_the_reads_and_plus_changes_buffer_size(self):
		from liner.cli.visualizer import VisualizerScreen
		app = self.app(folder=self.project)
		async with app.run_test(size=(120, 40)) as pilot:
			run = await self.wait_report(pilot)
			await pilot.press("v")
			await self.wait(pilot, lambda: isinstance(app.screen, VisualizerScreen) and app.screen.steps, "the steps")
			viz = app.screen
			self.assertEqual(viz.buffer_size, 8)
			await pilot.press("end")
			now = rendered(viz.query_one("#viz-now"))
			self.assertIn("returns NULL", now)
			self.assertIn("4 lines returned", now)
			# The fake reads with stdio: no read() of its own to show, only its lines (see test_trace).
			await pilot.press("home", "right")
			self.assertIn("returns 'Roses are red,⏎'", rendered(viz.query_one("#viz-now")))
			await pilot.press("plus")
			await self.wait(pilot, lambda: viz.buffer_size == 10 and viz.steps and not viz.loading, "BUFFER_SIZE=10")
			self.assertIn("BUFFER_SIZE=10", rendered(viz.query_one("#viz-header")))
			await pilot.press("f")
			await self.wait(pilot, lambda: viz.sample == 1 and viz.steps and not viz.loading, "another file")
			await pilot.press("escape")
			await pilot.pause()
			self.assertIs(app.screen, run)

	@screen_test
	async def test_a_leak_is_said_and_escape_leaves_when_alone(self):
		from liner.cli.visualizer import VisualizerApp
		project = make_project(self.folder / "leaks", "leaks")
		app = VisualizerApp(project, self.folder / "viz", 8)
		async with app.run_test(size=(120, 40)) as pilot:
			await self.wait(pilot, lambda: app.screen.steps and not app.screen.loading, "the steps")
			viz = app.screen
			await pilot.press("end")
			self.assertIn("LEAK · 4 block(s) not freed", rendered(viz.query_one("#viz-now")))
			await pilot.press("escape")
			await pilot.pause()
		self.assertFalse(app.is_running)

class TestThePanel(unittest.TestCase):
	"""The panel of the suites: a row a suite, a cell a test; 42pal draws the same from the JSON."""

	def styles(self, text):
		return [str(span.style) for span in text.spans if text.plain[span.start:span.end] == "■" * (span.end - span.start)]

	def test_a_cell_a_test(self):
		from liner.cli.display import BAD, GOOD, WAITING, suites_panel
		rows = [{"key": "buffer_1", "name": "BUFFER_SIZE=1", "group": "BUFFER_SIZE", "label": "1", "tests": 4}]
		text = suites_panel(rows, {"buffer_1": [True, False]})
		self.assertEqual(text.plain, "BUFFER_SIZE\n 1 ■■■■ 1/2")
		self.assertEqual(self.styles(text), [GOOD, BAD, WAITING, WAITING])

	def test_more_tests_than_room_and_a_long_label(self):
		from liner.cli.display import suites_panel
		rows = [{"key": "a", "name": "a", "group": "The other tests", "label": "read as little as possible, really",
			"tests": 100}]
		text = suites_panel(rows, {"a": [True] * 100}, width=44)
		line = text.plain.splitlines()[1]
		self.assertLessEqual(len(line), 44)
		self.assertIn("…", line)
		self.assertTrue(line.endswith("100/100"))

	def test_the_groups(self):
		from liner.names import suite_rows
		from liner.cli.display import suites_panel
		text = suites_panel(suite_rows([("buffer_1", 16), ("buffer_default", 16), ("stdin", 6), ("info", 2)]), {})
		self.assertEqual([line.strip()[:12] for line in text.plain.splitlines() if line.strip()],
			["BUFFER_SIZE", "1       ■■■■", "default ■■■■", "The other te", "standard inp"])

class TestTheReport(unittest.TestCase):

	def test_the_disclaimer_at_the_end(self):
		from liner.cli.display import report_lines
		self.assertIn("not an oracle", report_lines(Report())[-1].plain)

if __name__ == "__main__":
	unittest.main()

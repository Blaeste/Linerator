"""The steps of Linerator, with the fake get_next_line of tests/fakes (stdio: it can never be handed in)."""

import tempfile
import unittest
from pathlib import Path

from liner.build import Builder
from liner.files import lines_of
from liner.judge import Result, interleave, parse
from liner.suite import MALLOC_FAILURES, judge_all, planned, run_suite
from tests.fakes import make_project

class SuiteTestCase(unittest.TestCase):

	def setUp(self):
		folder = tempfile.TemporaryDirectory()
		self.addCleanup(folder.cleanup)
		self.folder = Path(folder.name)

	def results(self, mode="good", steps=None, bonus=False):
		project = make_project(self.folder / mode, mode, bonus=bonus)
		builder = Builder(project, self.folder / mode / "build")
		bonus_builder = Builder(project, self.folder / mode / "build", bonus=True) if bonus else None
		return {r.name: r for r in judge_all(builder, self.folder / mode / "run", bonus_builder=bonus_builder,
			steps=steps, timeout=10)}

	def statuses(self, results, suite):
		return {r.status for name, r in results.items() if name.startswith(suite + "/")}

class TestTheParts(unittest.TestCase):

	def test_the_lines_of_a_file(self):
		self.assertEqual(lines_of(b"a\nbb\n"), [b"a\n", b"bb\n"])
		self.assertEqual(lines_of(b"a\nlast"), [b"a\n", b"last"])
		self.assertEqual(lines_of(b""), [])
		self.assertEqual(lines_of(b"\n\n"), [b"\n", b"\n"])

	def test_the_events_of_the_program(self):
		out = parse(b"F 0\nL 2\na\n\nX\nN\nR 3 42\nabc\nS reads=2 bytes=3 first=3 mallocs=1\n!P\n")
		self.assertEqual(out.results, [b"a\n", None])
		self.assertEqual(out.files, [0, 0])
		self.assertEqual(out.read_failed, 1)
		self.assertEqual(out.reads[0][:3], (3, 42, b"abc"))
		self.assertEqual(out.stats["mallocs"], 1)
		self.assertEqual(out.end, ("P", ""))

	def test_files_in_turn(self):
		self.assertEqual(interleave([[b"a\n", b"b\n"], [b"c\n"]]),
			[(0, b"a\n"), (1, b"c\n"), (0, b"b\n"), (1, None), (0, None)])

	def test_the_plan(self):
		self.assertEqual(planned(["lines"], False), 11 * 16)
		self.assertEqual(planned(["limits"], False), 2 * 18)
		self.assertGreater(planned(None, True), planned(None, False))

class TestAGoodFake(SuiteTestCase):

	def test_every_line_for_every_buffer_size(self):
		results = self.results(steps=("lines", "stdin", "fds"))
		for suite in ("buffer_1", "buffer_42", "buffer_10000000", "buffer_default", "stdin", "fds"):
			bad = {n: r.detail for n, r in results.items() if n.startswith(suite + "/") and r.bad}
			self.assertEqual(bad, {}, suite)
		self.assertIn("buffer_9999/long_line", results)

	def test_malloc_failures_and_reading_little(self):
		results = self.results(steps=("malloc_failures", "read_little"))
		self.assertEqual(self.statuses(results, "read_little"), {"PASS"})
		self.assertEqual(self.statuses(results, "malloc_failures"), {"PASS"})
		self.assertEqual(results["malloc_failures/malloc_1"].status, "PASS")

	def test_malloc_made_to_fail_as_many_times_as_it_is_called(self):
		project = make_project(self.folder / "count", "good")
		builder = Builder(project, self.folder / "count" / "build")
		events = list(run_suite(builder, self.folder / "count" / "run", steps=("malloc_failures",)))
		fewer = [event for event in events if isinstance(event, tuple) and event[0] == "fewer"]
		results = [event for event in events if isinstance(event, Result)]
		# The fake calls malloc once a line of few_lines (5), plus nothing for the NULLs.
		self.assertEqual(len(results), 5)
		self.assertEqual(fewer, [("fewer", "malloc_failures", MALLOC_FAILURES - 5)])

	def test_a_fake_that_never_calls_read(self):
		results = self.results(steps=("read_errors",))
		self.assertEqual(results["read_errors/first_read"].status, "FAIL")
		self.assertIn("never called read()", results["read_errors/first_read"].detail)

	def test_the_bonus(self):
		results = self.results(steps=("bonus",), bonus=True)
		self.assertEqual(self.statuses(results, "bonus"), {"PASS"})

	def test_the_undefined_cases(self):
		results = self.results(steps=("info",))
		self.assertEqual(self.statuses(results, "info"), {"INFO"})

class TestTheCasesOfOtherTesters(SuiteTestCase):
	"""Cases from the testers of francinette (fsoares, MIT) and ideas from gnlTester."""

	def test_the_limits_around_buffer_size(self):
		from liner.suite import limit_contents
		files = limit_contents(10)
		self.assertEqual(files["9"], b"012345678")
		self.assertEqual(files["10_nl_9"], b"0123456789\n012345678")
		self.assertEqual(len(files), 18)
		results = self.results(steps=("limits",))
		self.assertIn("limits_42/41_nl", results)
		self.assertEqual(self.statuses(results, "limits_10"), {"PASS"})
		self.assertEqual(self.statuses(results, "limits_42"), {"PASS"})

	def test_a_read_error_then_the_file_opened_again(self):
		results = self.results("sees_read_errors", steps=("read_errors",))
		self.assertEqual(results["read_errors/error_then_reopen_buffer_42"].status, "PASS")

	def test_the_new_files(self):
		from liner.files import contents
		self.assertEqual(contents()["one_char"], b"0")
		self.assertIn(b"\n\n", contents()["alternating_empty_lines"])

class TestBrokenFakes(SuiteTestCase):

	def test_a_leak(self):
		results = self.results("leaks", steps=("lines",))
		self.assertEqual(results["buffer_42/few_lines"].status, "LEAK")

	def test_a_line_without_its_terminator(self):
		results = self.results("no_terminator", steps=("lines",))
		self.assertEqual(results["buffer_42/few_lines"].status, "OOB")

	def test_the_newline_forgotten(self):
		results = self.results("no_newline", steps=("lines",))
		self.assertEqual(results["buffer_42/few_lines"].status, "FAIL")
		self.assertIn("'one⏎' expected", results["buffer_42/few_lines"].detail)

	def test_a_crash_on_a_long_line(self):
		results = self.results("crash_long", steps=("lines",))
		self.assertEqual(results["buffer_42/long_line"].status, "CRASH")
		self.assertEqual(results["buffer_42/few_lines"].status, "PASS")

	def test_a_buffer_of_buffer_size_on_the_stack(self):
		results = self.results("stack_buffer", steps=("lines",))
		self.assertEqual(results["buffer_10000000/few_lines"].status, "CRASH")
		self.assertIn("stack", results["buffer_10000000/few_lines"].detail)
		self.assertEqual(results["buffer_42/few_lines"].status, "PASS")

	def test_the_whole_file_read_before_the_first_line(self):
		results = self.results("reads_all", steps=("read_little",))
		self.assertEqual(results["read_little/buffer_42"].status, "FAIL")
		self.assertIn("whole file", results["read_little/buffer_42"].detail)

	def test_a_fake_that_sees_a_failed_read(self):
		results = self.results("sees_read_errors", steps=("read_errors",))
		self.assertEqual(results["read_errors/first_read"].status, "PASS")
		self.assertEqual(results["read_errors/second_read_buffer_1"].status, "PASS")

	def test_a_line_without_its_terminator_in_a_bigger_block(self):
		# The bytes after the line are not zeros: strlen() runs up to the protected page.
		results = self.results("unterminated", steps=("lines",))
		self.assertEqual(results["buffer_42/few_lines"].status, "OOB")
		self.assertEqual(results["buffer_1/few_lines"].status, "OOB")

class TestAStash(SuiteTestCase):
	"""A get_next_line that keeps a block from malloc between calls, like most of them do."""

	def test_the_stash_freed_when_null_is_returned(self):
		# The read() made to fail keeps failing, and the run goes on up to NULL after a failed malloc:
		# what the next calls read again is freed at the end, so a correct stash is no leak.
		results = self.results("keeps_a_stash", steps=("read_errors", "malloc_failures"))
		bad = {name: f"{r.status} {r.detail}" for name, r in results.items() if r.status != "PASS"}
		self.assertEqual(bad, {})
		self.assertIn("malloc_failures/malloc_1", results)
		self.assertIn("read_errors/first_read", results)

	def test_the_stash_lost_on_an_error(self):
		results = self.results("loses_its_stash", steps=("read_errors", "malloc_failures"))
		self.assertEqual(results["read_errors/second_read_buffer_1"].status, "LEAK")
		self.assertEqual(results["malloc_failures/malloc_2"].status, "LEAK")

if __name__ == "__main__":
	unittest.main()

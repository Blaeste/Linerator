"""The reads step by step, for the visualizer: what is read, returned, kept in the static."""

import unittest

from liner.judge import parse
from liner.trace import Step, layout, shown_byte, steps, zone

# BUFFER_SIZE=4 on "ab\ncd\n": read "ab\nc", return "ab\n", read "d\n", return "cd\n", read 0, NULL.
TRACE = b"R 4 4\nab\nc\nL 3\nab\n\nR 2 4\nd\n\nL 3\ncd\n\nR 0 4\n\nN\n!P\n"

class TestTheSteps(unittest.TestCase):

	def test_reads_lines_and_what_is_kept(self):
		found = steps(parse(TRACE))
		self.assertEqual([(step.kind, step.call) for step in found],
			[("read", 1), ("line", 1), ("read", 2), ("line", 2), ("read", 3), ("null", 3)])
		self.assertEqual([step.kept for step in found], [4, 1, 3, 0, 0, 0])
		self.assertEqual(found[2].data, b"d\n")
		self.assertEqual(found[1].data, b"ab\n")

	def test_a_failed_read(self):
		found = steps(parse(b"R -1 4\n\nN\n!P\n"))
		self.assertEqual((found[0].returned, found[0].read_total), (-1, 0))

	def test_the_zone_of_each_byte(self):
		found = steps(parse(TRACE))
		self.assertEqual([zone(offset, None) for offset in range(6)], ["unread"] * 6)
		self.assertEqual([zone(offset, found[0]) for offset in range(6)], ["new"] * 4 + ["unread"] * 2)
		self.assertEqual([zone(offset, found[1]) for offset in range(6)], ["out"] * 3 + ["kept"] + ["unread"] * 2)
		self.assertEqual([zone(offset, found[2]) for offset in range(6)], ["returned"] * 3 + ["kept"] + ["new"] * 2)

class TestTheDrawing(unittest.TestCase):

	def test_a_row_a_line_cut_when_long(self):
		self.assertEqual(layout(b"ab\ncdefg", 3), [[0, 1, 2], [3, 4, 5], [6, 7]])
		self.assertEqual(layout(b"", 3), [[]])

	def test_the_cells(self):
		self.assertEqual("".join(map(shown_byte, b"a\n\x00")), "a⏎·")

	def test_kept_never_negative(self):
		self.assertEqual(Step("line", 1, read_total=2, returned_total=3).kept, 0)

if __name__ == "__main__":
	unittest.main()

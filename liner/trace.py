"""The reads of get_next_line, step by step, for the visualizer.

The test program, in its trace mode, prints each read() and each result
(see engine/harness.c). steps() turns them into Steps: a read(), a line
returned, or NULL; each knows how many bytes were read and returned so far,
so the bytes still in the static are those read but not returned yet.
"""

from dataclasses import dataclass

from liner.i18n import N_

# The files of the visualizer: (name, bytes).
SAMPLES = (
	(N_("a poem"), b"Roses are red,\nviolets are blue,\nget_next_line\nreads lines for you.\n"),
	(N_("empty lines, no newline at the end"), b"first\n\n\nfourth\n\nthe last one, without a newline"),
	(N_("a long line"), b"a long line: " + b"0123456789" * 6 + b"\nshort\n"),
	(N_("one line without a newline"), b"Hello, world!"),
)
# The BUFFER_SIZE + and - go through.
SIZES = (1, 2, 3, 4, 5, 8, 10, 16, 32, 42, 64, 100, 1000)

@dataclass
class Step:
	# "read", "line" or "null".
	kind: str
	# The call to get_next_line it belongs to, from 1.
	call: int
	# read(): what it returned, the size asked, the bytes read. line: the line.
	returned: int = 0
	asked: int = 0
	data: bytes = b""
	# The bytes read and returned once this step is done.
	read_total: int = 0
	returned_total: int = 0

	@property
	def kept(self):
		"""The bytes in the static once this step is done."""
		return max(0, self.read_total - self.returned_total)

def steps(out):
	"""The Steps of a parsed Output (judge.parse) of the trace mode."""
	found, read_total, returned_total = [], 0, 0
	reads = list(out.reads)
	for index, result in enumerate(out.results + [False]):
		call = index + 1
		while reads and reads[0][3] == index:
			returned, asked, data, _ = reads.pop(0)
			read_total += max(returned, 0)
			found.append(Step("read", call, returned, asked, data, read_total, returned_total))
		if result is False:
			break
		if result is None:
			found.append(Step("null", call, read_total=read_total, returned_total=returned_total))
		else:
			returned_total += len(result)
			found.append(Step("line", call, data=result, read_total=read_total, returned_total=returned_total))
	return found

def shown_byte(byte):
	"""One cell for a byte: itself when printable, ⏎ for a newline, · otherwise."""
	if byte == 10:
		return "⏎"
	return chr(byte) if 32 <= byte < 127 else "·"

def layout(data, width):
	"""The rows of the file for a strip `width` cells wide: [[offset, ...]], a row a line of the file, cut when long."""
	rows, row = [], []
	for offset, byte in enumerate(data):
		row.append(offset)
		if byte == 10 or len(row) == width:
			rows.append(row)
			row = []
	if row or not rows:
		rows.append(row)
	return rows

def zone(offset, step):
	"""What the byte at `offset` is once `step` is done (None: before the first one).

	"new" (just read), "out" (just returned), "returned", "kept" (in the static) or "unread".
	"""
	if step is None:
		return "unread"
	if step.kind == "read" and step.read_total - max(step.returned, 0) <= offset < step.read_total:
		return "new"
	if step.kind == "line" and step.returned_total - len(step.data) <= offset < step.returned_total:
		return "out"
	if offset < step.returned_total:
		return "returned"
	if offset < step.read_total:
		return "kept"
	return "unread"

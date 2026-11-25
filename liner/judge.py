"""What the test program printed, and what Linerator says of it.

parse reads its events (see engine/harness.c); each judge_* gives a Result:
PASS, FAIL, CRASH, TIMEOUT, LEAK, MEMERR, OOB, INTERNAL; WARN (to look at)
and INFO (an undefined case) are not counted.
"""

from dataclasses import dataclass, field

from liner.i18n import t

@dataclass
class Result:
	name: str
	status: str
	detail: str = ""
	ms: int = 0

	@property
	def suite(self):
		return self.name.split("/", 1)[0]

	@property
	def bad(self):
		return self.status not in ("PASS", "INFO", "WARN")

@dataclass
class Output:
	"""The events of a run: the results of get_next_line (bytes, or None for NULL), in order."""
	results: list = field(default_factory=list)
	# (multi) the file each result was read from.
	files: list = field(default_factory=list)
	# (trace) each read(): (returned, asked, bytes), and the result it came before.
	reads: list = field(default_factory=list)
	stats: dict = field(default_factory=dict)
	# The index of the result the failed read() came before, or None.
	read_failed: int = None
	# ("P", "") when nothing was wrong; ("L", why) a leak, ("M", ...), ("O", ...), ("X", ...).
	end: tuple = None

def parse(data):
	"""The Output of the bytes the test program printed."""
	out = Output()
	at, size, current = 0, len(data), None

	def line():
		nonlocal at
		end = data.find(b"\n", at)
		if end < 0:
			end = size
		text = data[at:end].decode("utf-8", "replace")
		at = end + 1
		return text

	while at < size:
		head = line()
		if head.startswith("L "):
			length = int(head[2:])
			out.results.append(data[at:at + length])
			out.files.append(current)
			at += length + 1
		elif head == "N":
			out.results.append(None)
			out.files.append(current)
		elif head.startswith("F "):
			current = int(head[2:])
		elif head.startswith("R "):
			returned, asked = map(int, head[2:].split())
			chunk = data[at:at + returned] if returned > 0 else b""
			at += max(returned, 0) + 1
			out.reads.append((returned, asked, chunk, len(out.results)))
		elif head == "X":
			out.read_failed = len(out.results)
		elif head.startswith("S "):
			out.stats = {key: int(value) for key, value in (word.split("=") for word in head[2:].split())}
		elif head.startswith("!"):
			out.end = (head[1:2], head[3:])
	return out

def shown(line, length=40):
	"""A line for a message: its newline as ⏎, cut when long."""
	if line is None:
		return "NULL"
	text = line.decode("utf-8", "replace").replace("\n", "⏎")
	return repr(text if len(text) <= length else text[:length] + f"… ({len(line)} bytes)")

ENDS = {"L": "LEAK", "M": "MEMERR", "O": "OOB", "X": "INTERNAL", "C": "CRASH", "F": "FAIL"}

def problem(name, run, timeout, buffer_size=None):
	"""A Result when the run went wrong as a process (crash, timeout, memory), else None, and the Output."""
	result = lambda status, detail: (Result(name, status, detail, run.ms), None)  # noqa: E731
	if run.failed:
		return result("CRASH", t("could not start: {error}", error=run.failed))
	if run.timed_out:
		return result("TIMEOUT", t("more than {seconds} s", seconds=timeout))
	if run.signal:
		hint = ""
		if buffer_size and buffer_size >= 1000000:
			hint = " · " + t("a buffer of BUFFER_SIZE bytes on the stack?")
		return result("CRASH", run.signal + hint)
	out = parse(run.stdout)
	if out.end is None:
		return result("CRASH", t("the test ended before its end (code {code})", code=run.code))
	if out.end[0] != "P":
		return result(ENDS.get(out.end[0], "FAIL"), out.end[1])
	return None, out

def compare(got, expected):
	"""The first difference between the lines got and those expected (both end with NULL), or None."""
	for index, (line, want) in enumerate(zip(got, expected), start=1):
		if line != want:
			if want is None:
				return t("call {index}: {line} after the end, NULL expected", index=index, line=shown(line))
			if line is None:
				return t("call {index}: NULL, {want} expected", index=index, want=shown(want))
			return t("call {index}: {line}, {want} expected", index=index, line=shown(line), want=shown(want))
	if len(got) < len(expected):
		return t("the test stopped after {count} calls", count=len(got))
	return None

def lines_text(count):
	return t("1 line") if count == 1 else t("{count} lines", count=count)

def judge_lines(name, run, expected, timeout=10, buffer_size=None):
	"""Every line of the file, then NULL, and NULL again."""
	result, out = problem(name, run, timeout, buffer_size)
	if result:
		return result
	difference = compare(out.results, expected + [None, None])
	if difference:
		return Result(name, "FAIL", difference, run.ms)
	return Result(name, "PASS", lines_text(len(expected)), run.ms)

def judge_null(name, run, timeout=10):
	"""An fd get_next_line cannot read: NULL each time."""
	result, out = problem(name, run, timeout)
	if result:
		return result
	lines = [line for line in out.results if line is not None]
	if lines:
		return Result(name, "FAIL", t("{line} returned, NULL expected", line=shown(lines[0])), run.ms)
	return Result(name, "PASS", "NULL", run.ms)

def judge_closed(name, run, first, timeout=10):
	"""The first line, then NULL once the fd is closed."""
	result, out = problem(name, run, timeout)
	if result:
		return result
	difference = compare(out.results, [first, None])
	if difference:
		return Result(name, "FAIL", t("after close(fd): {difference}", difference=difference), run.ms)
	return Result(name, "PASS", t("NULL once the fd is closed"), run.ms)

def judge_read_error(name, run, expected, timeout=10):
	"""The read() made to fail: NULL from that call, no crash, no leak, the lines before it right."""
	result, out = problem(name, run, timeout)
	if result:
		return result
	if out.read_failed is None:
		return Result(name, "FAIL", t("get_next_line never called read() that many times"), run.ms)
	before = out.results[:out.read_failed]
	if before != expected[:len(before)]:
		return Result(name, "FAIL", compare(before, expected) or t("wrong lines before the error"), run.ms)
	after = out.results[out.read_failed] if out.read_failed < len(out.results) else None
	if after is not None:
		return Result(name, "FAIL", t("read() returned -1, but get_next_line returned {line}", line=shown(after)), run.ms)
	return Result(name, "PASS", t("NULL when read() fails, nothing left allocated"), run.ms)

def judge_malloc_failure(name, run, expected, call, timeout=10):
	"""The malloc number `call` made to fail: no crash, no leak, and the lines returned before the NULL right."""
	result, out = problem(name, run, timeout)
	if result:
		return result
	got = out.results
	stop = got.index(None) if None in got else len(got)
	if got[:stop] != expected[:stop]:
		return Result(name, "FAIL", compare(got[:stop], expected) or t("wrong lines"), run.ms)
	if out.stats.get("mallocs", 0) < call:
		return Result(name, "INFO", t("only {count} calls to malloc", count=out.stats.get("mallocs", 0)), run.ms)
	return Result(name, "PASS", t("NULL, nothing left allocated"), run.ms)

def judge_read_little(name, run, first_line, file_size, buffer_size, timeout=10):
	"""Read as little as possible: before the first line, the line and a BUFFER_SIZE at most."""
	result, out = problem(name, run, timeout, buffer_size)
	if result:
		return result
	read = out.stats.get("first", 0)
	enough = len(first_line) + buffer_size
	if out.results[:1] != [first_line]:
		return Result(name, "FAIL", compare(out.results[:1], [first_line]) or t("wrong first line"), run.ms)
	if read >= file_size:
		return Result(name, "FAIL", t("the whole file ({size} bytes) read before the first line", size=file_size), run.ms)
	if read > enough:
		return Result(name, "WARN", t("{read} bytes read before the first line: {enough} are enough", read=read,
			enough=enough), run.ms)
	return Result(name, "PASS", t("{read} bytes read before the first line", read=read), run.ms)

def interleave(per_file):
	"""The results expected when the files are read in turn, each up to NULL: [(file, line or None)]."""
	queues = [list(lines) + [None] for lines in per_file]
	order, left = [], set(range(len(per_file)))
	while left:
		for index in range(len(per_file)):
			if index in left:
				line = queues[index].pop(0)
				order.append((index, line))
				if line is None:
					left.discard(index)
	return order

def judge_multi(name, run, per_file, timeout=10):
	"""(bonus) The files read in turn: each keeps its own place."""
	result, out = problem(name, run, timeout)
	if result:
		return result
	got = list(zip(out.files, out.results))
	for index, ((file, line), (want_file, want)) in enumerate(zip(got, interleave(per_file)), start=1):
		if (file, line) != (want_file, want):
			return Result(name, "FAIL", t("call {index} (file {file}): {line}, {want} expected", index=index,
				file=want_file + 1, line=shown(line), want=shown(want)), run.ms)
	return Result(name, "PASS", t("{count} files read in turn", count=len(per_file)), run.ms)

def judge_info(name, run, timeout=10):
	"""An undefined case: what get_next_line did, in a few words."""
	result, out = problem(name, run, timeout)
	if result:
		return Result(name, "INFO", f"{result.status}: {result.detail}", run.ms)
	lines = [line for line in out.results if line is not None]
	return Result(name, "INFO", lines_text(len(lines)) + (", " + shown(lines[0]) if lines else ""), run.ms)

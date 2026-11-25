"""The steps of the tests of get_next_line, and their runs.

run_suite gives, in order: ("step", name) when a step starts, then a
Result for each run. The runs of a step go in parallel; their results come
in the order of the cases. plan() says how many results each suite will
give at most: ("fewer", suite, n) says n of them will not come (malloc is
made to fail only as many times as get_next_line calls it).
"""

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from liner.files import BIG_FIRST_LINE, READ_ERROR, big, contents, lines_of, write_files
from liner.i18n import language, t
from liner.judge import (Result, judge_closed, judge_info, judge_lines, judge_malloc_failure, judge_multi,
	judge_null, judge_read_error, judge_read_little, judge_reopen, parse)
from liner.run import run_program

BUFFER_SIZES = (1, 2, 3, 5, 10, 42, 100, 1000, 9999, 10000000, None)
STEPS = ("lines", "limits", "stdin", "fds", "read_errors", "malloc_failures", "read_little", "bonus", "info")
# Lines around BUFFER_SIZE (from the testers of francinette, fsoares, MIT; and the files 41, 42, 43 of gnlTester).
LIMIT_SIZES = (10, 42)
REOPEN_SIZES = (1, 42, 1000)
STDIN_FILES = ("few_lines", "last_line_no_newline", "empty", "long_line", "many_lines")
# The calls to malloc made to fail, each in its own run, at most.
MALLOC_FAILURES = 20
READ_LITTLE_SIZES = (1, 42, 1000)
BONUS_SETS = ((42, ("few_lines", "last_line_no_newline", "many_lines")), (1, ("one_line", "empty", "long_line")))

def label(buffer_size):
	return "default" if buffer_size is None else str(buffer_size)

def steps_to_run(steps, bonus):
	return [step for step in STEPS if (steps is None or step in steps) and (step != "bonus" or bonus)]

def plan(steps, bonus):
	"""[(suite, results)] the steps will give, in order (malloc_failures at most)."""
	sizes = {"stdin": len(STDIN_FILES) + 1, "fds": 3, "read_errors": 3 + len(REOPEN_SIZES),
		"malloc_failures": MALLOC_FAILURES, "read_little": len(READ_LITTLE_SIZES), "bonus": len(BONUS_SETS), "info": 2}
	found = []
	for step in steps_to_run(steps, bonus):
		if step == "lines":
			found += [(f"buffer_{label(size)}", len(contents())) for size in BUFFER_SIZES]
		elif step == "limits":
			found += [(f"limits_{size}", len(limit_contents(size))) for size in LIMIT_SIZES]
		else:
			found.append((step, sizes[step]))
	return found

def planned(steps, bonus):
	"""How many results the steps will give."""
	return sum(count for _, count in plan(steps, bonus))

def limit_contents(size):
	"""{name: bytes}: lines of size - 1 to 2 × size + 1, with or without their newline, and pairs."""
	patterns = [(length,) for length in (size - 1, size, size + 1, 2 * size - 1, 2 * size, 2 * size + 1)]
	patterns = [pattern + nl for pattern in patterns for nl in ((), ("nl",))]
	patterns += [(size - 1, "nl", size - 1, "nl"), (size - 1, "nl", size), (size - 1, "nl", size, "nl"),
		(size, "nl", size - 2, "nl"), (size, "nl", size - 1), (size, "nl", size - 1, "nl")]
	digits = b"0123456789" * (2 * size // 10 + 2)
	return {"_".join(map(str, pattern)): b"".join(b"\n" if part == "nl" else digits[:part] for part in pattern)
		for pattern in patterns}

class Programs:
	"""The test program for each BUFFER_SIZE, built once (or why it cannot be)."""

	def __init__(self, builder):
		self.builder = builder
		self.built = {}
		self.locks = {}
		self.lock = threading.Lock()

	def get(self, buffer_size):
		# One lock a size: the runs of a size wait for its program, built once.
		with self.lock:
			lock = self.locks.setdefault(buffer_size, threading.Lock())
		with lock:
			if buffer_size not in self.built:
				self.built[buffer_size] = self.builder.build(buffer_size)
			return self.built[buffer_size]

def run_suite(builder, folder, bonus_builder=None, seed=42, timeout=10, steps=None, workers=None):
	"""Run the steps with the programs of `builder` (and `bonus_builder` for the bonus)."""
	paths = write_files(Path(folder) / "files", seed)
	data = {**contents(seed), "big": big(), "read_error": READ_ERROR}
	expected = {name: lines_of(content) for name, content in data.items()}
	programs, bonus_programs = Programs(builder), Programs(bonus_builder) if bonus_builder else None
	lang = ["--lang", "fr"] if language() == "fr" else []
	workers = workers or min(8, os.cpu_count() or 2)

	def run(name, buffer_size, args, judge, stdin=b"", which=None):
		program, error = (which or programs).get(buffer_size)
		if program is None:
			return Result(name, "FAIL", t("does not compile with BUFFER_SIZE={size}: {error}", size=label(buffer_size),
				error=error.splitlines()[-1] if error else ""))
		return judge(run_program(program, [*lang, *args], stdin=stdin, timeout=timeout))

	def malloc_calls():
		"""How many times malloc is made to fail: the calls of a run without failure, MALLOC_FAILURES at most."""
		program, _ = programs.get(42)
		if program is None:
			return MALLOC_FAILURES
		out = parse(run_program(program, [*lang, "lines", str(paths["few_lines"])], timeout=timeout).stdout)
		return max(1, min(MALLOC_FAILURES, out.stats.get("mallocs", MALLOC_FAILURES)))

	def cases(step):
		if step == "lines":
			for size in BUFFER_SIZES:
				for file in contents(seed):
					yield lambda size=size, file=file: run(f"buffer_{label(size)}/{file}", size, ["lines", str(paths[file])],
						lambda r, file=file, size=size: judge_lines(f"buffer_{label(size)}/{file}", r, expected[file],
						timeout, size))
		elif step == "limits":
			for size in LIMIT_SIZES:
				folder_ = Path(folder) / "files" / f"limits_{size}"
				folder_.mkdir(parents=True, exist_ok=True)
				for file, content in limit_contents(size).items():
					path = folder_ / f"{file}.txt"
					path.write_bytes(content)
					name = f"limits_{size}/{file}"
					yield lambda size=size, path=path, name=name, content=content: run(name, size, ["lines", str(path)],
						lambda r: judge_lines(name, r, lines_of(content), timeout, size))
		elif step == "stdin":
			for size, file in [(42, file) for file in STDIN_FILES] + [(1, "few_lines")]:
				name = f"stdin/{file}" + ("_buffer_1" if size == 1 else "")
				yield lambda size=size, file=file, name=name: run(name, size, ["lines", "-"],
					lambda r: judge_lines(name, r, expected[file], timeout, size), stdin=data[file])
		elif step == "fds":
			yield lambda: run("fds/minus_one", 42, ["fd", "-1"], lambda r: judge_null("fds/minus_one", r, timeout))
			yield lambda: run("fds/never_opened", 42, ["fd", "1000"], lambda r: judge_null("fds/never_opened", r, timeout))
			yield lambda: run("fds/closed_between_calls", 42, ["closed", str(paths["closed"])],
				lambda r: judge_closed("fds/closed_between_calls", r, b"one\n", timeout))
		elif step == "read_errors":
			for name, size, call, file in (("first_read", 42, 1, "few_lines"), ("second_read_buffer_1", 1, 2, "few_lines"),
					("in_a_long_line", 42, 3, "long_line")):
				yield lambda name=name, size=size, call=call, file=file: run(f"read_errors/{name}", size,
					["--fail-read", str(call), "lines", str(paths[file])],
					lambda r: judge_read_error(f"read_errors/{name}", r, expected[file], timeout))
			for size in REOPEN_SIZES:
				name = f"read_errors/error_then_reopen_buffer_{size}"
				yield lambda size=size, name=name: run(name, size, ["reopen", str(paths["read_error"])],
					lambda r: judge_reopen(name, r, lines_of(data["read_error"]), timeout))
		elif step == "malloc_failures":
			for call in range(1, malloc_calls() + 1):
				yield lambda call=call: run(f"malloc_failures/malloc_{call}", 42,
					["--fail-malloc", str(call), "lines", str(paths["few_lines"])],
					lambda r: judge_malloc_failure(f"malloc_failures/malloc_{call}", r, expected["few_lines"], call,
					timeout))
		elif step == "read_little":
			for size in READ_LITTLE_SIZES:
				yield lambda size=size: run(f"read_little/buffer_{size}", size, ["first", str(paths["big"])],
					lambda r: judge_read_little(f"read_little/buffer_{size}", r, BIG_FIRST_LINE, len(data["big"]), size,
					timeout))
		elif step == "bonus":
			for size, files in BONUS_SETS:
				name = f"bonus/{len(files)}_files_buffer_{size}"
				yield lambda size=size, files=files, name=name: run(name, size,
					["multi", *(str(paths[file]) for file in files)],
					lambda r: judge_multi(name, r, [expected[file] for file in files], timeout), which=bonus_programs)
		elif step == "info":
			binary = Path(folder) / "files" / "binary.bin"
			binary.write_bytes(bytes(range(256)) * 4 + b"\n\x00\n")
			yield lambda: run("info/binary_file", 42, ["lines", str(binary)], lambda r: judge_info("info/binary_file", r,
				timeout))
			def buffer_size_0():
				result = run("info/buffer_size_0", 0, ["lines", str(paths["few_lines"])],
					lambda r: judge_info("info/buffer_size_0", r, timeout))
				# Not compiling with BUFFER_SIZE=0 is a choice, never a failure.
				return Result(result.name, "INFO", result.detail, result.ms)
			yield buffer_size_0

	with ThreadPoolExecutor(max_workers=workers) as pool:
		for step in steps_to_run(steps, bonus_builder is not None):
			yield ("step", step)
			found = list(cases(step))
			if step == "malloc_failures" and len(found) < MALLOC_FAILURES:
				yield ("fewer", "malloc_failures", MALLOC_FAILURES - len(found))
			yield from pool.map(lambda case: case(), found)

def judge_all(builder, folder, **options):
	"""The results only, in a list."""
	return [event for event in run_suite(builder, folder, **options) if isinstance(event, Result)]

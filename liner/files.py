"""The files get_next_line reads in the tests, and the lines expected from each.

They come from a seed: the same seed gives the same files.
"""

import random
from pathlib import Path

# A long line: longer than any BUFFER_SIZE but the biggest, short enough for BUFFER_SIZE=1.
LONG = 20000

def contents(seed=42):
	"""{name: bytes} of the files the lines are read from, in order."""
	rng = random.Random(seed)
	many = b"".join(bytes(rng.choice(b"abcdefghijklmnopqrstuvwxyz 0123456789") for _ in range(rng.randint(0, 120))) + b"\n"
		for _ in range(2000))
	around = b"".join(b"x" * size + b"\n" for size in range(38, 47))
	return {
		"empty": b"",
		"one_newline": b"\n",
		"one_line": b"Hello, world!\n",
		"one_line_no_newline": b"Hello, world!",
		"few_lines": b"one\ntwo\nthree\nfour\nfive\n",
		"only_newlines": b"\n\n\n\n\n",
		"last_line_no_newline": b"first\nsecond\nthird",
		"empty_lines_between": b"a\n\n\nb\n\n",
		"one_char_lines": b"a\nb\nc\nd\ne\n",
		"one_char": b"0",
		"alternating_empty_lines": b"line 1\n\nline 3\n\nline 5\n\n",
		"lines_around_42": around,
		"long_line": b"x" * LONG + b"\nend\n",
		"long_line_no_newline": b"y" * LONG,
		"utf8": "héllo wörld ✓\nこんにちは\n🙂\n".encode(),
		"many_lines": many,
	}

# The file the reads are counted on: a short first line, then a lot.
BIG_FIRST_LINE = b"first line\n"

# The file of the read error, then opened again (from the testers of francinette, fsoares, MIT).
READ_ERROR = b"aaaaaaaaaa\nbbbbbbbbbb\ncccccccccc\ndddddddddd\n"

# The file closed between two calls: its second line is too long to be read already.
CLOSED = b"one\n" + b"x" * 1000 + b"\nend\n"

def big(size=1 << 20):
	return BIG_FIRST_LINE + (b"0123456789abcdef" * (size // 16) + b"\n")

def lines_of(data):
	"""The lines get_next_line must return for `data`, each with its newline but maybe the last."""
	lines = data.split(b"\n")
	result = [line + b"\n" for line in lines[:-1]]
	if lines[-1]:
		result.append(lines[-1])
	return result

def write_files(folder, seed=42):
	"""Write the files in `folder`; return {name: path}, with "big" too."""
	folder = Path(folder)
	folder.mkdir(parents=True, exist_ok=True)
	paths = {}
	for name, data in {**contents(seed), "big": big(), "closed": CLOSED, "read_error": READ_ERROR}.items():
		path = folder / f"{name}.txt"
		path.write_bytes(data)
		paths[name] = path
	return paths

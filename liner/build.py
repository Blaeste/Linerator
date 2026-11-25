"""The test program of Linerator built with the files of the student, one for each BUFFER_SIZE.

The engine (engine/*.c) is compiled once, quietly; the files of the student
with -Wall -Wextra -Werror like the subject asks, with -D BUFFER_SIZE=n, or
without it (None). malloc, free and read go through the engine (ld --wrap).
"""

import shutil
import subprocess
import threading
from pathlib import Path

ENGINE = Path(__file__).resolve().parent.parent / "engine"
ENGINE_SOURCES = ("harness.c", "alloc.c", "guard.c")
MANDATORY = ("get_next_line.c", "get_next_line_utils.c")
BONUS = ("get_next_line_bonus.c", "get_next_line_utils_bonus.c")
FLAGS = ("-Wall", "-Wextra", "-Werror")
WRAP = "-Wl,--wrap=malloc,--wrap=free,--wrap=read"

def _tail(text, lines=15):
	return "\n".join(text.strip().splitlines()[-lines:])

class Builder:
	"""Builds in `folder` the test program with the files of `project` (a copy: nothing is written in it)."""

	def __init__(self, project, folder, bonus=False, cc="cc"):
		self.project = Path(project)
		self.folder = Path(folder)
		self.sources = BONUS if bonus else MANDATORY
		self.name = "bonus" if bonus else "mandatory"
		self.cc = shutil.which(cc) or cc
		self._engine = None
		self._lock = threading.Lock()

	def _run(self, command):
		try:
			done = subprocess.run(command, capture_output=True, text=True, errors="replace", timeout=120)
		except (OSError, subprocess.TimeoutExpired) as error:
			return False, str(error)
		return done.returncode == 0, done.stdout + done.stderr

	def engine(self):
		"""The objects of the engine, compiled once."""
		with self._lock:
			if self._engine is None:
				out = self.folder / "engine"
				out.mkdir(parents=True, exist_ok=True)
				objects = []
				for source in ENGINE_SOURCES:
					obj = out / (Path(source).stem + ".o")
					ok, output = self._run([self.cc, "-g", "-O0", "-w", "-I", str(ENGINE), "-c", str(ENGINE / source),
						"-o", str(obj)])
					if not ok:
						raise RuntimeError(output)
					objects.append(str(obj))
				self._engine = objects
			return self._engine

	def build(self, buffer_size):
		"""The program for `buffer_size` (None: no -D), or (None, why it could not be built)."""
		label = "default" if buffer_size is None else str(buffer_size)
		out = self.folder / f"{self.name}_{label}"
		out.mkdir(parents=True, exist_ok=True)
		define = [] if buffer_size is None else [f"-D BUFFER_SIZE={buffer_size}"]
		objects = []
		for source in self.sources:
			path = self.project / source
			if not path.is_file():
				return None, f"{source}: missing"
			obj = out / (Path(source).stem + ".o")
			ok, output = self._run([self.cc, *FLAGS, *define, "-g", "-I", str(self.project), "-c", str(path), "-o",
				str(obj)])
			if not ok:
				return None, _tail(output)
			objects.append(str(obj))
		program = out / "harness"
		ok, output = self._run([self.cc, "-g", *objects, *self.engine(), WRAP, "-o", str(program)])
		if not ok:
			return None, _tail(output)
		return program, None

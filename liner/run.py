"""Running the test program: its output as bytes (lines may hold any byte), a crash or a timeout."""

import signal
import subprocess
import time
from dataclasses import dataclass

@dataclass
class Run:
	"""What a run gave. signal: SIGSEGV... when it was killed; failed: why it could not start."""
	stdout: bytes = b""
	stderr: bytes = b""
	code: int = None
	signal: str = None
	timed_out: bool = False
	ms: int = 0
	failed: str = None

def run_program(program, args, stdin=b"", timeout=10):
	"""Run `program` with `args`, `stdin` on its standard input."""
	start = time.monotonic()
	try:
		done = subprocess.run([str(program), *args], input=stdin, capture_output=True, timeout=timeout)
	except subprocess.TimeoutExpired as expired:
		return Run(expired.stdout or b"", expired.stderr or b"", timed_out=True, ms=int(timeout * 1000))
	except OSError as error:
		return Run(failed=str(error))
	name = None
	if done.returncode < 0:
		try:
			name = signal.Signals(-done.returncode).name
		except ValueError:
			name = f"signal {-done.returncode}"
	return Run(done.stdout, done.stderr, done.returncode, name, ms=int((time.monotonic() - start) * 1000))

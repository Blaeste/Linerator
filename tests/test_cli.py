"""The launcher: ./linerator from any folder, with the system python3."""

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAUNCHER = ROOT / "linerator"

class TestLauncher(unittest.TestCase):

	def test_the_version(self):
		from liner import __version__
		done = subprocess.run([str(LAUNCHER), "--version"], capture_output=True, text=True, cwd="/")
		self.assertEqual(done.returncode, 0, done.stderr)
		self.assertEqual(done.stdout.strip(), f"linerator {__version__}")

if __name__ == "__main__":
	unittest.main()

"""./linerator [folder] [options]: the command line.

In a terminal, Linerator opens full screen; --plain (or a pipe) prints the
report line by line instead. --json writes the results for other tools,
--stream prints each event as it comes (both for 42pal). The exit code is
0 when everything passes, 1 when something fails, 2 for a wrong use.
"""

import argparse
import json
import os
import sys
from pathlib import Path

from liner import __version__, i18n
from liner.suite import STEPS

# Where 42pal keeps its settings: Linerator speaks the language chosen there.
PAL42_SETTINGS = Path.home() / ".42pal" / "settings.json"

def positive_size(text):
	try:
		size = int(text)
	except ValueError:
		raise argparse.ArgumentTypeError("BUFFER_SIZE must be a number") from None
	if size < 1:
		raise argparse.ArgumentTypeError("BUFFER_SIZE must be positive")
	return size

def parse_args(argv):
	parser = argparse.ArgumentParser(prog="linerator", description="A tester of get_next_line.")
	parser.add_argument("folder", nargs="?", help="the folder of the get_next_line project (asked when not given)")
	parser.add_argument("--version", action="version", version=f"linerator {__version__}")
	parser.add_argument("--plain", action="store_true", help="the report line by line, instead of the full screen")
	parser.add_argument("--no-color", action="store_true", help="no colors")
	parser.add_argument("--json", metavar="FILE", help="write the results in JSON")
	parser.add_argument("--stream", action="store_true", help="each event on a line of JSON, as it comes")
	parser.add_argument("--lang", choices=sorted(i18n.languages()), help="the language (default: the one of 42pal, else English)")
	parser.add_argument("--seed", type=int, default=42, help="the seed of the random lines (default: 42)")
	parser.add_argument("--timeout", type=float, default=10, help="seconds a run may take (default: 10)")
	parser.add_argument("--no-norm", action="store_true", help="no norminette")
	parser.add_argument("--only", metavar="STEPS", help="only these steps, comma separated: " + ",".join(STEPS))
	parser.add_argument("--visualize", action="store_true", help="build get_next_line and open the visualizer at once")
	parser.add_argument("--buffer-size", type=positive_size, default=8,
		help="the BUFFER_SIZE of the visualizer at first (default: 8)")
	args = parser.parse_args(argv)
	if args.timeout <= 0:
		parser.error("--timeout must be positive")
	if args.only:
		args.only = tuple(step.strip() for step in args.only.split(",") if step.strip())
		unknown = [step for step in args.only if step not in STEPS]
		if unknown:
			parser.error(f"unknown step: {', '.join(unknown)}")
	return args

def choose_language(args, settings=PAL42_SETTINGS, environ=None):
	"""--lang, else PAL42_LANG, else the language of 42pal, else English."""
	environ = os.environ if environ is None else environ
	code = args.lang or environ.get("PAL42_LANG")
	if not code:
		try:
			code = json.loads(Path(settings).read_text(encoding="utf-8")).get("language")
		except (OSError, ValueError, AttributeError):
			code = None
	return i18n.set_language(code or i18n.DEFAULT)

def options(args):
	"""What test_project needs, from the command line."""
	return dict(seed=args.seed, timeout=args.timeout, norminette="" if args.no_norm else "norminette", steps=args.only)

def main(argv=None):
	args = parse_args(sys.argv[1:] if argv is None else argv)
	choose_language(args)
	import liner.cli  # noqa: F401  (puts vendor/ in Python's path)
	if args.visualize:
		from liner.cli.visualizer import run_visualizer
		return run_visualizer(args)
	headless = args.plain or args.json or args.stream or not sys.stdout.isatty()
	if not headless:
		from liner.cli.tui import run_app
		return run_app(args)
	return run_plain(args)

def run_plain(args):
	"""The report line by line (or the events, with --stream); return the exit code."""
	from rich.console import Console

	from liner.cli.display import Progress, report_lines
	from liner.engine import test_project
	from liner.i18n import t
	from liner.report import Stream, to_json

	console = Console(no_color=args.no_color, highlight=False)
	errors = Console(stderr=True, no_color=args.no_color, highlight=False)
	folder = Path(args.folder).expanduser() if args.folder else Path.cwd()
	if not folder.is_dir():
		message = t("Folder not found: {path}", path=folder)
		errors.print(message, markup=False)
		if args.json:
			Path(args.json).write_text(json.dumps({"format": 1, "tester": "linerator", "version": __version__,
				"lang": i18n.language(), "error": {"title": message, "detail": ""}, "notes": [], "conformity": [],
				"tests": []}), encoding="utf-8")
		return 2
	if args.stream:
		report = test_project(folder.resolve(), on_event=Stream(sys.stdout), **options(args))
	else:
		progress = Progress()
		with console.status(progress.text(), spinner="dots") as spinner:
			def on_event(kind, data):
				progress.update(kind, data)
				spinner.update(progress.text())
			report = test_project(folder.resolve(), on_event=on_event, **options(args))
		for line in report_lines(report):
			console.print(line)
	if args.json:
		to_json(report, args.json, lang=i18n.language())
	return 0 if report.passed else 1

"""The results for other tools (42pal): the JSON of --json (format 1, like libfterator) and --stream.

The JSON is written even when nothing could run. Its fields are those of
libfterator; the notes say which BUFFER_SIZE fail, and "suites" gives the
name of each suite and the rows of the panel (names.suite_rows), so that
42pal shows them like Linerator does.
"""

import json
from pathlib import Path

from liner import __version__
from liner.engine import check_dict, test_dict
from liner.i18n import t

JSON_FORMAT = 1

def failing_sizes(results):
	"""The BUFFER_SIZE of the tests of the lines that fail, in order: ["1", "10000000"]."""
	sizes = []
	for result in results:
		if result.bad and result.suite.startswith("buffer_"):
			size = result.suite[len("buffer_"):]
			if size not in sizes:
				sizes.append(size)
	return sizes

def notes(report):
	sizes = failing_sizes(report.results)
	if not sizes:
		return []
	names = [t("by default") if size == "default" else size for size in sizes]
	return [t("The lines fail with BUFFER_SIZE: {sizes}", sizes=", ".join(names))]

def to_dict(report, lang="en"):
	error = {"title": report.error[0], "detail": report.error[1]} if report.error else None
	return {
		"format": JSON_FORMAT,
		"tester": "linerator",
		"version": __version__,
		"lang": lang,
		"seed": report.seed,
		"log": None,
		"error": error,
		"notes": notes(report),
		"conformity": [check_dict(check) for check in report.checks],
		"tests": [test_dict(result) for result in report.results],
		"suites": report.suites,
	}

def to_json(report, path, lang="en"):
	Path(path).write_text(json.dumps(to_dict(report, lang), ensure_ascii=False, indent=1), encoding="utf-8")

class Stream:
	"""--stream: each event on a line of JSON, as it comes."""

	def __init__(self, out):
		self.out = out

	def __call__(self, kind, data):
		self.out.write(json.dumps({"event": kind, **data}, ensure_ascii=False) + "\n")
		self.out.flush()

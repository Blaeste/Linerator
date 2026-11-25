"""The whole run of Linerator: the project, then the tests.

test_project gives a Report. on_event(kind, data), when given, is called
as things happen, with the events of --stream: start, step (subject: the
project; tests), check, plan (the number of runs to come and the rows of
the panel; it may come again, smaller), phase (lines, limits... : what the
tests are doing), test, error.
"""

from dataclasses import dataclass, field
from pathlib import Path

from liner import __version__
from liner.build import Builder
from liner.i18n import language, t
from liner.judge import Result
from liner.names import suite_rows
from liner.project import Workspace, check_project
from liner.suite import plan, run_suite

@dataclass
class Report:
	checks: list = field(default_factory=list)
	results: list = field(default_factory=list)
	# (title, detail) when the tests could not run.
	error: tuple = None
	project: Path = None
	seed: int = 42
	# The copy where the tests were built, kept for the visualizer (keep=True).
	workspace: object = None
	# The rows of the panel: a row a suite (names.suite_rows).
	suites: list = field(default_factory=list)

	@property
	def conformity_score(self):
		counted = [check for check in self.checks if check.status in ("OK", "KO")]
		return sum(check.status == "OK" for check in counted), len(counted)

	@property
	def test_score(self):
		"""The tests passed out of those counted: an undefined case (INFO) is not; a warning passes."""
		counted = [result for result in self.results if result.status != "INFO"]
		return sum(not result.bad for result in counted), len(counted)

	@property
	def passed(self):
		return (self.error is None and all(check.status != "KO" for check in self.checks)
			and not any(result.bad for result in self.results))

def test_project(source, seed=42, timeout=10, norminette="norminette", steps=None, on_event=None, keep=False,
		workers=None):
	"""Test the get_next_line of the folder `source`."""
	emit = on_event or (lambda kind, data: None)
	source = Path(source).expanduser()
	report = Report(project=source, seed=seed)
	emit("start", {"tester": "linerator", "version": __version__, "lang": language()})
	if not source.is_dir():
		return _fail(report, emit, t("Folder not found: {path}", path=source), "")
	workspace = Workspace(source)
	try:
		emit("step", {"step": "subject"})
		project = check_project(workspace, norminette, on_check=lambda check: emit("check", check_dict(check)))
		report.checks = project.checks
		files = next(check for check in project.checks if check.key == "files.mandatory")
		if files.status != "OK":
			return _fail(report, emit, t("The files of get_next_line are not at the root: the tests cannot run."),
				files.detail)
		build = next(check for check in project.checks if check.key == "build.with_buffer_size")
		if build.status != "OK":
			return _fail(report, emit, t("get_next_line does not compile: the tests cannot run."), build.detail)
		builder = Builder(workspace.path, workspace.root / "build")
		bonus = Builder(workspace.path, workspace.root / "build", bonus=True) if project.bonus else None
		suites = plan(steps, bonus is not None)
		report.suites = suite_rows(suites)
		emit("plan", plan_dict(suites))
		emit("step", {"step": "tests"})
		for event in run_suite(builder, workspace.root / "run", bonus, seed=seed, timeout=timeout, steps=steps,
				workers=workers):
			if isinstance(event, Result):
				report.results.append(event)
				emit("test", test_dict(event))
			elif event[0] == "fewer":
				suites = [(key, count - event[2] if key == event[1] else count) for key, count in suites]
				report.suites = suite_rows(suites)
				emit("plan", plan_dict(suites))
			else:
				emit("phase", {"phase": event[1]})
		return report
	finally:
		if keep:
			report.workspace = workspace
		else:
			workspace.cleanup()

def _fail(report, emit, title, detail):
	report.error = (title, detail)
	emit("error", {"title": title, "detail": detail})
	return report

def check_dict(check):
	return {"key": check.key, "group": check.group, "label": check.label, "status": check.status,
		"detail": check.detail}

def plan_dict(suites):
	"""The plan event: the number of tests to come, and the rows of the panel."""
	return {"tests": sum(count for _, count in suites), "suites": suite_rows(suites)}

def test_dict(result):
	return {"name": result.name, "status": result.status, "detail": result.detail, "ms": result.ms}

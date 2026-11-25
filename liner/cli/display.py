"""How Linerator looks: the report and the progress, as rich Texts, for the terminal and the full screen.

The style is the one of Pushterator: green for what passes, red for what
fails, violet for what matters.
"""

from pathlib import Path

from rich.panel import Panel
from rich.text import Text

from liner.i18n import N_, t
from liner.names import suite_name
from liner.report import notes

# The style of each status; any other one (FAIL, CRASH, LEAK...) is a failure.
STYLES = {"OK": "green", "PASS": "green", "KO": "red", "WARN": "yellow", "SKIP": "dim", "INFO": "cyan"}

# What the tests are doing, in the counter.
PHASES = {
	"lines": N_("lines, each BUFFER_SIZE"),
	"limits": N_("lines around BUFFER_SIZE"),
	"stdin": N_("standard input"),
	"fds": N_("file descriptors"),
	"read_errors": N_("read() fails"),
	"malloc_failures": N_("malloc() fails"),
	"read_little": N_("read as little as possible"),
	"bonus": N_("several fds (bonus)"),
	"info": N_("undefined cases"),
}

ACCENT = "bold #a5b4fc"

# Said at the bottom of the home screen and at the end of the report.
DISCLAIMER = N_("A helper tool, not an oracle: it does not cover every test of the evaluation. Test your project yourself too.")

def short_path(path):
	"""`path` with ~ for the home folder."""
	path = Path(path)
	home = Path.home()
	if path == home:
		return "~"
	if home in path.parents:
		return "~/" + path.relative_to(home).as_posix()
	return path.as_posix()

def status(word):
	return Text(f"{word:8}", style=STYLES.get(word, "red"))

def leader(name, width=30):
	"""`name` then dots up to `width`."""
	text = Text("  " + name + " ")
	text.append("." * max(2, width - len(name)), style="dim")
	return text

def score(passed, total):
	return Text(f" {passed}/{total}", style="green" if passed == total else "red")

def details(text, indent=12, lines=4):
	return [Text(" " * indent + line, style="dim") for line in text.splitlines()[:lines]]

def suites(results):
	"""[(suite, [results])] in the order of the results, the undefined cases apart."""
	grouped = []
	for result in results:
		if result.suite == "info":
			continue
		if not grouped or grouped[-1][0] != result.suite:
			grouped.append((result.suite, []))
		grouped[-1][1].append(result)
	return grouped

def check_lines(checks):
	lines, group = [], None
	for check in checks:
		if check.group != group:
			group = check.group
			lines.append(Text("  " + group, style="bold"))
		line = Text("    ")
		line.append_text(status(check.status))
		line.append(check.label)
		lines.append(line)
		if check.status != "OK" and check.detail:
			lines += details(check.detail, indent=14, lines=6)
	return lines

def result_line(result):
	line = Text("    ")
	line.append_text(status(result.status))
	line.append(result.name.split("/", 1)[-1])
	return [line] + details(result.detail, lines=3)

def suite_lines(suite, results):
	"""A suite: its score, then its failures and its warnings; one line when they all fail the same way.

	Counted like 42pal counts: an undefined case (INFO) is not, a warning passes.
	"""
	counted = [result for result in results if result.status != "INFO"]
	bad = [result for result in counted if result.bad]
	line = leader(suite_name(suite))
	if not counted:
		line.append(" " + t("not measured"), style="dim")
		lines = [line]
	else:
		line.append_text(score(len(counted) - len(bad), len(counted)))
		lines = [line]
	if len(bad) > 2 and len(bad) == len(counted) and len({result.detail for result in bad}) == 1:
		same = Text("    ")
		same.append_text(status(bad[0].status))
		same.append(t("all {count}", count=len(bad)))
		return lines + [same] + details(bad[0].detail, lines=2)
	# The failures, then the warnings (not counted, but to look at).
	shown = bad + [result for result in results if result.status == "WARN"]
	for result in shown[:10]:
		lines += result_line(result)
	if len(shown) > 10:
		lines.append(Text("    " + t("… and {count} more", count=len(shown) - 10), style="dim"))
	return lines

def report_lines(report, name="linerator"):
	"""The whole report: the project, the tests by suite, the undefined cases, the verdict."""
	head = Text(name, style=ACCENT)
	if report.project is not None:
		head.append(f" · {short_path(report.project)}", style="dim")
	lines = [head]
	if report.checks:
		passed, counted = report.conformity_score
		section = Text("\n" + t("The subject"), style="bold")
		section.append_text(score(passed, counted))
		lines.append(section)
		lines += check_lines(report.checks)
	if report.error is not None:
		title, detail = report.error
		lines.append(Text("\n✗ " + title, style="bold red"))
		if detail:
			lines.append(Panel(Text(detail), border_style="red"))
	grouped = suites(report.results)
	if grouped:
		passed, total = report.test_score
		section = Text("\n" + t("The tests"), style="bold")
		section.append_text(score(passed, total))
		lines.append(section)
		for suite, results in grouped:
			lines += suite_lines(suite, results)
	info = [result for result in report.results if result.suite == "info"]
	if info:
		lines.append(Text("\n" + t("Undefined cases, not counted"), style="bold"))
		for result in info:
			line = leader(result.name.split("/", 1)[-1])
			line.append(" " + result.detail, style="cyan")
			lines.append(line)
	lines += [Text("! " + note, style="yellow") for note in notes(report)]
	lines.append(Text())
	lines.append(verdict(report))
	lines.append(Text("\n" + t(DISCLAIMER), style="dim italic"))
	return lines

def verdict(report):
	"""✓ OK or ✗ KO, with the scores."""
	text = Text("✓ OK" if report.passed else "✗ KO", style="bold green" if report.passed else "bold red")
	scores = []
	if report.checks:
		scores.append(t("subject {passed}/{total}", passed=report.conformity_score[0], total=report.conformity_score[1]))
	if report.results:
		scores.append(t("tests {passed}/{total}", passed=report.test_score[0], total=report.test_score[1]))
	if scores:
		text.append("  " + " · ".join(scores))
	return text

# The colors of the cells of the panel.
GOOD, BAD, WAITING = "#4ade80", "#f87171", "#2a2f3a"

def suites_panel(rows, done, width=44, label_width=22):
	"""The panel of the suites: a group of rows, each its label, a cell a test (green, red, or waiting), its score.

	rows: names.suite_rows (or the "suites" of the JSON); done: {suite: [True when it passed, ...]}.
	With more tests than room, a cell stands for several: red when one failed. 42pal draws the same.
	"""
	text, group = Text(), None
	for row in rows:
		if row["group"] != group:
			group = row["group"]
			if text:
				text.append("\n\n")
			text.append(group, style="bold")
			label_room = min(label_width, max(len(other["label"]) for other in rows if other["group"] == group))
		results = done.get(row["key"], [])
		label = row["label"] if len(row["label"]) <= label_room else row["label"][:label_room - 1] + "…"
		text.append("\n " + label.ljust(label_room) + " ", style="#d1d5db")
		tests = max(row["tests"], len(results), 1)
		room = max(4, width - label_room - 10)
		cells = min(tests, room)
		for cell in range(cells):
			part = results[cell * tests // cells:(cell + 1) * tests // cells]
			covered = (cell + 1) * tests // cells - cell * tests // cells
			if False in part:
				style = BAD
			elif part and len(part) == covered:
				style = GOOD
			else:
				style = WAITING
			text.append("■", style=style)
		if results:
			bad = results.count(False)
			finished = len(results) >= row["tests"]
			text.append(f" {len(results) - bad}/{len(results)}", style=BAD if bad else GOOD if finished else "#9ca3af")
	return text

class Progress:
	"""What the run has done so far, from its events: for a spinner or a header."""

	def __init__(self):
		self.step = ""
		self.phase = ""
		self.checks = 0
		self.total = 0
		self.done = 0
		self.bad = 0

	def update(self, kind, data):
		if kind == "step":
			self.step = data["step"]
		elif kind == "phase":
			self.phase = data["phase"]
		elif kind == "check":
			self.checks += 1
		elif kind == "plan":
			self.total = data["tests"]
		elif kind == "test":
			self.done += 1
			self.bad += data["status"] not in ("PASS", "INFO", "WARN")

	def text(self, name="linerator"):
		if self.step == "subject":
			return t("{name} · the subject: {count} checks", name=name, count=self.checks)
		if self.step == "tests":
			filled = round(24 * self.done / self.total) if self.total else 0
			bar = "━" * filled + "─" * (24 - filled)
			return t("{name} · {phase} · tests {done}/{total} {bar} {bad} KO", name=name,
				phase=t(PHASES.get(self.phase, self.phase)), done=self.done, total=self.total, bar=bar, bad=self.bad)
		return t("{name} is starting…", name=name)

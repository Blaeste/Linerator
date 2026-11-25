"""The full screen of Linerator, with the look of Pushterator (textual, copied into vendor/).

The home screen: the logo, and the folder of the project, typed or chosen
in a live list (the projects found, the folders below what is typed). The
run screen: the project and the failures as they come, each BUFFER_SIZE
drawn test after test, then the whole report. Its look is in tui.tcss.
"""

import os
import time
from pathlib import Path

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.suggester import Suggester
from textual.widgets import Input, OptionList, RichLog, Static
from textual.widgets.option_list import Option

from liner.cli import display
from liner.cli.display import Progress, report_lines, short_path
from liner.engine import test_project
from liner.files import contents
from liner.find import iter_projects, last_project, looks_like_project, remember_project
from liner.i18n import N_, t
from liner.suite import BUFFER_SIZES, label

LETTERS = [
	"██╗  ██╗██████╗ ██████╗  █████╗ ██╗     ",
	"██║  ██║╚════██╗██╔══██╗██╔══██╗██║     ",
	"███████║ █████╔╝██████╔╝███████║██║     ",
	"╚════██║██╔═══╝ ██╔═══╝ ██╔══██║██║     ",
	"     ██║███████╗██║     ██║  ██║███████╗",
	"     ╚═╝╚══════╝╚═╝     ╚═╝  ╚═╝╚══════╝",
]
# The left half of the moustache; the right half is its mirror.
MOUSTACHE = [
	"           ",
	" ▄▀▀▄      ",
	"▐▌  ▀      ",
	" ▀▀▄▄▄▄▄▄▄▄",
	"   ▀▀█████▀",
	"           ",
]
MIRRORED = str.maketrans("▌▐", "▐▌")
LOGO = [f"{left} {letters.ljust(40)} {left[::-1].translate(MIRRORED)}" for left, letters in zip(MOUSTACHE, LETTERS)]
# The colors the logo goes through, cyan to violet; they move slowly.
GRADIENT = ["#5eead4", "#67e8f9", "#7dd3fc", "#93c5fd", "#a5b4fc", "#c4b5fd", "#d8b4fe"]
TAGLINE = N_("get_next_line tester")
# Under this many lines, the screens get the "-compact" class.
COMPACT_HEIGHT = 30

def hints(pairs):
	"""The line of keys at the bottom of a screen: [("⏎", "choose"), ...]."""
	text = Text()
	for key, what in pairs:
		if text:
			text.append("   ")
		text.append(key, style="bold #a5b4fc")
		text.append(f" {t(what)}")
	return text

class Logo(Static):
	"""The logo; its gradient moves slowly. One line on a small terminal."""

	def on_mount(self):
		self.shift = 0
		self.paint()
		self.set_interval(0.12, self.paint)

	def paint(self):
		self.shift += 1
		lines = ["4 2 p a l"] if self.screen.has_class("-compact") else LOGO
		text = Text()
		for row, line in enumerate(lines):
			for col, char in enumerate(line):
				text.append(char, style=GRADIENT[((col + row * 2 - self.shift) // 4) % len(GRADIENT)])
			if row < len(lines) - 1:
				text.append("\n")
		self.update(text)

def folder_matches(text):
	"""The folders whose path starts with `text`, each ending with /, as typed (~ stays ~)."""
	if not text:
		return []
	parent, start = os.path.split(text)
	listed = os.path.expanduser(parent or ".")
	try:
		names = sorted(os.listdir(listed))
	except OSError:
		return []
	return [text + name[len(start):] + "/" for name in names
		if name.startswith(start) and (start.startswith(".") or not name.startswith("."))
		and os.path.isdir(os.path.join(listed, name))]

class FolderSuggester(Suggester):
	"""Completes a folder as it is typed (→ takes it)."""

	def __init__(self):
		super().__init__(use_cache=False, case_sensitive=True)

	async def get_suggestion(self, value):
		matches = folder_matches(value)
		return matches[0] if matches else None

class HomeScreen(Screen):
	"""The logo and the folder of the project: typed, or chosen in the list below, which follows what is typed.

	With nothing typed, the list gives the projects found in the home folder,
	as they are found, the last one tested first. With a path, the folders in
	it (★ for a get_next_line project, .. to go up). ↑↓ move in the list;
	Enter opens the folder highlighted, or tests it when it is a project;
	Enter after typing tests the folder typed. Tab completes. Esc quits.
	"""

	BINDINGS = [
		("escape", "app.quit", "Quit"),
		("up", "move(-1)", "Up"),
		("down", "move(1)", "Down"),
		("tab", "open", "Open"),
	]
	SHOWN = 200

	def __init__(self, root=None, last=None):
		super().__init__()
		self.root = root
		self.last = Path(last) if last and Path(last).is_dir() else None
		self.entries = []
		self.found = [self.last] if self.last else []
		self.searching = True
		self.in_list = False

	def compose(self) -> ComposeResult:
		with Vertical(classes="root"):
			yield Logo(classes="logo")
			yield Static(t(TAGLINE), classes="tagline")
			with Vertical(classes="card"):
				yield Static(t("Folder of your get_next_line"), classes="field-label")
				yield Input(id="folder", suggester=FolderSuggester())
				yield Static("", id="folder-status")
				yield OptionList(id="folders")
			yield Static(hints([("↑↓", N_("choose")), ("⏎", N_("open or test")), ("tab", N_("complete")),
				("esc", N_("quit"))]), classes="hints")
			yield Static(t(display.DISCLAIMER), classes="disclaimer")

	def on_mount(self):
		self.query_one(".card").border_title = " linerator "
		self.query_one("#folder", Input).focus()
		self.refresh_list()
		self.search()

	def on_resize(self, event):
		self.set_class(event.size.height < COMPACT_HEIGHT, "-compact")

	@work(thread=True, exclusive=True, group="search")
	def search(self):
		"""Look for the projects; each one shows as soon as it is found."""
		for path in iter_projects(self.root):
			self.app.call_from_thread(self.add_found, path)
		self.app.call_from_thread(self.search_done)

	def add_found(self, path):
		if path not in self.found:
			self.found.append(path)
			if not self.query_one("#folder", Input).value.strip():
				self.refresh_list()

	def search_done(self):
		self.searching = False
		if not self.query_one("#folder", Input).value.strip():
			self.refresh_list()

	def entry_labels(self):
		"""(label, path) of each line of the list."""
		return [(label, path) for label, path, _ in self.entries]

	def refresh_list(self):
		typed = self.query_one("#folder", Input).value
		status = ""
		if not typed.strip():
			self.entries = [(short_path(path), path, True) for path in self.found]
			self.entries.append(("~/", Path.home(), False))
			if self.searching:
				status = t("Looking for your get_next_line… {count} found", count=len(self.found))
			elif not self.found:
				status = t("No get_next_line found: type its path, or browse from ~/.")
		else:
			path = Path(typed).expanduser()
			if typed.endswith("/") and path.is_dir():
				parent, start = path, ""
				self.entries = [("..", path.parent, False)] if path.parent != path else []
			else:
				parent, start = path.parent, path.name
				self.entries = []
			self.entries += [(("★ " if looks_like_project(child) else "") + child.name + "/", child,
				looks_like_project(child)) for child in self.subfolders(parent, start)]
			if path.is_dir() and looks_like_project(path):
				status = t("✓ a get_next_line project: Enter tests it")
		menu = self.query_one("#folders", OptionList)
		menu.clear_options()
		menu.add_options([Option(Text(label, style="bold #a5b4fc" if project else ""), id=str(index))
			for index, (label, _, project) in enumerate(self.entries)])
		menu.highlighted = None
		self.in_list = False
		self.query_one("#folder-status", Static).update(Text(status, style="#86efac" if status.startswith("✓")
			else "#9ca3af"))

	def subfolders(self, parent, start):
		try:
			names = sorted(os.listdir(parent))
		except OSError:
			return []
		return [parent / name for name in names if name.startswith(start)
			and (start.startswith(".") or not name.startswith(".")) and (parent / name).is_dir()][:self.SHOWN]

	def on_input_changed(self, event):
		self.refresh_list()

	def action_move(self, step):
		menu = self.query_one("#folders", OptionList)
		if not self.entries:
			return
		if menu.highlighted is None:
			menu.highlighted = 0 if step > 0 else len(self.entries) - 1
		else:
			menu.highlighted = max(0, min(len(self.entries) - 1, menu.highlighted + step))
		self.in_list = True

	def highlighted_entry(self):
		index = self.query_one("#folders", OptionList).highlighted
		return self.entries[index] if index is not None and index < len(self.entries) else None

	def action_open(self):
		entry = self.highlighted_entry() or (self.entries[0] if self.entries and self.entries[0][0] != ".." else None)
		if entry is not None:
			self.open(entry[1])

	def open(self, path):
		folder = self.query_one("#folder", Input)
		folder.value = short_path(path).rstrip("/") + "/" if str(path) != "/" else "/"
		folder.cursor_position = len(folder.value)

	def choose(self, entry):
		_, path, project = entry
		if project:
			self.app.start_run(path)
		else:
			self.open(path)

	def on_option_list_option_selected(self, event):
		self.choose(self.entries[int(event.option.id)])

	def on_input_submitted(self, event):
		entry = self.highlighted_entry()
		if self.in_list and entry is not None:
			self.choose(entry)
			return
		typed = event.value.strip()
		if not typed:
			return
		path = Path(typed).expanduser()
		path = (path if path.is_absolute() else Path.cwd() / path).resolve()
		if not path.is_dir():
			self.query_one("#folder-status", Static).update(Text(t("No folder here: {path}", path=short_path(path)),
				style="#f87171"))
			return
		self.app.start_run(path)

GOOD, BAD, WAITING = "#4ade80", "#f87171", "#2a2f3a"

class SizesPanel(Static):
	"""Each BUFFER_SIZE as its tests come: a cell a file, green when it passes, red when not; then the other steps."""

	def on_mount(self):
		self.border_title = " BUFFER_SIZE "
		self.reset()

	def reset(self):
		self.sizes = {label(size): [] for size in BUFFER_SIZES}
		self.others = {}
		self.paint()

	def add(self, name, status, paint=True):
		suite = name.split("/", 1)[0]
		good = status in ("PASS", "INFO", "WARN")
		if suite.startswith("buffer_") and suite[len("buffer_"):] in self.sizes:
			self.sizes[suite[len("buffer_"):]].append(good)
		elif suite != "info":
			self.others.setdefault(suite, []).append(good)
		if paint:
			self.paint()

	def paint(self):
		files = len(contents())
		text = Text()
		for size, cells in self.sizes.items():
			if text:
				text.append("\n")
			text.append(f"{t('default') if size == 'default' else size:>9} ", style="bold")
			for good in cells[:files]:
				text.append("■", style=GOOD if good else BAD)
			text.append("■" * max(0, files - len(cells)), style=WAITING)
			if cells:
				bad = cells.count(False)
				text.append(f" {len(cells) - bad}/{len(cells)}", style=BAD if bad else "#9ca3af")
		if self.others:
			text.append("\n\n" + t("The other tests"), style="bold")
			for suite, cells in self.others.items():
				bad = cells.count(False)
				name = display.suite_name(suite)
				text.append(f"\n  {name[:26]:26} ", style="#d1d5db")
				text.append(f"{len(cells) - bad}/{len(cells)}", style=BAD if bad else GOOD)
		self.update(text)

class RunScreen(Screen):
	"""A run: the project and the failures as they come, each BUFFER_SIZE drawn, then the report.

	run(folder, on_event) runs the tests and returns the Report, in a thread.
	r runs again, v opens the visualizer, Esc (or f) goes back to the folder.
	"""

	BINDINGS = [
		("r", "again", "Run again"),
		("v", "visualize", "Visualizer"),
		("f", "back", "Another folder"),
		("escape", "back", "Back"),
		("ctrl+shift+c", "screen.copy_text", "Copy"),
	]
	# The counter changes at most this often; a check or a failure shows at once.
	PROGRESS_EVERY = 0.1

	def __init__(self, folder, run):
		super().__init__()
		self.folder = Path(folder)
		self.run = run
		self.busy = False
		self.report = None
		self.progress = Progress()
		self.shown_at = 0.0
		self.live_group = None
		self.live_failures = False
		self.pending = []

	def compose(self) -> ComposeResult:
		yield Static(id="header")
		with Container(id="body"):
			yield RichLog(id="log", wrap=True, min_width=0, markup=False, highlight=False)
			yield SizesPanel(id="sizes")
		yield Static(id="activity")
		yield Static(hints([("r", N_("run again")), ("v", N_("visualize")), ("esc", N_("another folder")),
			("ctrl+q", N_("quit"))]), id="run-hints")

	def on_mount(self):
		self.query_one("#header", Static).border_title = " linerator "
		self.query_one("#log").border_title = " log "
		self.action_again()

	def refresh_header(self):
		text = Text("get_next_line", style="bold #e0e7ff")
		text.append("   " + short_path(self.folder), style="#9ca3af")
		if self.report is not None and not self.busy:
			text.append("   ")
			text.append_text(display.verdict(self.report))
		self.query_one("#header", Static).update(text)

	def action_again(self):
		if self.busy:
			return
		self.busy = True
		self.progress = Progress()
		self.live_group = None
		self.live_failures = False
		self.refresh_header()
		self.query_one("#log", RichLog).clear()
		self.query_one(SizesPanel).reset()
		activity = self.query_one("#activity", Static)
		activity.set_class(True, "-busy")
		activity.update("⠿ " + self.progress.text())
		self.run_in_background()

	@work(thread=True, exclusive=True)
	def run_in_background(self):
		report = self.run(self.folder, self.event_from_thread)
		self.app.call_from_thread(self.show_report, report)

	def event_from_thread(self, kind, data):
		"""From the thread of the run: what shows a line at once; the passing tests a few at a time."""
		now = time.monotonic()
		if kind == "test" and data["status"] in ("PASS", "INFO", "WARN"):
			self.pending.append((kind, data))
			if now - self.shown_at < self.PROGRESS_EVERY:
				return
		else:
			self.pending.append((kind, data))
		events, self.pending = self.pending, []
		self.shown_at = now
		self.app.call_from_thread(self.show_events, events)

	def show_events(self, events):
		for kind, data in events:
			self.show_event(kind, data)
		self.query_one("#activity", Static).update("⠿ " + self.progress.text())

	def show_event(self, kind, data):
		self.progress.update(kind, data)
		log = self.query_one("#log", RichLog)
		if kind == "check":
			if self.live_group is None:
				log.write(Text(t("The project"), style="bold"))
			if data["group"] != self.live_group:
				self.live_group = data["group"]
				log.write(Text("  " + data["group"], style="bold"))
			line = Text("    ")
			line.append_text(display.status(data["status"]))
			line.append(data["label"])
			log.write(line)
			if data["status"] != "OK" and data["detail"]:
				for detail in display.details(data["detail"], indent=14, lines=2):
					log.write(detail)
		elif kind == "test":
			self.query_one(SizesPanel).add(data["name"], data["status"])
			if data["status"] not in ("PASS", "INFO", "WARN"):
				if not self.live_failures:
					self.live_failures = True
					log.write(Text("\n" + t("Failed so far"), style="bold"))
				line = Text("    ")
				line.append_text(display.status(data["status"]))
				line.append(data["name"])
				log.write(line)
				for detail in display.details(data["detail"], lines=1):
					log.write(detail)

	def show_report(self, report):
		if self.pending:
			events, self.pending = self.pending, []
			self.show_events(events)
		self.report = report
		self.busy = False
		self.query_one("#activity", Static).set_class(False, "-busy")
		log = self.query_one("#log", RichLog)
		log.clear()
		for line in report_lines(report):
			log.write(line)
		# Once written: the report opens at its top (the verdict is in the header).
		self.call_after_refresh(log.scroll_home, animate=False)
		panel = self.query_one(SizesPanel)
		panel.reset()
		for result in report.results:
			panel.add(result.name, result.status, paint=False)
		panel.paint()
		self.refresh_header()

	def action_back(self):
		# Not while the tests run: their thread writes to this screen at the end.
		if not self.busy:
			self.app.pop_screen()

	def action_visualize(self):
		if not self.busy:
			self.app.visualize(self.report)

class LineratorApp(App):
	"""Linerator in full screen: the folder, then the run.

	options are those of engine.test_project. folder: run it at once.
	projects_root and settings: where projects are looked for and where the
	last one is kept (the tests give their own). run(folder, on_event)
	replaces the real run.
	"""

	CSS_PATH = "tui.tcss"
	ENABLE_COMMAND_PALETTE = False
	TITLE = "linerator"
	BINDINGS = [("ctrl+c", "quit", "Quit"), ("ctrl+q", "quit", "Quit")]

	def __init__(self, options, folder=None, projects_root=None, settings=None, run=None, buffer_size=8):
		super().__init__()
		self.options = dict(options)
		self.folder = folder
		self.projects_root = projects_root
		self.settings = settings
		self.runner = run or self.real_run
		self.buffer_size = buffer_size
		self.last_report = None
		# The copies where the tests were built: kept for the visualizer, removed at the end.
		self.workspaces = []

	def on_mount(self):
		self.push_screen(HomeScreen(self.projects_root, last_project(self.settings)))
		if self.folder is not None:
			self.start_run(Path(self.folder).expanduser().resolve())

	def real_run(self, folder, on_event):
		self.clean_workspaces()
		report = test_project(folder, on_event=on_event, keep=True, **self.options)
		if report.workspace is not None:
			self.workspaces.append(report.workspace)
		return report

	def clean_workspaces(self):
		while self.workspaces:
			self.workspaces.pop().cleanup()

	def on_unmount(self):
		self.clean_workspaces()

	def visualize(self, report):
		"""The visualizer of the reads, with the files of the copy tested."""
		from liner.cli.visualizer import VisualizerScreen
		workspace = getattr(report, "workspace", None)
		if workspace is None or report.error is not None:
			self.notify(t("The visualizer needs get_next_line to compile: run the tests first."), severity="warning")
			return
		self.push_screen(VisualizerScreen(workspace.path, workspace.root / "visualizer", self.buffer_size))

	def start_run(self, folder):
		remember_project(folder, self.settings)

		def run(folder, on_event):
			report = self.runner(folder, on_event)
			self.last_report = report
			return report

		self.push_screen(RunScreen(folder, run))

def run_app(args):
	"""Linerator full screen on the real terminal; return the exit code (that of the last run)."""
	from liner.cli.main import options
	app = LineratorApp(options(args), folder=args.folder, buffer_size=args.buffer_size)
	app.run()
	report = app.last_report
	if report is not None:
		from rich.console import Console
		Console().print(display.verdict(report))
		return 0 if report.passed else 1
	return 0

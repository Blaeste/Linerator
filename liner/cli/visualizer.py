"""The visualizer: get_next_line at work on a small file, read() after read().

The file is drawn a line a row, each byte a cell: grey once returned,
yellow while it waits in the static, dim while unread; the bytes the last
read() brought shine in cyan, the line just returned in green. On the side:
the step now (the read() and what it gave, or the line returned), what is
in the static, the counts, and the last steps. Space plays or pauses, ←
and → step, + and - change BUFFER_SIZE (get_next_line is built again), f
takes another file.
"""

from pathlib import Path

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Static

from liner.build import Builder
from liner.i18n import N_, language, t
from liner.judge import ENDS, parse, shown
from liner.run import run_program
from liner.trace import SAMPLES, SIZES, layout, shown_byte, steps, zone

ZONES = {
	"returned": "#4b5563",
	"kept": "bold #fbbf24 on #2a2410",
	"unread": "#6b7280 on #151821",
	"new": "bold #0f1117 on #67e8f9",
	"out": "bold #0f1117 on #4ade80",
}
# Steps a second when it plays.
SPEED = 3

def strip(data, step, width):
	"""The file drawn for `step`, `width` cells a row."""
	text = Text()
	for number, row in enumerate(layout(data, width)):
		if number:
			text.append("\n")
		for offset in row:
			text.append(shown_byte(data[offset]), style=ZONES[zone(offset, step)])
	return text

def legend():
	"""What the colors of the file mean, on two lines."""
	text = Text()
	for row in ((("new", N_("just read")), ("kept", N_("in the static")), ("out", N_("returned now"))),
			(("returned", N_("returned")), ("unread", N_("not read yet")))):
		if text:
			text.append("\n")
		for number, (name, label) in enumerate(row):
			text.append("   " if number else "")
			text.append("ab", style=ZONES[name])
			text.append(" " + t(label), style="#9ca3af")
	return text

def describe(step):
	"""A step in a few words, for the list of the last ones."""
	if step.kind == "read":
		if step.returned < 0:
			return f"read(fd, buf, {step.asked}) → -1"
		return f"read(fd, buf, {step.asked}) → {step.returned}" + (f"  {shown(step.data, 24)}" if step.data else "")
	if step.kind == "null":
		return t("returns NULL")
	return t("returns {line}", line=shown(step.data, 28))

class VisualizerScreen(Screen):
	"""get_next_line of the files in `project`, built in `folder`, on a sample file, step by step."""

	BINDINGS = [
		("space", "play", "Play or pause"),
		("right", "step(1)", "Forward"),
		("left", "step(-1)", "Back"),
		("home", "restart", "From the start"),
		("end", "finish", "To the end"),
		("plus", "size(1)", "Bigger BUFFER_SIZE"),
		("equals_sign", "size(1)", "Bigger BUFFER_SIZE"),
		("minus", "size(-1)", "Smaller BUFFER_SIZE"),
		("f", "file", "Another file"),
		("escape", "back", "Back"),
	]

	def __init__(self, project, folder, buffer_size=8, timeout=10, leave=False):
		super().__init__()
		# leave: Esc leaves the app (the visualizer alone, opened by 42pal).
		self.leave = leave
		self.folder = Path(folder)
		self.builder = Builder(project, self.folder / "build")
		self.timeout = timeout
		self.buffer_size = min(SIZES, key=lambda size: abs(size - buffer_size))
		self.sample = 0
		self.steps = []
		self.index = 0
		self.playing = False
		self.loading = False
		# Why the run went wrong (a crash, a leak...), or why it could not be built.
		self.problem = None
		self.error = None

	def compose(self) -> ComposeResult:
		yield Static(id="viz-header")
		with Horizontal(id="viz-body"):
			with Vertical(id="viz-left"):
				yield Static(id="viz-file")
				yield Static(id="viz-steps")
			yield Static(id="viz-now")
		yield Static(id="viz-hints")

	def on_mount(self):
		self.query_one("#viz-header").border_title = " linerator · visualizer "
		self.query_one("#viz-file").border_title = f" {t('the file')} "
		self.query_one("#viz-steps").border_title = f" {t('the last steps')} "
		self.query_one("#viz-now").border_title = f" {t('now')} "
		from liner.cli.tui import hints
		self.query_one("#viz-hints", Static).update(hints([("space", N_("play")), ("←→", N_("step")),
			("+-", "BUFFER_SIZE"), ("f", N_("another file")), ("esc", N_("back"))]))
		self.set_interval(1 / SPEED, self.tick)
		self.load()

	def load(self):
		self.loading = True
		self.playing = False
		self.paint()
		self.trace(self.buffer_size, self.sample)

	@work(thread=True, exclusive=True)
	def trace(self, size, sample):
		"""Build for `size` (once), run the trace on the sample, then show it."""
		program, error = self.builder.build(size)
		if program is None:
			self.app.call_from_thread(self.loaded, [], None, error or "")
			return
		path = self.folder / "samples" / f"sample_{sample}.txt"
		path.parent.mkdir(parents=True, exist_ok=True)
		path.write_bytes(SAMPLES[sample][1])
		lang = ["--lang", "fr"] if language() == "fr" else []
		run = run_program(program, [*lang, "trace", str(path)], timeout=self.timeout)
		out = parse(run.stdout)
		problem = None
		if run.failed:
			problem = t("could not start: {error}", error=run.failed)
		elif run.timed_out:
			problem = t("more than {seconds} s", seconds=self.timeout)
		elif run.signal:
			problem = t("crash: {signal}", signal=run.signal)
		elif out.end is not None and out.end[0] != "P":
			problem = f"{ENDS.get(out.end[0], 'FAIL')} · {out.end[1]}"
		self.app.call_from_thread(self.loaded, steps(out), problem, None)

	def loaded(self, found, problem, error):
		self.steps, self.problem, self.error = found, problem, error
		self.index = 0
		self.loading = False
		self.playing = bool(found)
		self.paint()

	def tick(self):
		if self.playing and not self.loading:
			if self.index < len(self.steps):
				self.index += 1
				self.paint()
			else:
				self.playing = False
				self.paint()

	def action_play(self):
		if self.index >= len(self.steps):
			self.index = 0
		self.playing = not self.playing
		self.paint()

	def action_step(self, delta):
		self.playing = False
		self.index = max(0, min(len(self.steps), self.index + delta))
		self.paint()

	def action_restart(self):
		self.playing = False
		self.index = 0
		self.paint()

	def action_finish(self):
		self.playing = False
		self.index = len(self.steps)
		self.paint()

	def action_size(self, delta):
		index = max(0, min(len(SIZES) - 1, SIZES.index(self.buffer_size) + delta))
		if SIZES[index] != self.buffer_size:
			self.buffer_size = SIZES[index]
			self.load()

	def action_file(self):
		self.sample = (self.sample + 1) % len(SAMPLES)
		self.load()

	def action_back(self):
		if self.leave:
			self.app.exit()
		else:
			self.app.pop_screen()

	@property
	def step(self):
		return self.steps[self.index - 1] if self.index > 0 else None

	def paint(self):
		name, data = SAMPLES[self.sample]
		header = Text("get_next_line", style="bold #e0e7ff")
		header.append(f"   BUFFER_SIZE={self.buffer_size}", style="bold #a5b4fc")
		header.append(f"   {t(name)}", style="#9ca3af")
		if self.steps:
			header.append(f"   {t('step {index}/{count}', index=self.index, count=len(self.steps))}", style="#9ca3af")
			header.append("   ▶" if self.playing else "   ⏸", style="#fbbf24")
		self.query_one("#viz-header", Static).update(header)
		file_panel = self.query_one("#viz-file", Static)
		width = max(10, (file_panel.size.width or 60) - 4)
		drawing = strip(data, self.step, width)
		drawing.append("\n\n")
		drawing.append_text(legend())
		file_panel.update(drawing)
		self.query_one("#viz-steps", Static).update(self.last_steps())
		self.query_one("#viz-now", Static).update(self.now())

	def last_steps(self, count=8):
		text = Text()
		done = self.steps[:self.index]
		for step in done[-count:]:
			if text:
				text.append("\n")
			text.append(f"{step.call:>3}  ", style="#6b7280")
			text.append(describe(step), style={"read": "#67e8f9", "line": "#4ade80", "null": "#a5b4fc"}[step.kind])
		if not done:
			text.append(t("space plays, → goes one step forward"), style="#6b7280")
		return text

	def now(self):
		text = Text()
		if self.loading:
			text.append(t("Building get_next_line with BUFFER_SIZE={size}…", size=self.buffer_size), style="#fbbf24")
			return text
		if self.error is not None:
			text.append(t("does not compile with BUFFER_SIZE={size}", size=self.buffer_size) + "\n\n", style="bold #f87171")
			text.append(self.error, style="#9ca3af")
			return text
		step = self.step
		if step is None:
			text.append(t("Before the first call."), style="#9ca3af")
		else:
			text.append(t("Call {call} of get_next_line", call=step.call) + "\n", style="bold #e0e7ff")
			if step.kind == "read":
				text.append(f"read(fd, buf, {step.asked}) → {step.returned}\n", style="bold #67e8f9")
				if step.returned > 0:
					text.append("  " + shown(step.data, 30) + "\n", style="#67e8f9")
				elif step.returned == 0:
					text.append("  " + t("the end of the file") + "\n", style="#9ca3af")
				else:
					text.append("  " + t("an error") + "\n", style="#f87171")
			elif step.kind == "line":
				text.append(t("returns {line}", line=shown(step.data, 30)) + "\n", style="bold #4ade80")
				text.append("  " + t("{count} bytes", count=len(step.data)) + "\n", style="#9ca3af")
			else:
				text.append(t("returns NULL") + "\n", style="bold #a5b4fc")
			kept = SAMPLES[self.sample][1][step.returned_total:step.read_total]
			text.append("\n" + t("In the static: {count} bytes", count=step.kept) + "\n", style="bold #fbbf24")
			if kept:
				text.append("  " + shown(kept, 30) + "\n", style="#fbbf24")
		done = self.steps[:self.index]
		reads = [s for s in done if s.kind == "read"]
		lines = [s for s in done if s.kind == "line"]
		text.append("\n" + t("So far") + "\n", style="bold")
		text.append("  " + t("{count} calls to read()", count=len(reads)) + "\n", style="#9ca3af")
		text.append("  " + t("{count} bytes read", count=sum(max(s.returned, 0) for s in reads)) + "\n", style="#9ca3af")
		text.append("  " + t("{count} lines returned", count=len(lines)) + "\n", style="#9ca3af")
		if self.index == len(self.steps) and self.steps:
			total = len(SAMPLES[self.sample][1])
			text.append("\n" + t("The whole file: {size} bytes, {reads} calls to read()", size=total,
				reads=len(reads)) + "\n", style="#a5b4fc")
		if self.problem:
			text.append("\n" + self.problem, style="bold #f87171")
		return text

	def on_resize(self, event):
		self.paint()

class VisualizerApp(App):
	"""The visualizer alone, full screen: ./linerator <folder> --visualize. Esc leaves."""

	CSS_PATH = "tui.tcss"
	ENABLE_COMMAND_PALETTE = False
	TITLE = "linerator"
	BINDINGS = [("ctrl+c", "quit", "Quit"), ("ctrl+q", "quit", "Quit")]

	def __init__(self, project, folder, buffer_size=8):
		super().__init__()
		self.project = project
		self.folder = folder
		self.buffer_size = buffer_size

	def on_mount(self):
		self.push_screen(VisualizerScreen(self.project, self.folder, self.buffer_size, leave=True))

def run_visualizer(args):
	"""The visualizer on a copy of the folder; return the exit code."""
	from rich.console import Console

	from liner.project import Workspace
	folder = Path(args.folder).expanduser() if args.folder else Path.cwd()
	if not folder.is_dir():
		Console(stderr=True).print(t("Folder not found: {path}", path=folder), markup=False)
		return 2
	if not (folder / "get_next_line.c").is_file():
		Console(stderr=True).print(t("No get_next_line.c in {path}", path=folder), markup=False)
		return 1
	workspace = Workspace(folder.resolve())
	try:
		VisualizerApp(workspace.path, workspace.root / "visualizer", args.buffer_size).run()
		return 0
	finally:
		workspace.cleanup()

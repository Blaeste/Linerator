"""The project of the student: its files, its header, its build, what the subject forbids, the README, the norm.

The project itself is never touched: everything happens in a copy, made
without what a build leaves (.o, .a). Each check gives OK or KO; WARN (to
look at) and SKIP (could not be checked) are not counted.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from liner.i18n import t

OK, KO, WARN, SKIP = "OK", "KO", "WARN", "SKIP"
FLAGS = ("-Wall", "-Wextra", "-Werror")
MANDATORY = ("get_next_line.c", "get_next_line_utils.c", "get_next_line.h")
BONUS = ("get_next_line_bonus.c", "get_next_line_utils_bonus.c", "get_next_line_bonus.h")
PROTOTYPE = re.compile(r"\bchar\s*\*\s*get_next_line\s*\(\s*int(\s+\w+)?\s*\)\s*;")

@dataclass
class Check:
	key: str
	group: str
	label: str
	status: str
	detail: str = ""

@dataclass
class ProjectResult:
	"""The checks; bonus is True when the bonus files are there and build."""
	checks: list = field(default_factory=list)
	bonus: bool = False
	on_check: object = None

	def add(self, key, group, label, status, detail=""):
		check = Check(key, group, label, status, detail)
		self.checks.append(check)
		if self.on_check is not None:
			self.on_check(check)
		return check

	def status(self, key):
		return next((check.status for check in self.checks if check.key == key), None)

def _tail(text, lines=12):
	return "\n".join(text.strip().splitlines()[-lines:])

class Workspace:
	"""A copy of the project in a temporary folder; the tests build there too."""

	def __init__(self, source):
		self.source = Path(source).resolve()
		self.root = Path(tempfile.mkdtemp(prefix="linerator-"))
		self.path = self.root / (self.source.name or "project")

		def ignore(folder, names):
			return {name for name in names if name == ".git" or name.endswith((".o", ".a"))
				or name.startswith("linerator")}

		shutil.copytree(self.source, self.path, symlinks=True, ignore=ignore)

	def has(self, name):
		return (self.path / name).is_file()

	def cleanup(self):
		shutil.rmtree(self.root, ignore_errors=True)

def _without_comments(code):
	return re.sub(r"/\*.*?\*/|//[^\n]*", " ", code, flags=re.DOTALL)

def _compile(workspace, sources, out, buffer_size, cc="cc"):
	"""Compile `sources` of the copy into `out` like the subject: (objects, None) or (None, why)."""
	out.mkdir(parents=True, exist_ok=True)
	define = [] if buffer_size is None else [f"-D BUFFER_SIZE={buffer_size}"]
	objects = []
	env = dict(os.environ, LC_ALL="C", LANG="C")
	for source in sources:
		obj = out / (Path(source).stem + ".o")
		try:
			done = subprocess.run([shutil.which(cc) or cc, *FLAGS, *define, "-c", source, "-o", str(obj)],
				capture_output=True, text=True, errors="replace", timeout=120, cwd=workspace.path, env=env)
		except (OSError, subprocess.TimeoutExpired) as error:
			return None, str(error)
		if done.returncode != 0:
			return None, _tail(done.stdout + done.stderr)
		objects.append(obj)
	return objects, None

def check_project(workspace, norminette="norminette", on_check=None):
	"""The checks of the subject on the copy."""
	result = ProjectResult(on_check=on_check)
	files = t("Files")
	missing = [name for name in MANDATORY if not workspace.has(name)]
	detail = ""
	if missing:
		elsewhere = sorted(path.relative_to(workspace.path).as_posix() for name in missing
			for path in workspace.path.rglob(name))
		detail = t("missing: {files}", files=", ".join(missing))
		if elsewhere:
			detail += " · " + t("found in a folder: {files}", files=", ".join(elsewhere))
	result.add("files.mandatory", files, t("get_next_line.c, get_next_line_utils.c, get_next_line.h at the root"),
		KO if missing else OK, detail)
	_header(workspace, result, "get_next_line.h", "header.prototype", files)
	sources = [name for name in MANDATORY if name.endswith(".c") and workspace.has(name)]
	objects = _builds(workspace, result, sources, "build", t("Build"))
	code = t("Code")
	_libft(workspace, result, code)
	if objects:
		_globals(objects, result, code)
		_externals(objects, result, "code.externals", code)
	else:
		reason = t("does not compile")
		result.add("code.globals", code, t("No global variable"), SKIP, reason)
		result.add("code.externals", code, t("Only read, malloc and free from the libc"), SKIP, reason)
	_bonus(workspace, result)
	_readme(workspace, result)
	_norm(workspace, result, norminette)
	return result

def _header(workspace, result, name, key, group):
	label = t("The prototype of get_next_line in {header}", header=name)
	if not workspace.has(name):
		result.add(key, group, label, KO, t("no {header}", header=name))
		return
	code = _without_comments((workspace.path / name).read_text(encoding="utf-8", errors="replace"))
	found = PROTOTYPE.search(code) is not None
	result.add(key, group, label, OK if found else KO, "" if found else t("expected: {prototype}",
		prototype="char *get_next_line(int fd);"))

def _builds(workspace, result, sources, prefix, group, bonus=False):
	"""Built with and without -D BUFFER_SIZE; the objects of the first build, or None."""
	objects = None
	for buffer_size, key, label in ((42, "with_buffer_size", t("cc -Wall -Wextra -Werror -D BUFFER_SIZE=42")),
			(None, "without_buffer_size", t("cc -Wall -Wextra -Werror, without -D BUFFER_SIZE"))):
		if not sources:
			result.add(f"{prefix}.{key}", group, label, SKIP, t("no file to compile"))
			continue
		out = workspace.root / "objects" / f"{'bonus' if bonus else 'mandatory'}_{key}"
		built, error = _compile(workspace, sources, out, buffer_size)
		if built is None and buffer_size is None:
			error = t("the subject asks for a default value of BUFFER_SIZE") + "\n" + error
		result.add(f"{prefix}.{key}", group, label, OK if built else KO, error or "")
		if objects is None and buffer_size == 42:
			objects = built
	return objects

def _libft(workspace, result, group):
	label = t("No libft")
	found = [path.relative_to(workspace.path).as_posix() for path in workspace.path.rglob("*")
		if path.name.lower() in ("libft", "libft.h", "libft.a")]
	for path in workspace.path.glob("*.[ch]"):
		if re.search(r'#\s*include\s*[<"][^>"]*libft\.h[>"]', path.read_text(encoding="utf-8", errors="replace")):
			found.append(path.name)
	result.add("code.libft", group, label, KO if found else OK,
		t("the subject forbids the libft: {files}", files=", ".join(sorted(set(found)))) if found else "")

def _nm(*args):
	"""The lines of nm, or None when it cannot run."""
	try:
		done = subprocess.run(["nm", *args], capture_output=True, text=True, errors="replace", timeout=60)
	except (OSError, subprocess.TimeoutExpired):
		return None
	return done.stdout.splitlines() if done.returncode == 0 else None

def _symbol(name):
	"""A name of nm without its version (read@GLIBC_2.2.5) nor the _ macOS puts before it."""
	name = name.split("@")[0]
	return name[1:] if sys.platform == "darwin" and name.startswith("_") else name

def _symbols(objects):
	"""[(kind, name)] of the objects, or None."""
	lines = _nm(*map(str, objects))
	if lines is None:
		return None
	return [(parts[-2], _symbol(parts[-1])) for parts in (line.split() for line in lines)
		if len(parts) >= 2 and len(parts[-2]) == 1]

def _data(symbols):
	"""(the global variables, the static variables) in the symbols. A static in a function has a dot: files.0."""
	globals_, statics = set(), set()
	for kind, name in symbols:
		if kind in "DBCGSV":
			globals_.add(name)
		elif kind in "dbgsv" and not name.startswith((".", "__")):
			if "." in name:
				# gcc: files.0; clang: get_next_line.files.
				parts = name.split(".")
				statics.add(parts[0] if parts[-1].isdigit() else parts[-1])
			else:
				globals_.add(name)
	return globals_, statics

def _globals(objects, result, group):
	"""No global variable (a static at the top of a file is one too)."""
	label = t("No global variable")
	symbols = _symbols(objects)
	if symbols is None:
		result.add("code.globals", group, label, SKIP, t("nm cannot read the object files"))
		return
	globals_ = _data(symbols)[0]
	result.add("code.globals", group, label, KO if globals_ else OK, ", ".join(sorted(globals_)))

# What a program needs from the libc without asking for it, or what the compiler adds.
RUNTIME = {"__stack_chk_fail", "__stack_chk_guard", "_GLOBAL_OFFSET_TABLE_", "__gmon_start__", "dyld_stub_binder"}
ALLOWED = {"read", "malloc", "free"}
# A compiler may turn a loop into one of these: a warning, not an error.
BUILTINS = {"memset", "memcpy", "memmove", "memcmp", "strlen", "bzero"}

def _externals(objects, result, key, group):
	"""Only read, malloc and free: what the objects use without defining it."""
	label = t("Only read, malloc and free from the libc")
	symbols = _symbols(objects)
	if symbols is None:
		result.add(key, group, label, SKIP, t("nm cannot read the object files"))
		return
	defined = {name for kind, name in symbols if kind != "U"}
	used = {name for kind, name in symbols if kind == "U"} - defined - RUNTIME - ALLOWED
	forbidden, builtins = sorted(used - BUILTINS), sorted(used & BUILTINS)
	if forbidden:
		detail = t("not allowed: {names}", names=", ".join(forbidden))
		if "lseek" in forbidden:
			detail += " · " + t("lseek is forbidden by the subject")
		result.add(key, group, label, KO, detail)
	elif builtins:
		result.add(key, group, label, WARN, t("{names}: maybe put there by the compiler", names=", ".join(builtins)))
	else:
		result.add(key, group, label, OK)

def _bonus(workspace, result):
	group = t("Bonus")
	label = t("get_next_line_bonus.c, get_next_line_utils_bonus.c, get_next_line_bonus.h at the root")
	present = [name for name in BONUS if workspace.has(name)]
	if not present:
		result.add("files.bonus", group, label, SKIP, t("no bonus file"))
		return
	missing = [name for name in BONUS if name not in present]
	result.add("files.bonus", group, label, KO if missing else OK,
		t("missing: {files}", files=", ".join(missing)) if missing else "")
	_header(workspace, result, "get_next_line_bonus.h", "bonus.prototype", group)
	sources = [name for name in BONUS if name.endswith(".c") and name in present]
	objects = _builds(workspace, result, sources, "bonus.build", group, bonus=True)
	static_label = t("One static variable")
	if not objects:
		result.add("bonus.static", group, static_label, SKIP, t("does not compile"))
		return
	symbols = _symbols(objects)
	if symbols is None:
		result.add("bonus.static", group, static_label, SKIP, t("nm cannot read the object files"))
	else:
		globals_, statics = _data(symbols)
		count = len(globals_ | statics)
		result.add("bonus.static", group, static_label, OK if count <= 1 else KO,
			"" if count <= 1 else t("{count} variables kept between calls: {names}", count=count,
			names=", ".join(sorted(globals_ | statics))))
		_externals(objects, result, "bonus.externals", group)
	result.bonus = not missing and result.status("bonus.build.with_buffer_size") == OK

# The first line the README must have, with the logins.
FIRST_LINE = re.compile(r"^(\*|_)This project has been created as part of the 42 curriculum by (?P<logins>[^*_]+?)\.?\1\.?\s*$")
AI_WORDS = re.compile(r"\b(AI|IA|LLM|ChatGPT|GPT|Claude|Copilot|Gemini)\b|artificial intelligence|intelligence artificielle",
	re.IGNORECASE)

def _readme_sections(text):
	"""[(title, content)] for the titles with # and the underlined ones."""
	sections, title, body = [], None, []
	lines = text.splitlines()
	for number, line in enumerate(lines):
		underlined = number + 1 < len(lines) and re.match(r"^\s*(=+|-+)\s*$", lines[number + 1]) and line.strip()
		heading = re.match(r"^\s*#{1,6}\s+(.*)$", line)
		if heading or underlined:
			if title is not None:
				sections.append((title, "\n".join(body)))
			title, body = (heading.group(1) if heading else line).strip(), []
		elif not re.match(r"^\s*(=+|-+)\s*$", line):
			body.append(line)
	if title is not None:
		sections.append((title, "\n".join(body)))
	return sections

def _readme(workspace, result):
	"""The README the subject asks for: its first line, its sections, AI, the algorithm."""
	group = "README"
	path = next((workspace.path / name for name in ("README.md", "readme.md", "Readme.md")
		if (workspace.path / name).is_file()), None)
	if path is None:
		result.add("readme.exists", group, t("README.md at the root"), KO, t("no README.md"))
		return
	result.add("readme.exists", group, t("README.md at the root"), OK)
	text = path.read_text(encoding="utf-8", errors="replace")
	first = FIRST_LINE.match(text.splitlines()[0] if text.strip() else "")
	result.add("readme.first_line", group, t("First line in italics with the login"), OK if first else KO,
		"" if first else t("expected: {line}", line="*This project has been created as part of the 42 curriculum by <login>.*"))
	sections = _readme_sections(text)
	titles = [title for title, _ in sections]
	absent = [name for name, pattern in (("Description", r"description"), ("Instructions", r"instructions?"),
		("Resources", r"res+ources?")) if not any(re.search(pattern, title, re.IGNORECASE) for title in titles)]
	result.add("readme.sections", group, t("Sections Description, Instructions, Resources"), KO if absent else OK,
		t("missing: {sections}", sections=", ".join(absent)) if absent else "")
	resources = "\n".join(body for title, body in sections if re.search(r"res+ources?", title, re.IGNORECASE))
	result.add("readme.ai", group, t("Use of AI said in Resources"), OK if AI_WORDS.search(resources) else WARN,
		"" if AI_WORDS.search(resources) else t("the subject asks for which tasks and which parts AI was used"))
	algorithm = re.search(r"algorithm|algorithme", text, re.IGNORECASE)
	result.add("readme.algorithm", group, t("The algorithm explained"), OK if algorithm else WARN,
		"" if algorithm else t("the subject asks for a detailed explanation and justification of the algorithm"))

def _norm(workspace, result, norminette):
	group = t("Norm")
	label = t("Norminette on the .c and .h files")
	command = shutil.which(norminette) or (norminette if os.access(norminette, os.X_OK) else None)
	if command is None:
		result.add("norm", group, label, SKIP, t("norminette not found"))
		return
	files = sorted(str(path) for path in workspace.path.rglob("*") if path.suffix in (".c", ".h")
		and not any(part.startswith(".") for part in path.relative_to(workspace.path).parts))
	if not files:
		result.add("norm", group, label, SKIP, t("no file to check"))
		return
	try:
		done = subprocess.run([command, *files], capture_output=True, text=True, errors="replace", timeout=120,
			cwd=workspace.path)
	except (OSError, subprocess.TimeoutExpired) as error:
		result.add("norm", group, label, SKIP, t("cannot run it: {error}", error=error))
		return
	output = done.stdout.replace(str(workspace.path) + "/", "")
	errors = [line for line in output.splitlines() if "Error" in line]
	if done.returncode == 0 and not errors:
		result.add("norm", group, label, OK)
	else:
		result.add("norm", group, label, KO, _tail("\n".join(errors) or output, 15))

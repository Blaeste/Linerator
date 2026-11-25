"""The get_next_line projects of the student: found in the home folder, the last one tested kept.

A project is a folder with get_next_line.c. The last folder tested is kept
in the settings of 42pal (~/.42pal/settings.json, under testers.linerator),
where 42pal keeps it too.
"""

import json
import os
from pathlib import Path

SETTINGS = Path.home() / ".42pal" / "settings.json"
# Folders never looked into: besides the hidden ones, those of tools.
SKIPPED = {"node_modules", "__pycache__", "venv", "snap", "Library", "go", "miniconda3", "anaconda3"}

def looks_like_project(folder):
	"""True when `folder` has get_next_line.c."""
	return (Path(folder) / "get_next_line.c").is_file()

def iter_projects(root=None, depth=4, limit=5000):
	"""The projects under `root` (the home folder), the nearest first, each as soon as it is found."""
	level = [Path(root or Path.home())]
	read = 0
	for _ in range(depth + 1):
		below = []
		for folder in level:
			try:
				entries = sorted(os.scandir(folder), key=lambda entry: entry.name)
			except OSError:
				continue
			read += 1
			if any(entry.name == "get_next_line.c" for entry in entries):
				yield folder
			below += [Path(entry.path) for entry in entries if not entry.name.startswith(".")
				and entry.name not in SKIPPED and _is_folder(entry)]
			if read >= limit:
				return
		level = below

def _is_folder(entry):
	try:
		return entry.is_dir(follow_symlinks=False)
	except OSError:
		return False

def _load(path):
	try:
		data = json.loads(Path(path).read_text(encoding="utf-8"))
	except (OSError, ValueError):
		return {}
	return data if isinstance(data, dict) else {}

def last_project(path=None):
	value = ((_load(path or SETTINGS).get("testers") or {}).get("linerator") or {})
	return value.get("project") if isinstance(value, dict) else None

def remember_project(project, path=None):
	path = Path(path or SETTINGS)
	data = _load(path)
	testers = data.get("testers") if isinstance(data.get("testers"), dict) else {}
	testers["linerator"] = {**(testers.get("linerator") or {}), "project": str(project)}
	data["testers"] = testers
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

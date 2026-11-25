"""The languages of Linerator: each text in the language chosen.

In the code, a text to translate is t("English text {field}", field=value).
liner/locales/<code>.json maps each English text to its translation, with
"_name": the name of the language in itself, for the menu. English needs
no file: it is the key. A text a catalog lacks, or gets wrong, stays in
English: nothing breaks, and the tests say what is missing.
Adding a language is adding its file, like in 42pal. Like the
rest of the core, this module never prints.
"""

import json
from pathlib import Path

# The catalogs, next to this module.
LOCALES_DIR = Path(__file__).resolve().parent / "locales"
DEFAULT = "en"

# The language in use, and its catalog (English: empty, the texts are the keys).
_language = DEFAULT
_catalog = {}

def _read(path):
	"""The catalog in `path` as a dict, or None if it cannot be read."""
	try:
		data = json.loads(path.read_text(encoding="utf-8"))
	except (OSError, ValueError):
		return None
	return data if isinstance(data, dict) else None

def languages(folder=None):
	"""{code: name in itself}: English first, then each catalog found, by code."""
	folder = folder or LOCALES_DIR
	found = {DEFAULT: "English"}
	for path in sorted(folder.glob("*.json")):
		data = _read(path)
		if data is not None and path.stem != DEFAULT:
			found[path.stem] = str(data.get("_name") or path.stem)
	return found

def set_language(code, folder=None):
	"""Use the language `code` from now on (English if unknown); return the code used."""
	global _language, _catalog
	folder = folder or LOCALES_DIR
	data = _read(folder / f"{code}.json") if code != DEFAULT else None
	if data is None:
		code, data = DEFAULT, {}
	_language = code
	# The texts only: "_name" and the other keys starting with _ are about the file.
	_catalog = {key: value for key, value in data.items()
		if not key.startswith("_") and isinstance(value, str) and value}
	return code

def language():
	"""The code of the language in use, like "en" or "fr"."""
	return _language

def t(text, **fields):
	"""`text` in the language in use, with its {fields} filled; English if not translated.

	Without fields the text is returned as it is: its braces stay. A
	translation whose fields do not match gives the English text.
	"""
	translated = _catalog.get(text, text)
	if not fields:
		return translated
	try:
		return translated.format(**fields)
	except (KeyError, IndexError, ValueError):
		return text.format(**fields)

def N_(text):
	"""Mark `text` to be translated where it is shown, with t(); return it as it is.

	For texts set once, when a module is loaded (constants, tables): the
	language can change after that.
	"""
	return text

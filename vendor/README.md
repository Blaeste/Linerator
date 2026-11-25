# vendor/

Third-party libraries copied into the repository, so that Linerator runs on the
campus machines with nothing to install and no sudo.

| Library | Version | License | Why |
|---|---|---|---|
| [textual](https://github.com/Textualize/textual) | 8.2.8 | MIT (`LICENSES/textual.txt`) | the full-screen interface: screens, keyboard and mouse, the visualizer |
| [rich](https://github.com/Textualize/rich) | 15.0.0 | MIT (`LICENSES/rich.txt`) | terminal display: colors, tables, panels; textual draws with it |
| [platformdirs](https://github.com/tox-dev/platformdirs) | 4.12.4 | MIT (`LICENSES/platformdirs.txt`) | needed by textual |
| [typing_extensions](https://github.com/python/typing_extensions) | 4.16.0 | PSF (`LICENSES/typing_extensions.txt`) | needed by rich and textual on Python 3.10 |

platformdirs is not at its latest version on purpose: from 4.13, it needs
Python 3.11, and the campus machines have 3.10. Each copy is exactly the
content of the official wheel, without its `__pycache__`.

Not copied, on purpose: `pygments` (5 MB, only for code highlighting) and
`markdown-it-py` with its plugins (only for Markdown). `rich.syntax`,
`rich.markdown` and textual's `Markdown` widget do not work without them,
and Linerator does not use them.

Only `liner/cli/` uses these libraries: `liner/cli/__init__.py` puts this
folder first in Python's path. The core (`liner/` outside `cli/`) stays
standard library only. They are the same copies as in
[42pal](https://github.com/Blaeste/42pal).

## Updating

Download the wheels for the oldest Python the campus has, so that pip picks
versions that still run on it:

```sh
python3 -m pip download --no-deps --only-binary=:all: --python-version 3.10 \
	textual rich platformdirs typing_extensions -d /tmp/wheels
```

Extract each wheel (`python3 -m zipfile -e <wheel> <folder>`), replace
`vendor/textual/`, `vendor/rich/`, `vendor/platformdirs/` and
`vendor/typing_extensions.py`, copy the `LICENSE` of each `.dist-info` into
`LICENSES/`, update the table above, then run the tests with Python 3.10.

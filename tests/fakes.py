"""The fake get_next_line of the tests (tests/fakes/stdio_gnl.c), set in a project folder.

It reads with stdio, which the subject forbids: it can never be handed in.
make_project(folder, mode) writes get_next_line.c (the fake, broken as
`mode` says), get_next_line_utils.c and get_next_line.h, and the bonus files
with bonus=True.
"""

from pathlib import Path

FAKES = Path(__file__).resolve().parent / "fakes"
MODES = {"good": 0, "leaks": 1, "no_terminator": 2, "no_newline": 3, "crash_long": 4, "stack_buffer": 5,
	"reads_all": 6, "sees_read_errors": 7, "two_statics": 8}

def make_project(folder, mode="good", bonus=False, name="get_next_line"):
	project = Path(folder) / name
	project.mkdir(parents=True)
	source = f"#define FAKE_MODE {MODES[mode]}\n" + (FAKES / "stdio_gnl.c").read_text()
	(project / "get_next_line.c").write_text(source)
	(project / "get_next_line_utils.c").write_text('#include "get_next_line.h"\n')
	(project / "get_next_line.h").write_text((FAKES / "get_next_line.h").read_text())
	if bonus:
		(project / "get_next_line_bonus.c").write_text(source.replace('"get_next_line.h"', '"get_next_line_bonus.h"'))
		(project / "get_next_line_utils_bonus.c").write_text('#include "get_next_line_bonus.h"\n')
		(project / "get_next_line_bonus.h").write_text((FAKES / "get_next_line.h").read_text())
	return project

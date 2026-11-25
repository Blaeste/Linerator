"""The names of the suites of tests, in the language chosen, and the rows of the panels that draw them.

The panel of the full screen (and the one of 42pal, from the JSON) draws a
row a suite, a cell a test: the BUFFER_SIZE first, then the other steps.
"""

from liner.i18n import N_, t

# The name of each suite of tests (buffer_<n> and limits_<n> apart).
SUITES = {
	"stdin": N_("standard input"),
	"fds": N_("file descriptors"),
	"read_errors": N_("read() fails"),
	"malloc_failures": N_("malloc() fails"),
	"read_little": N_("read as little as possible"),
	"bonus": N_("several fds (bonus)"),
	"info": N_("undefined cases"),
}

def suite_name(suite):
	if suite == "buffer_default":
		return t("BUFFER_SIZE by default")
	if suite.startswith("buffer_"):
		return f"BUFFER_SIZE={suite[len('buffer_'):]}"
	if suite.startswith("limits_"):
		return t("lines around {size}", size=suite[len("limits_"):])
	return t(SUITES.get(suite, suite))

def suite_rows(plan):
	"""The rows of the panel from [(suite, tests)]: {key, name, group, label, tests}; the undefined cases apart."""
	rows = []
	for key, count in plan:
		if key == "info":
			continue
		if key.startswith("buffer_"):
			size = key[len("buffer_"):]
			group, label = "BUFFER_SIZE", t("default") if size == "default" else size
		else:
			group, label = t("The other tests"), suite_name(key)
		rows.append({"key": key, "name": suite_name(key), "group": group, "label": label, "tests": count})
	return rows

"""./linerator [folder] [options]: the command line."""

import argparse

from liner import __version__

def parse_args(argv):
	parser = argparse.ArgumentParser(prog="linerator", description="A tester of get_next_line.")
	parser.add_argument("--version", action="version", version=f"linerator {__version__}")
	return parser.parse_args(argv)

def main(argv=None):
	parse_args(argv)
	return 0

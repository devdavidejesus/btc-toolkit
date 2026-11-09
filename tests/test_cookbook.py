"""docs/cookbook.md must only use commands, flags and --json keys that exist (docs/json-schema.md)."""

import argparse
import re
import shlex
import unittest
from pathlib import Path

from btc_toolkit.cli import build_parser

ROOT = Path(__file__).resolve().parent.parent
COOKBOOK = ROOT / "docs" / "cookbook.md"
SCHEMA = ROOT / "docs" / "json-schema.md"
README = ROOT / "README.md"


def _recipes() -> list[tuple[str, str, str]]:
    """(heading, command, sample output) for every `## ` section of the cookbook."""
    text = COOKBOOK.read_text(encoding="utf-8")
    out = []
    for section in re.split(r"^## ", text, flags=re.M)[1:]:
        heading = section.splitlines()[0]
        blocks = re.findall(r"^```(\w+)\n(.*?)^```", section, re.M | re.S)
        out.append((heading, *[body.strip() for _, body in blocks], *[lang for lang, _ in blocks]))
    return out


def _schema_keys() -> dict[str, set[str]]:
    """Every JSON key shown under each command's `### ` heading in docs/json-schema.md."""
    text = SCHEMA.read_text(encoding="utf-8")
    keys: dict[str, set[str]] = {}
    for section in re.split(r"^### ", text, flags=re.M)[1:]:
        names = re.findall(r"`(\w+) ", section.splitlines()[0])
        found = set(re.findall(r'"(\w+)":', section))
        for name in names:
            keys.setdefault(name, set()).update(found)
    return keys


def _cli_flags() -> dict[str, set[str]]:
    parser = build_parser()
    sub = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    return {name: {o for a in cmd._actions for o in a.option_strings} for name, cmd in sub.choices.items()}


def _split(command: str) -> tuple[list[str], str]:
    """The btc-toolkit argv and the jq filter of one recipe."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    stages: list[list[str]] = [[]]
    for token in lexer:
        if token == "|":
            stages.append([])
        else:
            stages[-1].append(token)
    tool = next(s for s in stages if s[0] == "btc-toolkit")
    jq = next(s for s in stages if s[0] == "jq")
    return tool[1:], jq[-1]


class TestCookbook(unittest.TestCase):
    def test_cookbook_exists_and_is_linked(self) -> None:
        self.assertTrue(COOKBOOK.is_file(), "docs/cookbook.md is missing")
        self.assertIn("docs/cookbook.md", README.read_text(encoding="utf-8"))

    def test_recipes_are_well_formed(self) -> None:
        recipes = _recipes()
        self.assertGreaterEqual(len(recipes), 5)
        self.assertLessEqual(len(recipes), 8)
        for recipe in recipes:
            with self.subTest(recipe=recipe[0]):
                # one command block, then one sample output under it
                self.assertEqual(recipe[3:], ("bash", "text"))
                self.assertNotIn("\n", recipe[1])
                self.assertTrue(recipe[2])
                argv, _ = _split(recipe[1])
                self.assertIn("--json", argv)

    def test_recipes_use_real_commands_and_flags(self) -> None:
        flags = _cli_flags()
        for heading, command, *_ in _recipes():
            with self.subTest(recipe=heading):
                argv, _ = _split(command)
                self.assertIn(argv[0], flags)
                for arg in argv[1:]:
                    if arg.startswith("--"):
                        self.assertIn(arg, flags[argv[0]])

    def test_recipes_use_only_documented_keys(self) -> None:
        schema = _schema_keys()
        for heading, command, *_ in _recipes():
            with self.subTest(recipe=heading):
                argv, jq = _split(command)
                # "error" is the documented error object every command can print
                documented = schema[argv[0]] | {"error"}
                used = set(re.findall(r"\.([A-Za-z_]\w*)", jq))
                self.assertTrue(used)
                self.assertLessEqual(used, documented, f"undocumented keys: {sorted(used - documented)}")


if __name__ == "__main__":
    unittest.main()

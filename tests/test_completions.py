"""The static shell completions must offer exactly the commands and flags the CLI accepts."""

import argparse
import re
import unittest
from pathlib import Path

from btc_toolkit.cli import build_parser

COMPLETIONS = Path(__file__).resolve().parent.parent / "completions"


def _cli_flags() -> dict[str, set[str]]:
    parser = build_parser()
    sub = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    return {
        name: {opt for action in cmd._actions for opt in action.option_strings if opt.startswith("--")}
        for name, cmd in sub.choices.items()
    }


def _bash_flags(commands: list[str]) -> dict[str, set[str]]:
    text = (COMPLETIONS / "btc-toolkit.bash").read_text(encoding="utf-8")
    base = set(re.search(r'^\s*flags="([^"$]+)"', text, re.M).group(1).split())
    extra = {m.group(1): set(m.group(2).split())
             for m in re.finditer(r'^\s*([\w*]+)\)\s+flags="\$\{flags\} ([^"]+)"', text, re.M)}
    plain = set(re.findall(r'^\s*(\w+)\)\s+;;', text, re.M))
    out = {}
    for name in commands:
        if name in plain:
            out[name] = base
        else:
            out[name] = base | extra.get(name, extra["*"])
    return out


def _zsh_flags(commands: list[str]) -> dict[str, set[str]]:
    text = (COMPLETIONS / "btc-toolkit.zsh").read_text(encoding="utf-8")
    common_block = re.search(r"common=\((.*?)\n\s*\)", text, re.S).group(1)
    common = set(re.findall(r"(--[a-z-]+)", common_block))
    branches = {m.group(1): m.group(2) for m in re.finditer(r"^\s{8}([\w*]+)\)\n(.*?);;", text, re.M | re.S)}
    out = {}
    for name in commands:
        body = branches.get(name, branches["*"])
        out[name] = (common if "$common" in body else set()) | set(re.findall(r"'(--[a-z-]+)\[", body))
    return out


def _fish_flags(commands: list[str]) -> dict[str, set[str]]:
    text = (COMPLETIONS / "btc-toolkit.fish").read_text(encoding="utf-8")
    variables: dict[str, set[str]] = {}
    for m in re.finditer(r"^\s*set\s+-l\s+(\w+)\s+(.+)$", text, re.M):
        variables[m.group(1)] = set(m.group(2).split())
    out: dict[str, set[str]] = {name: set() for name in commands}
    for m in re.finditer(
        r"complete\s+-c\s+btc-toolkit\s+-n\s+['\"]__fish_seen_subcommand_from\s+([^'\"]+)['\"]\s+.*?-l\s+([a-z-]+)",
        text,
    ):
        target_str, flag = m.group(1), f"--{m.group(2)}"
        targets: set[str] = set()
        for token in target_str.split():
            if token.startswith("$"):
                targets |= variables.get(token[1:], set())
            else:
                targets.add(token)
        for name in targets:
            if name in out:
                out[name].add(flag)
    return out


class TestCompletions(unittest.TestCase):
    def setUp(self) -> None:
        self.cli = _cli_flags()

    def test_bash_commands(self) -> None:
        text = (COMPLETIONS / "btc-toolkit.bash").read_text(encoding="utf-8")
        listed = re.search(r'commands="([^"]+)"', text).group(1).split()
        self.assertEqual(sorted(listed), sorted(self.cli))

    def test_zsh_commands(self) -> None:
        text = (COMPLETIONS / "btc-toolkit.zsh").read_text(encoding="utf-8")
        listed = re.findall(r"^\s+'(\w+):", text, re.M)
        self.assertEqual(sorted(listed), sorted(self.cli))

    def test_fish_commands(self) -> None:
        text = (COMPLETIONS / "btc-toolkit.fish").read_text(encoding="utf-8")
        listed = re.findall(r"complete -c btc-toolkit -n ['\"]__fish_use_subcommand['\"] -a (\w+)", text)
        self.assertEqual(sorted(listed), sorted(self.cli))

    def test_bash_flags_per_command(self) -> None:
        self.assertEqual(_bash_flags(list(self.cli)), self.cli)

    def test_zsh_flags_per_command(self) -> None:
        self.assertEqual(_zsh_flags(list(self.cli)), self.cli)

    def test_fish_flags_per_command(self) -> None:
        self.assertEqual(_fish_flags(list(self.cli)), self.cli)


if __name__ == "__main__":
    unittest.main()

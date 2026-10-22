"""The static shell completions must offer exactly the commands and flags the CLI accepts."""

import argparse
import os
import re
import shutil
import subprocess
import tempfile
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


# Typed so far -> what Tab must produce. Options after the subcommand and after an operand are the cases a static
# check cannot see: in 1.8.1 zsh completed command names but no option at all.
CASES = [
    ("btc-toolkit ver", "verify"),
    ("btc-toolkit tx --in", "--inputs"),
    ("btc-toolkit tx abc --out", "--outputs"),
    ("btc-toolkit block 0 -n s", "signet"),
    ("btc-toolkit decode --tx", "--txid"),
]

_ZSH = r"""
zmodload zsh/zpty
zpty z 'TERM=dumb zsh -f -i'
zpty -w z "fpath=($1 \$fpath); autoload -Uz compinit; compinit -u -D; PS1='> '; unsetopt beep; btc-toolkit(){ :; }"
zpty -w -n z "$2"$'\t'
local out='' chunk
for i in {1..100}; do
  zpty -r -t z chunk && out+=$chunk
  [[ $out == *"$3"* ]] && break
  sleep 0.1
done
zpty -d z
print -r -- "$out"
"""

_BASH = r"""
source "$1"
fn=$(complete -p btc-toolkit | sed -E 's/.*-F ([^ ]+).*/\1/')
read -r -a COMP_WORDS <<< "$2"
case "$2" in *" ") COMP_WORDS+=("") ;; esac
COMP_CWORD=$(( ${#COMP_WORDS[@]} - 1 ))
COMP_LINE="$2"; COMP_POINT=${#COMP_LINE}; COMPREPLY=()
"$fn" btc-toolkit "${COMP_WORDS[$COMP_CWORD]}" "${COMP_WORDS[$((COMP_CWORD - 1))]}"
echo "${COMPREPLY[*]}"
"""


@unittest.skipIf(os.name == "nt", "POSIX shells only")
class TestCompletionsInRealShells(unittest.TestCase):
    """Press Tab in a real zsh, bash and fish: the completion scripts must complete commands, options and values."""

    def test_zsh(self) -> None:
        zsh = shutil.which("zsh")
        if zsh is None:
            self.skipTest("zsh not installed")
        fdir = self.enterContext(tempfile.TemporaryDirectory())
        shutil.copy(COMPLETIONS / "btc-toolkit.zsh", Path(fdir) / "_btc-toolkit")  # the name zsh looks for
        for typed, expected in CASES:
            with self.subTest(typed=typed):
                out = subprocess.run([zsh, "-f", "-c", _ZSH, "zsh", fdir, typed, expected],
                                     capture_output=True, text=True, timeout=60).stdout
                self.assertIn(expected, out)

    def test_bash(self) -> None:
        bash = shutil.which("bash")
        if bash is None:
            self.skipTest("bash not installed")
        script = str(COMPLETIONS / "btc-toolkit.bash")
        for typed, expected in CASES:
            with self.subTest(typed=typed):
                out = subprocess.run([bash, "-c", _BASH, "bash", script, typed],
                                     capture_output=True, text=True, timeout=60).stdout
                self.assertIn(expected, out.split())

    def test_fish(self) -> None:
        fish = shutil.which("fish")
        if fish is None:
            self.skipTest("fish not installed")
        script = str(COMPLETIONS / "btc-toolkit.fish")
        for typed, expected in CASES:
            with self.subTest(typed=typed):
                out = subprocess.run([fish, "--no-config", "-c", "source $argv[1]; complete -C $argv[2]",
                                      script, typed], capture_output=True, text=True, timeout=60).stdout
                self.assertIn(expected, [line.split("\t")[0] for line in out.splitlines()])


if __name__ == "__main__":
    unittest.main()

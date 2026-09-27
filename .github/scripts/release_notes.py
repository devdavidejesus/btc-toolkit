"""
Print the release notes (or, with --title, the release title) for a tag,
taken from CHANGELOG.md. Exits non-zero if the tag has no CHANGELOG entry,
so a release cannot be published without release notes.

    python .github/scripts/release_notes.py v1.6.1
    python .github/scripts/release_notes.py v1.6.1 --title
"""

import re
import sys

REPO = "https://github.com/devdavidejesus/btc-toolkit"


def section(tag: str) -> tuple[str, str]:
    version = tag.removeprefix("v")
    with open("CHANGELOG.md", encoding="utf-8") as fh:
        text = fh.read()
    match = re.search(rf"^## \[{re.escape(version)}\](.*)$", text, re.M)
    if not match:
        sys.exit(f"CHANGELOG.md has no entry for {version}")
    parts = [p.strip() for p in match.group(1).split("—") if p.strip()]
    # heading is "## [X.Y.Z] — date" or "## [X.Y.Z] — date — Name"
    title = f"{tag} — {parts[1]}" if len(parts) > 1 else tag
    start = match.end()
    nxt = re.search(r"^## \[", text[start:], re.M)
    body = text[start:start + nxt.start()] if nxt else text[start:]
    return title, body.strip()


def main() -> None:
    tag = sys.argv[1]
    title, body = section(tag)
    if "--title" in sys.argv:
        print(title)
        return
    version = tag.removeprefix("v")
    print(body)
    print(f"""
## Verify this release

Every file below has a Sigstore signature (`.sigstore.json`) made by this repository's release workflow:

```bash
pip install sigstore
python -m sigstore verify github btc_toolkit-{version}-py3-none-any.whl \\
  --cert-identity {REPO}/.github/workflows/release.yml@refs/tags/{tag}
```

The same files on PyPI carry PEP 740 attestations:

```bash
pip install pypi-attestations
pypi-attestations verify pypi --repository {REPO} pypi:btc_toolkit-{version}-py3-none-any.whl
```""")


if __name__ == "__main__":
    main()

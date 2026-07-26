"""Allow running as: python -m btc_toolkit <command> ..."""

import sys
from .cli import run

sys.exit(run())

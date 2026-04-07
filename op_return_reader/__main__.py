"""Allow running as: python -m op_return_reader <txid>"""

import sys
from .cli import run

sys.exit(run())

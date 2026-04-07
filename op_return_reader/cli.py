#!/usr/bin/env python3
"""
btc-toolkit: OP_RETURN Reader

CLI tool to decode OP_RETURN messages from Bitcoin transactions.
Uses the Mempool.space API — no Bitcoin Core required.

Usage:
    python -m op_return_reader <txid>
    python -m op_return_reader <txid> --network testnet
    python -m op_return_reader <txid> --json
"""

import argparse
import json
import sys

from . import __version__
from .decoder import (
    MempoolAPIError,
    TransactionNotFoundError,
    decode_op_return,
    SUPPORTED_NETWORKS,
)


# ANSI colors (disabled if not a TTY)
_USE_COLOR = sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    if not _USE_COLOR:
        return text
    return f"\033[{code}m{text}\033[0m"


def _green(t: str) -> str:
    return _c("32", t)


def _yellow(t: str) -> str:
    return _c("33", t)


def _red(t: str) -> str:
    return _c("31", t)


def _cyan(t: str) -> str:
    return _c("36", t)


def _dim(t: str) -> str:
    return _c("2", t)


def _bold(t: str) -> str:
    return _c("1", t)


BANNER = r"""
  ___  ___   ___ ___ _____ _   _ ___ _  _
 / _ \| _ \ | _ \ __|_   _| | | | _ \ \| |
| (_) |  _/ |   / _|  | | | |_| |   / .` |
 \___/|_|   |_|_\___| |_|  \___/|_|_\_|\_|
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="op_return_reader",
        description="Decode OP_RETURN messages from Bitcoin transactions.",
        epilog="Part of btc-toolkit · github.com/devdavidejesus/btc-toolkit",
    )
    parser.add_argument(
        "txid",
        help="Bitcoin transaction ID (64-char hex string).",
    )
    parser.add_argument(
        "-n",
        "--network",
        choices=SUPPORTED_NETWORKS,
        default="mainnet",
        help="Bitcoin network (default: mainnet).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output results as JSON.",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Show raw hex bytes only (one per line).",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def run(argv: list[str] | None = None) -> int:
    """Main entry point. Returns exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    # JSON mode: minimal output
    if args.json_output:
        return _run_json(args)

    # Banner
    print(_cyan(BANNER))
    print(_dim(f"  btc-toolkit v{__version__} · Mempool.space API\n"))

    txid_short = f"{args.txid[:8]}...{args.txid[-8:]}"
    print(f"  {_bold('TXID:')}  {txid_short}")
    print(f"  {_bold('Network:')} {args.network}")
    print(f"  {'─' * 48}\n")

    try:
        results = decode_op_return(args.txid, args.network)
    except TransactionNotFoundError:
        print(f"  {_red('✗')} Transaction not found.\n")
        print(f"  Verify: https://mempool.space/tx/{args.txid}")
        return 1
    except MempoolAPIError as e:
        print(f"  {_red('✗')} API error: {e}\n")
        return 1
    except ValueError as e:
        print(f"  {_red('✗')} {e}\n")
        return 1

    if not results:
        print(f"  {_yellow('⚠')}  No OP_RETURN outputs found in this transaction.\n")
        return 0

    print(f"  {_green('✓')} Found {len(results)} OP_RETURN output(s):\n")

    for r in results:
        if args.raw:
            print(r.raw_hex)
            continue

        print(f"  {_bold(f'Output #{r.vout_index}')}")
        print(f"  ├─ Size:     {r.size} bytes")
        print(f"  ├─ Hex:      {_dim(r.raw_hex[:64])}{'…' if len(r.raw_hex) > 64 else ''}")

        if r.decoded_text:
            print(f"  └─ Message:  {_green(r.decoded_text)}")
        else:
            print(f"  └─ Message:  {_dim('(binary data — not UTF-8 text)')}")
        print()

    print(f"  {_dim(f'https://mempool.space/tx/{args.txid}')}\n")
    return 0


def _run_json(args: argparse.Namespace) -> int:
    """JSON output mode."""
    try:
        results = decode_op_return(args.txid, args.network)
    except TransactionNotFoundError:
        _json_error("Transaction not found", args.txid)
        return 1
    except MempoolAPIError as e:
        _json_error(str(e), args.txid)
        return 1
    except ValueError as e:
        _json_error(str(e), args.txid)
        return 1

    output = {
        "txid": args.txid,
        "network": args.network,
        "op_return_count": len(results),
        "outputs": [r.to_dict() for r in results],
    }
    print(json.dumps(output, indent=2))
    return 0


def _json_error(message: str, txid: str) -> None:
    print(json.dumps({"error": message, "txid": txid}, indent=2))


if __name__ == "__main__":
    sys.exit(run())

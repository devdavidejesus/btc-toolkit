#!/usr/bin/env python3
"""
btc-toolkit — Bitcoin CLI tools.

A unified command-line toolkit for querying the Bitcoin network via the
Mempool.space API. No Bitcoin Core required, zero external dependencies.

Usage:
    btc-toolkit opreturn <txid> [--network testnet] [--json] [--raw]
    btc-toolkit balance <address> [--network testnet] [--json]

Run `btc-toolkit <command> --help` for command-specific options.
"""

import argparse
import json
import sys

from . import __version__
from . import colors as c
from .api import MempoolAPIError, SUPPORTED_NETWORKS
from .opreturn import decode_op_return, TransactionNotFoundError
from .balance import get_balance, AddressNotFoundError
from .fees import get_fees
from .block import get_block, BlockNotFoundError
from .utxo import get_utxos


BANNER = r"""
  ___ _____ ___   _____ ___   ___  _    _  _____ _____
 | _ )_   _/ __| |_   _/ _ \ / _ \| |  | |/ /_ _|_   _|
 | _ \ | || (__    | || (_) | (_) | |__| ' < | |  | |
 |___/ |_| \___|   |_| \___/ \___/|____|_|\_\___| |_|
"""


# ──────────────────────────────────────────────────────────────────────
# opreturn subcommand
# ──────────────────────────────────────────────────────────────────────

def _cmd_opreturn(args: argparse.Namespace) -> int:
    if args.json_output:
        return _opreturn_json(args)

    print(c.cyan(BANNER))
    print(c.dim(f"  btc-toolkit v{__version__} · opreturn · Mempool.space API\n"))

    txid_short = f"{args.txid[:8]}...{args.txid[-8:]}"
    print(f"  {c.bold('TXID:')}    {txid_short}")
    print(f"  {c.bold('Network:')} {args.network}")
    print(f"  {'─' * 48}\n")

    try:
        results = decode_op_return(args.txid, args.network)
    except TransactionNotFoundError:
        print(f"  {c.red('✗')} Transaction not found.\n")
        print(f"  Verify: https://mempool.space/tx/{args.txid}")
        return 1
    except MempoolAPIError as e:
        print(f"  {c.red('✗')} API error: {e}\n")
        return 1
    except ValueError as e:
        print(f"  {c.red('✗')} {e}\n")
        return 1

    if not results:
        print(f"  {c.yellow('⚠')}  No OP_RETURN outputs found in this transaction.\n")
        return 0

    print(f"  {c.green('✓')} Found {len(results)} OP_RETURN output(s):\n")

    for r in results:
        if args.raw:
            print(r.raw_hex)
            continue

        print(f"  {c.bold(f'Output #{r.vout_index}')}")
        print(f"  ├─ Size:     {r.size} bytes")
        hex_preview = r.raw_hex[:64] + ("…" if len(r.raw_hex) > 64 else "")
        print(f"  ├─ Hex:      {c.dim(hex_preview)}")
        if r.decoded_text:
            print(f"  └─ Message:  {c.green(r.decoded_text)}")
        else:
            print(f"  └─ Message:  {c.dim('(binary data — not UTF-8 text)')}")
        print()

    print(f"  {c.dim(f'https://mempool.space/tx/{args.txid}')}\n")
    return 0


def _opreturn_json(args: argparse.Namespace) -> int:
    try:
        results = decode_op_return(args.txid, args.network)
    except (TransactionNotFoundError, MempoolAPIError, ValueError) as e:
        print(json.dumps({"error": str(e), "txid": args.txid}, indent=2))
        return 1

    output = {
        "txid": args.txid,
        "network": args.network,
        "op_return_count": len(results),
        "outputs": [r.to_dict() for r in results],
    }
    print(json.dumps(output, indent=2))
    return 0


# ──────────────────────────────────────────────────────────────────────
# balance subcommand
# ──────────────────────────────────────────────────────────────────────

def _cmd_balance(args: argparse.Namespace) -> int:
    if args.json_output:
        return _balance_json(args)

    print(c.cyan(BANNER))
    print(c.dim(f"  btc-toolkit v{__version__} · balance · Mempool.space API\n"))

    addr_short = args.address if len(args.address) <= 24 else (
        f"{args.address[:12]}...{args.address[-8:]}"
    )
    print(f"  {c.bold('Address:')} {addr_short}")
    print(f"  {c.bold('Network:')} {args.network}")
    print(f"  {'─' * 48}\n")

    try:
        bal = get_balance(args.address, args.network)
    except AddressNotFoundError:
        print(f"  {c.red('✗')} Address not found.\n")
        print(f"  Verify: https://mempool.space/address/{args.address}")
        return 1
    except MempoolAPIError as e:
        print(f"  {c.red('✗')} API error: {e}\n")
        return 1
    except ValueError as e:
        print(f"  {c.red('✗')} {e}\n")
        return 1

    confirmed_btc = bal.sats_to_btc(bal.confirmed_sats)
    total_btc = bal.sats_to_btc(bal.total_sats)

    print(f"  {c.bold('Confirmed:')}   {c.green(confirmed_btc + ' BTC')}")
    print(f"  {c.dim(f'              {bal.confirmed_sats:,} sats')}")

    if bal.unconfirmed_sats != 0:
        unconf_btc = bal.sats_to_btc(bal.unconfirmed_sats)
        color = c.yellow if bal.unconfirmed_sats > 0 else c.red
        print(f"  {c.bold('Unconfirmed:')} {color(unconf_btc + ' BTC')}")
        print(f"  {c.dim(f'              {bal.unconfirmed_sats:,} sats (mempool)')}")
        print(f"  {c.bold('Total:')}       {c.green(total_btc + ' BTC')}")

    print()
    print(f"  {c.dim(f'Confirmed txs: {bal.confirmed_tx_count}  ·  '
                      f'Mempool txs: {bal.mempool_tx_count}')}")
    print()
    print(f"  {c.dim(f'https://mempool.space/address/{args.address}')}\n")
    return 0


def _balance_json(args: argparse.Namespace) -> int:
    try:
        bal = get_balance(args.address, args.network)
    except (AddressNotFoundError, MempoolAPIError, ValueError) as e:
        print(json.dumps({"error": str(e), "address": args.address}, indent=2))
        return 1

    output = {"network": args.network, **bal.to_dict()}
    print(json.dumps(output, indent=2))
    return 0


# ──────────────────────────────────────────────────────────────────────
# fees subcommand
# ──────────────────────────────────────────────────────────────────────

def _cmd_fees(args: argparse.Namespace) -> int:
    if args.json_output:
        return _fees_json(args)

    print(c.cyan(BANNER))
    print(c.dim(f"  btc-toolkit v{__version__} · fees · Mempool.space API\n"))

    print(f"  {c.bold('Network:')} {args.network}")
    print(f"  {'─' * 48}\n")

    try:
        est = get_fees(args.network)
    except MempoolAPIError as e:
        print(f"  {c.red('✗')} API error: {e}\n")
        return 1

    print(f"  {c.bold('Recommended fee rates (sat/vB):')}\n")
    print(f"  ├─ Fastest (~10 min):   {c.green(str(est.fastest))}")
    print(f"  ├─ Half hour (~30 min): {c.green(str(est.half_hour))}")
    print(f"  ├─ Hour (~60 min):      {c.yellow(str(est.hour))}")
    print(f"  ├─ Economy:             {c.yellow(str(est.economy))}")
    print(f"  └─ Minimum:             {c.dim(str(est.minimum))}")
    print()
    print(f"  {c.bold('Mempool backlog:')}\n")
    print(f"  ├─ Pending txs:  {est.mempool_tx_count:,}")
    print(f"  ├─ Size:         {est.mempool_vsize_mb:.2f} vMB")
    print(f"  └─ ~Blocks to clear: {est.blocks_to_clear:.1f}")
    print()
    print(f"  {c.dim('https://mempool.space')}\n")
    return 0


def _fees_json(args: argparse.Namespace) -> int:
    try:
        est = get_fees(args.network)
    except MempoolAPIError as e:
        print(json.dumps({"error": str(e)}, indent=2))
        return 1

    output = {"network": args.network, **est.to_dict()}
    print(json.dumps(output, indent=2))
    return 0


# ──────────────────────────────────────────────────────────────────────
# block subcommand
# ──────────────────────────────────────────────────────────────────────

def _cmd_block(args: argparse.Namespace) -> int:
    if args.json_output:
        return _block_json(args)

    print(c.cyan(BANNER))
    print(c.dim(f"  btc-toolkit v{__version__} · block · Mempool.space API\n"))

    print(f"  {c.bold('Block:')}   {args.ref}")
    print(f"  {c.bold('Network:')} {args.network}")
    print(f"  {'─' * 48}\n")

    try:
        blk = get_block(args.ref, args.network)
    except BlockNotFoundError:
        print(f"  {c.red('✗')} Block not found: {args.ref}\n")
        return 1
    except MempoolAPIError as e:
        print(f"  {c.red('✗')} API error: {e}\n")
        return 1
    except ValueError as e:
        print(f"  {c.red('✗')} {e}\n")
        return 1

    hash_short = f"{blk.hash[:16]}...{blk.hash[-8:]}"
    prev_short = (
        f"{blk.previousblockhash[:16]}...{blk.previousblockhash[-8:]}"
        if blk.previousblockhash else c.dim("(none — genesis block)")
    )

    print(f"  {c.bold(f'Block #{blk.height:,}')}\n")
    print(f"  ├─ Hash:        {c.green(hash_short)}")
    print(f"  ├─ Mined:       {blk.timestamp_utc}")
    print(f"  ├─ Txs:         {blk.tx_count:,}")
    print(f"  ├─ Size:        {blk.size_mb:.2f} MB ({blk.size:,} bytes)")
    print(f"  ├─ Weight:      {blk.weight:,} WU")
    print(f"  ├─ Difficulty:  {blk.difficulty:,.0f}")
    print(f"  ├─ Nonce:       {blk.nonce}")
    print(f"  └─ Previous:    {prev_short}")
    print()
    print(f"  {c.dim(f'https://mempool.space/block/{blk.hash}')}\n")
    return 0


def _block_json(args: argparse.Namespace) -> int:
    try:
        blk = get_block(args.ref, args.network)
    except (BlockNotFoundError, MempoolAPIError, ValueError) as e:
        print(json.dumps({"error": str(e), "ref": args.ref}, indent=2))
        return 1

    output = {"network": args.network, **blk.to_dict()}
    print(json.dumps(output, indent=2))
    return 0


# ──────────────────────────────────────────────────────────────────────
# utxo subcommand
# ──────────────────────────────────────────────────────────────────────

def _cmd_utxo(args: argparse.Namespace) -> int:
    if args.json_output:
        return _utxo_json(args)

    print(c.cyan(BANNER))
    print(c.dim(f"  btc-toolkit v{__version__} · utxo · Mempool.space API\n"))

    addr_short = args.address if len(args.address) <= 24 else (
        f"{args.address[:12]}...{args.address[-8:]}"
    )
    print(f"  {c.bold('Address:')} {addr_short}")
    print(f"  {c.bold('Network:')} {args.network}")
    print(f"  {'─' * 48}\n")

    try:
        us = get_utxos(args.address, args.network, args.confirmed_only)
    except AddressNotFoundError:
        print(f"  {c.red('✗')} Address not found.\n")
        return 1
    except MempoolAPIError as e:
        print(f"  {c.red('✗')} API error: {e}\n")
        return 1
    except ValueError as e:
        print(f"  {c.red('✗')} {e}\n")
        return 1

    if not us.utxos:
        print(f"  {c.yellow('⚠')}  No UTXOs found for this address.\n")
        return 0

    label = "confirmed " if args.confirmed_only else ""
    print(f"  {c.green('✓')} {len(us.utxos)} {label}UTXO(s) · "
          f"{c.bold(us.sats_to_btc(us.total_sats) + ' BTC')} total\n")

    shown = us.utxos[: args.limit]
    for u in shown:
        txid_short = f"{u.txid[:12]}...{u.txid[-6:]}"
        status = c.green("✓ confirmed") if u.confirmed else c.yellow("⧗ mempool")
        height = f"#{u.block_height:,}" if u.block_height else "—"
        print(f"  ├─ {txid_short}:{u.vout}")
        print(f"  │  {us.sats_to_btc(u.value)} BTC ({u.value:,} sats) · "
              f"{status} · {c.dim(height)}")

    remaining = len(us.utxos) - len(shown)
    if remaining > 0:
        print(f"  └─ {c.dim(f'… and {remaining} more (use --limit to show more)')}")
    else:
        print(f"  └─ {c.dim('end')}")

    print()
    if us.unconfirmed_count and not args.confirmed_only:
        print(f"  {c.dim(f'Confirmed: {us.confirmed_count}  ·  '
                          f'Mempool: {us.unconfirmed_count}')}")
        print()
    print(f"  {c.dim(f'https://mempool.space/address/{args.address}')}\n")
    return 0


def _utxo_json(args: argparse.Namespace) -> int:
    try:
        us = get_utxos(args.address, args.network, args.confirmed_only)
    except (AddressNotFoundError, MempoolAPIError, ValueError) as e:
        print(json.dumps({"error": str(e), "address": args.address}, indent=2))
        return 1

    output = {"network": args.network, **us.to_dict()}
    print(json.dumps(output, indent=2))
    return 0


# ──────────────────────────────────────────────────────────────────────
# argument parser
# ──────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="btc-toolkit",
        description="Bitcoin CLI tools — query the network via Mempool.space. "
                    "No Bitcoin Core required.",
        epilog="github.com/devdavidejesus/btc-toolkit",
    )
    parser.add_argument(
        "-v", "--version", action="version", version=f"%(prog)s {__version__}"
    )

    subparsers = parser.add_subparsers(dest="command", metavar="<command>")
    subparsers.required = True

    # opreturn
    p_op = subparsers.add_parser(
        "opreturn", help="Decode OP_RETURN messages from a transaction."
    )
    p_op.add_argument("txid", help="Bitcoin transaction ID (64-char hex).")
    p_op.add_argument(
        "-n", "--network", choices=SUPPORTED_NETWORKS, default="mainnet",
        help="Bitcoin network (default: mainnet).",
    )
    p_op.add_argument(
        "--json", action="store_true", dest="json_output",
        help="Output as JSON.",
    )
    p_op.add_argument(
        "--raw", action="store_true", help="Show raw hex only (one per line).",
    )
    p_op.set_defaults(func=_cmd_opreturn)

    # balance
    p_bal = subparsers.add_parser(
        "balance", help="Check the confirmed and unconfirmed balance of an address."
    )
    p_bal.add_argument("address", help="Bitcoin address (any type).")
    p_bal.add_argument(
        "-n", "--network", choices=SUPPORTED_NETWORKS, default="mainnet",
        help="Bitcoin network (default: mainnet).",
    )
    p_bal.add_argument(
        "--json", action="store_true", dest="json_output",
        help="Output as JSON.",
    )
    p_bal.set_defaults(func=_cmd_balance)

    # fees
    p_fees = subparsers.add_parser(
        "fees", help="Show recommended fee rates and mempool backlog."
    )
    p_fees.add_argument(
        "-n", "--network", choices=SUPPORTED_NETWORKS, default="mainnet",
        help="Bitcoin network (default: mainnet).",
    )
    p_fees.add_argument(
        "--json", action="store_true", dest="json_output",
        help="Output as JSON.",
    )
    p_fees.set_defaults(func=_cmd_fees)

    # block
    p_blk = subparsers.add_parser(
        "block", help="Show block metadata by height, hash, or 'latest'."
    )
    p_blk.add_argument(
        "ref", help="Block height, 64-char block hash, or 'latest'.",
    )
    p_blk.add_argument(
        "-n", "--network", choices=SUPPORTED_NETWORKS, default="mainnet",
        help="Bitcoin network (default: mainnet).",
    )
    p_blk.add_argument(
        "--json", action="store_true", dest="json_output",
        help="Output as JSON.",
    )
    p_blk.set_defaults(func=_cmd_block)

    # utxo
    p_utxo = subparsers.add_parser(
        "utxo", help="List the unspent outputs (UTXOs) of an address."
    )
    p_utxo.add_argument("address", help="Bitcoin address (any type).")
    p_utxo.add_argument(
        "-n", "--network", choices=SUPPORTED_NETWORKS, default="mainnet",
        help="Bitcoin network (default: mainnet).",
    )
    p_utxo.add_argument(
        "--json", action="store_true", dest="json_output",
        help="Output as JSON.",
    )
    p_utxo.add_argument(
        "--confirmed-only", action="store_true",
        help="Exclude unconfirmed (mempool) UTXOs.",
    )
    p_utxo.add_argument(
        "--limit", type=int, default=15,
        help="Max UTXOs to display (default: 15; JSON always shows all).",
    )
    p_utxo.set_defaults(func=_cmd_utxo)

    return parser


def run(argv: list[str] | None = None) -> int:
    """Main entry point. Returns an exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(run())

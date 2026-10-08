#!/usr/bin/env python3
"""
btc-toolkit — Bitcoin CLI tools.

A unified command-line toolkit for querying the Bitcoin network via the
Mempool.space API. No Bitcoin Core required, zero external dependencies.

Usage:
    btc-toolkit <command> <item> [--network mainnet|testnet|signet] [--json]
                [--api-url URL] [--timeout SECONDS] [--file PATH]

Commands: opreturn, tx, address, balance, fees, block, utxo. Every inspecting
command also reads one item per line from stdin (-) or --file.
Run `btc-toolkit <command> --help` for command-specific options.
"""

import argparse
from collections.abc import Iterable
import json
import sys
import unicodedata

from . import __version__
from . import colors as c
import os

from .api import set_api_base, set_timeout, MempoolAPIError, SUPPORTED_NETWORKS
from .opreturn import decode_op_return, TransactionNotFoundError
from .balance import get_balance, AddressNotFoundError
from .fees import get_fees
from .block import get_block, BlockNotFoundError
from .utxo import get_utxos
from .tx import get_tx
from .address import get_address_overview


BANNER = r"""
  ___ _____ ___   _____ ___   ___  _    _  _____ _____
 | _ )_   _/ __| |_   _/ _ \ / _ \| |  | |/ /_ _|_   _|
 | _ \ | || (__    | || (_) | (_) | |__| ' < | |  | |
 |___/ |_| \___|   |_| \___/ \___/|____|_|\_\___| |_|
"""

_EXPLORER = {
    "mainnet": "https://mempool.space",
    "testnet": "https://mempool.space/testnet",
    "signet": "https://mempool.space/signet",
}

# Bidirectional-text controls can reorder what a terminal shows ("Trojan Source").
_BIDI_CONTROLS = {"\u061c", "\u200e", "\u200f", *map(chr, range(0x202A, 0x202F)), *map(chr, range(0x2066, 0x206A))}


def _explorer_url(network: str, kind: str, ident: str) -> str | None:
    """mempool.space link for the network; None for a custom API (its explorer is unknown)."""
    base = _EXPLORER.get(network)
    return f"{base}/{kind}/{ident}" if base else None


def _print_link(network: str, kind: str, ident: str, prefix: str = "") -> None:
    url = _explorer_url(network, kind, ident)
    if url:
        print(f"  {prefix}{c.dim(url) if not prefix else url}" + ("" if prefix else "\n"))


def _terminal_safe(text: str) -> str:
    """
    Escape control characters before printing on-chain text to a terminal.

    Anyone can write an OP_RETURN. Without this, a message could carry ANSI/OSC
    escape sequences (rewrite the screen, the window title, links) or bidi
    controls that reorder what is displayed. They are shown escaped (\\x1b).
    """
    return "".join(
        ch.encode("unicode_escape").decode("ascii")
        if unicodedata.category(ch) == "Cc" or ch in _BIDI_CONTROLS else ch
        for ch in text
    )


# ──────────────────────────────────────────────────────────────────────
# opreturn subcommand
# ──────────────────────────────────────────────────────────────────────

def _cmd_opreturn(args: argparse.Namespace) -> int:
    if args.json_output:
        return _opreturn_json(args)
    if args.raw:
        return _opreturn_raw(args)

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
        _print_link(args.network, "tx", args.txid, prefix="Verify: ")
        return 1
    except MempoolAPIError as e:
        print(f"  {c.red('✗')} API error: {e}\n")
        return 1
    except ValueError as e:
        print(f"  {c.red('✗')} {e}\n")
        return 2

    if not results:
        print(f"  {c.yellow('⚠')}  No OP_RETURN outputs found in this transaction.\n")
        return 0

    print(f"  {c.green('✓')} Found {len(results)} OP_RETURN output(s):\n")

    for r in results:
        print(f"  {c.bold(f'Output #{r.vout_index}')}")
        print(f"  ├─ Size:     {r.size} bytes")
        hex_preview = r.raw_hex[:64] + ("…" if len(r.raw_hex) > 64 else "")
        print(f"  ├─ Hex:      {c.dim(hex_preview or '(empty)')}")
        if r.decoded_text:
            print(f"  └─ Message:  {c.green(_terminal_safe(r.decoded_text))}")
        elif r.size == 0:
            print(f"  └─ Message:  {c.dim('(no data)')}")
        else:
            print(f"  └─ Message:  {c.dim('(binary data — not UTF-8 text)')}")
        print()

    _print_link(args.network, "tx", args.txid)
    return 0


def _opreturn_raw(args: argparse.Namespace) -> int:
    """--raw: only the payload hex, one line per OP_RETURN output; errors on stderr."""
    try:
        results = decode_op_return(args.txid, args.network)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    except MempoolAPIError as e:  # includes TransactionNotFoundError
        print(f"Error: {e}", file=sys.stderr)
        return 1
    for r in results:
        print(r.raw_hex)
    return 0


def _opreturn_json(args: argparse.Namespace) -> int:
    try:
        results = decode_op_return(args.txid, args.network)
    except ValueError as e:  # invalid input -> exit 2, same as text mode
        print(json.dumps({"error": str(e), "txid": args.txid}, indent=_indent()))
        return 2
    except (TransactionNotFoundError, MempoolAPIError) as e:
        print(json.dumps({"error": str(e), "txid": args.txid}, indent=_indent()))
        return 1

    output = {
        "txid": args.txid,
        "network": args.network,
        "op_return_count": len(results),
        "outputs": [r.to_dict() for r in results],
    }
    print(json.dumps(output, indent=_indent()))
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
        _print_link(args.network, "address", args.address, prefix="Verify: ")
        return 1
    except MempoolAPIError as e:
        print(f"  {c.red('✗')} API error: {e}\n")
        return 1
    except ValueError as e:
        print(f"  {c.red('✗')} {e}\n")
        return 2

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
    txs_line = f"Confirmed txs: {bal.confirmed_tx_count}  ·  Mempool txs: {bal.mempool_tx_count}"
    print(f"  {c.dim(txs_line)}")
    print()
    _print_link(args.network, "address", args.address)
    return 0


def _balance_json(args: argparse.Namespace) -> int:
    try:
        bal = get_balance(args.address, args.network)
    except ValueError as e:  # invalid input -> exit 2, same as text mode
        print(json.dumps({"error": str(e), "address": args.address}, indent=_indent()))
        return 2
    except (AddressNotFoundError, MempoolAPIError) as e:
        print(json.dumps({"error": str(e), "address": args.address}, indent=_indent()))
        return 1

    output = {"network": args.network, **bal.to_dict()}
    print(json.dumps(output, indent=_indent()))
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
    if args.network in _EXPLORER:
        print(f"  {c.dim(_EXPLORER[args.network])}\n")
    return 0


def _fees_json(args: argparse.Namespace) -> int:
    try:
        est = get_fees(args.network)
    except MempoolAPIError as e:
        print(json.dumps({"error": str(e)}, indent=_indent()))
        return 1

    output = {"network": args.network, **est.to_dict()}
    print(json.dumps(output, indent=_indent()))
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
        return 2

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
    _print_link(args.network, "block", blk.hash)
    return 0


def _block_json(args: argparse.Namespace) -> int:
    try:
        blk = get_block(args.ref, args.network)
    except ValueError as e:  # invalid input -> exit 2, same as text mode
        print(json.dumps({"error": str(e), "ref": args.ref}, indent=_indent()))
        return 2
    except (BlockNotFoundError, MempoolAPIError) as e:
        print(json.dumps({"error": str(e), "ref": args.ref}, indent=_indent()))
        return 1

    output = {"network": args.network, **blk.to_dict()}
    print(json.dumps(output, indent=_indent()))
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
        return 2

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
        _dim_line = f"Confirmed: {us.confirmed_count}  ·  Mempool: {us.unconfirmed_count}"
        print(f"  {c.dim(_dim_line)}")
        print()
    _print_link(args.network, "address", args.address)
    return 0


def _utxo_json(args: argparse.Namespace) -> int:
    try:
        us = get_utxos(args.address, args.network, args.confirmed_only)
    except ValueError as e:  # invalid input -> exit 2, same as text mode
        print(json.dumps({"error": str(e), "address": args.address}, indent=_indent()))
        return 2
    except (AddressNotFoundError, MempoolAPIError) as e:
        print(json.dumps({"error": str(e), "address": args.address}, indent=_indent()))
        return 1

    output = {"network": args.network, **us.to_dict()}
    print(json.dumps(output, indent=_indent()))
    return 0


# ──────────────────────────────────────────────────────────────────────
# tx subcommand
# ──────────────────────────────────────────────────────────────────────

def _cmd_tx(args: argparse.Namespace) -> int:
    if args.json_output:
        return _tx_json(args)

    print(c.cyan(BANNER))
    print(c.dim(f"  btc-toolkit v{__version__} · tx · Mempool.space API\n"))

    txid_short = f"{args.txid[:8]}...{args.txid[-8:]}"
    print(f"  {c.bold('TXID:')}    {txid_short}")
    print(f"  {c.bold('Network:')} {args.network}")
    print(f"  {'─' * 48}\n")

    try:
        tx = get_tx(args.txid, args.network)
    except TransactionNotFoundError:
        print(f"  {c.red('✗')} Transaction not found.\n")
        return 1
    except MempoolAPIError as e:
        print(f"  {c.red('✗')} API error: {e}\n")
        return 1
    except ValueError as e:
        print(f"  {c.red('✗')} {e}\n")
        return 2

    if tx.confirmed:
        status = c.green(f"✓ confirmed · block #{tx.block_height:,}")
        if tx.block_time_utc:
            status += c.dim(f" · {tx.block_time_utc}")
    else:
        status = c.yellow("⧗ unconfirmed (mempool)")

    print(f"  {c.bold('Status:')}   {status}")

    flags = []
    if tx.is_coinbase:
        flags.append(c.cyan("coinbase"))
    if tx.is_rbf:
        flags.append(c.yellow("RBF"))
    if flags:
        print(f"  {c.bold('Flags:')}    {' · '.join(flags)}")
    print()

    print(f"  {c.bold('Amounts:')}\n")
    if not tx.is_coinbase:
        print(f"  ├─ Total in:   {tx.total_input:,} sats")
    print(f"  ├─ Total out:  {tx.total_output:,} sats")
    if not tx.is_coinbase:
        print(f"  ├─ Fee:        {c.green(f'{tx.fee:,} sats')}")
        print(f"  └─ Fee rate:   {c.green(f'{tx.fee_rate:.2f} sat/vB')}")
    else:
        print(f"  └─ Fee:        {c.dim('0 (coinbase — collects block reward)')}")
    print()

    print(f"  {c.bold('Structure:')}\n")
    print(f"  ├─ Inputs:     {tx.input_count}")
    print(f"  ├─ Outputs:    {tx.output_count}")
    print(f"  ├─ Size:       {tx.size:,} bytes")
    print(f"  ├─ Weight:     {tx.weight:,} WU")
    print(f"  ├─ vSize:      {tx.vsize:,} vB")
    print(f"  ├─ Version:    {tx.version}")
    print(f"  └─ Locktime:   {tx.locktime}")
    print()
    _print_link(args.network, "tx", args.txid)
    return 0


def _tx_json(args: argparse.Namespace) -> int:
    try:
        tx = get_tx(args.txid, args.network)
    except ValueError as e:  # invalid input -> exit 2, same as text mode
        print(json.dumps({"error": str(e), "txid": args.txid}, indent=_indent()))
        return 2
    except (TransactionNotFoundError, MempoolAPIError) as e:
        print(json.dumps({"error": str(e), "txid": args.txid}, indent=_indent()))
        return 1

    output = {"network": args.network, **tx.to_dict()}
    print(json.dumps(output, indent=_indent()))
    return 0


# ──────────────────────────────────────────────────────────────────────
# address subcommand
# ──────────────────────────────────────────────────────────────────────

def _cmd_address(args: argparse.Namespace) -> int:
    if args.json_output:
        return _address_json(args)

    print(c.cyan(BANNER))
    print(c.dim(f"  btc-toolkit v{__version__} · address · Mempool.space API\n"))

    addr_short = args.address if len(args.address) <= 24 else (
        f"{args.address[:12]}...{args.address[-8:]}"
    )
    print(f"  {c.bold('Address:')} {addr_short}")
    print(f"  {c.bold('Network:')} {args.network}")
    print(f"  {'─' * 48}\n")

    try:
        ov = get_address_overview(args.address, args.network)
    except AddressNotFoundError:
        print(f"  {c.red('✗')} Address not found.\n")
        return 1
    except MempoolAPIError as e:
        print(f"  {c.red('✗')} API error: {e}\n")
        return 1
    except ValueError as e:
        print(f"  {c.red('✗')} {e}\n")
        return 2

    bal = ov.balance
    print(f"  {c.bold('Type:')}        {c.cyan(ov.address_type)}")
    print(f"  {c.bold('Confirmed:')}   {c.green(bal.sats_to_btc(bal.confirmed_sats) + ' BTC')}")
    if bal.unconfirmed_sats != 0:
        color = c.yellow if bal.unconfirmed_sats > 0 else c.red
        print(f"  {c.bold('Unconfirmed:')} {color(bal.sats_to_btc(bal.unconfirmed_sats) + ' BTC')}")
        print(f"  {c.bold('Total:')}       {c.green(bal.sats_to_btc(bal.total_sats) + ' BTC')}")
    print()
    print(f"  {c.bold('Lifetime:')}\n")
    print(f"  ├─ Received:   {bal.sats_to_btc(bal.funded_sats)} BTC")
    print(f"  ├─ Spent:      {bal.sats_to_btc(bal.spent_sats)} BTC")
    print(f"  ├─ Confirmed txs: {bal.confirmed_tx_count:,}")
    print(f"  └─ Mempool txs:   {bal.mempool_tx_count}")
    print()
    _print_link(args.network, "address", args.address)
    return 0


def _address_json(args: argparse.Namespace) -> int:
    try:
        ov = get_address_overview(args.address, args.network)
    except (AddressNotFoundError, MempoolAPIError) as e:
        print(json.dumps({"error": str(e), "address": args.address}, indent=_indent()))
        return 1
    except ValueError as e:
        print(json.dumps({"error": str(e), "address": args.address}, indent=_indent()))
        return 2

    output = {"network": args.network, **ov.to_dict()}
    print(json.dumps(output, indent=_indent()))
    return 0


# ──────────────────────────────────────────────────────────────────────
# argument parser
# ──────────────────────────────────────────────────────────────────────

_BATCH = False  # set by run() when reading multiple items (stdin / --file)

ENV_API_URL = "BTC_TOOLKIT_API_URL"
ENV_NETWORK = "BTC_TOOLKIT_NETWORK"
ENV_TIMEOUT = "BTC_TOOLKIT_TIMEOUT"


def _indent() -> int | None:
    """Pretty JSON for humans; one object per line (JSON Lines) in batch mode."""
    return None if _BATCH else 2


def _positive_int(value: str) -> int:
    try:
        n = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid int value: {value!r}") from None
    if n < 1:
        raise argparse.ArgumentTypeError(f"must be at least 1, got {value}")
    return n


def _add_common_flags(parser: argparse.ArgumentParser, batch: bool = False) -> None:
    parser.add_argument(
        "--api-url", dest="api_url", default=None, metavar="URL",
        help="Custom Mempool instance API root (e.g. http://umbrel.local:3006/api). "
             f"Overrides --network — your node, your rules. Env: ${ENV_API_URL}.",
    )
    parser.add_argument(
        "--timeout", dest="timeout", type=float, default=None, metavar="SECONDS",
        help=f"Per-request timeout in seconds (default 15). Env: ${ENV_TIMEOUT}.",
    )
    if batch:
        parser.add_argument(
            "--file", dest="file", default=None, metavar="PATH",
            help="Read one item per line from PATH (blank lines and # comments "
                 "ignored). With --json, output is JSON Lines.",
        )


def _add_api_url(parser: argparse.ArgumentParser) -> None:
    # kept for readability at call sites; batch-capable commands opt in below
    _add_common_flags(parser, batch=parser.prog.split()[-1] != "fees")


def _positional_key(args: argparse.Namespace) -> str | None:
    for key in ("txid", "address", "ref"):
        if hasattr(args, key):
            return key
    return None


def _collect_items(args: argparse.Namespace, key: str | None) -> list[str] | None:
    """Return the list of items for batch mode, or None for a single run."""
    if key is None:
        return None
    file_path = getattr(args, "file", None)
    value = getattr(args, key)
    if file_path is None and value != "-":
        return None
    if file_path is not None and value not in (None, "-"):
        # both a positional and --file: the file wins, positional must be '-'
        raise ValueError("use '-' as the positional when passing --file")
    if file_path is None and sys.stdin.isatty():
        raise ValueError(f"missing {key}: pass a value, use --file, or pipe items via stdin")
    if file_path is None:
        return _clean_lines(sys.stdin)
    with open(file_path, encoding="utf-8-sig") as fh:  # -sig: tolerate a BOM (Windows Notepad)
        return _clean_lines(fh)


def _clean_lines(lines: Iterable[str]) -> list[str]:
    """Strip each line (and any byte-order mark); drop blanks and # comments."""
    return [s for s in (line.replace("\ufeff", "").strip() for line in lines) if s and not s.startswith("#")]


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
    p_op.add_argument("txid", nargs="?", default="-", help="Transaction ID (64-char hex), or - for stdin.")
    p_op.add_argument(
        "-n", "--network", choices=SUPPORTED_NETWORKS, default=None,
        help=f"Bitcoin network (default: ${ENV_NETWORK}, else mainnet).",
    )
    p_op.add_argument(
        "--json", action="store_true", dest="json_output",
        help="Output as JSON.",
    )
    p_op.add_argument(
        "--raw", action="store_true", help="Show raw hex only (one per line).",
    )
    _add_api_url(p_op)
    p_op.set_defaults(func=_cmd_opreturn)

    # balance
    p_bal = subparsers.add_parser(
        "balance", help="Check the confirmed and unconfirmed balance of an address."
    )
    p_bal.add_argument("address", nargs="?", default="-", help="Bitcoin address (any type), or - to read from stdin.")
    p_bal.add_argument(
        "-n", "--network", choices=SUPPORTED_NETWORKS, default=None,
        help=f"Bitcoin network (default: ${ENV_NETWORK}, else mainnet).",
    )
    p_bal.add_argument(
        "--json", action="store_true", dest="json_output",
        help="Output as JSON.",
    )
    _add_api_url(p_bal)
    p_bal.set_defaults(func=_cmd_balance)

    # fees
    p_fees = subparsers.add_parser(
        "fees", help="Show recommended fee rates and mempool backlog."
    )
    p_fees.add_argument(
        "-n", "--network", choices=SUPPORTED_NETWORKS, default=None,
        help=f"Bitcoin network (default: ${ENV_NETWORK}, else mainnet).",
    )
    p_fees.add_argument(
        "--json", action="store_true", dest="json_output",
        help="Output as JSON.",
    )
    _add_api_url(p_fees)
    p_fees.set_defaults(func=_cmd_fees)

    # block
    p_blk = subparsers.add_parser(
        "block", help="Show block metadata by height, hash, or 'latest'."
    )
    p_blk.add_argument("ref", nargs="?", default="-", help="Block height, 64-char hash, or 'latest'; - for stdin.",
    )
    p_blk.add_argument(
        "-n", "--network", choices=SUPPORTED_NETWORKS, default=None,
        help=f"Bitcoin network (default: ${ENV_NETWORK}, else mainnet).",
    )
    p_blk.add_argument(
        "--json", action="store_true", dest="json_output",
        help="Output as JSON.",
    )
    _add_api_url(p_blk)
    p_blk.set_defaults(func=_cmd_block)

    # utxo
    p_utxo = subparsers.add_parser(
        "utxo", help="List the unspent outputs (UTXOs) of an address."
    )
    p_utxo.add_argument("address", nargs="?", default="-", help="Bitcoin address (any type), or - to read from stdin.")
    p_utxo.add_argument(
        "-n", "--network", choices=SUPPORTED_NETWORKS, default=None,
        help=f"Bitcoin network (default: ${ENV_NETWORK}, else mainnet).",
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
        "--limit", type=_positive_int, default=15,
        help="Max UTXOs to display (default: 15; JSON always shows all).",
    )
    _add_api_url(p_utxo)
    p_utxo.set_defaults(func=_cmd_utxo)

    # tx
    p_tx = subparsers.add_parser(
        "tx", help="Inspect a transaction: status, fees, size, I/O, RBF."
    )
    p_tx.add_argument("txid", nargs="?", default="-", help="Transaction ID (64-char hex), or - for stdin.")
    p_tx.add_argument(
        "-n", "--network", choices=SUPPORTED_NETWORKS, default=None,
        help=f"Bitcoin network (default: ${ENV_NETWORK}, else mainnet).",
    )
    p_tx.add_argument(
        "--json", action="store_true", dest="json_output",
        help="Output as JSON.",
    )
    _add_api_url(p_tx)
    p_tx.set_defaults(func=_cmd_tx)

    # address
    p_addr = subparsers.add_parser(
        "address", help="Aggregated overview of an address: type, balance, lifetime totals."
    )
    p_addr.add_argument("address", nargs="?", default="-", help="Bitcoin address (any type), or - to read from stdin.")
    p_addr.add_argument(
        "-n", "--network", choices=SUPPORTED_NETWORKS, default=None,
        help=f"Bitcoin network (default: ${ENV_NETWORK}, else mainnet).",
    )
    p_addr.add_argument(
        "--json", action="store_true", dest="json_output",
        help="Output as JSON.",
    )
    _add_api_url(p_addr)
    p_addr.set_defaults(func=_cmd_address)

    return parser


def run(argv: list[str] | None = None) -> int:
    """Main entry point. Returns an exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    # Flags win over environment variables: --api-url, then --network, then
    # $BTC_TOOLKIT_API_URL, then $BTC_TOOLKIT_NETWORK, then mainnet.
    network_flag = getattr(args, "network", None)
    api_url = getattr(args, "api_url", None) or (None if network_flag else os.environ.get(ENV_API_URL) or None)
    if network_flag is None and not api_url:
        env_network = os.environ.get(ENV_NETWORK, "").strip().lower()
        if env_network and env_network not in SUPPORTED_NETWORKS:
            print(f"Error: ${ENV_NETWORK} must be one of {', '.join(SUPPORTED_NETWORKS)}.", file=sys.stderr)
            return 2
        args.network = env_network or "mainnet"
    set_api_base(api_url)
    if api_url:
        args.network = "custom"

    timeout = getattr(args, "timeout", None)
    if timeout is None and os.environ.get(ENV_TIMEOUT):
        try:
            timeout = float(os.environ[ENV_TIMEOUT])
        except ValueError:
            print(f"Error: ${ENV_TIMEOUT} must be a number.", file=sys.stderr)
            return 2
    if timeout is not None:
        try:
            set_timeout(timeout)
        except ValueError as e:
            print(f"Error: {e}.", file=sys.stderr)
            return 2

    key = _positional_key(args)
    try:
        items = _collect_items(args, key)
    except (OSError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    if items is None:
        code: int = args.func(args)
        return code
    assert key is not None  # items is only a list when a positional key exists

    if not items:
        print("Error: no items to process.", file=sys.stderr)
        return 2

    global _BATCH
    _BATCH = True
    worst = 0
    try:
        for item in items:
            setattr(args, key, item)
            worst = max(worst, args.func(args))
    finally:
        _BATCH = False
    return worst


if __name__ == "__main__":
    sys.exit(run())

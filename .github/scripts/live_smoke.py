"""
Weekly live smoke test: read known, immutable on-chain facts from the real
network and fail loudly if any of them stops reading correctly. Catches
upstream API drift that the mocked unit tests cannot see.
"""

import json
import subprocess
import sys

GENESIS_HASH = "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f"
SATOSHI = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
CRAIG_TX = "f4ac7abcb689df30ec5e8d829733622f389ca91367c47b319bc582e653cd8cab"
LIQUID_FIRST_MSG = "c103de95817b43f2df635ec6f35ff126ca26a7c6d20570c4b01866b2b3e69a19"
DONATION = "bc1qulq8xfcmgxxumjx3yndkfktqgw2exh0rym45sn"

failures = []


def run(*args):
    proc = subprocess.run([sys.executable, "-m", "btc_toolkit", *args], capture_output=True, text=True)
    data = None
    if "--json" in args and proc.stdout.strip():
        data = json.loads(proc.stdout)
    return proc.returncode, data


def check(name, condition, detail=""):
    print(f"  {'ok  ' if condition else 'FAIL'} {name}{f' — {detail}' if detail and not condition else ''}")
    if not condition:
        failures.append(name)


def safe(name, fn):
    try:
        fn()
    except Exception as e:  # any crash is a failure of that check, not of the run
        check(name, False, repr(e))


def block_genesis():
    code, d = run("block", "0", "--json")
    check("block 0 is the genesis block", code == 0 and d["hash"] == GENESIS_HASH and d["tx_count"] == 1, str(d))


def opreturn_craig():
    code, d = run("opreturn", CRAIG_TX, "--json")
    text = d["outputs"][0]["decoded_text"] if code == 0 and d["outputs"] else ""
    check("opreturn decodes the Craig Wright message", "Craig Wright is a liar and a fraud" in text, text)


def tx_liquid():
    code, d = run("tx", LIQUID_FIRST_MSG, "--json")
    ok = code == 0 and d["fee_sats"] == 269 and d["block_height"] == 965818 and d["is_rbf"] is True
    check("tx reads the Liquid first-contact transaction", ok, str(d))


def address_satoshi():
    code, d = run("address", SATOSHI, "--json")
    ok = code == 0 and d["address_type"] == "P2PKH" and d["total"]["sats"] > 5_000_000_000
    check("address: genesis address is P2PKH with > 50 BTC", ok, str(d))


def balance_satoshi():
    code, d = run("balance", SATOSHI, "--json")
    check("balance: genesis address > 50 BTC", code == 0 and d["total"]["sats"] > 5_000_000_000, str(d))


def utxo_small():
    code, d = run("utxo", DONATION, "--json")
    check("utxo answers with a well-formed set", code == 0 and "utxo_count" in d and "utxos" in d, str(d))


def fees_live():
    code, d = run("fees", "--json")
    f = d["fees_sat_vb"] if code == 0 else {}
    check("fees are ordered fastest >= minimum >= 0", code == 0 and f["fastest"] >= f["minimum"] >= 0, str(d))


def signet_tip():
    code, d = run("block", "latest", "--network", "signet", "--json")
    check("signet tip is reachable", code == 0 and d["height"] > 200_000, str(d))


def not_found_contract():
    code, _ = run("tx", "0" * 64, "--json")
    check("unknown txid exits 1 (network contract)", code == 1, f"exit {code}")


if __name__ == "__main__":
    print("btc-toolkit live smoke test")
    for name, fn in [
        ("block", block_genesis), ("opreturn", opreturn_craig), ("tx", tx_liquid),
        ("address", address_satoshi), ("balance", balance_satoshi), ("utxo", utxo_small),
        ("fees", fees_live), ("signet", signet_tip), ("not-found", not_found_contract),
    ]:
        safe(name, fn)
    print(f"\n{9 - len(failures)}/9 checks passed")
    sys.exit(1 if failures else 0)

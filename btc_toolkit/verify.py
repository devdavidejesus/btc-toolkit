"""
Merkle-proof verification: check, by computation, that a transaction is in a block.

Instead of trusting the API's "confirmed", btc-toolkit recomputes:

1. the txid, by hashing the raw transaction the API returns (a 64-byte
   transaction is refused);
2. the Merkle root, from that txid and the proof's sibling hashes — refusing
   any 64-byte pair of nodes that is also a valid transaction, the ambiguity
   behind CVE-2017-12842;
3. the block hash, by hashing the 80-byte header, which must contain that root;
4. the proof of work: the header hash must be below the target its `bits`
   encode, within the network's limit.

The verdict depends only on the work proven, never on what the API claims
(height, date): a forger chooses those. A mainnet header at difficulty 50 T or
more ("strong") takes about 2^77.5 hashes to forge — over a third of the work
of a block at October 2026's difficulty (about 133 T). Below that (older blocks, testnet, signet, an unknown chain)
the work is reported as "weak": the data is consistent, but cheap to fake.
Signet block signatures are not checked.

What this does NOT prove: that the block is in the chain everyone follows, or
its height (the API reports it; a header does not contain it). Only a full
node checks everything.

Endpoints:
    GET /api/tx/:txid/status        -> confirmed?, block height and hash
    GET /api/tx/:txid/hex           -> the raw transaction
    GET /api/tx/:txid/merkle-proof  -> {block_height, merkle: [...], pos}
    GET /api/block/:hash/header     -> the 80-byte header, hex
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
import math
from typing import Any

from .api import MempoolAPIError, NotFoundError, _is_hash, as_object, field_bool, field_hash, field_int, field_opt_int
from .api import get_json, get_text
from .encoding import sha256d
from .opreturn import TransactionNotFoundError, _validate_txid
from .rawtx import decode_tx, parse_hex

# Largest target (lowest difficulty) each network allows.
_POW_LIMIT = {
    "mainnet": 0xFFFF << 208,
    "testnet": 0xFFFF << 208,
    "signet": 0x00000377AE << 216,
}
_DIFF1_TARGET = 0xFFFF << 208  # difficulty 1

# "Strong" work: a mainnet header at this difficulty or more. 50 T is ~2^77.5 hashes, over a third of a block's work
# at October 2026's difficulty (~133 T). It depends on nothing the API claims: an old block below it is reported
# with "weak" work, not refused.
STRONG_DIFFICULTY = 50e12


class VerificationError(MempoolAPIError):
    """A check failed: the data the API returned does not prove what it claims."""


class NotConfirmedError(MempoolAPIError):
    """The transaction is not in a block yet, so there is nothing to verify."""


@dataclass
class Header:
    version: int
    prev_hash: str
    merkle_root: str
    time: int
    bits: int
    nonce: int
    hash: str

    @property
    def target(self) -> int:
        return bits_to_target(self.bits)

    @property
    def difficulty(self) -> float:
        return _DIFF1_TARGET / self.target

    @property
    def work_log2(self) -> float:
        """log2 of the expected number of hashes to find a header this hard."""
        return math.log2((1 << 256) / (self.target + 1))


def parse_header(raw: bytes) -> Header:
    if len(raw) != 80:
        raise ValueError(f"a block header is 80 bytes, got {len(raw)}")
    return Header(
        version=int.from_bytes(raw[0:4], "little", signed=True),
        prev_hash=raw[4:36][::-1].hex(),
        merkle_root=raw[36:68][::-1].hex(),
        time=int.from_bytes(raw[68:72], "little"),
        bits=int.from_bytes(raw[72:76], "little"),
        nonce=int.from_bytes(raw[76:80], "little"),
        hash=sha256d(raw)[::-1].hex(),
    )


def bits_to_target(bits: int) -> int:
    """Decode the compact `bits` field into the 256-bit target. Raises ValueError if invalid."""
    exponent, mantissa = bits >> 24, bits & 0x007FFFFF
    if bits & 0x00800000:
        raise ValueError("bits encode a negative target")
    target = mantissa >> 8 * (3 - exponent) if exponent <= 3 else mantissa << 8 * (exponent - 3)
    if target == 0 or target >= 1 << 256:
        raise ValueError("bits encode an invalid target")
    return target


def _decodes_as_tx(data: bytes) -> bool:
    try:
        decode_tx(data, "custom")
    except ValueError:
        return False
    return True


def merkle_root_from_proof(txid: str, branch: list[str], pos: int) -> str:
    """
    Fold a txid up its Merkle branch (sibling hashes, bottom first) to the root.

    Raises ValueError on a malformed branch, and when a pair of nodes is also a
    valid 64-byte transaction: such a "node" could be a transaction posing as
    an inner node, proving a txid that is not in the block (CVE-2017-12842).
    """
    if not all(isinstance(h, str) and _is_hash(h) for h in [txid, *branch]):
        raise ValueError("txid and branch hashes must be 64 hex digits")
    if not 0 <= pos < 1 << len(branch):
        raise ValueError("position does not fit the branch length")
    node = bytes.fromhex(txid)[::-1]
    for sibling_hex in branch:
        sibling = bytes.fromhex(sibling_hex)[::-1]
        pair = sibling + node if pos & 1 else node + sibling
        if _decodes_as_tx(pair):
            raise ValueError("a pair of Merkle nodes is also a valid 64-byte transaction (CVE-2017-12842)")
        node = sha256d(pair)
        pos >>= 1
    return node[::-1].hex()


@dataclass
class Verification:
    txid: str
    block_hash: str
    block_height: int
    header: Header
    position: int
    branch_length: int
    network: str = "mainnet"
    checks: list[tuple[str, str]] = field(default_factory=list)  # (check, what was computed)

    @property
    def work(self) -> str:
        """'strong' for a mainnet header at STRONG_DIFFICULTY or more; 'weak' otherwise."""
        return "strong" if self.network == "mainnet" and self.header.difficulty >= STRONG_DIFFICULTY else "weak"

    @property
    def block_time_utc(self) -> str:
        return datetime.fromtimestamp(self.header.time, tz=UTC).strftime("%Y-%m-%d %H:%M:%S UTC")

    def to_dict(self) -> dict[str, Any]:
        return {
            "txid": self.txid,
            "verified": True,
            "work": self.work,
            "block_hash": self.block_hash,
            "block_height": self.block_height,
            "block_time": self.header.time,
            "block_time_utc": self.block_time_utc,
            "merkle_root": self.header.merkle_root,
            "position": self.position,
            "branch_length": self.branch_length,
            "bits": self.header.bits,
            "difficulty": self.header.difficulty,
            "work_log2": round(self.header.work_log2, 2),
            "checks": [{"check": name, "passed": True, "detail": detail} for name, detail in self.checks],
        }


def _fail(message: str) -> VerificationError:
    return VerificationError(f"verification failed: {message}")


def verify_tx(txid: str, network: str = "mainnet") -> Verification:
    """
    Verify that `txid` is committed to by a block header with valid proof of work.

    Raises:
        ValueError: The txid is malformed.
        TransactionNotFoundError: The API does not know the transaction.
        NotConfirmedError: The transaction is not in a block yet.
        VerificationError: A computed value does not match — the API's data is wrong.
        MempoolAPIError: Other API errors.
    """
    txid = _validate_txid(txid)
    try:
        status = as_object(get_json(f"/tx/{txid}/status", network), "/tx/status")
    except NotFoundError as e:
        raise TransactionNotFoundError(f"Transaction not found: {txid}") from e
    if not field_bool(status, "confirmed", "/tx/status"):
        raise NotConfirmedError("not confirmed yet: a Merkle proof only exists once the transaction is in a block")
    block_hash = field_hash(status, "block_hash", "/tx/status")
    height = field_opt_int(status, "block_height", "/tx/status")
    if not block_hash or height is None:
        raise MempoolAPIError("Unexpected response from /tx/status: confirmed without a block hash and height")

    checks: list[tuple[str, str]] = []

    # 1. The raw transaction hashes to the txid.
    try:
        tx = decode_tx(parse_hex(get_text(f"/tx/{txid}/hex", network)), network)
    except ValueError as e:
        raise _fail(f"the raw transaction from the API does not decode: {e}") from None
    if tx.txid != txid:
        raise _fail(f"the raw transaction hashes to {tx.txid}, not to the txid asked for")
    if tx.base_size == 64:
        raise _fail("a 64-byte transaction can be confused with a Merkle tree node (CVE-2017-12842)")
    checks.append(("raw transaction hashes to the txid", f"sha256d -> {tx.txid}"))

    # 2. The Merkle branch leads to a root.
    proof = as_object(get_json(f"/tx/{txid}/merkle-proof", network), "/tx/merkle-proof")
    branch = proof.get("merkle")
    if not isinstance(branch, list) or not all(isinstance(h, str) and _is_hash(h) for h in branch):
        raise MempoolAPIError("Unexpected response from /tx/merkle-proof: 'merkle' is not a list of hashes")
    if len(branch) > 32:
        raise _fail("Merkle branch longer than any block allows")
    pos = field_int(proof, "pos", "/tx/merkle-proof")
    if field_int(proof, "block_height", "/tx/merkle-proof") != height:
        raise _fail("the Merkle proof is for a different block height than the transaction status")
    try:
        root = merkle_root_from_proof(txid, branch, pos)
    except ValueError as e:
        raise _fail(f"bad Merkle proof: {e}") from None

    # 3. The header hashes to the block hash and contains that root.
    header_hex = get_text(f"/block/{block_hash}/header", network)
    try:
        header = parse_header(parse_hex(header_hex))
    except ValueError as e:
        raise _fail(f"the block header from the API is invalid: {e}") from None
    if header.hash != block_hash:
        raise _fail(f"the header hashes to {header.hash}, not to block {block_hash}")
    checks.append(("header hashes to the block hash", f"sha256d -> {header.hash}"))
    if header.merkle_root != root:
        raise _fail(f"the Merkle branch leads to {root}, but the header commits to {header.merkle_root}")
    checks.append(("Merkle branch leads to the header's root",
                   f"{len(branch)} hashes from position {pos} -> {root}"))

    # 4. Proof of work.
    try:
        target = header.target
    except ValueError as e:
        raise _fail(str(e)) from None
    limit = _POW_LIMIT.get(network, _POW_LIMIT["signet"])  # an unknown chain: accept the loosest public limit
    if target > limit:
        raise _fail("the header's target is easier than the network allows")
    if int(header.hash, 16) > target:
        raise _fail("the header hash is above its target: no valid proof of work")
    checks.append(("proof of work",
                   f"hash below target; difficulty {format_difficulty(header.difficulty)}, "
                   f"about 2^{header.work_log2:.1f} hashes"))

    return Verification(txid, block_hash, height, header, pos, len(branch), network, checks)


def format_difficulty(d: float) -> str:
    """1 -> '1', 0.0023 -> '0.0023', 1.4e14 -> '140,000,000,000,000'."""
    return f"{d:,.0f}" if d >= 1 else f"{d:.4g}"

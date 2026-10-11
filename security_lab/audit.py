"""Allowlisted events and a hash chain checked against a separately held anchor.

This checks consistency relative to a trusted checkpoint. It cannot establish
that the event is true or stop the writer from replacing both log and anchor.
"""
from __future__ import annotations
import hmac
from .common import Rejected, canonical, digest, integer, label, sha256_text

EVENTS = {'proposal', 'approved', 'accepted', 'denied', 'stopped', 'restored'}
REASONS = {'ok', 'changed', 'blocked', 'revoked', 'expired', 'policy-denied', 'restore-complete', 'clock-stale', 'fixture'}

def event_record(*, event: str, request_hash: str, epoch: int, reason: str,
                 sequence: int, observed_at: int) -> dict:
    if event not in EVENTS:
        raise Rejected('EVENT_UNKNOWN')
    sha256_text(request_hash)
    if reason not in REASONS:
        raise Rejected('REASON_UNKNOWN')
    integer(epoch, 0, 2**62); integer(sequence, 1, 2**62); integer(observed_at, 0, 2**62)
    # No generic **kwargs/payload/text field to leak prompts, tokens or paths.
    return dict(event=event, request_hash=request_hash, epoch=epoch,
                reason=reason, sequence=sequence, observed_at=observed_at)

def make_chain(records: list[dict]) -> tuple[list[dict], dict]:
    previous = '0' * 64
    chain = []
    for i, record in enumerate(records, 1):
        if type(record) is not dict:
            raise Rejected('EVENT_SCHEMA')
        try:
            normalized = event_record(**record)
        except TypeError as exc:
            raise Rejected('EVENT_SCHEMA') from exc
        if normalized['sequence'] != i:
            raise Rejected('SEQUENCE')
        head = digest({'previous': previous, 'record': normalized})
        chain.append({'previous': previous, 'record': normalized, 'hash': head})
        previous = head
    return chain, {'count': len(chain), 'head': previous}

def verify(chain: list[dict], anchor: dict) -> bool:
    if type(chain) is not list or type(anchor) is not dict or set(anchor) != {'count', 'head'}:
        raise Rejected('ANCHOR_SCHEMA')
    integer(anchor['count'], 0, 100000); sha256_text(anchor['head'])
    if len(chain) != anchor['count']:
        raise Rejected('ANCHOR_COUNT')
    records = []
    for node in chain:
        if type(node) is not dict or set(node) != {'previous', 'record', 'hash'}:
            raise Rejected('CHAIN_SCHEMA')
        records.append(node['record'])
    rebuilt, expected = make_chain(records)
    if canonical(chain) != canonical(rebuilt) or not hmac.compare_digest(expected['head'], anchor['head']):
        raise Rejected('CHAIN_MISMATCH')
    return True

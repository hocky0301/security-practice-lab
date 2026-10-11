"""Policy over normalized scanner results; not a vulnerability scanner.

Advisory IDs in the bundled test data start DEMO-. No real registry is queried.
Actual scanner adapters must prove coverage, freshness and exit-code meaning.
"""
from __future__ import annotations
from datetime import datetime, timezone
from .common import Rejected, label, sha256_text

RANK = {'low': 1, 'medium': 2, 'high': 3, 'critical': 4}

def instant(text: str) -> datetime:
    if type(text) is not str:
        raise Rejected('INVALID_TIME')
    try:
        value = datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError as exc:
        raise Rejected('INVALID_TIME') from exc
    if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
        raise Rejected('TIME_NOT_UTC')
    return value

def evaluate(report: dict, exceptions: list[dict], *, now: str,
             expected_inventory: str) -> dict:
    current = instant(now)
    sha256_text(expected_inventory)
    if type(report) is not dict:
        raise Rejected('REPORT_SCHEMA')
    needed = {'schema', 'complete', 'skipped', 'checked', 'inventory_sha256',
              'generated_at', 'findings', 'scanner'}
    if set(report) != needed or report['schema'] != 'scan-normalized-v1':
        raise Rejected('REPORT_SCHEMA')
    label(report['scanner'])
    if report['complete'] is not True or report['skipped'] != []:
        raise Rejected('SCAN_INCOMPLETE')
    if type(report['checked']) is not int or report['checked'] < 1:
        raise Rejected('SCAN_EMPTY')
    if report['inventory_sha256'] != expected_inventory:
        raise Rejected('INVENTORY_CHANGED')
    age = (current - instant(report['generated_at'])).total_seconds()
    if not 0 <= age <= 86400:
        raise Rejected('SCAN_STALE')
    if type(report['findings']) is not list or type(exceptions) is not list:
        raise Rejected('LIST_REQUIRED')
    decisions: dict[tuple[str, str, str], dict] = {}
    for ex in exceptions:
        fields = {'package', 'version', 'advisory', 'owner', 'reason',
                  'approved_at', 'expires_at', 'inventory_sha256'}
        if type(ex) is not dict or set(ex) != fields:
            raise Rejected('EXCEPTION_SCHEMA')
        for key in ('package', 'version', 'advisory', 'owner'):
            label(ex[key])
        if type(ex['reason']) is not str or not 8 <= len(ex['reason']) <= 400:
            raise Rejected('EXCEPTION_REASON')
        approved, expiry = instant(ex['approved_at']), instant(ex['expires_at'])
        if not approved <= current < expiry or (expiry - approved).total_seconds() > 30 * 86400:
            raise Rejected('EXCEPTION_EXPIRED_OR_TOO_LONG')
        if ex['inventory_sha256'] != expected_inventory:
            raise Rejected('EXCEPTION_INVENTORY_CHANGED')
        key = (ex['package'], ex['version'], ex['advisory'])
        if key in decisions:
            raise Rejected('DUPLICATE_EXCEPTION')
        decisions[key] = ex
    blocked, accepted, seen = [], [], set()
    for finding in report['findings']:
        if type(finding) is not dict or set(finding) != {'package', 'version', 'advisory', 'severity'}:
            raise Rejected('FINDING_SCHEMA')
        key = tuple(label(finding[k]) for k in ('package', 'version', 'advisory'))
        if key in seen:
            raise Rejected('DUPLICATE_FINDING')
        seen.add(key)
        severity = finding['severity']
        if severity not in RANK:
            raise Rejected('SEVERITY_UNKNOWN')
        if RANK[severity] >= RANK['high']:
            (accepted if key in decisions else blocked).append(finding['advisory'])
    if set(decisions) - seen:
        raise Rejected('ORPHAN_EXCEPTION')
    return {'verdict': 'BLOCK' if blocked else 'PASS',
            'blocking_advisories': blocked, 'temporary_exceptions': accepted,
            'scope': 'normalized-fixture-policy-not-live-scan'}

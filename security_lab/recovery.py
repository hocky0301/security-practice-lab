"""Recover benign application data, never old authorization state.

The expected hash and minimum epoch must come from a separately trusted
recovery record. This module cannot make that record independent by itself.
"""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from .authority import Authority
from .common import Rejected, canonical, digest, integer, sha256_text

def recover_preview(snapshot: dict, *, expected_hash: str, trusted_epoch: int,
                    destination: Path) -> dict:
    sha256_text(expected_hash); integer(trusted_epoch, 1, 2**60)
    if type(snapshot) is not dict or set(snapshot) != {'schema', 'motions'}:
        raise Rejected('SNAPSHOT_SCHEMA')
    if snapshot['schema'] != 'motion-data-v1' or type(snapshot['motions']) is not list:
        raise Rejected('SNAPSHOT_SCHEMA')
    if len(snapshot['motions']) > 1000:
        raise Rejected('SNAPSHOT_TOO_LARGE')
    if digest(snapshot) != expected_hash:
        raise Rejected('SNAPSHOT_CHANGED')
    for item in snapshot['motions']:
        Authority.validate(item)
    # Nothing is written before every input has been checked.
    destination.mkdir(parents=False, exist_ok=False)
    try:
        (destination/'motions.json').write_bytes(canonical(snapshot))
        a=Authority(destination/'authority.sqlite')
        with a._db() as c:
            c.execute('BEGIN IMMEDIATE')
            c.execute('UPDATE control SET stopped=1,epoch=? WHERE singleton=1',(trusted_epoch+1,))
            c.commit()
        return {'motions': len(snapshot['motions']), 'restored_data_hash': digest(snapshot),
                'authorization_count':0,'stopped':True,'epoch':trusted_epoch+1,
                'scope':'local-recovery-fixture'}
    except Exception:
        # Keep a failed recovery directory for inspection; never overwrite live state.
        raise

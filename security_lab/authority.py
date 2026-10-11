"""SQLite-backed one-use authorizations for a local fake actuator.

No model, network, real actuator, OAuth service, secret or shell is used.
Authorization records stay inside a trusted service. Callers must already be
authenticated: actor/audience parameters are NOT an authentication mechanism.
Approval cannot be called by the untrusted proposal-producing model.
"""
from __future__ import annotations
import json
from contextlib import contextmanager
import secrets
import sqlite3
from pathlib import Path
from .common import Rejected, canonical, digest, integer, label

class Authority:
    def __init__(self, path: Path | str):
        self.path = str(path)
        with self._db() as c:
            c.executescript('''
            CREATE TABLE IF NOT EXISTS control (
                singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                epoch INTEGER NOT NULL, stopped INTEGER NOT NULL,
                policy TEXT NOT NULL);
            INSERT OR IGNORE INTO control VALUES(1,1,0,'motion-policy-v1');
            CREATE TABLE IF NOT EXISTS grants (
                id TEXT PRIMARY KEY, content_hash TEXT NOT NULL,
                actor TEXT NOT NULL, audience TEXT NOT NULL,
                epoch INTEGER NOT NULL, policy TEXT NOT NULL,
                issued INTEGER NOT NULL, expires INTEGER NOT NULL,
                used INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS observations (
                id TEXT PRIMARY KEY, measured_at INTEGER NOT NULL,
                target TEXT NOT NULL, trusted INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS receipts (
                id INTEGER PRIMARY KEY, grant_id TEXT UNIQUE NOT NULL,
                request_hash TEXT NOT NULL, epoch INTEGER NOT NULL,
                effect TEXT NOT NULL);
            ''')
    @contextmanager
    def _db(self):
        c = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        c.row_factory = sqlite3.Row
        try:
            yield c
        finally:
            c.close()
    @staticmethod
    def validate(request: dict) -> bytes:
        fields = {'operation', 'resource', 'position_mdeg', 'duration_ms', 'observation_id'}
        if type(request) is not dict or set(request) != fields:
            raise Rejected('REQUEST_SCHEMA')
        if request['operation'] != 'preview_motion' or request['resource'] != 'paper-stage':
            raise Rejected('OPERATION_NOT_ALLOWED')
        integer(request['position_mdeg'], -30000, 30000)
        integer(request['duration_ms'], 100, 2000)
        label(request['observation_id'])
        return canonical(request)
    def observe(self, *, observation_id: str, measured_at: int, target: str,
                trusted: bool = True) -> None:
        label(observation_id); label(target)
        integer(measured_at, 0, 2**62)
        if type(trusted) is not bool:
            raise Rejected('TRUST_TYPE')
        # Only a trusted adapter calls this method. A label is not proof of truth.
        try:
            with self._db() as c:
                c.execute('INSERT INTO observations VALUES(?,?,?,?)',
                          (observation_id, measured_at, target, int(trusted)))
        except sqlite3.IntegrityError as exc:
            raise Rejected('OBSERVATION_ID_REUSED') from exc
    def approve(self, request: dict, *, actor: str, audience: str,
                now: int, ttl: int = 30, reviewer_role: str = 'human') -> str:
        raw = self.validate(request)
        if reviewer_role != 'human':
            raise Rejected('REVIEWER_REQUIRED')
        label(actor); label(audience)
        integer(now, 0, 2**62); integer(ttl, 1, 60)
        token = secrets.token_urlsafe(24)
        with self._db() as c:
            c.execute('BEGIN IMMEDIATE')
            state = c.execute('SELECT * FROM control WHERE singleton=1').fetchone()
            if state['stopped']:
                c.rollback(); raise Rejected('STOPPED')
            c.execute('INSERT INTO grants VALUES(?,?,?,?,?,?,?,?,0)',
                      (token, digest(json.loads(raw)), actor, audience,
                       state['epoch'], state['policy'], now, now + ttl))
            c.commit()
        return token
    def execute(self, grant_id: str, request: dict, *, actor: str,
                audience: str, now: int) -> dict:
        raw = self.validate(request)
        integer(now, 0, 2**62)
        label(actor); label(audience)
        with self._db() as c:
            c.execute('BEGIN IMMEDIATE')
            state = c.execute('SELECT * FROM control WHERE singleton=1').fetchone()
            grant = c.execute('SELECT * FROM grants WHERE id=?', (grant_id,)).fetchone()
            def deny(code: str):
                c.rollback(); raise Rejected(code)
            if state['stopped']:
                deny('STOPPED')
            if not grant:
                deny('UNKNOWN_GRANT')
            if grant['actor'] != actor or grant['audience'] != audience:
                deny('IDENTITY_MISMATCH')
            if grant['epoch'] != state['epoch'] or grant['policy'] != state['policy']:
                deny('REVOKED')
            if not grant['issued'] <= now < grant['expires']:
                deny('EXPIRED_OR_CLOCK')
            if grant['used']:
                deny('ALREADY_USED')
            if grant['content_hash'] != digest(json.loads(raw)):
                deny('CONTENT_CHANGED')
            obs = c.execute('SELECT * FROM observations WHERE id=?',
                            (request['observation_id'],)).fetchone()
            if not obs or not obs['trusted'] or obs['target'] != request['resource']:
                deny('OBSERVATION_UNTRUSTED')
            if not 0 <= now - obs['measured_at'] <= 5:
                deny('OBSERVATION_STALE')
            c.execute('UPDATE grants SET used=1 WHERE id=? AND used=0', (grant_id,))
            # The only effect is a row in this same transaction, not real I/O.
            c.execute('INSERT INTO receipts(grant_id,request_hash,epoch,effect) VALUES(?,?,?,?)',
                      (grant_id, grant['content_hash'], state['epoch'], 'DRY_RUN_ONLY'))
            c.commit()
            return {'accepted': True, 'effect': 'DRY_RUN_ONLY',
                    'request_hash': grant['content_hash'], 'epoch': state['epoch']}
    def stop(self) -> int:
        with self._db() as c:
            c.execute('BEGIN IMMEDIATE')
            c.execute('UPDATE control SET stopped=1, epoch=epoch+1 WHERE singleton=1')
            epoch = c.execute('SELECT epoch FROM control WHERE singleton=1').fetchone()[0]
            c.commit()
            return epoch
    def resume(self, *, reviewer_role: str) -> int:
        if reviewer_role != 'human':
            raise Rejected('REVIEWER_REQUIRED')
        with self._db() as c:
            c.execute('BEGIN IMMEDIATE')
            c.execute('UPDATE control SET stopped=0, epoch=epoch+1 WHERE singleton=1')
            epoch = c.execute('SELECT epoch FROM control WHERE singleton=1').fetchone()[0]
            c.commit()
            return epoch
    def set_policy(self, version: str) -> None:
        label(version)
        with self._db() as c:
            c.execute('BEGIN IMMEDIATE')
            c.execute('UPDATE control SET policy=?,epoch=epoch+1 WHERE singleton=1', (version,))
            c.commit()
    def receipts(self) -> int:
        with self._db() as c:
            return c.execute('SELECT COUNT(*) FROM receipts').fetchone()[0]

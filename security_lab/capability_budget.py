"""Transactional, shared quota for local dry-run jobs. No billing/remote tool calls.

This is a quota kernel, not authentication. Only a trusted dispatcher may invoke
methods. Unknown external outcomes remain charged/reserved until reconciled.
SQLite serializes one shared store; separate databases do NOT share this guarantee.
"""
from __future__ import annotations
import sqlite3
from contextlib import closing
from pathlib import Path
from .common import integer, label, Rejected

class BudgetStore:
    def __init__(self,path: Path,total: int=300,per_call: int=100):
        integer(total,1,10**9);integer(per_call,1,total)
        self.path=str(path)
        with closing(self._db()) as con:
            con.executescript("""CREATE TABLE IF NOT EXISTS policy(
                id INTEGER PRIMARY KEY CHECK(id=1),total INTEGER,per_call INTEGER,
                epoch INTEGER,stopped INTEGER);
                CREATE TABLE IF NOT EXISTS jobs(
                id TEXT PRIMARY KEY,units INTEGER,charge INTEGER,epoch INTEGER,state TEXT);
                CREATE TABLE IF NOT EXISTS dry_effects(id TEXT PRIMARY KEY);""")
            con.execute('INSERT OR IGNORE INTO policy VALUES(1,?,?,1,0)',(total,per_call))
            row=con.execute('SELECT total,per_call FROM policy').fetchone()
            if row!=(total,per_call):raise Rejected('EXISTING_POLICY_DIFFERENT')
    def _db(self):
        con=sqlite3.connect(self.path,timeout=15,isolation_level=None)
        con.execute('PRAGMA busy_timeout=15000');return con
    def reserve(self,job_id: str,units: int)->str:
        label(job_id);integer(units,1,10**9)
        con=self._db()
        try:
            con.execute('BEGIN IMMEDIATE')
            total,limit,epoch,stopped=con.execute('SELECT total,per_call,epoch,stopped FROM policy').fetchone()
            old=con.execute('SELECT units,epoch,state FROM jobs WHERE id=?',(job_id,)).fetchone()
            if stopped: result='STOPPED'
            elif old is not None:
                if old[0]!=units:result='IDEMPOTENCY_CONFLICT'
                elif old[1]!=epoch:result='OLD_EPOCH'
                else:result='EXISTING_'+old[2].upper()
            elif units>limit:result='PER_CALL_LIMIT'
            elif con.execute('SELECT COALESCE(SUM(charge),0) FROM jobs').fetchone()[0]+units>total:
                result='TOTAL_BUDGET_EXCEEDED'
            else:
                con.execute('INSERT INTO jobs VALUES(?,?,?,?,?)',(job_id,units,units,epoch,'reserved'))
                result='RESERVED'
            con.execute('COMMIT');return result
        except BaseException:
            if con.in_transaction:con.execute('ROLLBACK')
            raise
        finally:con.close()
    def deliver(self,job_id: str)->str:
        """Recheck authority at local effect boundary, not only at queue admission."""
        label(job_id);con=self._db()
        try:
            con.execute('BEGIN IMMEDIATE')
            epoch,stopped=con.execute('SELECT epoch,stopped FROM policy').fetchone()
            row=con.execute('SELECT epoch,state FROM jobs WHERE id=?',(job_id,)).fetchone()
            if row is None:result='UNKNOWN_JOB'
            elif stopped:result='STOPPED'
            elif row[0]!=epoch:result='OLD_EPOCH'
            elif row[1]=='done':result='ALREADY_DONE'
            elif row[1]!='reserved':result='OUTCOME_UNRESOLVED'
            else:
                con.execute('INSERT INTO dry_effects VALUES(?)',(job_id,))
                con.execute("UPDATE jobs SET state='done' WHERE id=?",(job_id,))
                result='DRY_RUN_ONLY'
            con.execute('COMMIT');return result
        except BaseException:
            if con.in_transaction:con.execute('ROLLBACK')
            raise
        finally:con.close()
    def mark_unknown(self,job_id: str)->None:
        """Reserved budget is not refunded just because the caller timed out."""
        label(job_id)
        with closing(self._db()) as con:
            cur=con.execute("UPDATE jobs SET state='unknown' WHERE id=? AND state='reserved'",(job_id,))
            if cur.rowcount!=1:raise Rejected('NOT_RESERVED')
    def reconcile_no_effect(self,job_id: str)->None:
        """TRUSTED reconciliation hook; not evidence that remote work actually failed."""
        label(job_id)
        with closing(self._db()) as con:
            cur=con.execute("UPDATE jobs SET state='cancelled',charge=0 WHERE id=? AND state IN ('reserved','unknown')",(job_id,))
            if cur.rowcount!=1:raise Rejected('NOT_RECONCILABLE')
    def transition(self,stopped: bool)->int:
        if type(stopped) is not bool:raise Rejected('INVALID_STATE')
        con=self._db()
        try:
            con.execute('BEGIN IMMEDIATE')
            con.execute('UPDATE policy SET epoch=epoch+1,stopped=?',(int(stopped),))
            value=con.execute('SELECT epoch FROM policy').fetchone()[0]
            con.execute('COMMIT');return value
        finally:con.close()
    def snapshot(self)->dict:
        with closing(self._db()) as con:
            total,limit,epoch,stopped=con.execute('SELECT total,per_call,epoch,stopped FROM policy').fetchone()
            spent=con.execute('SELECT COALESCE(SUM(charge),0) FROM jobs').fetchone()[0]
            effects=con.execute('SELECT COUNT(*) FROM dry_effects').fetchone()[0]
            return dict(total=total,per_call=limit,epoch=epoch,stopped=bool(stopped),
                        reserved_or_spent=spent,remaining=total-spent,dry_effects=effects)

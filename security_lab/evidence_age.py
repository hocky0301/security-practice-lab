"""Data-lineage/freshness experiment, not perception or real-time robot safety.

Timestamps share one synthetic monotonic clock. They are trusted adapter outputs,
not client-supplied truth. A malicious source can lie; that boundary is not solved.
"""
from __future__ import annotations
from dataclasses import dataclass
from .common import integer, label, Rejected

@dataclass(frozen=True)
class DisplayState:
    measured_ms: int
    received_ms: int
    rendered_ms: int
    session: str
    kind: str
    confidence_percent: int = 99

def validate(x: DisplayState,now_ms:int)->None:
    if type(x) is not DisplayState:raise Rejected('STATE_TYPE')
    for v in (x.measured_ms,x.received_ms,x.rendered_ms,now_ms):integer(v,0,2**63-1)
    if not x.measured_ms<=x.received_ms<=x.rendered_ms<=now_ms:raise Rejected('CLOCK_ORDER')
    label(x.session);integer(x.confidence_percent,0,100)
    if x.kind not in ('measured','predicted'):raise Rejected('STATE_KIND')

def repaint(x:DisplayState,now_ms:int)->DisplayState:
    validate(x,now_ms)
    return DisplayState(x.measured_ms,x.received_ms,now_ms,x.session,'predicted',x.confidence_percent)

def authorize_from_evidence(x:DisplayState,now_ms:int,session:str,max_age_ms:int=250)->str:
    validate(x,now_ms);label(session);integer(max_age_ms,0,60000)
    if x.session!=session:return 'SESSION_CHANGED'
    if now_ms-x.measured_ms>max_age_ms:return 'MEASUREMENT_TOO_OLD'
    if x.kind!='measured':return 'PREDICTION_NOT_OBSERVATION'
    return 'ALLOW_FRESH_OBSERVATION'

def display_only_freshness(x:DisplayState,now_ms:int,max_age_ms:int=250)->bool:
    """Deliberately incomplete comparator. MUST NOT authorize real effects."""
    validate(x,now_ms);integer(max_age_ms,0,60000)
    return now_ms-x.rendered_ms<=max_age_ms

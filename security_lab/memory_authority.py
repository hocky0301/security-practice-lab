"""Memory is reference material; authorization comes from current trusted events.

Complete history + independently trusted current head are required in this model.
Hashes detect mismatch with that head; they do not authenticate whoever wrote it.
Summaries are never parsed as policy. No LLM is run by this module.
"""
from __future__ import annotations
from dataclasses import dataclass
from .common import digest, label, integer, sha256_text, Rejected

@dataclass(frozen=True)
class Head:
    sequence: int
    chain_digest: str
    incarnation: str

def head_of(events: list,incarnation: str)->Head:
    label(incarnation)
    if type(events) is not list or len(events)>10000:raise Rejected('EVENTS_TYPE')
    chain=digest({'incarnation':incarnation,'genesis':True})
    for index,e in enumerate(events,1):
        if type(e) is not dict or set(e)!= {'sequence','kind','subject','resource'}:
            raise Rejected('EVENT_FIELDS')
        if type(e['sequence']) is not int or e['sequence']!=index:raise Rejected('EVENT_ORDER')
        if e['kind'] not in ('grant','revoke'):raise Rejected('EVENT_KIND')
        label(e['subject']);label(e['resource'])
        chain=digest({'previous':chain,'event':e})
    return Head(len(events),chain,incarnation)

def check_current(events: list,expected: Head,incarnation: str,
                  subject: str,resource: str,summary: str='')->str:
    label(subject);label(resource)
    if type(expected) is not Head:raise Rejected('HEAD_REQUIRED')
    integer(expected.sequence,0,10000);sha256_text(expected.chain_digest);label(expected.incarnation)
    actual=head_of(events,incarnation)
    if actual!=expected:return 'POLICY_VIEW_NOT_CURRENT'
    allowed=False
    for e in events:
        if e['subject']==subject and e['resource']==resource:
            allowed=e['kind']=='grant'
    # summary intentionally has no effect, including statements claiming approval.
    return 'ALLOW_CURRENT_GRANT' if allowed else 'NO_CURRENT_GRANT'

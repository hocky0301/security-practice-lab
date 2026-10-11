"""Validate observation provenance metadata, without claiming it proves reality."""
from __future__ import annotations
from .common import Rejected, integer, label

def usable(observation: dict, *, now: int, session: str, current_seq: int) -> bool:
    fields = {'source', 'kind', 'clock', 'observed_at', 'sequence', 'session', 'quality'}
    if type(observation) is not dict or set(observation) != fields:
        raise Rejected('OBSERVATION_SCHEMA')
    integer(now, 0, 2**62); integer(current_seq, 0, 2**62); label(session)
    if observation['source'] != 'trusted-local-adapter' or observation['kind'] != 'measured':
        raise Rejected('NOT_MEASUREMENT')
    if observation['clock'] != 'local-monotonic-ms' or observation['session'] != session:
        raise Rejected('CLOCK_OR_SESSION')
    stamp = integer(observation['observed_at'], 0, 2**62)
    sequence = integer(observation['sequence'], 1, 2**62)
    if sequence <= current_seq:
        raise Rejected('NOT_NEW')
    if not 0 <= now - stamp <= 350:
        raise Rejected('STALE_OR_FUTURE')
    if observation['quality'] != 'usable':
        raise Rejected('QUALITY')
    return True

def residual_authority_area(samples: list[dict]) -> int:
    """Step integral of authorized operation counts, in operation-seconds.

A diagnostic exposure metric, not a probability or expected monetary loss.
"""
    if len(samples) < 2:
        raise Rejected('SAMPLES_REQUIRED')
    total = 0
    previous = None
    for row in samples:
        if type(row) is not dict or set(row) != {'second', 'operations'}:
            raise Rejected('SAMPLE_SCHEMA')
        t = integer(row['second'], 0, 2**62)
        a = integer(row['operations'], 0, 100000)
        if previous is not None:
            pt, pa = previous
            if t <= pt:
                raise Rejected('TIME_ORDER')
            total += (t - pt) * pa
        previous = t, a
    return total

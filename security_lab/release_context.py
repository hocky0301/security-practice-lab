"""Policy checks AFTER independent provenance verification; never a signature verifier.

All arguments are injected by a trusted caller in this local model. A client must
not be allowed to forge verified_claims or approval. No file/network side effects.
"""
from __future__ import annotations
from dataclasses import dataclass
from .common import sha256_text, label, integer, Rejected

@dataclass(frozen=True)
class VerifiedBuild:
    artifact_sha256: str
    producer: str
    workflow: str
    source_commit: str
    # Describes input to this model, NOT actual cryptographic verification here.

@dataclass(frozen=True)
class ReleaseApproval:
    artifact_sha256: str
    producer: str
    workflow: str
    source_commit: str
    destination: str
    visibility: str
    expires_ms: int

def check_release(claims: VerifiedBuild, approval: ReleaseApproval,
                  destination: str, visibility: str, now_ms: int) -> str:
    if type(claims) is not VerifiedBuild or type(approval) is not ReleaseApproval:
        raise Rejected('INVALID_TRUSTED_RECORD')
    for h in [claims.artifact_sha256, approval.artifact_sha256]: sha256_text(h)
    integer(now_ms,0,2**63-1);integer(approval.expires_ms,1,2**63-1)
    for s in [claims.producer,claims.workflow,claims.source_commit,
              approval.producer,approval.workflow,approval.source_commit,
              approval.destination,destination]: label(s)
    if approval.visibility not in ('private','public') or visibility not in ('private','public'):
        raise Rejected('INVALID_VISIBILITY')
    for field, reason in [('artifact_sha256','CONTENT_CHANGED'),('producer','PRODUCER_MISMATCH'),
                          ('workflow','WORKFLOW_MISMATCH'),('source_commit','SOURCE_MISMATCH')]:
        if getattr(claims,field)!=getattr(approval,field): return reason
    if destination!=approval.destination: return 'DESTINATION_MISMATCH'
    if visibility!=approval.visibility: return 'VISIBILITY_MISMATCH'
    if now_ms>=approval.expires_ms: return 'EXPIRED'
    return 'ALLOW_REVIEWED_RELEASE'

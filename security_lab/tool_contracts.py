"""Locally reviewed tool descriptors, not a live MCP implementation or sandbox.

A matching descriptor proves equality, not that a remote implementation honors it.
Permission changes require a separate trusted policy decision.
"""
from __future__ import annotations
from .common import digest, label, sha256_text, Rejected
FIELDS=frozenset({'tool','server','description','input_schema','operations','egress','revision'})

def contract_digest(contract: dict) -> str:
    if type(contract) is not dict or set(contract)!=FIELDS: raise Rejected('CONTRACT_FIELDS')
    for k in ('tool','server','revision'): label(contract[k])
    if type(contract['description']) is not str or not 0<len(contract['description'])<=5000:
        raise Rejected('CONTRACT_DESCRIPTION')
    if type(contract['input_schema']) is not dict: raise Rejected('CONTRACT_SCHEMA')
    for k in ('operations','egress'):
        a=contract[k]
        if type(a) is not list or len(a)>50: raise Rejected('CONTRACT_LIST')
        for v in a: label(v)
        if len(a)!=len(set(a)): raise Rejected('CONTRACT_DUPLICATE')
    # List order is part of this simple fingerprint. NOT a semantic equivalence proof.
    return digest(contract)

def check_contract(contract: dict, reviewed_digest: str) -> str:
    sha256_text(reviewed_digest)
    return 'ALLOW_REVIEWED_DESCRIPTOR' if contract_digest(contract)==reviewed_digest else 'DESCRIPTOR_CHANGED'

def enforce_effect(operation: str, destination: str, policy: dict) -> str:
    """Illustrative fixed dispatcher boundary. Policy must be trusted, not tool metadata."""
    if type(policy) is not dict or set(policy)!= {'operations','destinations'}:
        raise Rejected('POLICY_FIELDS')
    label(operation);label(destination)
    for key in ('operations','destinations'):
        if type(policy[key]) is not list: raise Rejected('POLICY_LIST')
        for item in policy[key]:label(item)
    if operation not in policy['operations']:return 'OPERATION_NOT_GRANTED'
    if destination not in policy['destinations']:return 'DESTINATION_NOT_GRANTED'
    return 'ALLOW_DRY_RUN'

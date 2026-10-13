"""Small domain objects used by administrative callers of the audit service."""
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class Tenant:
    tenant_id: int
    name: str

@dataclass(frozen=True)
class Policy:
    policy_id: int
    tenant_id: int
    resource_prefix: str
    action: str
    effect: str
    priority: int
    reason: str

@dataclass(frozen=True)
class Revision:
    revision_id: int
    policy_id: int
    revision_ts: int
    revision_seq: int
    valid_from: int
    valid_until: Optional[int]

@dataclass(frozen=True)
class Request:
    request_sequence: int
    request_id: str
    tenant_id: int
    resource: str
    action: str
    event_ts: int

@dataclass(frozen=True)
class Decision:
    request_sequence: int
    tenant: str
    decision: Optional[str]
    matched_policy_revision: Optional[int]
    reason: Optional[str]

    def as_dict(self):
        return {
            "request_sequence": self.request_sequence,
            "tenant": self.tenant,
            "decision": self.decision,
            "matched_policy_revision": self.matched_policy_revision,
            "reason": self.reason,
        }

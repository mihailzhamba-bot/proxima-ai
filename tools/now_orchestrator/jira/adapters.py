from __future__ import annotations

from .ledger import JiraLedger
from .policy import JiraDecision, JiraIntent, JiraResult, authorize


class AuditBeforeWriteAdapter:
    """Shared client-adapter seam: record AUTO intent before the client invokes MCP."""
    def __init__(self, ledger: JiraLedger) -> None:
        self.ledger = ledger

    def prepare(self, intent: JiraIntent) -> tuple[JiraDecision, str | None]:
        decision, intent_id = self.ledger.authorize(intent)
        if decision.status != "AUTO":
            return decision, None
        return decision, intent_id

    def record(self, result: JiraResult) -> None:
        self.ledger.record(result)

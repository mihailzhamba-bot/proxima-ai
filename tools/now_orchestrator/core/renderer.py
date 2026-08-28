from __future__ import annotations

from .models import Card, NowDecision


def _joined(values: tuple[str, ...]) -> str:
    return ", ".join(values) if values else "none"


def _render_card(card: Card) -> list[str]:
    if card.action == "BLOCKED":
        return [
            f"[{card.track}] BLOCKED",
            f"reason: {card.reason}",
            f"current_state: {card.current_state}",
            f"next_gate: {card.next_gate}",
            f"recovery: {card.recovery_action}",
        ]
    return [
        f"[{card.track}] {card.action} {card.key}",
        f"outcome: {card.outcome}",
        f"owner: {card.owner}",
        f"current_state: {card.current_state}",
        f"next_gate: {card.next_gate}",
        f"blockers: {_joined(card.blockers)}",
        f"AC: {_joined(card.acceptance_criteria)}",
        f"DoD: {_joined(card.definition_of_done)}",
        f"zones: {_joined(card.zones)}",
        f"sources: {_joined(card.sources)}",
        f"captured_at: {card.captured_at}",
        f"rule: {card.rule}",
    ]


def render(decision: NowDecision) -> str:
    """Render the canonical byte-stable text card body for every adapter."""
    recommendation = decision.recommendation_key or "BLOCKED"
    groups = [
        [f"SNAPSHOT: {decision.snapshot_version} captured_at={decision.captured_at}", f"RECOMMENDATION: {recommendation}"],
        *[_render_card(card) for card in decision.cards],
        ["[D] FROZEN", "reason: Track D requires an explicit Mike decision"],
    ]
    return "\n\n".join("\n".join(group) for group in groups) + "\n"

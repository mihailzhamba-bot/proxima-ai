"""Строгие read-only контракты ежедневного цикла PROXIMA.

Контракты намеренно не содержат marketplace-команд, HTTP payload и client-send
полей. Все вычисления и решения привязаны к tenant, immutable snapshot,
версиям policy/formula/permission и проверяемым SourceRef.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

ScenarioId = Literal[
    "SCN-001",
    "SCN-002",
    "SCN-003",
    "SCN-004",
    "SCN-005",
    "SCN-006",
    "SCN-007",
    "SCN-008",
]
SourceQuality = Literal["fresh", "stale", "partial", "conflicting", "unknown"]
SourceTrustClass = Literal["analytics", "external_text", "policy"]
SnapshotStatus = Literal["ready", "blocked", "partial", "conflicting"]
CycleStatus = Literal["NO_ACTION", "ACTIONS_READY", "AWAITING_APPROVAL", "BLOCKED", "INCIDENT"]
ScenarioStatus = Literal["NO_ACTION", "PROPOSED", "BLOCKED", "INCIDENT"]
RiskLevel = Literal["R0", "R1", "R2", "R3"]
WorkflowState = Literal["SIGNAL", "ANALYSIS", "RECOMMENDATION_DRAFT", "REVIEW_PENDING", "TERMINAL"]
DecisionState = Literal[
    "proposed",
    "review_pending",
    "approved",
    "rejected",
    "measuring",
    "closed",
    "blocked",
    "incident",
]
ActionDomain = Literal["sales", "orders", "profit", "margin", "stock", "ads", "data_quality"]

_SECRET_KEYS = frozenset(
    {
        "authorization",
        "cookie",
        "cookies",
        "password",
        "secret",
        "token",
        "api_key",
        "access_token",
        "refresh_token",
    }
)
_TRANSIENT_PASSPORT_KEYS = frozenset(
    {"signals", "incidents", "tasks", "recommendations", "outcomes"}
)
_EXECUTION_KEYS = frozenset(
    {
        "command",
        "executable_payload",
        "http_request",
        "marketplace_payload",
        "request_body",
        "_".join(("send", "to", "client")),
        "write_payload",
    }
)

_ANALYTICS_SOURCES = frozenset(
    {
        "advertising_spend",
        "attribution_mature",
        "client_stock",
        "cogs",
        "contribution_margin",
        "contribution_profit_baseline",
        "data_quality",
        "demand_per_day",
        "drr_baseline",
        "drr_current",
        "lead_time_days",
        "logistics",
        "margin_baseline",
        "marketplace_commission",
        "moq",
        "orders_baseline",
        "orders_current",
        "paid_storage",
        "returns_cost",
        "revenue",
        "sales_baseline",
        "sales_current",
        "seasonality",
        "stock",
        "stock_current",
        "storage_exposure",
        "synthetic",
        "synthetic-wb-report",
    }
)
_EXTERNAL_TEXT_SOURCES = frozenset(
    {"client_message", "customer_feedback", "customer_question", "customer_review"}
)


def trusted_source_class(source: str) -> SourceTrustClass:
    """Return application-owned source trust; unknown sources never default to trusted."""

    if source == "policy":
        return "policy"
    if source in _ANALYTICS_SOURCES:
        return "analytics"
    if source in _EXTERNAL_TEXT_SOURCES:
        return "external_text"
    raise ValueError("SOURCE_TRUST_TAXONOMY_UNKNOWN")


def _iter_keys(value: JsonValue) -> tuple[str, ...]:
    keys: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            keys.append(key.lower())
            keys.extend(_iter_keys(nested))
    elif isinstance(value, list):
        for nested in value:
            keys.extend(_iter_keys(nested))
    return tuple(keys)


def _reject_keys(value: JsonValue, forbidden: frozenset[str], label: str) -> JsonValue:
    present = sorted(
        key
        for key in set(_iter_keys(value))
        if any(
            key == marker
            or key.startswith(f"{marker}_")
            or key.endswith(f"_{marker}")
            or f"_{marker}_" in key
            for marker in forbidden
        )
    )
    if present:
        raise ValueError(f"{label}: {present}")
    return value


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp обязан содержать timezone")
    return value.astimezone(UTC)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class SourceRef(StrictModel):
    source_ref_id: str = Field(min_length=1)
    client_id: str = Field(min_length=1)
    cabinet_id: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    trust_class: SourceTrustClass = "analytics"
    retrieved_at: datetime
    period: str = Field(min_length=1)
    locator: str = Field(min_length=1)
    value: JsonValue
    quality: SourceQuality
    run_id: str | None = None
    lineage_checksum: str | None = None

    _retrieved_at_utc = field_validator("retrieved_at")(_utc)

    @field_validator("value")
    @classmethod
    def no_secret_fields(cls, value: JsonValue) -> JsonValue:
        return _reject_keys(value, _SECRET_KEYS, "secret-like SourceRef field")

    @model_validator(mode="after")
    def trust_matches_application_taxonomy(self) -> SourceRef:
        if self.trust_class != trusted_source_class(self.source):
            raise ValueError("SOURCE_TRUST_CLASS_MISMATCH")
        return self


class Money(StrictModel):
    amount: float
    currency: str = Field(min_length=3, max_length=3)
    definition: str = Field(min_length=1)
    period: str = Field(min_length=1)


class SnapshotRef(StrictModel):
    snapshot_id: str = Field(min_length=1)
    client_id: str = Field(min_length=1)
    cabinet_id: str = Field(min_length=1)
    marketplace: Literal["WB"]
    data_as_of: datetime
    status: SnapshotStatus
    passport_version: str = Field(min_length=1)
    data_contract_version: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)
    checksum: str = Field(min_length=1)
    source_permission_ref: str = Field(min_length=1)
    data_mode: Literal["real", "synthetic"]

    _data_as_of_utc = field_validator("data_as_of")(_utc)

    @model_validator(mode="after")
    def mode_matches_client(self) -> SnapshotRef:
        if (self.data_mode == "synthetic") != self.client_id.startswith("SYNTH-"):
            raise ValueError("data_mode и client_id не согласованы")
        return self


class VersionedKnowledge(StrictModel):
    version: str = Field(min_length=1)
    values: dict[str, JsonValue]

    @field_validator("values")
    @classmethod
    def no_secret_fields(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        _reject_keys(value, _SECRET_KEYS, "secret-like knowledge field")
        return value


class ClientContext(VersionedKnowledge):
    client_id: str = Field(min_length=1)
    cabinet_id: str = Field(min_length=1)
    passport_version: str = Field(min_length=1)

    @field_validator("values")
    @classmethod
    def durable_rules_only(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        _reject_keys(value, _SECRET_KEYS, "secret-like client context field")
        _reject_keys(value, _TRANSIENT_PASSPORT_KEYS, "transient records forbidden in passport")
        return value

    @model_validator(mode="after")
    def versions_match(self) -> ClientContext:
        if self.version != self.passport_version:
            raise ValueError("client context version обязана совпадать с passport_version")
        return self


class DecisionMemoryRef(StrictModel):
    event_id: str = Field(min_length=1)
    client_id: str = Field(min_length=1)
    cabinet_id: str = Field(min_length=1)
    scenario_id: ScenarioId | None = None
    version: str = Field(min_length=1)
    locator: str = Field(min_length=1)
    decision_state: DecisionState
    content_hash: str = Field(min_length=1)
    related_contract_id: str | None = None


class ContextEnvelope(StrictModel):
    snapshot_id: str = Field(min_length=1)
    global_knowledge: VersionedKnowledge
    client_context: ClientContext
    operational_data: tuple[SourceRef, ...]
    decision_memory: tuple[DecisionMemoryRef, ...]
    methodology_version: str = Field(min_length=1)
    kpi_formula_version: str = Field(min_length=1)
    permission_version: str = Field(min_length=1)

    @model_validator(mode="after")
    def namespaces_share_only_identity(self) -> ContextEnvelope:
        if self.global_knowledge.version != self.methodology_version:
            raise ValueError("global knowledge version обязана совпадать с methodology_version")
        tenant = (self.client_context.client_id, self.client_context.cabinet_id)
        for source in self.operational_data:
            if (
                source.client_id,
                source.cabinet_id,
            ) != tenant or source.snapshot_id != self.snapshot_id:
                raise ValueError("SourceRef не принадлежит ContextEnvelope tenant/snapshot")
        for memory in self.decision_memory:
            if (memory.client_id, memory.cabinet_id) != tenant:
                raise ValueError("Decision Memory не принадлежит ContextEnvelope tenant")
        source_ref_ids = [source.source_ref_id for source in self.operational_data]
        if len(source_ref_ids) != len(set(source_ref_ids)):
            raise ValueError("DUPLICATE_SOURCE_REF_ID")
        semantic_locators = [(source.source, source.locator) for source in self.operational_data]
        if len(semantic_locators) != len(set(semantic_locators)):
            raise ValueError("DUPLICATE_SOURCE_SEMANTIC_LOCATOR")
        return self


class CycleRequest(StrictModel):
    actor: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    client_id: str = Field(min_length=1)
    cabinet_id: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    mode: Literal["shadow"]
    scenario_ids: tuple[ScenarioId, ...]
    workflow_version: str = Field(min_length=1)

    @field_validator("scenario_ids")
    @classmethod
    def unique_scenarios(cls, value: tuple[ScenarioId, ...]) -> tuple[ScenarioId, ...]:
        if not value or len(value) != len(set(value)):
            raise ValueError("scenario_ids must be non-empty and unique")
        return value


class ScenarioPolicy(StrictModel):
    scenario_id: ScenarioId
    version: str = Field(min_length=1)
    formula_version: str = Field(min_length=1)
    permission_version: str = Field(min_length=1)
    source_ref_ids: tuple[str, ...]
    required_sources: tuple[str, ...]
    parameters: dict[str, JsonValue]
    risk_level: RiskLevel
    owner: str = Field(min_length=1)
    review_at: datetime | None = None
    recommendation_code: str = Field(min_length=1)
    expected_result: str | None = None
    client_dependency: str | None = None
    do_nothing: str = Field(min_length=1)

    _review_at_utc = field_validator("review_at")(
        lambda value: None if value is None else _utc(value)
    )

    @field_validator("source_ref_ids", "required_sources")
    @classmethod
    def nonempty_unique_tuple(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value or any(not item for item in value) or len(value) != len(set(value)):
            raise ValueError("policy references must be non-empty and unique")
        return value

    @field_validator("parameters")
    @classmethod
    def safe_parameters(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        _reject_keys(value, _SECRET_KEYS, "secret-like policy field")
        _reject_keys(value, _EXECUTION_KEYS, "executable policy field")
        return value


class OpenActionContractRef(StrictModel):
    contract_id: str = Field(min_length=1)
    client_id: str = Field(min_length=1)
    cabinet_id: str = Field(min_length=1)
    scenario_id: ScenarioId
    state: Literal["proposed", "review_pending", "approved", "measuring"]
    version: int = Field(ge=1)
    trigger_fingerprint: str = Field(min_length=1)
    facts_fingerprint: str = Field(min_length=1)
    evidence_hash: str = Field(min_length=1)
    decision_state_version: str = Field(min_length=1)


class ScenarioInput(StrictModel):
    scenario_id: ScenarioId
    snapshot: SnapshotRef
    context: ContextEnvelope
    policy_version: str = Field(min_length=1)
    policy: ScenarioPolicy | None
    open_contracts: tuple[OpenActionContractRef, ...] = ()

    @model_validator(mode="after")
    def bind_tenant_snapshot_and_policy(self) -> ScenarioInput:
        tenant = (self.snapshot.client_id, self.snapshot.cabinet_id)
        client = self.context.client_context
        if (client.client_id, client.cabinet_id) != tenant:
            raise ValueError("client context не принадлежит snapshot")
        if self.context.snapshot_id != self.snapshot.snapshot_id:
            raise ValueError("ContextEnvelope не принадлежит snapshot")
        if client.passport_version != self.snapshot.passport_version:
            raise ValueError("passport version не совпадает со snapshot")
        if self.policy is not None:
            if (
                self.policy.scenario_id != self.scenario_id
                or self.policy.version != self.policy_version
            ):
                raise ValueError("scenario policy не совпадает с ScenarioInput")
            synthetic_policy = self.policy.version.startswith("SYNTH-")
            if synthetic_policy != (self.snapshot.data_mode == "synthetic"):
                raise ValueError("synthetic policy запрещена для real snapshot и наоборот")
            if self.policy.formula_version != self.context.kpi_formula_version:
                raise ValueError("formula version не совпадает с ContextEnvelope")
            if self.policy.permission_version != self.context.permission_version:
                raise ValueError("permission version не совпадает с ContextEnvelope")
        for contract in self.open_contracts:
            if (
                contract.client_id,
                contract.cabinet_id,
            ) != tenant or contract.scenario_id != self.scenario_id:
                raise ValueError("open Action Contract не принадлежит scenario tenant")
        return self


class DeterministicScenarioResult(StrictModel):
    scenario_id: ScenarioId
    status: ScenarioStatus
    trigger_fingerprint: str = Field(min_length=1)
    facts_fingerprint: str = Field(min_length=1)
    evidence_hash: str = Field(min_length=1)
    decision_state_fingerprint: str = Field(min_length=1)
    deterministic_inputs: dict[str, JsonValue]
    deterministic_outputs: dict[str, JsonValue]
    evidence_ref_ids: tuple[str, ...]
    counterevidence_ref_ids: tuple[str, ...]
    missing_data: tuple[str, ...]
    reason_codes: tuple[str, ...]
    state_trace: tuple[WorkflowState, ...]


class TypedFailure(StrictModel):
    code: str = Field(min_length=1)
    missing_data: tuple[str, ...] = ()
    detail: str | None = None


class ActionContractDraft(StrictModel):
    action_contract_id: str = Field(min_length=1)
    version: int = Field(ge=1)
    prior_contract_id: str | None = None
    client_id: str = Field(min_length=1)
    cabinet_id: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    scenario_id: ScenarioId
    state: Literal["review_pending"]
    domain: ActionDomain
    trigger_fingerprint: str = Field(min_length=1)
    facts_fingerprint: str = Field(min_length=1)
    evidence_hash: str = Field(min_length=1)
    decision_state_fingerprint: str = Field(min_length=1)
    risk_level: RiskLevel
    policy_version: str = Field(min_length=1)
    permission_version: str = Field(min_length=1)
    evidence_ref_ids: tuple[str, ...]
    counterevidence_ref_ids: tuple[str, ...]
    missing_data: tuple[str, ...]
    recommendation_code: str = Field(min_length=1)
    expected_result: str = Field(min_length=1)
    review_at: datetime
    owner: str = Field(min_length=1)
    client_dependency: str | None = None
    do_nothing: str = Field(min_length=1)
    requires_human: bool
    reversible: bool

    _review_at_utc = field_validator("review_at")(_utc)

    @model_validator(mode="after")
    def shadow_draft_cannot_grant_execution(self) -> ActionContractDraft:
        if not self.requires_human:
            raise ValueError("Phase 3 Action Contract всегда требует human review")
        if self.reversible:
            raise ValueError("Phase 3 draft не является исполнимым reversible command")
        return self


class CycleResult(StrictModel):
    cycle_id: str = Field(min_length=1)
    client_id: str = Field(min_length=1)
    cabinet_id: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    scenario_ids: tuple[ScenarioId, ...]
    workflow_version: str = Field(min_length=1)
    status: CycleStatus
    data_mode: Literal["real", "synthetic"]
    snapshot_checksum: str = Field(min_length=1)
    passport_version: str = Field(min_length=1)
    data_contract_version: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)
    policy_versions: dict[str, str]
    tool_versions: dict[str, str]
    input_hash: str = Field(min_length=1)
    result_hash: str = Field(min_length=1)
    scenario_results: tuple[DeterministicScenarioResult, ...]
    action_drafts: tuple[ActionContractDraft, ...] = ()
    incident_ids: tuple[str, ...] = ()


class CycleInputBundle(StrictModel):
    request: CycleRequest
    global_knowledge: VersionedKnowledge
    client_context: ClientContext
    operational_data: tuple[SourceRef, ...]
    scenario_policies: tuple[ScenarioPolicy, ...]
    methodology_version: str = Field(min_length=1)
    kpi_formula_version: str = Field(min_length=1)
    permission_version: str = Field(min_length=1)
    tool_versions: dict[str, str]

    @model_validator(mode="after")
    def bind_bundle_to_request(self) -> CycleInputBundle:
        request_tenant = (self.request.client_id, self.request.cabinet_id)
        if (self.client_context.client_id, self.client_context.cabinet_id) != request_tenant:
            raise ValueError("client context не принадлежит CycleRequest")
        if self.client_context.passport_version != self.client_context.version:
            raise ValueError("passport version mismatch")
        for source in self.operational_data:
            if (
                source.client_id,
                source.cabinet_id,
            ) != request_tenant or source.snapshot_id != self.request.snapshot_id:
                raise ValueError("SourceRef не принадлежит CycleRequest")
        source_ref_ids = [source.source_ref_id for source in self.operational_data]
        if len(source_ref_ids) != len(set(source_ref_ids)):
            raise ValueError("DUPLICATE_SOURCE_REF_ID")
        semantic_locators = [(source.source, source.locator) for source in self.operational_data]
        if len(semantic_locators) != len(set(semantic_locators)):
            raise ValueError("DUPLICATE_SOURCE_SEMANTIC_LOCATOR")
        policy_ids = [policy.scenario_id for policy in self.scenario_policies]
        if len(policy_ids) != len(set(policy_ids)):
            raise ValueError("scenario policies must be unique")
        if not self.tool_versions or any(
            not key or not value for key, value in self.tool_versions.items()
        ):
            raise ValueError("tool_versions must be non-empty and versioned")
        return self

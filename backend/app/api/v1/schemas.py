from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class CompanyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticker: str
    name: str
    accounting_standard: str | None = None
    reporting_basis_default: str


class PeriodRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fiscal_year: int
    label: str
    period_type: str
    source_period_code: str
    start_date: date
    end_date: date
    instant_date: date


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    file_name: str
    file_role: str
    parse_status: str
    file_size_bytes: int | None = None
    sha256: str | None = None
    source_url: str


class StatementFactRead(BaseModel):
    concept: str
    label_id: str | None = None
    label_en: str | None = None
    statement_type: str
    value_normalized: Decimal
    value_display: str
    display_scale: int
    currency: str | None = None
    unit: str
    source_scale: int
    source_fact_id: str
    source_context_ref: str
    source_file: str
    source_url: str
    validation_status: str
    document_version: int
    publication_status: str
    period_kind: str
    duration_kind: str
    standard_account: str | None = None
    mapping_status: str | None = None
    source_context_details: dict[str, Any] = Field(default_factory=dict)


class StatementRead(BaseModel):
    ticker: str
    company_name: str
    period: str
    period_label: str
    basis: str
    statement: str
    facts: list[StatementFactRead]


class IngestionJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_type: str
    status: str
    parameters: dict[str, Any]
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class UserRead(BaseModel):
    user_id: int
    email: str
    display_name: str
    roles: list[str]


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


class MetricRead(BaseModel):
    id: int
    code: str
    name: str
    value: Decimal | None = None
    unit: str
    calculation_status: str
    unavailable_reason: str | None = None
    validation_warnings: list[str]
    formula_version: str
    formula_definition: dict[str, Any]
    input_document_versions: list[int]
    publication_status: str | None = None


class DerivedValueRead(BaseModel):
    id: int
    concept: str
    period: str
    period_type: str
    value: Decimal | None = None
    status: str
    formula_code: str
    formula_version: str
    unavailable_reason: str | None = None
    validation_warnings: list[str]
    source_context_details: dict[str, Any]


class MappingRead(BaseModel):
    id: int
    source_account_name: str
    source_taxonomy_concept: str | None = None
    standard_account_code: str | None = None
    status: str
    confidence: Decimal
    rule_code: str | None = None
    rule_version: str | None = None
    evidence: str | None = None
    reason: str | None = None
    is_current: bool


class ValidationLogRead(BaseModel):
    id: int
    rule_code: str
    severity_level: str
    rule_category: str
    entity_type: str
    entity_id: str
    message: str
    is_blocking: bool
    status: str
    review_policy: str | None = None
    validation_run_id: int | None = None
    created_at: datetime


class ValidationRunRead(BaseModel):
    id: int
    scope_type: str
    scope_id: str
    status: str
    summary: dict[str, Any]
    started_at: datetime
    finished_at: datetime | None = None


class ValidationOutcomeRead(BaseModel):
    run: ValidationRunRead
    issues: list[ValidationLogRead]
    can_publish: bool
    failures: list[str]
    warnings: list[str]


class AcknowledgeRequest(BaseModel):
    reason: str


class ApproveRequest(BaseModel):
    reason: str


class RestatementRead(BaseModel):
    id: int
    predecessor_fact_id: int
    successor_fact_id: int
    concept: str
    period: str
    document: str
    document_version: int
    reason: str
    filing_date: date | None = None
    approval_status: str
    created_at: datetime | None = None


class PublicationRequest(BaseModel):
    ticker: str
    period: str
    basis: Literal["consolidated", "separate"] = "consolidated"


class PublicationRead(BaseModel):
    id: int
    status: str
    validation_run_id: int | None = None
    facts_published: int
    metrics_published: int
    created_at: datetime


class PublicationEventRead(BaseModel):
    id: int
    reporting_basis: str
    status: str
    validation_run_id: int | None = None
    previous_event_id: int | None = None
    publication_metadata: dict[str, Any]
    created_at: datetime


class AuditEventRead(BaseModel):
    id: int
    actor_id: int | None = None
    action: str
    entity_type: str
    entity_id: str
    before_state: dict[str, Any] | None = None
    after_state: dict[str, Any] | None = None
    reason: str | None = None
    request_context: dict[str, Any]
    created_at: datetime

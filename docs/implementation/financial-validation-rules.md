# Financial Validation Rules

**Status:** Phase 2, milestone M2.
**Scope:** Severity, categories, workflow states, and publication gate behavior.

## Severity and categories

- `BLOCKER`: prevents publication; cannot be overridden.
- `ERROR`: prevents publication; cannot be overridden.
- `WARNING`: may be published only after reviewer acknowledgement.
- `INFO`: informational.

Categories used by M2: `document`, `extraction`, `accounting`, `period`, `reporting_basis`, `mapping`, `metric`, `publication`, `other`.

## Workflow states

`ValidationRun.status` progresses through `pending`, `processing`, then one of `validation_failed`, `review_required`, or `validated`. Successful publication sets the run to `published`. Superseded publication cycles retain prior runs for audit.

`ValidationLog.status` values are `open` and `overridden`. Only `WARNING` findings can be overridden, and overrides store reviewer, timestamp, reason, and review policy.

## M1 rules retained

| Rule | Severity | Meaning |
| --- | --- | --- |
| `XFORM-001` | ERROR | Core concept reconciliation across source formats. |
| `FACT-001` | ERROR | Bank balance equation reconciliation. |
| `DOC-001` | ERROR | Document parse or checksum failure. |
| `ARELLE-001` | ERROR | Offline XBRL taxonomy validation failure. |

## M2 scope rules

| Rule | Severity | Category | Condition |
| --- | --- | --- | --- |
| `DOC-003` | BLOCKER | document | No source documents for the publication scope, or document identity/period mismatch. |
| `DOC-002` | BLOCKER | document | Duplicate source document and file role. |
| `DOC-001` | ERROR | document | Document not parsed or missing checksum/size. |
| `FACT-004` | BLOCKER | extraction | No current facts for the publication scope. |
| `FACT-002` | BLOCKER | extraction | Duplicate source fact in the current population. |
| `FACT-003` | BLOCKER/ERROR | extraction | Invalid numeric value, missing unit/currency/context, or fact not validated. |
| `PER-001` | ERROR | period | Invalid period kind, invalid instant/duration dates, or source context reused with inconsistent period/basis dimensions. |
| `BASIS-001` | BLOCKER | reporting_basis | Mixed reporting basis, unknown basis, or basis mismatch. |
| `MAP-001` | BLOCKER | mapping | Fact has no approved source account mapping or references an inactive standard account. |
| `MET-001` | BLOCKER | metric | Current metric is invalid or uses an unsupported formula version. Unavailable metrics with explicit reasons are allowed. |
| `PUB-001` | WARNING | publication | Scope was previously published; republishing supersedes the prior event. |
| `FACT-001` | ERROR | accounting | Bank balance equation does not reconcile. |

## Publication gate

Publication is rejected when any of the following exists:

- Any `BLOCKER` or `ERROR` finding in the freshly created validation run.
- Any `WARNING` finding without a recorded reviewer acknowledgement for the same rule, entity type, and entity ID.
- A current metric with `calculation_status == invalid` or an unsupported formula version. Unavailable metrics with explicit reasons remain visible but are not published as values.
- Missing explicit consolidated/separate basis.

On success, current facts and metrics receive `publication_status=published`, metrics receive `published_at`/`published_by`, a new `publication_event` is created, and the previous published event is marked `superseded`.

## Manual review constraints

- `POST /api/v1/validation/warnings/{id}/acknowledge` requires `reviewer` or `admin`.
- `POST /api/v1/normalization/mappings/{id}/approve` requires `reviewer` or `admin`.
- `POST /api/v1/restatements/{id}/approve` requires `reviewer` or `admin`.
- `POST /api/v1/publication/publish` requires `publisher` or `admin`.
- Every sensitive action writes an `audit_event` with sanitized request context; tokens are never stored.

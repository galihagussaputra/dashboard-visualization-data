import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import (
    Company,
    CompanySector,
    DataSource,
    FactRevision,
    FinancialAccount,
    FinancialDocument,
    FinancialFact,
    FinancialPeriod,
    IngestionJob,
    Sector,
    TaxonomyVersion,
    ValidationLog,
)
from app.normalization.accounts import AccountNormalizer, TAXONOMY_CODE, ensure_reference_data
from app.normalization.periods import classify_context, normalize_duration_kind
from app.normalization.registry import ALL_CONCEPTS
from app.parsers.arelle import validate_instance
from app.parsers.inline_xbrl import parse_inline_zip
from app.parsers.instance_xbrl import parse_instance_zip
from app.parsers.models import Period
from app.parsers.pdf import parse_pdf
from app.parsers.xlsx import parse_xlsx
from app.validation.engine import build_validation_issues, has_errors

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "bbca-2025"
RAW_DIR = Path("/app/raw_docs")
TAXONOMY_NAMESPACE = "http://www.idx.co.id/xbrl/taxonomy/2020-01-01/cor"
TAXONOMY_VERSION = "2020-01-01"

PARSERS = {
    "instance_xbrl": parse_instance_zip,
    "inline_xbrl": parse_inline_zip,
    "xlsx": parse_xlsx,
    "pdf": parse_pdf,
}

FILE_ROLE_TO_SOURCE = {
    "instance_xbrl": "instance_xbrl",
    "inline_xbrl": "inline_xbrl",
    "spreadsheet": "xlsx",
    "pdf": "pdf",
}


@dataclass(frozen=True)
class IngestionSummary:
    job_id: int
    documents: int
    facts: int
    validation_logs: int
    status: str


class FixtureIngestionService:
    def __init__(self, db: Session, fixture_dir: Path = FIXTURE_DIR, raw_dir: Path = RAW_DIR):
        self.db = db
        self.fixture_dir = fixture_dir
        self.raw_dir = raw_dir
        self.settings = get_settings()

    def run(self, ticker: str = "BBCA", year: int = 2025, period_code: str = "audit") -> IngestionSummary:
        metadata = json.loads((self.fixture_dir / "metadata.json").read_text(encoding="utf-8"))
        if metadata["company"]["ticker"] != ticker:
            raise ValueError("fixture ticker mismatch")
        if metadata["period"]["fiscal_year"] != year:
            raise ValueError("fixture fiscal year mismatch")
        if metadata["period"]["source_period_code"] != period_code:
            raise ValueError("fixture period code mismatch")

        now = datetime.now(timezone.utc)
        stale_jobs = self.db.scalars(
            select(IngestionJob).where(
                IngestionJob.job_type == "fixture_ingestion",
                IngestionJob.status == "running",
            )
        ).all()
        stale_job_ids = [stale.id for stale in stale_jobs]
        if stale_job_ids:
            stale_logs = self.db.scalars(
                select(ValidationLog).where(
                    ValidationLog.log_metadata["ingestion_job_id"].astext.in_(
                        [str(job_id) for job_id in stale_job_ids]
                    )
                )
            ).all()
            for stale_log in stale_logs:
                self.db.delete(stale_log)
            for stale in stale_jobs:
                stale.status = "failed"
                stale.error_message = "superseded by new ingestion run"
                stale.finished_at = now
            self.db.commit()

        job = IngestionJob(
            job_type="fixture_ingestion",
            status="running",
            parameters={"ticker": ticker, "year": year, "period": period_code, "source": "local_fixture"},
            started_at=now,
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)

        try:
            data_source = self._data_source()
            sector = self._sector(metadata["company"])
            company = self._company(metadata["company"], data_source.id)
            self._company_sector(company.id, sector.id, year)
            period = self._period(company.id, metadata["period"], year)
            job.company_id = company.id
            job.period_id = period.id
            self.db.commit()

            taxonomy = self._taxonomy()
            ensure_reference_data(self.db)
            normalizer = AccountNormalizer(self.db)
            period_model = Period(
                start_date=date.fromisoformat(metadata["period"]["start_date"]),
                end_date=date.fromisoformat(metadata["period"]["end_date"]),
                instant_date=date.fromisoformat(metadata["period"]["instant_date"]),
            )

            documents: dict[str, FinancialDocument] = {}
            document_checks: dict[str, tuple[bool, bool]] = {}
            source_paths: dict[str, Path] = {}
            for attachment in metadata["attachments"]:
                document, size_match, hash_match, stored_path = self._document(
                    job.id, data_source.id, company.id, period.id, attachment, ticker, year, period_code
                )
                role = attachment["file_role"]
                source_key = FILE_ROLE_TO_SOURCE[role]
                documents[source_key] = document
                source_paths[source_key] = stored_path
                document_checks[attachment["file_name"]] = (size_match, hash_match)

            sources = {
                source_key: parser(source_paths[source_key], period_model)
                for source_key, parser in PARSERS.items()
            }
            arelle_result = validate_instance(source_paths["instance_xbrl"])
            issues = build_validation_issues(sources, arelle_result, document_checks)
            for issue in issues:
                issue_metadata = dict(issue.log_metadata or {})
                issue_metadata["ingestion_job_id"] = job.id
                self.db.add(
                    ValidationLog(
                        rule_code=issue.rule_code,
                        severity=issue.severity,
                        entity_type=issue.entity_type,
                        entity_id=issue.entity_id,
                        message=issue.message,
                        expected_value=issue.expected_value,
                        actual_value=issue.actual_value,
                        log_metadata=issue_metadata,
                        severity_level=issue.severity.upper(),
                        rule_category=issue.rule_category,
                        is_blocking=issue.severity in {"error", "blocker"},
                    )
                )

            if has_errors(issues):
                job.status = "failed"
                job.error_message = "validation errors blocked ingestion"
                job.finished_at = datetime.now(timezone.utc)
                self.db.commit()
                raise RuntimeError(job.error_message)

            accounts = self._accounts(taxonomy.id)
            fact_count = self._facts(
                job.id,
                company.id,
                period.id,
                documents["instance_xbrl"].id,
                sources["instance_xbrl"],
                accounts,
                metadata["company"]["reporting_basis_default"],
                period,
                normalizer,
                taxonomy,
                metadata["company"]["subsector"],
            )

            for document in documents.values():
                document.parse_status = "parsed"
                document.parsed_at = datetime.now(timezone.utc)
            job.status = "validated"
            job.finished_at = datetime.now(timezone.utc)
            self.db.commit()

            return IngestionSummary(
                job_id=job.id,
                documents=len(documents),
                facts=fact_count,
                validation_logs=len(issues),
                status=job.status,
            )
        except Exception as exc:
            self.db.rollback()
            failed_job = self.db.get(IngestionJob, job.id)
            if failed_job is not None:
                failed_job.status = "failed"
                failed_job.error_message = str(exc)[:2000]
                failed_job.finished_at = datetime.now(timezone.utc)
                self.db.commit()
            raise

    def _first(self, model, **filters):
        return self.db.scalars(select(model).filter_by(**filters)).first()

    def _data_source(self) -> DataSource:
        source = self._first(DataSource, code="idx_id")
        if source is None:
            source = DataSource(
                code="idx_id",
                display_name="Indonesia Stock Exchange",
                base_url=self.settings.idx_base_url,
                is_active=True,
            )
            self.db.add(source)
            self.db.flush()
        return source

    def _sector(self, company_metadata: dict) -> Sector:
        code = company_metadata["sector"].split(".", 1)[0]
        sector = self._first(Sector, code=code)
        if sector is None:
            sector = Sector(
                code=code,
                sector=company_metadata["sector"],
                subsector=company_metadata["subsector"],
                taxonomy_entry_point="Financial and Sharia",
            )
            self.db.add(sector)
            self.db.flush()
        return sector

    def _company(self, company_metadata: dict, data_source_id: int) -> Company:
        company = self._first(Company, ticker=company_metadata["ticker"])
        if company is None:
            company = Company(
                ticker=company_metadata["ticker"],
                name=company_metadata["name"],
                source_company_id=company_metadata["source_company_id"],
                data_source_id=data_source_id,
                accounting_standard=company_metadata["accounting_standard"],
                reporting_basis_default=company_metadata["reporting_basis_default"],
                is_active=True,
                company_metadata=dict(company_metadata),
            )
            self.db.add(company)
            self.db.flush()
        return company

    def _company_sector(self, company_id: int, sector_id: int, year: int) -> None:
        valid_from = date(year, 1, 1)
        existing = self._first(
            CompanySector, company_id=company_id, sector_id=sector_id, valid_from=valid_from
        )
        if existing is None:
            self.db.add(CompanySector(company_id=company_id, sector_id=sector_id, valid_from=valid_from))
            self.db.flush()

    def _period(self, company_id: int, period_metadata: dict, year: int) -> FinancialPeriod:
        period = self._first(
            FinancialPeriod,
            company_id=company_id,
            fiscal_year=year,
            period_type="FY",
            period_sequence=4,
        )
        if period is None:
            period = FinancialPeriod(
                company_id=company_id,
                fiscal_year=year,
                calendar_year=year,
                period_type="FY",
                period_sequence=4,
                is_ytd=True,
                start_date=date.fromisoformat(period_metadata["start_date"]),
                end_date=date.fromisoformat(period_metadata["end_date"]),
                instant_date=date.fromisoformat(period_metadata["instant_date"]),
                source_period_code=period_metadata["source_period_code"],
                label=period_metadata["label"],
            )
            self.db.add(period)
            self.db.flush()
        return period

    def _taxonomy(self) -> TaxonomyVersion:
        taxonomy = self._first(TaxonomyVersion, code="idx-taxonomy-2020", version=TAXONOMY_VERSION)
        if taxonomy is None:
            taxonomy = TaxonomyVersion(
                code="idx-taxonomy-2020",
                version=TAXONOMY_VERSION,
                namespace=TAXONOMY_NAMESPACE,
                entry_points=["1000000", "4220000", "4322000", "4510000"],
                source_url="https://www.idx.id/media/oxziiysv/04_idx_taxonomy_2020_guide_ver_2.pdf",
            )
            self.db.add(taxonomy)
            self.db.flush()
        return taxonomy

    def _document(
        self,
        job_id: int,
        data_source_id: int,
        company_id: int,
        period_id: int,
        attachment: dict,
        ticker: str,
        year: int,
        period_code: str,
    ) -> tuple[FinancialDocument, bool, bool, Path]:
        source_path = self.fixture_dir / attachment["file_name"]
        destination = self.raw_dir / ticker / str(year) / period_code / attachment["file_name"]
        if not destination.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination)
        stored_bytes = destination.read_bytes()
        actual_size = len(stored_bytes)
        actual_hash = hashlib.sha256(stored_bytes).hexdigest()
        size_match = actual_size == attachment["file_size"]
        hash_match = actual_hash == attachment["sha256"]

        document = self._first(
            FinancialDocument,
            data_source_id=data_source_id,
            source_document_id=attachment["source_document_id"],
            file_type=attachment["file_type"],
            file_role=attachment["file_role"],
        )
        if document is None:
            document = FinancialDocument(
                data_source_id=data_source_id,
                company_id=company_id,
                period_id=period_id,
                ingestion_job_id=job_id,
                source_document_id=attachment["source_document_id"],
                source_file_id=attachment["source_file_id"],
                file_name=attachment["file_name"],
                file_type=attachment["file_type"],
                file_role=attachment["file_role"],
                source_url=self.settings.idx_base_url + attachment["source_path"],
                raw_storage_path=str(destination),
                file_size_bytes=actual_size,
                source_file_size=attachment["file_size"],
                sha256=actual_hash,
                parse_status="pending",
                source_metadata={"stored_from": "local_fixture", "file_name": attachment["file_name"]},
            )
            self.db.add(document)
            self.db.flush()
        else:
            document.company_id = company_id
            document.period_id = period_id
            document.ingestion_job_id = job_id
            document.raw_storage_path = str(destination)
            document.file_size_bytes = actual_size
            document.source_file_size = attachment["file_size"]
            document.sha256 = actual_hash
            document.parse_status = "pending"
        return document, size_match, hash_match, destination

    def _accounts(self, taxonomy_id: int) -> dict[str, int]:
        accounts: dict[str, int] = {}
        for spec in ALL_CONCEPTS:
            account = self._first(
                FinancialAccount, taxonomy_version_id=taxonomy_id, concept_code=spec.concept
            )
            if account is None:
                account = FinancialAccount(
                    taxonomy_version_id=taxonomy_id,
                    concept_code=spec.concept,
                    concept_qname=f"idx-cor:{spec.local_name}",
                    namespace=TAXONOMY_NAMESPACE,
                    label_id=spec.label_id,
                    label_en=spec.label_en,
                    statement_type=spec.statement_type,
                    normal_sign=spec.normal_sign,
                    data_type="per_share" if spec.unit == "IDRPerShares" else "monetary",
                    unit_hint=spec.unit,
                    is_abstract=False,
                )
                self.db.add(account)
                self.db.flush()
            accounts[spec.concept] = account.id
        return accounts

    def _facts(
        self,
        job_id: int,
        company_id: int,
        period_id: int,
        document_id: int,
        authoritative_facts: dict,
        accounts: dict[str, int],
        reporting_basis: str,
        period: FinancialPeriod,
        normalizer: AccountNormalizer,
        taxonomy: TaxonomyVersion,
        industry: str | None,
    ) -> int:
        created = 0
        document = self.db.get(FinancialDocument, document_id)
        for spec in ALL_CONCEPTS:
            parsed = authoritative_facts[spec.concept]
            existing = self.db.scalars(
                select(FinancialFact)
                .where(
                    FinancialFact.document_id == document_id,
                    FinancialFact.source_fact_id == parsed.source_fact_id,
                )
                .order_by(FinancialFact.fact_version.desc())
            ).first()
            value = Decimal(str(parsed.value_normalized))
            mapping = normalizer.resolve(
                source_account_name=spec.label_en,
                company_id=company_id,
                taxonomy_version_id=taxonomy.id,
                source_taxonomy_code=TAXONOMY_CODE,
                source_taxonomy_concept=spec.concept,
                industry=industry,
                statement_type=spec.statement_type,
            )
            period_kind = classify_context(
                parsed.context_instant_date,
                parsed.context_start_date,
                parsed.context_end_date,
            )
            duration_kind = (
                "not_applicable"
                if period_kind == "instant"
                else normalize_duration_kind(period.period_type, period.is_ytd)
            )
            context_details = {
                "source_context_ref": parsed.source_context_ref,
                "context_start_date": parsed.context_start_date.isoformat() if parsed.context_start_date else None,
                "context_end_date": parsed.context_end_date.isoformat() if parsed.context_end_date else None,
                "context_instant_date": parsed.context_instant_date.isoformat() if parsed.context_instant_date else None,
                "taxonomy_code": TAXONOMY_CODE,
                "taxonomy_concept": spec.concept,
                "source_scale": parsed.source_scale,
                "source_file": parsed.source_file,
                "source_period_code": period.source_period_code,
            }
            if existing is not None and existing.value_normalized == value:
                existing.is_current = True
                existing.validation_status = "passed"
                existing.mapping_id = mapping.id
                existing.period_kind = period_kind
                existing.duration_kind = duration_kind
                existing.accounting_definition_key = spec.concept
                existing.document_version = document.document_version
                existing.publication_status = "draft"
                existing.source_context_details = context_details
                continue

            version = existing.fact_version + 1 if existing is not None else 1
            successor = FinancialFact(
                company_id=company_id,
                period_id=period_id,
                document_id=document_id,
                account_id=accounts[spec.concept],
                ingestion_job_id=job_id,
                source_fact_id=parsed.source_fact_id,
                source_context_ref=parsed.source_context_ref,
                context_start_date=parsed.context_start_date,
                context_end_date=parsed.context_end_date,
                context_instant_date=parsed.context_instant_date,
                value_original=parsed.value_original,
                value_normalized=value,
                currency=parsed.currency,
                unit=parsed.unit,
                source_scale=parsed.source_scale,
                source_decimals=parsed.decimals,
                reporting_basis=reporting_basis,
                is_restated=existing is not None,
                fact_version=version,
                is_current=True,
                validation_status="passed",
                period_kind=period_kind,
                duration_kind=duration_kind,
                accounting_definition_key=spec.concept,
                document_version=document.document_version,
                publication_status="draft",
                mapping_id=mapping.id,
                source_context_details=context_details,
            )
            self.db.add(successor)
            self.db.flush()
            if existing is not None:
                existing.is_current = False
                existing.superseded_by = successor.id
                existing.validation_status = "passed"
                self.db.add(
                    FactRevision(
                        predecessor_fact_id=existing.id,
                        successor_fact_id=successor.id,
                        company_id=company_id,
                        period_id=period_id,
                        document_id=document_id,
                        revision_reason="source value changed on re-ingestion",
                        filing_date=document.filing_date,
                        document_version=document.document_version,
                        approval_status="pending",
                        source_metadata={"source_fact_id": parsed.source_fact_id},
                    )
                )
            created += 1
        self.db.flush()
        return created

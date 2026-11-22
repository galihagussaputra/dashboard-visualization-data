import argparse
import logging

from app.core.db import SessionLocal
from app.ingestion.service import FixtureIngestionService

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="IDX ingestion runner")
    parser.add_argument("--ticker", default="BBCA")
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--period", default="audit")
    parser.add_argument("--source", choices=["fixture", "idx"], default="fixture")
    args = parser.parse_args()

    if args.source != "fixture":
        raise SystemExit("live IDX ingestion is disabled; use --source fixture for M1")

    with SessionLocal() as db:
        summary = FixtureIngestionService(db).run(args.ticker, args.year, args.period)

    logger.info(
        "Ingestion completed",
        extra={
            "job_id": summary.job_id,
            "ticker": args.ticker,
            "year": args.year,
            "period": args.period,
            "facts": summary.facts,
        },
    )
    print(
        f"M1 ingestion job={summary.job_id} status={summary.status} "
        f"documents={summary.documents} facts={summary.facts} logs={summary.validation_logs}"
    )


if __name__ == "__main__":
    main()

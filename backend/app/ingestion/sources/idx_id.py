import hashlib
import time
from pathlib import Path

import httpx

from app.core.config import get_settings

REPORT_ENDPOINT = "/primary/ListedCompany/GetFinancialReport"
EMITEN_ENDPOINT = "/primary/Helper/GetEmiten"


class IDXClient:
    def __init__(self, client: httpx.Client | None = None):
        settings = get_settings()
        self.settings = settings
        self.base_url = settings.idx_base_url.rstrip("/")
        self.delay = settings.idx_request_delay_seconds
        self._client = client or httpx.Client(
            base_url=self.base_url,
            headers={"User-Agent": settings.idx_user_agent, "Accept": "application/json"},
            timeout=30.0,
            follow_redirects=True,
        )

    def _throttle(self) -> None:
        if self.delay > 0:
            time.sleep(self.delay)

    def get_tickers(self) -> list[dict]:
        self._throttle()
        response = self._client.get(EMITEN_ENDPOINT, params={"emitenType": "s"})
        response.raise_for_status()
        return response.json()

    def get_financial_reports(self, ticker: str, year: int, period: str) -> list[dict]:
        self._throttle()
        response = self._client.get(
            REPORT_ENDPOINT,
            params={
                "indexFrom": 0,
                "pageSize": 50,
                "year": year,
                "reportType": "rdf",
                "EmitenType": "s",
                "periode": period,
                "kodeEmiten": ticker,
                "SortColumn": "",
                "SortOrder": "",
            },
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("Results", []) or []

    def download(self, source_path: str, destination: str | Path) -> tuple[Path, int, str]:
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        self._throttle()
        response = self._client.get(source_path, headers={"Accept": "*/*"})
        response.raise_for_status()
        target.write_bytes(response.content)
        digest = hashlib.sha256(response.content).hexdigest()
        return target, len(response.content), digest

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "IDXClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

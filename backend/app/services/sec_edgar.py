import asyncio
import re
import time
from typing import List, Optional, TypedDict

import httpx
from bs4 import BeautifulSoup

from app.config import settings

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
INDEX_URL = "https://www.sec.gov/Archives/edgar/data/{cik_short}/{accession_nodash}/index.json"
DOC_URL = "https://www.sec.gov/Archives/edgar/data/{cik_short}/{accession_nodash}/{filename}"

TRACKED_FORMS = ("10-K", "10-Q", "8-K")

# SEC fair-access guidelines: stay well under 10 requests/second.
_MIN_REQUEST_INTERVAL = 0.15
_last_request_at = 0.0
_request_lock = asyncio.Lock()


def _headers() -> dict:
    return {"User-Agent": f"NarrativeTracker research tool ({settings.sec_contact_email})"}


async def _get(client: httpx.AsyncClient, url: str) -> httpx.Response:
    global _last_request_at
    async with _request_lock:
        wait = _MIN_REQUEST_INTERVAL - (time.monotonic() - _last_request_at)
        if wait > 0:
            await asyncio.sleep(wait)
        response = await client.get(url, headers=_headers(), timeout=30.0)
        _last_request_at = time.monotonic()
    response.raise_for_status()
    return response


class FilingInfo(TypedDict):
    form: str
    filing_date: str
    accession_number: str
    document_url: str
    is_exhibit: bool


def _raw_entries_since(entries: dict, since_date: str) -> List[dict]:
    forms = entries.get("form", [])
    return [
        {
            "form": forms[i],
            "filing_date": entries["filingDate"][i],
            "accession_number": entries["accessionNumber"][i],
            "primary_document": entries["primaryDocument"][i],
        }
        for i in range(len(forms))
        if forms[i] in TRACKED_FORMS and entries["filingDate"][i] >= since_date
    ]


async def get_filings_since(
    client: httpx.AsyncClient, cik: str, since_date: str
) -> List[FilingInfo]:
    """Fetch all 10-K/10-Q/8-K filings on or after since_date (YYYY-MM-DD) for a company.

    8-Ks are only included when they carry a press-release exhibit (EX-99.x) —
    most 8-Ks are routine (exec changes, dividends, etc.) and not earnings releases.
    """
    response = await _get(client, SUBMISSIONS_URL.format(cik=cik))
    data = response.json()
    recent = data["filings"]["recent"]

    raw_entries = _raw_entries_since(recent, since_date)

    oldest_in_recent = min(recent["filingDate"], default=None)
    if oldest_in_recent and oldest_in_recent > since_date:
        # The "recent" window doesn't reach back far enough — pull older shard files.
        for shard in data["filings"].get("files", []):
            if shard.get("filingTo") and shard["filingTo"] < since_date:
                continue
            try:
                shard_response = await _get(
                    client, f"https://data.sec.gov/submissions/{shard['name']}"
                )
            except httpx.HTTPStatusError:
                continue
            raw_entries += _raw_entries_since(shard_response.json(), since_date)

    cik_short = str(int(cik))
    filings: List[FilingInfo] = []

    for entry in raw_entries:
        accession_nodash = entry["accession_number"].replace("-", "")
        document_url = DOC_URL.format(
            cik_short=cik_short, accession_nodash=accession_nodash, filename=entry["primary_document"]
        )
        is_exhibit = False

        if entry["form"] == "8-K":
            exhibit_doc = await _find_earnings_exhibit(client, cik_short, accession_nodash)
            if not exhibit_doc:
                continue
            document_url = DOC_URL.format(
                cik_short=cik_short, accession_nodash=accession_nodash, filename=exhibit_doc
            )
            is_exhibit = True

        filings.append(
            FilingInfo(
                form=entry["form"],
                filing_date=entry["filing_date"],
                accession_number=entry["accession_number"],
                document_url=document_url,
                is_exhibit=is_exhibit,
            )
        )

    return filings


async def _find_earnings_exhibit(
    client: httpx.AsyncClient, cik_short: str, accession_nodash: str
) -> Optional[str]:
    """Look for the EX-99.x press-release exhibit within an 8-K filing."""
    url = INDEX_URL.format(cik_short=cik_short, accession_nodash=accession_nodash)
    try:
        response = await _get(client, url)
    except httpx.HTTPStatusError:
        return None

    items = response.json().get("directory", {}).get("item", [])
    for item in items:
        item_type = (item.get("type") or "").upper()
        if item_type.startswith("EX-99"):
            return item["name"]
    return None


async def fetch_filing_text(client: httpx.AsyncClient, url: str) -> str:
    """Download a filing document and strip it down to plain text."""
    response = await _get(client, url)
    soup = BeautifulSoup(response.text, "lxml")

    for tag in soup(["script", "style"]):
        tag.decompose()

    text = soup.get_text(separator=" ")
    return re.sub(r"\s+", " ", text).strip()

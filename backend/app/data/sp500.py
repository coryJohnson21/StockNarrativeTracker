import csv
import os
from functools import lru_cache
from typing import List, TypedDict

CSV_PATH = os.path.join(os.path.dirname(__file__), "sp500_constituents.csv")


class SP500Company(TypedDict):
    ticker: str
    company: str
    sector: str
    cik: str


@lru_cache(maxsize=1)
def get_sp500_constituents() -> List[SP500Company]:
    with open(CSV_PATH, newline="") as f:
        reader = csv.DictReader(f)
        return [
            {
                "ticker": row["Symbol"].strip(),
                "company": row["Security"].strip(),
                "sector": row["GICS Sector"].strip(),
                "cik": row["CIK"].strip().zfill(10),
            }
            for row in reader
        ]


def find_company(ticker: str) -> SP500Company | None:
    ticker = ticker.upper().strip()
    for company in get_sp500_constituents():
        if company["ticker"] == ticker:
            return company
    return None

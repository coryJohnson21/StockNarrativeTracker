"""Parse SEC Form 4 (statement of changes in beneficial ownership) XML into
open-market insider transactions. Only non-derivative purchases (code P) and
sales (code S) are kept: grants, option exercises, tax withholding, and gifts
say nothing about what the insider thinks the stock is worth."""
from dataclasses import dataclass
from datetime import date
from typing import Optional
import xml.etree.ElementTree as ET

OPEN_MARKET_CODES = {"P": True, "S": False}  # code -> is_purchase


@dataclass
class Form4Transaction:
    owner_name: str
    owner_role: str
    transaction_date: date
    transaction_code: str
    is_purchase: bool
    shares: float
    price: Optional[float]
    value: Optional[float]
    shares_owned_after: Optional[float]
    is_10b5_1: bool
    security_title: str


@dataclass
class Form4:
    issuer_symbol: Optional[str]
    issuer_name: Optional[str]
    period_of_report: Optional[date]
    transactions: list[Form4Transaction]


def _text(node: Optional[ET.Element], path: str) -> Optional[str]:
    if node is None:
        return None
    found = node.find(path)
    if found is None:
        return None
    value = found.find("value")
    text = (value.text if value is not None else found.text) or ""
    text = text.strip()
    return text or None


def _number(node: Optional[ET.Element], path: str) -> Optional[float]:
    text = _text(node, path)
    if text is None:
        return None
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return None


def _flag(node: Optional[ET.Element], path: str) -> bool:
    text = (_text(node, path) or "").lower()
    return text in ("1", "true")


def _date(text: Optional[str]) -> Optional[date]:
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _owner_role(owner: ET.Element) -> str:
    rel = owner.find("reportingOwnerRelationship")
    if rel is None:
        return "Other"
    if _flag(rel, "isOfficer"):
        return _text(rel, "officerTitle") or "Officer"
    if _flag(rel, "isDirector"):
        return "Director"
    if _flag(rel, "isTenPercentOwner"):
        return "10% owner"
    return _text(rel, "otherText") or "Other"


def _transaction_plan_flag(tx: ET.Element, document_plan: bool) -> bool:
    """Whether this transaction was made under a pre-arranged 10b5-1 plan. The
    per-transaction flag wins when present; only filings that don't carry one fall
    back to the document-level marker."""
    for path in ("transactionCoding/rule10b5-1Flag", "rule10b5-1Flag"):
        node = tx.find(path)
        if node is not None:
            return _flag(tx, path)
    return document_plan


def parse_form4(xml_text: str) -> Form4:
    root = ET.fromstring(xml_text)
    issuer = root.find("issuer")
    owners = root.findall("reportingOwner")
    owner_names = [(_text(o, "reportingOwnerId/rptOwnerName") or "Unknown") for o in owners] or ["Unknown"]
    owner_roles = [_owner_role(o) for o in owners] or ["Other"]
    owner_name = "; ".join(dict.fromkeys(owner_names))
    owner_role = "; ".join(dict.fromkeys(owner_roles))
    # Since the 2022 amendments each transaction carries its own rule10b5-1Flag;
    # older filings only mark the whole document with aff10b5One. A document-level
    # flag is a fallback, never an override: a filing that reports a scheduled sale
    # alongside a discretionary purchase must not have the purchase marked scheduled.
    document_plan = _flag(root, "aff10b5One")

    transactions: list[Form4Transaction] = []
    table = root.find("nonDerivativeTable")
    for tx in (table.findall("nonDerivativeTransaction") if table is not None else []):
        code = _text(tx, "transactionCoding/transactionCode")
        if code not in OPEN_MARKET_CODES:
            continue
        tx_date = _date(_text(tx, "transactionDate"))
        shares = _number(tx, "transactionAmounts/transactionShares")
        if tx_date is None or shares is None or shares <= 0:
            continue
        price = _number(tx, "transactionAmounts/transactionPricePerShare")
        acquired = (_text(tx, "transactionAmounts/transactionAcquiredDisposedCode") or "").upper()
        is_purchase = OPEN_MARKET_CODES[code] if acquired not in ("A", "D") else acquired == "A"
        transactions.append(
            Form4Transaction(
                owner_name=owner_name,
                owner_role=owner_role,
                transaction_date=tx_date,
                transaction_code=code,
                is_purchase=is_purchase,
                shares=shares,
                price=price,
                value=round(shares * price, 2) if price is not None else None,
                shares_owned_after=_number(tx, "postTransactionAmounts/sharesOwnedFollowingTransaction"),
                is_10b5_1=_transaction_plan_flag(tx, document_plan),
                security_title=_text(tx, "securityTitle") or "Common Stock",
            )
        )

    return Form4(
        issuer_symbol=(_text(issuer, "issuerTradingSymbol") or None),
        issuer_name=_text(issuer, "issuerName"),
        period_of_report=_date(_text(root, "periodOfReport")),
        transactions=transactions,
    )

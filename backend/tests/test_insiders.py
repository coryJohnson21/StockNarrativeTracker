from datetime import date
from types import SimpleNamespace

import pytest

from app.services.form4 import parse_form4
from app.services.insiders import net_buy_ratio, summarize_transactions
from app.services.research import InsiderSeries
from app.services.signals import insider_vs_narrative_signal

FORM4 = """<?xml version="1.0"?>
<ownershipDocument>
  <documentType>4</documentType>
  <periodOfReport>2026-09-15</periodOfReport>
  <issuer><issuerCik>0000320193</issuerCik><issuerName>Apple Inc.</issuerName><issuerTradingSymbol>AAPL</issuerTradingSymbol></issuer>
  <reportingOwner>
    <reportingOwnerId><rptOwnerCik>0001780525</rptOwnerCik><rptOwnerName>Newstead Jennifer</rptOwnerName></reportingOwnerId>
    <reportingOwnerRelationship><isOfficer>true</isOfficer><officerTitle>SVP, GC and Government Affairs</officerTitle></reportingOwnerRelationship>
  </reportingOwner>
  <aff10b5One>true</aff10b5One>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <securityTitle><value>Common Stock</value></securityTitle>
      <transactionDate><value>2026-09-15</value></transactionDate>
      <transactionCoding><transactionFormType>4</transactionFormType><transactionCode>S</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>1,000</value></transactionShares>
        <transactionPricePerShare><value>331.50</value></transactionPricePerShare>
        <transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode>
      </transactionAmounts>
      <postTransactionAmounts><sharesOwnedFollowingTransaction><value>12000</value></sharesOwnedFollowingTransaction></postTransactionAmounts>
    </nonDerivativeTransaction>
    <nonDerivativeTransaction>
      <securityTitle><value>Common Stock</value></securityTitle>
      <transactionDate><value>2026-09-15</value></transactionDate>
      <transactionCoding><transactionCode>M</transactionCode></transactionCoding>
      <transactionAmounts><transactionShares><value>5000</value></transactionShares><transactionPricePerShare><value>50</value></transactionPricePerShare></transactionAmounts>
    </nonDerivativeTransaction>
    <nonDerivativeTransaction>
      <securityTitle><value>Common Stock</value></securityTitle>
      <transactionDate><value>2026-09-16</value></transactionDate>
      <transactionCoding><transactionCode>P</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>200</value></transactionShares>
        <transactionPricePerShare><value>330</value></transactionPricePerShare>
        <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>
      </transactionAmounts>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
  <derivativeTable>
    <derivativeTransaction><transactionCoding><transactionCode>P</transactionCode></transactionCoding></derivativeTransaction>
  </derivativeTable>
</ownershipDocument>"""


def test_parse_form4_keeps_only_open_market_common_stock_trades():
    form = parse_form4(FORM4)
    assert form.issuer_symbol == "AAPL" and form.period_of_report == date(2026, 9, 15)
    assert [t.transaction_code for t in form.transactions] == ["S", "P"]  # option exercise (M) and derivatives dropped
    sale, buy = form.transactions
    assert sale.owner_name == "Newstead Jennifer" and sale.owner_role == "SVP, GC and Government Affairs"
    assert sale.is_purchase is False and sale.shares == 1000 and sale.price == 331.5 and sale.value == 331500.0
    assert sale.shares_owned_after == 12000 and sale.is_10b5_1 is True
    assert buy.is_purchase is True and buy.value == 66000.0 and buy.transaction_date == date(2026, 9, 16)


def test_parse_form4_role_fallbacks_and_missing_price():
    xml = FORM4.replace(
        "<isOfficer>true</isOfficer><officerTitle>SVP, GC and Government Affairs</officerTitle>",
        "<isDirector>1</isDirector>",
    ).replace("<transactionPricePerShare><value>330</value></transactionPricePerShare>", "")
    form = parse_form4(xml)
    assert form.transactions[0].owner_role == "Director"
    assert form.transactions[1].price is None and form.transactions[1].value is None


def test_parse_form4_per_transaction_10b5_1_flag_beats_document_flag():
    # A filing can report a scheduled sale next to a discretionary purchase. The
    # document-level aff10b5One must not mark that purchase as scheduled, or the
    # cluster-buy signal (which ignores plan buys) would silently drop it.
    xml = FORM4.replace(
        "<transactionCode>S</transactionCode></transactionCoding>",
        "<transactionCode>S</transactionCode><rule10b5-1Flag><value>1</value></rule10b5-1Flag></transactionCoding>",
    ).replace(
        "<transactionCoding><transactionCode>P</transactionCode></transactionCoding>",
        "<transactionCoding><transactionCode>P</transactionCode><rule10b5-1Flag><value>0</value></rule10b5-1Flag></transactionCoding>",
    )
    sale, buy = parse_form4(xml).transactions
    assert sale.is_10b5_1 is True and buy.is_10b5_1 is False


def test_parse_form4_falls_back_to_document_flag_when_no_per_transaction_flag():
    # Pre-2022 filings only carry the document-level marker.
    sale, buy = parse_form4(FORM4).transactions
    assert sale.is_10b5_1 is True and buy.is_10b5_1 is True
    unflagged = parse_form4(FORM4.replace("<aff10b5One>true</aff10b5One>", "")).transactions
    assert all(t.is_10b5_1 is False for t in unflagged)


def test_parse_form4_no_table():
    form = parse_form4("<ownershipDocument><issuer><issuerTradingSymbol>X</issuerTradingSymbol></issuer></ownershipDocument>")
    assert form.transactions == [] and form.issuer_symbol == "X"


@pytest.mark.parametrize("buy, sell, expected", [(0, 0, None), (100, 0, 1.0), (0, 100, -1.0), (75, 25, 0.5), (30, 70, -0.4)])
def test_net_buy_ratio(buy, sell, expected):
    assert net_buy_ratio(buy, sell) == expected


def _tx(days_ago, is_purchase, value, owner, plan=False, today=date(2026, 9, 17)):
    from datetime import timedelta
    return SimpleNamespace(transaction_date=today - timedelta(days=days_ago), is_purchase=is_purchase, value=value, owner_name=owner, is_10b5_1=plan)


def test_summarize_transactions_windows_and_cluster():
    today = date(2026, 9, 17)
    rows = [
        _tx(5, True, 100_000, "A"), _tx(10, True, 50_000, "B"), _tx(20, True, 25_000, "C"),     # 3 buyers in 30d -> cluster
        _tx(40, False, 400_000, "D", plan=True),                                                  # scheduled sale
        _tx(60, False, 100_000, "E"),
        _tx(120, True, 9_999_999, "Z"),                                                           # outside 90d window
    ]
    s = summarize_transactions(rows, today=today)
    assert s["buys"] == 3 and s["sells"] == 2 and s["distinct_buyers"] == 3 and s["distinct_sellers"] == 2
    assert s["buy_value"] == 175_000 and s["sell_value"] == 500_000 and s["plan_sell_value"] == 400_000
    assert s["net_ratio"] == pytest.approx((175_000 - 500_000) / 675_000, abs=1e-3)
    assert s["discretionary_net_ratio"] == pytest.approx((175_000 - 100_000) / 275_000, abs=1e-3)
    assert s["cluster_buy"] is True and s["cluster_buyers"] == 3


def test_summarize_cluster_ignores_plan_buys_and_old_buys():
    today = date(2026, 9, 17)
    rows = [_tx(5, True, 1, "A", plan=True), _tx(6, True, 1, "B"), _tx(45, True, 1, "C")]
    s = summarize_transactions(rows, today=today)
    assert s["cluster_buy"] is False and s["cluster_buyers"] == 1


def test_summarize_empty():
    s = summarize_transactions([])
    assert s["net_ratio"] is None and s["cluster_buy"] is False and s["buys"] == 0


# --- point-in-time series --------------------------------------------------------


def test_insider_series_is_point_in_time_by_filing_date():
    d = date(2026, 6, 1)
    from datetime import timedelta
    series = InsiderSeries([
        (d, True, 100.0, False),
        (d + timedelta(days=10), False, 300.0, False),
        (d + timedelta(days=20), False, 1000.0, True),   # 10b5-1 sale: excluded
    ])
    assert series.net_ratio_as_of(d - timedelta(days=1)) is None
    assert series.net_ratio_as_of(d) == 1.0
    assert series.net_ratio_as_of(d + timedelta(days=15)) == pytest.approx(-0.5)
    assert series.net_ratio_as_of(d + timedelta(days=25)) == pytest.approx(-0.5)
    assert series.net_ratio_as_of(d + timedelta(days=95)) == pytest.approx(-1.0)   # the buy fell out of the 90d window
    assert series.net_ratio_as_of(d + timedelta(days=200)) is None


# --- signal ----------------------------------------------------------------------


def _summary(**kw):
    base = dict(window_days=90, distinct_buyers=0, distinct_sellers=0, net_value=0.0, buy_value=0.0, sell_value=0.0,
                discretionary_net_ratio=None, cluster_buy=False, cluster_buyers=0)
    base.update(kw)
    return base


def test_insiders_buying_into_bearish_narrative_is_alert():
    s = insider_vs_narrative_signal(_summary(distinct_buyers=2, net_value=250_000, buy_value=250_000), -35, 6, False)
    assert s["severity"] == "alert" and "buying into a bearish" in s["title"]


def test_insiders_buying_needs_two_buyers_and_bearish_media():
    assert insider_vs_narrative_signal(_summary(distinct_buyers=1, net_value=250_000, buy_value=250_000), -35, 6, False) is None
    assert insider_vs_narrative_signal(_summary(distinct_buyers=2, net_value=250_000, buy_value=250_000), 10, 6, False) is None
    assert insider_vs_narrative_signal(_summary(distinct_buyers=2, net_value=250_000, buy_value=250_000), -35, 1, False) is None


def test_insiders_selling_into_crowded_or_bullish_narrative():
    heavy = _summary(distinct_sellers=4, net_value=-2e6, sell_value=2e6, buy_value=0, discretionary_net_ratio=-1.0)
    assert insider_vs_narrative_signal(heavy, 10, 6, True)["title"].startswith("Insiders selling")
    assert insider_vs_narrative_signal(heavy, 60, 6, False)["title"].startswith("Insiders selling")
    assert insider_vs_narrative_signal(heavy, 10, 6, False) is None           # neither crowded nor bullish
    only_plan = _summary(distinct_sellers=4, net_value=-2e6, sell_value=2e6, discretionary_net_ratio=None)
    assert insider_vs_narrative_signal(only_plan, 60, 6, True) is None        # all sales were 10b5-1


def test_cluster_buy_is_a_watch_when_nothing_stronger_fires():
    s = insider_vs_narrative_signal(_summary(cluster_buy=True, cluster_buyers=3, distinct_buyers=3, net_value=5000, buy_value=5000), 30, 6, False)
    assert s["severity"] == "watch" and s["key"] == "insiders_vs_narrative"


def test_no_insider_activity_is_silent():
    assert insider_vs_narrative_signal(_summary(), -50, 10, True) is None


# --- recent notable trades ------------------------------------------------------


def test_recent_trades_rank_buys_and_sells_separately():
    """The point of splitting the two sides: one combined list ordered by dollar
    value would be all sells, because routine mega-cap selling dwarfs any purchase."""
    from app.services.insiders import get_recent_notable_trades
    import asyncio

    calls = []

    async def fake_recent(db, is_purchase, days, limit, include_institutions=True):
        calls.append((is_purchase, days, limit))
        return [{"is_purchase": is_purchase}]

    import app.services.insiders as mod
    original = mod._recent_trades
    mod._recent_trades = fake_recent
    try:
        out = asyncio.run(get_recent_notable_trades(None, days=14, limit=5))
    finally:
        mod._recent_trades = original

    assert calls == [(True, 14, 5), (False, 14, 5)]
    assert out["window_days"] == 14
    assert out["buys"] == [{"is_purchase": True}]
    assert out["sells"] == [{"is_purchase": False}]


def test_recent_trades_aggregate_shape_is_share_weighted():
    """The grouped query returns a share-weighted price and a line count, so a sale
    reported as many Form 4 lines shows up as one decision at a sensible price."""
    lines = [(1200.0, 100.0), (800.0, 110.0)]          # (shares, price)
    total_shares = sum(sh for sh, _ in lines)
    total_value = sum(sh * px for sh, px in lines)
    weighted = round(total_value / total_shares, 4)
    assert total_shares == 2000.0 and total_value == 208_000.0
    assert weighted == 104.0                            # not the 105.0 a naive mean would give


def test_insert_chunk_stays_under_the_postgres_bind_parameter_cap():
    """A full year of Form 4s for a heavily-traded issuer (DELL) exceeded Postgres's
    32767 bind-parameter cap in one statement, failing the whole ticker. The chunk
    size must keep columns x rows under that cap."""
    from app.services.insiders import _INSERT_CHUNK
    from app.models.models import InsiderTransaction

    columns = len(InsiderTransaction.__table__.columns)
    assert columns * _INSERT_CHUNK < 32767, (
        f"{columns} columns x {_INSERT_CHUNK} rows exceeds the bind-parameter cap"
    )


def test_exclude_institutions_clause_keeps_null_roles():
    """`!=` would drop rows whose owner_role is NULL, silently hiding trades whose
    role the filing did not state; IS DISTINCT FROM keeps them."""
    from app.services.insiders import _exclude_institutions_clause, TEN_PERCENT_ROLE

    compiled = str(_exclude_institutions_clause().compile(compile_kwargs={"literal_binds": True}))
    assert "IS DISTINCT FROM" in compiled.upper()
    assert TEN_PERCENT_ROLE in compiled


def test_recent_trades_passes_the_institution_filter_through():
    from app.services.insiders import get_recent_notable_trades
    import app.services.insiders as mod
    import asyncio

    seen = []

    async def fake(db, is_purchase, days, limit, include_institutions):
        seen.append(include_institutions)
        return []

    original = mod._recent_trades
    mod._recent_trades = fake
    try:
        out = asyncio.run(get_recent_notable_trades(None, days=30, limit=5, include_institutions=False))
    finally:
        mod._recent_trades = original

    assert seen == [False, False]
    assert out["include_institutions"] is False

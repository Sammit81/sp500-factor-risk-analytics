"""
Signal math correctness, checked against real data — the automated version
of the manual hand-verification done during development (AAPL momentum
matched a manual calculation exactly: 0.483417 both ways). Each signal is
independently recomputed in Python from raw closes and compared to the
dbt-computed value.
"""
SAMPLE_TICKERS = ["AAPL", "MSFT", "JPM", "XOM", "KO"]


def _closes_desc(bq_client, bq_table_ref, ticker: str):
    return list(bq_client.query(f"""
        SELECT PRICE_DATE, CLOSE_PRICE, ROW_NUMBER() OVER (ORDER BY PRICE_DATE DESC) AS rn
        FROM {bq_table_ref('stg_prices')}
        WHERE TICKER = "{ticker}"
        ORDER BY PRICE_DATE DESC
    """).result())


def test_momentum_matches_manual_calculation(bq_client, bq_table_ref):
    """momentum = (close_21_days_ago - close_252_days_ago) / close_252_days_ago"""
    checked = 0
    for ticker in SAMPLE_TICKERS:
        rows = _closes_desc(bq_client, bq_table_ref, ticker)
        if len(rows) < 253:
            continue
        close_21_ago = next(r.CLOSE_PRICE for r in rows if r.rn == 22)
        close_252_ago = next(r.CLOSE_PRICE for r in rows if r.rn == 253)
        expected = (close_21_ago - close_252_ago) / close_252_ago

        latest_date = rows[0].PRICE_DATE
        actual = list(bq_client.query(f"""
            SELECT MOMENTUM_SIGNAL FROM {bq_table_ref('int_signal_momentum')}
            WHERE TICKER = "{ticker}" AND PRICE_DATE = "{latest_date}"
        """).result())
        assert actual, f"no momentum row for {ticker} on {latest_date}"
        assert abs(actual[0].MOMENTUM_SIGNAL - expected) < 1e-4, (
            f"{ticker}: dbt={actual[0].MOMENTUM_SIGNAL}, manual={expected}"
        )
        checked += 1
    assert checked > 0, "no sample ticker had enough history to check — sample list may need updating"


def test_mean_reversion_matches_manual_calculation(bq_client, bq_table_ref):
    """mean_reversion = -1 * (close_today - close_5_days_ago) / close_5_days_ago"""
    checked = 0
    for ticker in SAMPLE_TICKERS:
        rows = _closes_desc(bq_client, bq_table_ref, ticker)
        if len(rows) < 6:
            continue
        close_today = rows[0].CLOSE_PRICE
        close_5_ago = next(r.CLOSE_PRICE for r in rows if r.rn == 6)
        expected = -1 * (close_today - close_5_ago) / close_5_ago

        latest_date = rows[0].PRICE_DATE
        actual = list(bq_client.query(f"""
            SELECT MEAN_REVERSION_SIGNAL FROM {bq_table_ref('int_signal_mean_reversion')}
            WHERE TICKER = "{ticker}" AND PRICE_DATE = "{latest_date}"
        """).result())
        assert actual, f"no mean-reversion row for {ticker} on {latest_date}"
        assert abs(actual[0].MEAN_REVERSION_SIGNAL - expected) < 1e-4, (
            f"{ticker}: dbt={actual[0].MEAN_REVERSION_SIGNAL}, manual={expected}"
        )
        checked += 1
    assert checked > 0


def test_low_vol_sign_convention_and_magnitude(bq_client, bq_table_ref):
    """low_vol_signal = -1 * (30-day annualised stddev of daily returns) —
    sign check (always <= 0) plus a manual recomputation for one ticker."""
    rows = list(bq_client.query(f"""
        SELECT COUNT(*) AS n
        FROM {bq_table_ref('int_signal_low_vol')}
        WHERE LOW_VOL_SIGNAL > 0
    """).result())
    assert rows[0].n == 0, "found positive low-vol signal values — sign convention violated"

    ticker = "AAPL"
    returns = list(bq_client.query(f"""
        SELECT DAILY_RETURN, PRICE_DATE
        FROM {bq_table_ref('int_daily_returns')}
        WHERE TICKER = "{ticker}"
        ORDER BY PRICE_DATE DESC
        LIMIT 30
    """).result())
    assert len(returns) == 30
    import statistics
    daily_stdev = statistics.stdev([r.DAILY_RETURN for r in returns])  # sample stdev, matches BigQuery's STDDEV()
    expected = -1 * daily_stdev * (252 ** 0.5)

    latest_date = returns[0].PRICE_DATE
    actual = list(bq_client.query(f"""
        SELECT LOW_VOL_SIGNAL FROM {bq_table_ref('int_signal_low_vol')}
        WHERE TICKER = "{ticker}" AND PRICE_DATE = "{latest_date}"
    """).result())
    assert actual
    assert abs(actual[0].LOW_VOL_SIGNAL - expected) < 1e-3, (
        f"{ticker}: dbt={actual[0].LOW_VOL_SIGNAL}, manual={expected}"
    )

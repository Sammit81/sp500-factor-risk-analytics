"""
The core anti-lookahead invariant for the Value signal: every row in
int_pointintime_pe must reference an EPS report strictly BEFORE its price
date. This is the layer most likely to be wrong in the whole project (see
docs/decisions.md) — a single flipped comparison operator in the as-of join
would silently let the backtest "know" a company's earnings before they were
actually reported.
"""


def test_no_future_eps_used(bq_client, bq_table_ref):
    violations = list(bq_client.query(f"""
        SELECT COUNT(*) AS n
        FROM {bq_table_ref('int_pointintime_pe')}
        WHERE EPS_REPORT_DATE >= PRICE_DATE
    """).result())
    n = violations[0].n
    assert n == 0, f"{n} rows use an EPS report on or after the price date — lookahead bug"


def test_pointintime_pe_has_rows(bq_client, bq_table_ref):
    """Sanity check the join isn't silently empty (e.g. a type mismatch that
    makes every join predicate false would pass the invariant test above
    trivially, for the wrong reason)."""
    rows = list(bq_client.query(f"""
        SELECT COUNT(*) AS n FROM {bq_table_ref('int_pointintime_pe')}
    """).result())
    assert rows[0].n > 0, "int_pointintime_pe is empty — the as-of join is likely broken, not just conservative"


def test_pe_ratio_is_positive_where_present(bq_client, bq_table_ref):
    """Negative/zero trailing EPS should already be filtered out upstream —
    confirm no negative or zero PE_RATIO leaked through."""
    violations = list(bq_client.query(f"""
        SELECT COUNT(*) AS n
        FROM {bq_table_ref('int_pointintime_pe')}
        WHERE PE_RATIO IS NOT NULL AND PE_RATIO <= 0
    """).result())
    n = violations[0].n
    assert n == 0, f"{n} rows have a non-positive PE_RATIO despite the upstream TRAILING_EPS > 0 filter"

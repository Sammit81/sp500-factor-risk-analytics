-- SPY isn't an S&P 500 constituent (it's the benchmark ETF, added separately
-- in fetch_prices.py) so it isn't in the sp500_constituents seed — union it
-- in explicitly, otherwise every SPY row in the fact tables fails its
-- relationships test against this dimension.

SELECT
    ticker         AS TICKER,
    name           AS NAME,
    sector         AS SECTOR,
    gics_industry  AS GICS_INDUSTRY
FROM {{ ref('sp500_constituents') }}

UNION ALL

SELECT
    'SPY'                                AS TICKER,
    'SPDR S&P 500 ETF Trust (benchmark)' AS NAME,
    'Benchmark'                          AS SECTOR,
    'ETF'                                AS GICS_INDUSTRY

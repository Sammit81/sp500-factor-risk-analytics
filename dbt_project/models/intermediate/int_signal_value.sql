-- int_signal_value: earnings yield (EPS / Price) — equivalent to 1/PE, the
-- standard academic convention, preferred over raw P/E or -P/E because it's
-- better-behaved statistically (bounded, symmetric) and the negative-EPS
-- case is already excluded upstream in int_pointintime_pe. Higher earnings
-- yield = cheaper stock = higher score, same convention as every other signal.

SELECT
    TICKER,
    PRICE_DATE,
    ROUND(SAFE_DIVIDE(TRAILING_EPS, CLOSE_PRICE), 6) AS VALUE_SIGNAL
FROM {{ ref('int_pointintime_pe') }}

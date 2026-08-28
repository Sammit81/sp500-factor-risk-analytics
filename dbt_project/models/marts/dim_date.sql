-- dim_date: standard date dimension. Power BI's time-intelligence DAX
-- functions (TOTALYTD, SAMEPERIODLASTYEAR, DATESINPERIOD) require a proper
-- marked date table related to the fact tables by a single Date column.

WITH spine AS (
    SELECT date
    FROM UNNEST(GENERATE_DATE_ARRAY('2020-01-01', '2030-12-31', INTERVAL 1 DAY)) AS date
)
SELECT
    date                                          AS Date,
    EXTRACT(YEAR FROM date)                        AS Year,
    EXTRACT(QUARTER FROM date)                     AS Quarter,
    FORMAT_DATE('Q%Q %Y', date)                    AS YearQuarter,
    EXTRACT(MONTH FROM date)                       AS Month,
    FORMAT_DATE('%B', date)                        AS MonthName,
    FORMAT_DATE('%Y-%m', date)                     AS YearMonth,
    NOT (EXTRACT(DAYOFWEEK FROM date) IN (1, 7))   AS IsTradingDay
FROM spine

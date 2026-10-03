-- ============================================================
-- Payment Fraud & Chargeback Risk — analysis SQL (T-SQL / Azure SQL)
-- Table: risk.fact_transactions (same columns as data/fact_transactions.csv)
-- ============================================================

-- 1) Daily fraud KPIs with 7-day rolling rate
SELECT  t.DateKey,
        COUNT(*)                                             AS Txns,
        SUM(CAST(t.IsFraud AS INT))                          AS FraudTxns,
        AVG(CAST(t.IsFraud AS FLOAT))                        AS FraudRate,
        AVG(AVG(CAST(t.IsFraud AS FLOAT))) OVER (ORDER BY t.DateKey
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)        AS FraudRate7D
FROM risk.fact_transactions t
GROUP BY t.DateKey
ORDER BY t.DateKey;

-- 2) Merchants breaching the 0.9% chargeback-to-transaction threshold (last 90 days)
WITH m AS (
    SELECT MerchantKey,
           COUNT(*)                          AS Txns,
           SUM(CAST(IsChargeback AS INT))    AS Chargebacks
    FROM risk.fact_transactions
    WHERE DateKey >= CONVERT(INT, FORMAT(DATEADD(DAY, -90, '2026-06-30'), 'yyyyMMdd'))
    GROUP BY MerchantKey
)
SELECT m.*, CAST(1.0 * Chargebacks / Txns AS DECIMAL(6,4)) AS CbRate
FROM m
WHERE Txns >= 50 AND 1.0 * Chargebacks / Txns > 0.009
ORDER BY CbRate DESC;

-- 3) Rule-engine confusion matrix
SELECT Decision,
       SUM(CASE WHEN IsFraud = 1 THEN 1 ELSE 0 END) AS Fraud,
       SUM(CASE WHEN IsFraud = 0 THEN 1 ELSE 0 END) AS Legit
FROM risk.fact_transactions
GROUP BY Decision;

-- 4) Threshold sweep: precision / recall at each candidate decline score
WITH thresholds AS (
    SELECT value AS Threshold FROM GENERATE_SERIES(40, 95, 5)
)
SELECT th.Threshold,
       SUM(CASE WHEN t.RiskScore >= th.Threshold THEN 1 ELSE 0 END)                    AS Blocked,
       SUM(CASE WHEN t.RiskScore >= th.Threshold AND t.IsFraud = 1 THEN 1 ELSE 0 END)  AS FraudCaught,
       1.0 * SUM(CASE WHEN t.RiskScore >= th.Threshold AND t.IsFraud = 1 THEN 1 ELSE 0 END)
           / NULLIF(SUM(CAST(t.IsFraud AS INT)), 0)                                    AS Recall,
       1.0 * SUM(CASE WHEN t.RiskScore >= th.Threshold AND t.IsFraud = 1 THEN 1 ELSE 0 END)
           / NULLIF(SUM(CASE WHEN t.RiskScore >= th.Threshold THEN 1 ELSE 0 END), 0)   AS [Precision]
FROM thresholds th CROSS JOIN risk.fact_transactions t
GROUP BY th.Threshold
ORDER BY th.Threshold;

-- 5) Fraud lift by risk signal
SELECT 'Geo mismatch'   AS Signal, AVG(CAST(IsFraud AS FLOAT)) AS FraudRate FROM risk.fact_transactions WHERE CardCountry <> IPCountry
UNION ALL SELECT 'Geo match',      AVG(CAST(IsFraud AS FLOAT)) FROM risk.fact_transactions WHERE CardCountry = IPCountry
UNION ALL SELECT 'No 3DS',         AVG(CAST(IsFraud AS FLOAT)) FROM risk.fact_transactions WHERE Is3DS = 0
UNION ALL SELECT '3DS',            AVG(CAST(IsFraud AS FLOAT)) FROM risk.fact_transactions WHERE Is3DS = 1
UNION ALL SELECT 'Account < 14d',  AVG(CAST(IsFraud AS FLOAT)) FROM risk.fact_transactions WHERE AccountAgeDays < 14
UNION ALL SELECT 'Unknown device', AVG(CAST(IsFraud AS FLOAT)) FROM risk.fact_transactions WHERE DeviceType = 'Unknown';

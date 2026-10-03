// ============================================================
// Power Query (M) — fact_transactions for the Fraud & Chargeback model
// Parameter: DataFolder = "...\02-payment-fraud-risk-monitor\data\"
// ============================================================
let
    Source   = Csv.Document(File.Contents(DataFolder & "fact_transactions.csv"),
                            [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),

    // Empty ChargebackDateKey ("") must become null before typing, otherwise the column errors
    BlankToNull = Table.ReplaceValue(Promoted, "", null, Replacer.ReplaceValue, {"ChargebackDateKey", "ChargebackReason"}),

    Typed = Table.TransformColumnTypes(BlankToNull, {
        {"TransactionID", type text}, {"DateKey", Int64.Type}, {"MerchantKey", Int64.Type},
        {"CustomerID", type text}, {"PaymentMethod", type text}, {"GrossAmountEUR", Currency.Type},
        {"CardCountry", type text}, {"IPCountry", type text}, {"DeviceType", type text},
        {"Is3DS", type logical}, {"AccountAgeDays", Int64.Type}, {"TxnLast24h", Int64.Type},
        {"RiskScore", type number}, {"Decision", type text}, {"IsFraud", type logical},
        {"IsChargeback", type logical}, {"ChargebackReason", type text},
        {"ChargebackDateKey", Int64.Type}, {"ChargebackFeeEUR", Currency.Type}}, "en-US"),

    // Feature columns used by slicers and the signals page
    GeoMismatch = Table.AddColumn(Typed, "GeoMismatch", each [CardCountry] <> [IPCountry], type logical),
    AccountAgeBand = Table.AddColumn(GeoMismatch, "AccountAgeBand", each
        if [AccountAgeDays] < 14 then "0-13 days"
        else if [AccountAgeDays] < 90 then "14-89 days"
        else if [AccountAgeDays] < 365 then "90-364 days"
        else "1y+", type text),
    RiskBand = Table.AddColumn(AccountAgeBand, "RiskBand", each
        if [RiskScore] >= 80 then "Critical"
        else if [RiskScore] >= 55 then "High"
        else if [RiskScore] >= 30 then "Medium"
        else "Low", type text)
in
    RiskBand

// What-if parameter table (Modeling > New parameter, or as a calculated table in DAX):
// Decline Threshold = GENERATESERIES ( 40, 95, 5 )

"""Synthetic but realistic datasets for 5 Power BI portfolio projects (e-commerce finance & risk)."""
import numpy as np, pandas as pd, json, os
rng = np.random.default_rng(42)
ROOT = __import__("os").path.abspath(__import__("os").path.join(__import__("os").path.dirname(__file__), "..", ".."))

COUNTRIES = [("DE","Germany","EUR","EU"),("FR","France","EUR","EU"),("ES","Spain","EUR","EU"),
             ("IT","Italy","EUR","EU"),("NL","Netherlands","EUR","EU"),("GB","United Kingdom","GBP","UK"),
             ("US","United States","USD","NA"),("CA","Canada","CAD","NA"),("IN","India","INR","APAC"),
             ("AU","Australia","AUD","APAC"),("BR","Brazil","BRL","LATAM"),("MX","Mexico","MXN","LATAM")]
CATEGORIES = ["Fashion","Electronics","Home & Living","Beauty","Sports","Toys","Books","Grocery"]
CHANNELS = ["Web","Mobile App","Marketplace","Social Commerce"]
PAY = ["Card","PayPal","Apple Pay","Google Pay","Bank Transfer","BNPL"]
START, END = pd.Timestamp("2024-01-01"), pd.Timestamp("2026-06-30")

def out(project, name, df):
    d = f"{ROOT}/{project}/data"; os.makedirs(d, exist_ok=True)
    df.to_csv(f"{d}/{name}.csv", index=False)

def dim_date():
    d = pd.DataFrame({"Date": pd.date_range(START, END)})
    d["DateKey"] = d.Date.dt.strftime("%Y%m%d").astype(int)
    d["Year"] = d.Date.dt.year; d["Quarter"] = "Q" + d.Date.dt.quarter.astype(str)
    d["MonthNum"] = d.Date.dt.month; d["Month"] = d.Date.dt.strftime("%b")
    d["YearMonth"] = d.Date.dt.strftime("%Y-%m"); d["WeekdayNum"] = d.Date.dt.weekday + 1
    d["Weekday"] = d.Date.dt.strftime("%a"); d["IsWeekend"] = d.WeekdayNum >= 6
    return d[["DateKey","Date","Year","Quarter","MonthNum","Month","YearMonth","WeekdayNum","Weekday","IsWeekend"]]

DATE = dim_date()
geo = pd.DataFrame(COUNTRIES, columns=["CountryCode","Country","Currency","Region"])

# ---------- shared merchant base ----------
N_M = 180
merchants = pd.DataFrame({
    "MerchantKey": range(1, N_M+1),
    "MerchantID": [f"M{10000+i}" for i in range(1, N_M+1)],
    "MerchantName": [f"{a} {b}" for a, b in zip(rng.choice(["Nova","Blue","Urban","Peak","Luna","Atlas","Vivid","Echo","Prime","Zen","Bright","Coral"], N_M),
                                                rng.choice(["Store","Goods","Market","Outlet","Collective","Supply","Boutique","Co"], N_M))],
    "Category": rng.choice(CATEGORIES, N_M),
    "CountryCode": rng.choice(geo.CountryCode, N_M, p=[.14,.1,.08,.07,.06,.12,.18,.05,.07,.05,.04,.04]),
    "Tier": rng.choice(["Enterprise","Growth","Starter"], N_M, p=[.15,.35,.5]),
    "OnboardDate": pd.to_datetime(rng.integers(START.value//10**9, pd.Timestamp("2026-03-01").value//10**9, N_M), unit="s").normalize(),
})
merchants["MerchantName"] = merchants.MerchantName + " " + merchants.MerchantKey.astype(str)
merchants = merchants.merge(geo[["CountryCode","Region"]], on="CountryCode")
merchants["AccountManagerEmail"] = merchants.Region.map({
    "EU":"am.eu@marbill-demo.com","UK":"am.uk@marbill-demo.com","NA":"am.na@marbill-demo.com",
    "APAC":"am.apac@marbill-demo.com","LATAM":"am.latam@marbill-demo.com"})
tier_scale = merchants.Tier.map({"Enterprise":8.0,"Growth":2.5,"Starter":1.0}).values

# ---------- orders (shared fact) ----------
days = DATE.Date.values
growth = np.linspace(1.0, 1.9, len(days))
season = 1 + 0.35*np.isin(pd.DatetimeIndex(days).month, [11,12]) + 0.08*(pd.DatetimeIndex(days).weekday >= 5)
daily_n = rng.poisson(110*growth*season)
rows = []
oid = 1
mw = tier_scale / tier_scale.sum()
for d, n in zip(days, daily_n):
    m = rng.choice(merchants.MerchantKey.values, n, p=mw)
    rows.append(pd.DataFrame({"OrderID": np.arange(oid, oid+n), "OrderDate": d, "MerchantKey": m}))
    oid += n
orders = pd.concat(rows, ignore_index=True)
orders = orders.merge(merchants[["MerchantKey","OnboardDate","Category"]], on="MerchantKey")
orders = orders[orders.OrderDate >= orders.OnboardDate].drop(columns="OnboardDate").reset_index(drop=True)
n = len(orders)
base = orders.Category.map({"Fashion":55,"Electronics":180,"Home & Living":85,"Beauty":35,"Sports":70,"Toys":40,"Books":22,"Grocery":48})
orders["GrossAmountEUR"] = np.round(base * rng.lognormal(0, .55, n), 2)
orders["DiscountEUR"] = np.round(orders.GrossAmountEUR * rng.choice([0,0,0,.05,.1,.2], n), 2)
orders["ShippingEUR"] = np.round(rng.choice([0,4.9,6.9,9.9], n, p=[.4,.3,.2,.1]), 2)
orders["TaxEUR"] = np.round((orders.GrossAmountEUR-orders.DiscountEUR)*.19, 2)
orders["COGS_EUR"] = np.round((orders.GrossAmountEUR-orders.DiscountEUR)*rng.uniform(.45,.68,n), 2)
orders["PaymentFeeEUR"] = np.round(orders.GrossAmountEUR*.029+.25, 2)
orders["Channel"] = rng.choice(CHANNELS, n, p=[.42,.33,.17,.08])
orders["PaymentMethod"] = rng.choice(PAY, n, p=[.45,.18,.1,.08,.07,.12])
orders["CustomerID"] = "C" + rng.integers(1, 60000, n).astype(str)
orders["Status"] = rng.choice(["Completed","Refunded","Cancelled"], n, p=[.91,.065,.025])
orders["RefundEUR"] = np.where(orders.Status=="Refunded", orders.GrossAmountEUR-orders.DiscountEUR, 0).round(2)
orders["DateKey"] = pd.to_datetime(orders.OrderDate).dt.strftime("%Y%m%d").astype(int)
orders = orders.drop(columns="Category")

# =================== P1: Finance P&L & Budget vs Actual ===================
P1 = "01-ecommerce-finance-pnl"
out(P1, "dim_date", DATE)
out(P1, "dim_merchant", merchants[["MerchantKey","MerchantID","MerchantName","Category","CountryCode","Region","Tier","OnboardDate"]])
out(P1, "dim_geography", geo)
out(P1, "fact_orders", orders[["OrderID","DateKey","MerchantKey","CustomerID","Channel","PaymentMethod","Status",
                              "GrossAmountEUR","DiscountEUR","ShippingEUR","TaxEUR","COGS_EUR","PaymentFeeEUR","RefundEUR"]])
# opex ledger
accts = [("6100","Marketing","Opex"),("6200","Salaries","Opex"),("6300","Cloud & Hosting","Opex"),
         ("6400","Customer Support","Opex"),("6500","Logistics","Opex"),("6600","G&A","Opex")]
months = pd.period_range("2024-01","2026-06",freq="M")
opex = []
for p in months:
    t = (p - months[0]).n
    for code, name, typ in accts:
        b = {"6100":13e3,"6200":30e3,"6300":4.2e3,"6400":5.2e3,"6500":9.5e3,"6600":3.8e3}[code]*(1+0.012*t)
        opex.append({"DateKey": int(p.to_timestamp().strftime("%Y%m%d")), "AccountCode": code,
                     "ActualEUR": round(b*rng.normal(1,.07),2), "BudgetEUR": round(b,2)})
out(P1, "fact_opex_gl", pd.DataFrame(opex))
out(P1, "dim_account", pd.DataFrame(accts, columns=["AccountCode","AccountName","AccountType"]))
mrev = orders.assign(YM=pd.to_datetime(orders.OrderDate).dt.to_period("M")).groupby(["YM","MerchantKey"]).GrossAmountEUR.sum().reset_index()
mrev["DateKey"] = mrev.YM.dt.to_timestamp().dt.strftime("%Y%m%d").astype(int)
mrev["BudgetGMV_EUR"] = (mrev.GrossAmountEUR*rng.normal(1.04,.08,len(mrev))).round(2)
out(P1, "fact_budget_gmv", mrev[["DateKey","MerchantKey","BudgetGMV_EUR"]])

# =================== P2: Fraud & Chargeback Risk ===================
P2 = "02-payment-fraud-risk-monitor"
tx = orders[orders.Status != "Cancelled"].sample(frac=.55, random_state=1).reset_index(drop=True)
k = len(tx)
tx["TransactionID"] = "T" + (tx.OrderID+5_000_000).astype(str)
tx["CardCountry"] = rng.choice(geo.CountryCode, k)
tx["IPCountry"] = np.where(rng.random(k) < .9, tx.CardCountry, rng.choice(geo.CountryCode, k))
tx["DeviceType"] = rng.choice(["Desktop","iOS","Android","Unknown"], k, p=[.38,.3,.28,.04])
tx["Is3DS"] = rng.random(k) < .72
tx["AccountAgeDays"] = rng.exponential(400, k).astype(int)
tx["TxnLast24h"] = rng.poisson(1.3, k)
mrisk = np.where(np.isin(tx.MerchantKey, rng.choice(merchants.MerchantKey, 14, replace=False)), 1.8, -0.6)
logit = (-4.4 + mrisk + 1.8*(tx.CardCountry != tx.IPCountry) + 1.2*(tx.DeviceType=="Unknown") - 1.1*tx.Is3DS
         + 0.9*(tx.AccountAgeDays < 14) + 0.35*np.clip(tx.TxnLast24h-2,0,None) + 0.004*np.clip(tx.GrossAmountEUR-200,0,None)/10
         + 0.6*(tx.PaymentMethod=="BNPL"))
p = 1/(1+np.exp(-logit))
tx["RiskScore"] = np.clip((np.log10(p)+2.6)*40 + rng.normal(0,8,k), 0, 100).round(1)
tx["Decision"] = np.select([tx.RiskScore>=80, tx.RiskScore>=55], ["Declined","Manual Review"], "Approved")
fraud = rng.random(k) < p
tx["IsFraud"] = fraud
cb = (fraud & (tx.Decision != "Declined") & (rng.random(k) < .75)) | (rng.random(k) < .0008)
tx["IsChargeback"] = cb
tx["ChargebackReason"] = np.where(cb, rng.choice(["Fraudulent","Not Received","Not as Described","Duplicate","Credit Not Processed"], k, p=[.55,.18,.14,.05,.08]), "")
cbdate = pd.to_datetime(tx.OrderDate) + pd.to_timedelta(rng.integers(5, 75, k), unit="D")
tx["ChargebackDateKey"] = np.where(cb, cbdate.dt.strftime("%Y%m%d"), "")
tx["ChargebackFeeEUR"] = np.where(cb, 15.0, 0)
out(P2, "dim_date", DATE); out(P2, "dim_geography", geo)
out(P2, "dim_merchant", merchants[["MerchantKey","MerchantID","MerchantName","Category","CountryCode","Region","Tier"]])
out(P2, "fact_transactions", tx[["TransactionID","DateKey","MerchantKey","CustomerID","PaymentMethod","GrossAmountEUR",
    "CardCountry","IPCountry","DeviceType","Is3DS","AccountAgeDays","TxnLast24h","RiskScore","Decision","IsFraud",
    "IsChargeback","ChargebackReason","ChargebackDateKey","ChargebackFeeEUR"]])
out(P2, "dim_risk_band", pd.DataFrame({"BandOrder":[1,2,3,4],"RiskBand":["Low","Medium","High","Critical"],
                                      "MinScore":[0,30,55,80],"MaxScore":[29.9,54.9,79.9,100]}))

# =================== P3: Multi-tenant merchant analytics with RLS ===================
P3 = "03-multitenant-merchant-rls"
out(P3, "dim_date", DATE)
out(P3, "dim_merchant", merchants[["MerchantKey","MerchantID","MerchantName","Category","CountryCode","Region","Tier","AccountManagerEmail"]])
out(P3, "fact_orders", orders[["OrderID","DateKey","MerchantKey","CustomerID","Channel","Status","GrossAmountEUR","DiscountEUR","RefundEUR","PaymentFeeEUR"]])
sec = [{"UserEmail": e, "Role": "AccountManager", "Region": r, "MerchantID": ""} for r, e in
       merchants[["Region","AccountManagerEmail"]].drop_duplicates().values]
for mid in merchants.MerchantID.sample(12, random_state=3):
    sec.append({"UserEmail": f"owner.{mid.lower()}@merchant-demo.com", "Role":"MerchantOwner", "Region":"", "MerchantID": mid})
sec.append({"UserEmail":"cfo@marbill-demo.com","Role":"Executive","Region":"ALL","MerchantID":""})
out(P3, "security_user_access", pd.DataFrame(sec))

# =================== P4: Support & fulfillment ops (raw API-style JSON -> ETL) ===================
P4 = "04-support-fulfillment-ops"
recent = orders[pd.to_datetime(orders.OrderDate) >= "2025-07-01"].sample(frac=.35, random_state=4).reset_index(drop=True)
m = len(recent)
ship = pd.to_datetime(recent.OrderDate) + pd.to_timedelta(rng.gamma(2, .8, m), unit="D")
carrier = rng.choice(["DHL","UPS","FedEx","DPD","Royal Mail","Delhivery"], m)
transit = rng.gamma(3, {"DHL":.9,"UPS":.8,"FedEx":.75,"DPD":1.0,"Royal Mail":1.1,"Delhivery":1.3}.__getitem__(carrier[0]) if False else 1, m)
transit = transit * pd.Series(carrier).map({"DHL":.9,"UPS":.8,"FedEx":.75,"DPD":1.0,"Royal Mail":1.1,"Delhivery":1.3}).values
deliv = ship + pd.to_timedelta(transit, unit="D")
shipments = pd.DataFrame({"order_id": recent.OrderID, "merchant_id": recent.MerchantKey.map(merchants.set_index("MerchantKey").MerchantID),
    "carrier": carrier, "ordered_at": pd.to_datetime(recent.OrderDate).dt.strftime("%Y-%m-%dT10:00:00Z"),
    "shipped_at": ship.dt.strftime("%Y-%m-%dT%H:%M:%SZ"), "delivered_at": deliv.dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
    "promised_days": rng.choice([5,7,9], m, p=[.3,.5,.2])})
shipments.loc[rng.random(m) < .03, "delivered_at"] = None  # lost / in transit
shipments.loc[rng.random(m) < .01, "carrier"] = shipments.carrier.str.lower()  # dirty casing for Power Query
out(P4, "raw_shipments", shipments)
T = int(m*.12)
tk = recent.sample(T, random_state=5).reset_index(drop=True)
created = pd.to_datetime(tk.OrderDate) + pd.to_timedelta(rng.integers(1, 15*24, T), unit="h")
prio = rng.choice(["low","normal","high","urgent"], T, p=[.25,.5,.18,.07])
frt = rng.gamma(2, pd.Series(prio).map({"low":6,"normal":4,"high":1.5,"urgent":.6}).values)
res = frt + rng.gamma(2, 8, T)
tickets = [{"id": 900000+i, "created_at": created[i].strftime("%Y-%m-%dT%H:%M:%SZ"),
            "priority": prio[i], "channel": rng.choice(["email","chat","web","voice"]),
            "tags": list(rng.choice(["where_is_my_order","refund","damaged","wrong_item","payment","account"], rng.integers(1,3), replace=False)),
            "external_id": str(int(tk.OrderID[i])), "status": rng.choice(["solved","closed","open","pending"], p=[.6,.3,.06,.04]),
            "metrics": {"reply_time_in_minutes": {"business": int(frt[i]*60)}, "full_resolution_time_in_minutes": {"business": int(res[i]*60)},
                        "reopens": int(rng.poisson(.15))},
            "satisfaction_rating": {"score": rng.choice(["good","bad","unoffered"], p=[.55,.12,.33])}}
           for i in range(T)]
os.makedirs(f"{ROOT}/{P4}/data", exist_ok=True)
json.dump({"tickets": tickets, "count": T, "next_page": None}, open(f"{ROOT}/{P4}/data/raw_zendesk_tickets.json","w"), indent=1)
out(P4, "dim_date", DATE)
out(P4, "sla_targets", pd.DataFrame({"priority":["low","normal","high","urgent"],"first_reply_hours":[24,8,4,1],"resolution_hours":[120,72,24,8]}))

# =================== P5: Cohort retention & LTV ===================
P5 = "05-merchant-cohort-retention-ltv"
cust = orders[orders.Status=="Completed"][["CustomerID","DateKey","OrderID","GrossAmountEUR","DiscountEUR","COGS_EUR","Channel","MerchantKey"]].copy()
out(P5, "fact_orders", cust)
first = cust.groupby("CustomerID").DateKey.min().reset_index().rename(columns={"DateKey":"FirstOrderDateKey"})
first["AcquisitionChannel"] = cust.sort_values("DateKey").groupby("CustomerID").Channel.first().values
first["CohortMonth"] = pd.to_datetime(first.FirstOrderDateKey.astype(str)).dt.strftime("%Y-%m")
out(P5, "dim_customer", first)
out(P5, "dim_date", DATE)
mk = DATE[["YearMonth"]].drop_duplicates().reset_index(drop=True)
mk["MonthIndex"] = range(len(mk))
out(P5, "dim_cohort_month", mk.rename(columns={"YearMonth":"CohortMonth"}))
out(P5, "dim_months_since", pd.DataFrame({"MonthsSinceFirst": range(0, 30)}))
spend = pd.period_range("2024-01","2026-06",freq="M")
out(P5, "fact_marketing_spend", pd.DataFrame([{"DateKey": int(p.to_timestamp().strftime("%Y%m%d")), "Channel": c,
     "SpendEUR": round({"Web":15e3,"Mobile App":11e3,"Marketplace":4e3,"Social Commerce":7e3}[c]*rng.normal(1,.12)*(1+.015*(p-spend[0]).n),2)}
     for p in spend for c in CHANNELS]))
print("orders", len(orders), "tx", len(tx), "ship", len(shipments), "tickets", T, "customers", len(first))

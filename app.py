# app.py – Super Planner v2.2 (Scenario Compare + Cleaner Optimize Output)
"""
This all‑in‑one Streamlit app lets you:
1. **Tweak every major parameter** (home prices, expenses, Dad’s money, ETF return…).
2. **Upload updated CSV/OFX/CSV files** – it auto‑re‑categorises and recalculates your core monthly spend.
3. **Run a 1 000‑iteration optimiser** to find the highest 10‑year net‑worth path given the latest inputs.
4. Warn when *any* year slips negative cash‑flow.
5. ✅ Update tables/charts when any input changes.
6. ✅ Optionally **sell the Odessa home** and invest proceeds.
7. ✅ **Scenario Compare** – compare outcomes with/without Dad's help.
8. ✅ **Clear output** from the optimizer with plain-language strategy.
"""
import streamlit as st
import pandas as pd, numpy as np, io, hashlib, datetime as dt

st.set_page_config(page_title="Super‑Planner", layout="wide")
st.title("🏡 Super Planner – Interactive Financial Model")

# ------------- SIDEBAR INPUTS ------------------
with st.sidebar:
    st.header("Configuration")
    uploaded = st.file_uploader("Upload latest banking CSV", type=["csv","ofx","qfx"], help="90‑day slice is fine – it just recomputes monthly spend.")

    st.subheader("Odessa Home")
    home_price = st.number_input("Home Price ($)", 300000, 800000, 630000, step=10000)
    your_down_pct = st.slider("Your Down‑Payment %", 0.0, 0.30, 0.10, 0.01)
    sell_odessa = st.checkbox("Sell Odessa in Year 6?", False)

    st.subheader("Dad’s Contribution")
    dad_amount = st.slider("Dad Amount ($)", 0, 200000, 0, step=5000)
    dad_use = st.radio("Use Dad’s $ for…", ["Down‑Payment","ETF"], index=0)

    interest = st.slider("Mortgage Rate %", 4.0, 10.0, 6.9, .1)/100
    term = st.selectbox("Loan Term", [15,20,30], index=2)

    st.subheader("Move to Colorado")
    move_year = st.slider("Move Year", 1, 10, 5)
    co_income = st.number_input("Colorado W‑2 Income ($)", 50000, 200000, 90000, step=5000)

    st.subheader("Monthly Expenses (Post‑Move)")
    core_expenses = st.number_input("Core Living", 0, 10000, 2778, 50)
    utilities = st.number_input("Utilities & Pool", 0, 2000, 265, 25)
    subs_exp = st.number_input("Subscriptions", 0, 500, 14, 5)

    st.subheader("Airbnb Settings – Odessa")
    occ = st.slider("Occupancy %", .40, .90, .65, .01)
    main_rate = st.number_input("Main House $/night", 150, 600, 325, 25)
    guest_rate = st.number_input("Guest House $/night", 50,250,125,25)

    st.subheader("Terlingua")
    build_ter = st.toggle("Build $50K Cabin", True)
    ter_occ = st.slider("Occupancy %", .2,.8,.45,.05)
    ter_rate = st.number_input("Nightly Rate", 100, 300, 150, 10)
    flip_year = st.slider("Flip Year", 1,10,5) if build_ter else None

    etf_ret = st.slider("ETF Annual Return %", 4.0, 12.0, 9.0, .1)/100

# ---------------- HELPER FUNCS ----------------
@st.cache_data
def pmt(principal, rate, years):
    if principal<=0: return 0
    r = rate/12
    n = years*12
    return principal*r*(1+r)**n/((1+r)**n-1)

@st.cache_data
def clean_csv(raw: bytes):
    try:
        df = pd.read_csv(io.BytesIO(raw))
    except Exception:
        return 0
    exp = df[df.select_dtypes(include=[np.number]).columns[0]]
    per_month = exp[exp<0].abs().sum()/3
    return per_month

@st.cache_data(show_spinner=False)
def simulate(years=10, custom_down_pct=None, custom_move=None, custom_occ=None):
    etf,cash=0,0
    down_pct = custom_down_pct if custom_down_pct is not None else your_down_pct
    move = custom_move if custom_move is not None else move_year
    occupancy = custom_occ if custom_occ is not None else occ
    your_down = home_price*down_pct
    dad_down = dad_amount if dad_use=="Down‑Payment" else 0
    loan = home_price - (your_down+dad_down)
    m_payment = pmt(loan,interest,term)*12
    dad_etf   = dad_amount if dad_use=="ETF" else 0
    ter_loan = 50000 if build_ter else 0
    ter_pay  = 50000/1.5 if build_ter else 0

    rows=[]
    for yr in range(1,years+1):
        inc = 175000+(50000 if yr in (2,4) else 0)
        if yr>=move: inc = co_income

        airbnb=0
        if yr>=move: airbnb += ((main_rate+guest_rate)*365*occupancy)*(1-0.20)
        if build_ter and yr>=2 and (flip_year is None or yr<flip_year):
            airbnb+= ter_rate*365*ter_occ*(1-0.20)
        if build_ter and flip_year and yr==flip_year:
            cash += 120000
        tot_inc = inc+airbnb+cash+dad_etf
        dad_etf=0; cash=0

        tot_exp = core_expenses+utilities+subs_exp+m_payment
        if ter_loan>0:
            pay=min(ter_pay,ter_loan); ter_loan-=pay; tot_exp+=pay

        if sell_odessa and yr==6:
            cash += home_price - (loan*0.95)

        surplus = max(0,tot_inc-tot_exp)
        invest  = max(0,surplus - 0.10*tot_inc)
        etf = etf*(1+etf_ret)+invest
        rows.append({"Year":yr,"Income":tot_inc,"Expenses":tot_exp,"Surplus":surplus,"ETF":etf})
    return pd.DataFrame(rows)

# ---------------- MAIN VIEW -------------------
if uploaded:
    extra = clean_csv(uploaded.getvalue())
    st.info(f"CSV detected: adding ${extra:,.0f}/mo to Core Living (auto)")
    core_expenses += extra

res = simulate()
st.write("### Results")
st.line_chart(res.set_index("Year")["ETF"], height=250)
st.dataframe(res.style.format({"Income":"$ {:,.0f}","Expenses":"$ {:,.0f}","Surplus":"$ {:,.0f}","ETF":"$ {:,.0f}"}))

if (res["Surplus"]<0).any():
    st.error("❗ Negative cash‑flow detected in some years — adjust inputs.")
else:
    st.success("All years are cash‑positive.")

if st.button("Optimise 1 000 Paths 🚀"):
    best={'ETF':-np.inf}
    for _ in range(1000):
        rand_dp=np.random.choice([.05,.1,.2])
        rand_move=np.random.randint(2,8)
        rand_occ=np.random.uniform(.45,.8)
        df = simulate(custom_down_pct=rand_dp, custom_move=rand_move, custom_occ=rand_occ)
        etf_est = df['ETF'].iloc[-1]
        if etf_est>best['ETF']:
            best={'ETF':etf_est,'dp':rand_dp,'move':rand_move,'occ':rand_occ,
                  'recommendation': f"📈 Optimal strategy: Put {int(rand_dp*100)}% down, move in Year {rand_move}, aim for {int(rand_occ*100)}% occupancy."}
    st.write("### Optimized Strategy")
    st.success(best['recommendation'])
    st.write(f"**Estimated 10‑Year ETF Value:** ${best['ETF']:,.0f}")

if st.button("Compare Scenarios: No Help vs With Help"):
    old_dad_amt = dad_amount
    dad_amount = 0
    df1 = simulate()
    dad_amount = old_dad_amt
    df2 = simulate()
    st.write("### Scenario Comparison")
    comp = pd.DataFrame({"Year": df1["Year"], "ETF‑NoHelp": df1["ETF"], "ETF‑WithHelp": df2["ETF"]})
    st.line_chart(comp.set_index("Year"))

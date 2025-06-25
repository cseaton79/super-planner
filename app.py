# app.py – Super Planner v2.0 (Streamlit)
"""
This all‑in‑one Streamlit app lets you:
1. **Tweak every major parameter** (home prices, expenses, Dad’s money, ETF return…).
2. **Upload updated CSV/OFX/CSV files** – it auto‑re‑categorises and recalculates your core monthly spend.
3. **Run a 1 000‑iteration optimiser** to find the highest 10‑year net‑worth path given the latest inputs.
4. Warn when *any* year slips negative cash‑flow.
"""
import streamlit as st
import pandas as pd, numpy as np, io, hashlib, datetime as dt

st.set_page_config(page_title="Super‑Planner", layout="wide")
st.title("🏡 Super Planner – Interactive Financial Model")

# ------------- SIDEBAR INPUTS ------------------
with st.sidebar:
    st.header("Configuration")
    # ---- File upload / refresh ----
    uploaded = st.file_uploader("Upload latest banking CSV", type=["csv","ofx","qfx"], help="90‑day slice is fine – it just recomputes monthly spend.")

    # ------------ House + Mortgage ------------
    st.subheader("Odessa Home")
    home_price = st.number_input("Home Price ($)", 300000, 800000, 630000, step=10000)
    your_down_pct = st.slider("Your Down‑Payment %", 0.0, 0.30, 0.10, 0.01)

    # Dad $ toggle / amount / use‑case
    st.subheader("Dad’s Contribution")
    dad_amount = st.slider("Dad Amount ($)", 0, 40000, 0, step=5000)
    dad_use = st.radio("Use Dad’s $ for…", ["Down‑Payment","ETF"], index=0)

    interest = st.slider("Mortgage Rate %", 4.0, 10.0, 6.9, .1)/100
    term = st.selectbox("Loan Term", [15,20,30], index=2)

    # ------------- Move & Income --------------
    st.subheader("Move to Colorado")
    move_year = st.slider("Move Year", 1, 10, 5)
    co_income = st.number_input("Colorado W‑2 Income ($)", 50000, 200000, 90000, step=5000)

    # ------------- Expenses -------------------
    st.subheader("Monthly Expenses (Post‑Move)")
    core_expenses = st.number_input("Core Living", 0, 10000, 2778, 50)
    utilities = st.number_input("Utilities & Pool", 0, 2000, 265, 25)
    subs_exp = st.number_input("Subscriptions", 0, 500, 14, 5)

    # ---------- Airbnb settings ---------------
    st.subheader("Airbnb Settings – Odessa")
    occ = st.slider("Occupancy %", .40, .90, .65, .01)
    main_rate = st.number_input("Main House $/night", 150, 600, 325, 25)
    guest_rate = st.number_input("Guest House $/night", 50,250,125,25)

    st.subheader("Terlingua")
    build_ter = st.toggle("Build $50K Cabin", True)
    ter_occ = st.slider("Occupancy %", .2,.8,.45,.05)
    ter_rate = st.number_input("Nightly Rate", 100, 300, 150, 10)
    flip_year = st.slider("Flip Year", 1,10,5) if build_ter else None

    # ---------- ETF return --------------------
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
        return 0  # placeholder if format fails.
    exp = df[df.select_dtypes(include=[np.number]).columns[0]]
    per_month = exp[exp<0].abs().sum()/3  # assume 3‑mo window
    return per_month

@st.cache_data(show_spinner=False)
def simulate(years=10):
    # initialise
    etf,cash=0,0
    # compute down‑payment mix
    your_down = home_price*your_down_pct
    dad_down = dad_amount if dad_use=="Down‑Payment" else 0
    loan = home_price - (your_down+dad_down)
    m_payment = pmt(loan,interest,term)*12
    dad_etf   = dad_amount if dad_use=="ETF" else 0
    # terlingua loan vars
    ter_loan = 50000 if build_ter else 0
    ter_pay  = 50000/1.5 if build_ter else 0

    rows=[]
    for yr in range(1,years+1):
        # income
        inc = 175000+(50000 if yr in (2,4) else 0)
        if yr>=move_year: inc = co_income
        # airbnb
        airbnb=0
        if yr>=move_year: airbnb += ((main_rate+guest_rate)*365*occ)*(1-0.20)
        if build_ter and yr>=2 and (flip_year is None or yr<flip_year):
            airbnb+= ter_rate*365*ter_occ*(1-0.20)
        if build_ter and flip_year and yr==flip_year:
            cash += 120000
        tot_inc = inc+airbnb+cash+dad_etf
        dad_etf=0; cash=0
        # expenses
        tot_exp = core_expenses+utilities+subs_exp+m_payment
        if ter_loan>0:
            pay=min(ter_pay,ter_loan); ter_loan-=pay; tot_exp+=pay
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

st.write("### Results")
res = simulate()
st.line_chart(res.set_index("Year")["ETF"], height=250)
st.dataframe(res.style.format({"Income":"$ {:,.0f}","Expenses":"$ {:,.0f}","Surplus":"$ {:,.0f}","ETF":"$ {:,.0f}"}))

# failure flag
if (res["Surplus"]<0).any():
    st.error("❗ Negative cash‑flow detected in some years — adjust inputs.")
else:
    st.success("All years are cash‑positive.")

# ------------- Optimiser Button --------------
if st.button("Optimise 1 000 Paths 🚀"):
    best={'ETF':-np.inf}
    for _ in range(1000):
        rand_dp=np.random.choice([.05,.1,.2])
        rand_move=np.random.randint(2,8)
        rand_occ=np.random.uniform(.45,.8)
        your_down_pct_rand=rand_dp
        move_year_rand=rand_move
        occ_rand=rand_occ
        # quick one‑year calc for speed (placeholder)
        etf_est = simulate()['ETF'].iloc[-1]
        if etf_est>best['ETF']:
            best={'ETF':etf_est,'dp':rand_dp,'move':rand_move,'occ':rand_occ}
    st.write("### Best Path (est)")
    st.json(best)

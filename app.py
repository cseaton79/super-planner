# app.py – Super Planner v2.3  
"""
Major tweaks from user feedback:
1. **All widgets inside a `st.form`** – you hit **“Update / Run”** to refresh results (no more half‑blank tables).
2. **Inputs menu is a top expander panel**, not a sidebar slide‑out.
3. Dad’s contribution slider now 0‑200 K.
4. Cleaner optimiser output + plan summary.
"""
import streamlit as st, pandas as pd, numpy as np, io

st.set_page_config(page_title="Super‑Planner", layout="wide")
st.title("🏡 Super Planner – Interactive Financial Model")

###############################################################################
# Helper / finance functions
###############################################################################

def pmt(principal: float, rate: float, years: int):
    if principal <= 0: return 0
    r = rate / 12
    n = years * 12
    return principal * r * (1 + r) ** n / ((1 + r) ** n - 1)

###############################################################################
# INPUT PANEL (top expander)
###############################################################################
with st.expander("⚙️ Configure Inputs", expanded=True):
    with st.form("input_form"):
        col1, col2, col3 = st.columns(3)
        # ------------- Column 1 -------------
        with col1:
            st.subheader("Odessa Home")
            home_price = st.number_input("Price $", 300_000, 800_000, 630_000, 10_000)
            your_down_pct = st.slider("Your Down %", 0.00, 0.30, 0.10, 0.01)
            sell_odessa = st.checkbox("Sell in Year 6", False)
        # ------------- Column 2 -------------
        with col2:
            st.subheader("Dad Contribution")
            dad_amt = st.slider("Dad $", 0, 200_000, 0, 5_000)
            dad_use = st.radio("Apply Dad $ to", ["Down‑Payment", "ETF"])
            st.subheader("Mortgage")
            rate = st.slider("Rate %", 4.0, 10.0, 6.9, 0.1) / 100
            term = st.selectbox("Years", [15, 20, 30], index=2)
        # ------------- Column 3 -------------
        with col3:
            st.subheader("Colorado Move + Income")
            move_year = st.slider("Move Year", 1, 10, 5)
            co_income = st.number_input("CO W‑2 $", 50_000, 200_000, 90_000, 5_000)
            st.subheader("ETF & Optimize")
            etf_ret = st.slider("ETF Return %", 4.0, 12.0, 9.0, 0.1) / 100
        # ------------- Expenses Row -------------
        st.markdown("---")
        colA, colB, colC = st.columns(3)
        with colA:
            core_exp = st.number_input("Core Living $/mo", 0, 10_000, 2_778, 50)
        with colB:
            utilities = st.number_input("Utilities+Pool $/mo", 0, 2_000, 265, 25)
        with colC:
            subs = st.number_input("Subscriptions $/mo", 0, 500, 14, 5)
        # ------------- Airbnb -------------
        st.markdown("---")
        st.subheader("Airbnb Settings – Odessa")
        air_occ = st.slider("Occupancy %", 0.40, 0.90, 0.65, 0.01)
        main_rt = st.number_input("Main House $/night", 150, 600, 325, 25)
        guest_rt = st.number_input("Guest House $/night", 50, 250, 125, 25)
        st.subheader("Terlingua Cabin")
        build_ter = st.toggle("Build $50K Cabin", True)
        ter_occ = st.slider("Ter Occ %", 0.20, 0.80, 0.45, 0.05)
        ter_rt = st.number_input("Ter $/night", 100, 300, 150, 10)
        flip_year = st.slider("Flip Year", 1, 10, 5) if build_ter else None
        # ------------- Upload -------------
        uploaded = st.file_uploader("Upload Latest CSV (optional)", type=["csv"])
        submitted = st.form_submit_button("🔄 Update / Run")

###############################################################################
# SIMULATION (runs only when form submitted)
###############################################################################
if submitted:
    # ------- Import CSV override for core_exp -------
    if uploaded:
        try:
            tmp = pd.read_csv(uploaded)
            numcol = tmp.select_dtypes(include=[np.number]).columns[0]
            extra = tmp[numcol][tmp[numcol] < 0].abs().sum() / 3  # 3‑month slice
            st.info(f"CSV detected → adding ${extra:,.0f}/mo to Core Living")
            core_exp += extra
        except Exception as e:
            st.warning("CSV parse failed – using manual expenses.")

    # ------- Derived values -------
    dp_user = home_price * your_down_pct
    dp_dad = dad_amt if dad_use == "Down‑Payment" else 0
    loan = home_price - (dp_user + dp_dad)
    m_payment = pmt(loan, rate, term) * 12  # annual

    def run_sim(years=10, dp_pct=None, mv=None, occ=None):
        dp_pct = dp_pct if dp_pct is not None else your_down_pct
        mv = mv if mv is not None else move_year
        occ = occ if occ is not None else air_occ
        etf = cash = 0
        loan_bal = loan
        results = []
        ter_loan = 50_000 if build_ter else 0
        ter_pay = 50_000 / 1.5 if build_ter else 0
        for yr in range(1, years + 1):
            income = 175_000 + (50_000 if yr in (2, 4) else 0)
            if yr >= mv:
                income = co_income
            # Airbnb
            air = 0
            if yr >= mv:
                air += ((main_rt + guest_rt) * 365 * occ) * .8
            if build_ter and yr >= 2 and (flip_year is None or yr < flip_year):
                air += ter_rt * 365 * ter_occ * .8
            if build_ter and flip_year and yr == flip_year:
                cash += 120_000
            total_income = income + air + cash + (dp_dad if dad_use == "ETF" and yr == 1 else 0)
            cash = 0
            # Expenses
            exp = (core_exp + utilities + subs) * 12 + m_payment
            if ter_loan > 0:
                pay = min(ter_pay, ter_loan)
                ter_loan -= pay
                exp += pay
            if sell_odessa and yr == 6:
                cash += home_price - loan * 0.95
            surplus = max(0, total_income - exp)
            invest = max(0, surplus - 0.10 * total_income)
            etf = etf * (1 + etf_ret) + invest
            results.append({"Year": yr, "Income": total_income, "Expenses": exp, "Surplus": surplus, "ETF": etf})
        return pd.DataFrame(results)

    df = run_sim()
    st.line_chart(df.set_index("Year")["ETF"], height=260)
    st.dataframe(df.style.format("$ {:,.0f}"))

    # ------------- Optimiser -------------
    if st.button("⚡ Optimise 1 000 Paths"):
        best = {"ETF": -np.inf}
        for _ in range(1000):
            dp = np.random.choice([.05, .10, .20])
            mv = np.random.randint(2, 8)
            occ = np.random.uniform(.45, .80)
            net = run_sim(dp_pct=dp, mv=mv, occ=occ)["ETF"].iloc[-1]
            if net > best["ETF"]:
                best = {"dp": dp, "mv": mv, "occ": occ, "ETF": net}
        st.success(f"Optimal ➜ Put {int(best['dp']*100)}% down, move Yr {best['mv']}, target {int(best['occ']*100)}% occ.\n10‑Yr ETF ≈ ${best['ETF']:,.0f}")

    # ------------- Scenario Compare -------------
    if st.button("Compare: No Dad vs With Dad"):
        saved = dad_amt
        dad_amt = 0
        nohelp = run_sim()
        dad_amt = saved
        withhelp = run_sim()
        compare_df = pd.DataFrame({"Year": nohelp["Year"], "No Dad": nohelp["ETF"], "With Dad": withhelp["ETF"]})
        st.line_chart(compare_df.set_index("Year"))

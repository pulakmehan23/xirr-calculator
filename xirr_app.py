
import streamlit as st
import pandas as pd
import numpy as np
import io
from datetime import datetime

st.set_page_config(page_title="Multi-Deal XIRR Calculator", layout="wide")

# ----------------------------
# Custom CSS for UI polish
# ----------------------------
st.markdown("""
<style>
.stButton>button {
    background-color: #2563eb;
    color: white;
    border-radius: 8px;
    padding: 8px 20px;
    margin: 5px;
    font-weight: bold;
}
.stDataFrame, .stDataEditor {
    border: 1px solid #e2e8f0;
    border-radius: 6px;
}
</style>
""", unsafe_allow_html=True)

st.markdown("<h1 style='text-align:center;'> Multi-Deal XIRR Calculator</h1>", unsafe_allow_html=True)

# ----------------------------
# Helper Functions
# ----------------------------
def xirr(cashflows, guess=0.1):
    """cashflows = list of tuples (date, amount)"""
    def npv(rate):
        return sum([
            cf / ((1 + rate) ** ((d - cashflows[0][0]).days / 365))
            for d, cf in cashflows
        ])
    rate = guess
    for _ in range(100):
        f = npv(rate)
        f_prime = sum([
            - (d - cashflows[0][0]).days/365 * cf /
            ((1 + rate) ** (((d - cashflows[0][0]).days / 365) + 1))
            for d, cf in cashflows
        ])
        if f_prime == 0:
            break
        rate -= f / f_prime
    return rate

def apply_bbsy(cashflows_df, bbsy_df, anniv_date=None):
    """Adjust floating rate cashflows using BBSY resets"""
    df = cashflows_df.copy()
    df = df.sort_values("Date").reset_index(drop=True)

    if bbsy_df is not None and anniv_date is not None:
        if isinstance(anniv_date, pd.Timestamp):
            anniv_date = anniv_date.to_pydatetime()
        elif not isinstance(anniv_date, datetime):
            anniv_date = datetime.combine(anniv_date, datetime.min.time())

        df["Rate"] = np.nan
        for i, row in df.iterrows():
            applicable = bbsy_df[bbsy_df["Date"] <= row["Date"]]
            if not applicable.empty:
                df.loc[i, "Rate"] = applicable.iloc[-1]["Rate"]
        df["Adj_CF"] = df["Cashflow"] * (1 + df["Rate"].fillna(0)/100)
    else:
        df["Adj_CF"] = df["Cashflow"]

    return df

# ----------------------------
# Session State for Deals
# ----------------------------
if "deals" not in st.session_state:
    st.session_state.deals = {
        1: pd.DataFrame({
            "Date": [datetime(2025,1,1), datetime(2025,6,1)],
            "Cashflow": [-10000, 2000],
            "Base Rate": [5.0, 5.0],
            "Higher Rate": [None, None],
            "Type": ["Outflow", "Inflow"]

        })
    }
if "settings" not in st.session_state:
    st.session_state.settings = {
        1: {"rate_type": "Fixed", "anniv_date": None}
    }

# ----------------------------
# Add Deal Button
# ----------------------------
if st.button(" Add Deal"):
    next_id = max(st.session_state.deals.keys()) + 1
    st.session_state.deals[next_id] = pd.DataFrame({
        "Date": [datetime(2025,1,1)],
        "Cashflow": [0],
        "Base Rate": [5.0],
        "Higher Rate": [None],
        "Type": ["Outflow"]
    })
    st.session_state.settings[next_id] = {"rate_type": "Fixed", "anniv_date": None}

# ----------------------------
# Upload BBSY
# ----------------------------
st.subheader(" Upload BBSY Rates")
bbsy_file = st.file_uploader("Upload BBSY (CSV or Excel)", type=["csv", "xlsx"])
bbsy_df = None
if bbsy_file:

    if bbsy_file.name.endswith(".csv"):
        bbsy_df = pd.read_csv(bbsy_file, parse_dates=[0])
    else:
        bbsy_df = pd.read_excel(bbsy_file, parse_dates=[0])
    bbsy_df.columns = ["Date", "Rate"]
    st.dataframe(bbsy_df)

# ----------------------------
# Deal Sections
# ----------------------------
results = []
base_rate_global = st.number_input(" Base Rate (%)", value=5.0, step=0.1)

for deal_id, df in st.session_state.deals.items():
    with st.expander(f" Deal {deal_id} Settings", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            rate_type = st.radio(f"Rate Type (Deal {deal_id})", ["Fixed", "Floating"], 
                                 key=f"rate_{deal_id}", 
                                 index=0 if st.session_state.settings[deal_id]["rate_type"]=="Fixed" else 1)
            st.session_state.settings[deal_id]["rate_type"] = rate_type
        with col2:
            if rate_type == "Floating":
                anniv_date = st.date_input(f"Anniversary Date (Deal {deal_id})", key=f"anniv_{deal_id}")

                st.session_state.settings[deal_id]["anniv_date"] = anniv_date
            else:
                st.write("Anniversary Date (N/A)")

        st.write(" Enter Cashflows for this Deal:")
        st.session_state.deals[deal_id] = st.data_editor(
            df,
            num_rows="dynamic",
            use_container_width=True
        )

# ----------------------------
# Calculate Button
# ----------------------------
if st.button(" Calculate XIRR for All Deals"):
    summary = []
    for deal_id, df in st.session_state.deals.items():
        settings = st.session_state.settings[deal_id]

        # Adjust for floating
        if settings["rate_type"] == "Floating" and bbsy_df is not None:
            adj_df = apply_bbsy(df, bbsy_df, settings["anniv_date"])
        else:
            adj_df = df.copy()
            adj_df["Adj_CF"] = adj_df["Cashflow"]

        # Build flows
        flows = [(row.Date.to_pydatetime(), row.Adj_CF) for row 

in adj_df.itertuples(index=False)]

        try:
            result = xirr(flows) * 100
            ups = result - base_rate_global

            st.subheader(f" Deal {deal_id} Results")
            st.success(f"Effective XIRR: {result:.2f}%")
            st.metric("Ups vs Base", f"{ups:.2f}%", delta=ups)
            st.dataframe(adj_df)

            summary.append({
                "Deal": deal_id,
                "XIRR (%)": result,
                "Base Rate (%)": base_rate_global,
                "Ups (%)": ups
            })

        except Exception as e:
            st.error(f" Error in Deal {deal_id}: {e}")

    # Summary
    if summary:
        st.subheader(" All Deals Summary")
        summary_df = pd.DataFrame(summary)
        st.dataframe(summary_df)

        # Export
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine="xlsxwriter") as writer:

            for d_id, df in st.session_state.deals.items():
                df.to_excel(writer, sheet_name=f"Deal{d_id}", index=False)
            if bbsy_df is not None:
                bbsy_df.to_excel(writer, sheet_name="BBSY", index=False)
            summary_df.to_excel(writer, sheet_name="Summary", index=False)

        st.download_button(
            " Export Results",
            data=out,
            file_name="xirr_results.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

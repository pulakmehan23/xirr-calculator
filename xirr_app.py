Import streamlit as st
Import pandas as pd
Import numpy as np
Import io
From datetime import datetime

St.set_page_config(page_title="Multi-Deal XIRR Calculator", layout="wide")

# ----------------------------
# Custom CSS for polish
# ----------------------------
St.markdown(“””
<style>
.stButton>button {
    Background-color: #2563eb;
    Color: white;
    Border-radius: 8px;
    Padding: 10px 22px;
    Font-size: 15px;
    Font-weight: bold;
    Margin: 6px;
}
.stButton>button:hover {
    Background-color: #1e40af;
}
</style>
“””, unsafe_allow_html=True)

St.markdown(“<h1 style=’text-align:center;’>📊 Multi-Deal XIRR Calculator</h1>”, unsafe_allow_html=True)

# ----------------------------
# Helper Functions
# ----------------------------
Def xirr(cashflows, guess=0.1):
    “””cashflows = list of tuples (date, amount)”””
    Def npv(rate):
        Return sum([
            Cf / ((1 + rate) ** ((d – cashflows[0][0]).days / 365))
            For d, cf in cashflows
        ])
    Rate = guess
    For _ in range(100):
        F = npv(rate)
        F_prime = sum([
-	(d – cashflows[0][0]).days/365 * cf /
            ((1 + rate) ** (((d – cashflows[0][0]).days / 365) + 1))
            For d, cf in cashflows
        ])
        If f_prime == 0:
            Break
        Rate -= f / f_prime
    Return rate

Def apply_bbsy(cashflows_df, bbsy_df, anniv_date=None):
    “””Adjust floating rate cashflows using BBSY resets”””
    Df = cashflows_df.copy()
    Df = df.sort_values(“Paid Out Date”).reset_index(drop=True)

    If bbsy_df is not None and anniv_date is not None:
        If isinstance(anniv_date, pd.Timestamp):
            Anniv_date = anniv_date.to_pydatetime()
        Elif not isinstance(anniv_date, datetime):
            Anniv_date = datetime.combine(anniv_date, datetime.min.time())

        Df[“Rate”] = np.nan
        For i, row in df.iterrows():
            Applicable = bbsy_df[bbsy_df[“Date”] <= row[“Paid Out Date”]]
            If not applicable.empty:
                Df.loc[i, “Rate”] = applicable.iloc[-1][“Rate”]
        Df[“Adj_CF”] = df[“Cashflow”] * (1 + df[“Rate”].fillna(0)/100)
    Else:
        Df[“Adj_CF”] = df[“Cashflow”]

    Return df

# ----------------------------
# Session State for Deals
# ----------------------------
If “deals” not in st.session_state:
    St.session_state.deals = {
        1: pd.DataFrame({
            “Paid Out Date”: [datetime(2025,1,1), datetime(2025,6,1)],
            “Cashflow”: [-10000, 2000],
            “Base Rate”: [5.0, 5.0],
            “Higher Rate”: [None, None],
            “Type”: [“Outflow”, “Inflow”]
        })
    }
If “settings” not in st.session_state:
    St.session_state.settings = {
        1: {“rate_type”: “Fixed”, “anniv_date”: None}
    }

# ----------------------------
# Add Deal
# ----------------------------
If st.button(“➕ Add Deal”):
    Next_id = max(st.session_state.deals.keys()) + 1
    St.session_state.deals[next_id] = pd.DataFrame({
        “Paid Out Date”: [datetime(2025,1,1)],
        “Cashflow”: [0],
        “Base Rate”: [5.0],
        “Higher Rate”: [None],
        “Type”: [“Outflow”]
    })
    St.session_state.settings[next_id] = {“rate_type”: “Fixed”, “anniv_date”: None}

# ----------------------------
# BBSY Upload
# ----------------------------
St.subheader(“📥 Upload BBSY Rates”)
Bbsy_file = st.file_uploader(“Upload BBSY (CSV or Excel)”, type=[“csv”, “xlsx”])
Bbsy_df = None
If bbsy_file:
    If bbsy_file.name.endswith(“.csv”):
        Bbsy_df = pd.read_csv(bbsy_file, parse_dates=[0])
    Else:
        Bbsy_df = pd.read_excel(bbsy_file, parse_dates=[0])
    Bbsy_df.columns = [“Date”, “Rate”]
    St.dataframe(bbsy_df)

# ----------------------------
# Global Settings
# ----------------------------
Base_rate_global = st.number_input(“🌍 Base Rate (%)”, value=5.0, step=0.1)

# ----------------------------
# Deal Sections
# ----------------------------
Results = []
For deal_id, df in st.session_state.deals.items():
    With st.expander(f”⚙️ Deal {deal_id} Settings”, expanded=True):
        Col1, col2 = st.columns(2)
        With col1:
            Rate_type = st.radio(f”Rate Type (Deal {deal_id})”, [“Fixed”, “Floating”], 
                                 Key=f”rate_{deal_id}”, 
                                 Index=0 if st.session_state.settings[deal_id][“rate_type”]==”Fixed” else 1)
            St.session_state.settings[deal_id][“rate_type”] = rate_type
        With col2:
            If rate_type == “Floating”:
                Anniv_date = st.date_input(f”Anniversary Date (Deal {deal_id})”, key=f”anniv_{deal_id}”)
                St.session_state.settings[deal_id][“anniv_date”] = anniv_date
            Else:
                St.text(“Anniversary Date (N/A)”)

        St.write(“✍️ Enter Cashflows for this Deal:”)
        St.session_state.deals[deal_id] = st.data_editor(
            Df,
            Num_rows=”dynamic”,
            Use_container_width=True
        )

# ----------------------------
# Calculate
# ----------------------------
If st.button(“🔄 Calculate XIRR for All Deals”):
    Summary = []
    For deal_id, df in st.session_state.deals.items():
        Settings = st.session_state.settings[deal_id]

        # Adjust for floating
        If settings[“rate_type”] == “Floating” and bbsy_df is not None:
            Adj_df = apply_bbsy(df, bbsy_df, settings[“anniv_date”])
        Else:
            Adj_df = df.copy()
            Adj_df[“Adj_CF”] = adj_df[“Cashflow”]

        # Build flows
        Flows = [(row._asdict()[“Paid Out Date”], row._asdict()[“Adj_CF”]) for row in adj_df.itertuples(index=False)]

        Try:
            Result = xirr(flows) * 100
            Ups = result – base_rate_global

            St.subheader(f”📌 Deal {deal_id} Results”)
            St.success(f”Effective XIRR: {result:.2f}%”)
            St.metric(“Ups vs Base”, f”{ups:.2f}%”, delta=ups)
            St.dataframe(adj_df)

            Summary.append({
                “Deal”: deal_id,
                “XIRR (%)”: result,
                “Base Rate (%)”: base_rate_global,
                “Ups (%)”: ups
            })

        Except Exception as e:
            St.error(f”❌ Error in Deal {deal_id}: {e}”)

    # Summary
    If summary:
        St.subheader(“📊 All Deals Summary”)
        Summary_df = pd.DataFrame(summary)
        St.dataframe(summary_df)

        # Export
        Out = io.BytesIO()
        With pd.ExcelWriter(out, engine=”xlsxwriter”) as writer:
            For d_id, df in st.session_state.deals.items():
                Df.to_excel(writer, sheet_name=f”Deal{d_id}”, index=False)
            If bbsy_df is not None:
                Bbsy_df.to_excel(writer, sheet_name=”BBSY”, index=False)
            Summary_df.to_excel(writer, sheet_name=”Summary”, index=False)

        St.download_button(
            “💾 Export Results”,
            Data=out,
            File_name=”xirr_results.xlsx”,
            Mime=”application/vnd.openxmlformats-officedocument.spreadsheetml.sheet”
        )

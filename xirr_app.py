import streamlit as st
import pandas as pd
import numpy as np
import io
from datetime import datetime
st.set_page_config(page_title="Multi-Deal XIRR Calculator", layout="wide")
st.title(" Multi-Deal XIRR Calculator")
# ----------------------------# Helper Functions# ----------------------------def xirr(cashflows, guess=0.1):    """cashflows = list of tuples (date, amount)"""    def npv(rate):        return sum([            cf / ((1 + rate) ** ((d - cashflows[0][0]).days / 365))            for d, cf in cashflows        ])    rate = guess    for _ in range(100):        f = npv(rate)        f_prime = sum([            - (d - cashflows[0][0]).days/365 * cf /            ((1 + rate) ** (((d - cashflows[0][0]).days / 365) + 1))            for d, cf in cashflows        ])        rate -= f / f_prime    return rate
def apply_bbsy(cashflows_df, bbsy_df, anniv_date=None):    
    """    
    Adjust floating rate cashflows using BBSY resets.    
    - cashflows_df: DataFrame with [Date, Cashflow]    
    - bbsy_df: DataFrame with [Date, Rate]    
    - anniv_date: resets annually from this date    
    """    
    df = cashflows_df.copy()    
    df = df.sort_values("Date").reset_index(drop=True)
    if bbsy_df is not None and anniv_date is not None:        # ensure anniv_date is datetime        if isinstance(anniv_date, pd.Timestamp):            anniv_date = anniv_date.to_pydatetime()        elif not isinstance(anniv_date, datetime):            anniv_date = datetime.combine(anniv_date, datetime.min.time())
        df["Rate"] = np.nan        
        for i, row in df.iterrows():            
            applicable = bbsy_df[bbsy_df["Date"] <= row["Date"]]            
            if not applicable.empty:                
                df.loc[i, "Rate"] = applicable.iloc[-1]["Rate"]        
                df["Adj_CF"] = df["Cashflow"] * (1 + df["Rate"].fillna(0)/100)    
            else:        df["Adj_CF"] = df["Cashflow"]
    return df
# ----------------------------# Step 1: Upload Files# ----------------------------st.header(" Upload Data")
cash_file = st.file_uploader("Upload Cashflows (CSV or Excel)", type=["csv", "xlsx"])
bbsy_file = st.file_uploader("Upload BBSY Rates (CSV or Excel)", type=["csv", "xlsx"])
cashflows_df, bbsy_df = None, None
if cash_file:    if cash_file.name.endswith(".csv"):        
    cashflows_df = pd.read_csv(cash_file, parse_dates=[0])    
else:        cashflows_df = pd.read_excel(cash_file, parse_dates=[0])    cashflows_df.columns = ["Date", "Cashflow"]    st.write("Cashflows Preview")    st.dataframe(cashflows_df)
if bbsy_file:    
if bbsy_file.name.endswith(".csv"):        bbsy_df = pd.read_csv(bbsy_file, parse_dates=[0])    
else:        bbsy_df = pd.read_excel(bbsy_file, parse_dates=[0])    bbsy_df.columns = ["Date", "Rate"]    st.write("BBSY Preview")    st.dataframe(bbsy_df)
# ----------------------------# Step 2: Deal Settings# ----------------------------st.header(" Deal Settings")
deal_count = st.number_input("Number of deals", min_value=1, max_value=10, value=1, step=1)
base_rate = st.number_input("Base Rate (%)", value=5.0, step=0.1)
deal_settings = []
for d in range(1, deal_count + 1):    
with st.expander(f" Deal {d} Settings", expanded=(d == 1)):        rate_type = st.radio(f"Rate Type (Deal {d})", ["Fixed", "Floating"], key=f"rate_{d}")        anniv_date = None        if rate_type == "Floating":            anniv_date = st.date_input(f"Anniversary Date (Deal {d})", key=f"anniv_{d}")            # convert date_input to datetime            anniv_date = datetime.combine(anniv_date, datetime.min.time())        deal_settings.append({            "deal_id": d,            "rate_type": rate_type,            "anniv_date": anniv_date        })
# ----------------------------# Step 3: Calculation# ----------------------------if st.button(" Calculate XIRR for All Deals"):    if cashflows_df is not None:        summary = []
        for deal in deal_settings:            d_id = deal["deal_id"]
            # Adjust floating cashflows if needed            if deal["rate_type"] == "Floating" and bbsy_df is not None:                adj_df = apply_bbsy(cashflows_df, bbsy_df, deal["anniv_date"])            else:                adj_df = cashflows_df.copy()                adj_df["Adj_CF"] = adj_df["Cashflow"]
            # Build flows for XIRR            flows = [(row.Date.to_pydatetime(), row.Adj_CF) for row in adj_df.itertuples(index=False)]
            try:                result = xirr(flows) * 100                ups = result - base_rate
                st.subheader(f" Deal {d_id} Results")                st.success(f"Effective XIRR: {result:.2f}%")                st.metric("Ups vs Base", f"{ups:.2f}%", delta=ups)                st.dataframe(adj_df)
                summary.append({                    "Deal": d_id,                    "XIRR (%)": result,                    "Base Rate (%)": base_rate,                    "Ups (%)": ups                })
            except Exception as e:                st.error(f"Error in Deal {d_id} XIRR calc: {e}")
        # Show summary table        if summary:            st.subheader(" All Deals Summary")            summary_df = pd.DataFrame(summary)            st.dataframe(summary_df)
            # Download Excel            out = io.BytesIO()            with pd.ExcelWriter(out, engine="xlsxwriter") as writer:                cashflows_df.to_excel(writer, sheet_name="Cashflows", index=False)                if bbsy_df is not None:                    bbsy_df.to_excel(writer, sheet_name="BBSY", index=False)                summary_df.to_excel(writer, sheet_name="Summary", index=False)            st.download_button(                label=" Download Results",                data=out,                file_name="xirr_multi_deal_results.xlsx",                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"            )    else:        st.error("Please upload cashflows first!")

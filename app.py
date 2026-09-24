import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import re
import json
import os
from datetime import datetime, timedelta

# Set page configuration
st.set_page_config(page_title="Data Portal", layout="wide")

# Prevent Streamlit's 'C' key shortcut from triggering the Clear Cache popup
components.html(
    """
    <script>
    const parentDoc = window.parent.document;
    parentDoc.addEventListener('keydown', function(e) {
        if (e.key.toLowerCase() === 'c' && !['INPUT', 'TEXTAREA'].includes(parentDoc.activeElement.tagName)) {
            e.stopPropagation();
        }
    }, true);
    </script>
    """,
    height=0,
)

# --- 1. GOOGLE SHEET CONFIGURATION ---
SHEET_ID = "12WnZLa93RQmFijkSztZvOygQXOFHkHJPWkTBzmgF8xs"
EXCEL_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=xlsx"
SETTINGS_FILE = "user_settings.json"

# --- 2. PREFERENCE PERSISTENCE FUNCTIONS ---
def load_saved_settings():
    """Reads saved user display choices from disk on startup."""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_settings_callback():
    """Triggered whenever sidebar dropdowns change to save choices to disk."""
    settings = {
        "target_search_col": st.session_state.get("target_search_col"),
        "selected_display_cols": st.session_state.get("selected_display_cols", [])
    }
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=4)
    except Exception as e:
        st.error(f"Failed to save settings: {e}")

# --- 3. LOAD & FORMAT ALL TABS ---
@st.cache_data(ttl=1800)
def load_all_tabs():
    all_sheets = pd.read_excel(EXCEL_URL, sheet_name=None)
    combined_list = []
    
    first_four_tabs = list(all_sheets.items())[:4]
    
    for tab_name, df_sheet in first_four_tabs:
        df_sheet["Source_Tab"] = tab_name
        combined_list.append(df_sheet)
    
    full_df = pd.concat(combined_list, ignore_index=True)
    
    # Format all Date columns to DD-Mon-YYYY for display
    for col in full_df.columns:
        if "date" in str(col).lower():
            try:
                dt = pd.to_datetime(full_df[col], errors="coerce")
                formatted_dates = dt.dt.strftime("%d-%b-%Y").str.lstrip("0")
                full_df[col] = formatted_dates.fillna(full_df[col])
            except Exception:
                pass
                
    return full_df

def clear_cache_callback():
    st.cache_data.clear()

# ==========================================
# PAGE 1: REPEATED SEARCH PORTAL (Original)
# ==========================================
def page_one(df, all_columns, saved_prefs):
    st.title("📦 4 Months Repeated Search Portal")
    st.caption("Searching across 4 Months of Data from Google Sheets")

    # Default Search Column (Local Service ID / Column H)
    default_search_idx = 0
    for idx, col in enumerate(all_columns):
        if "local service id" in str(col).lower() or idx == 7:
            default_search_idx = idx
            break

    if "target_search_col" not in st.session_state:
        saved_target = saved_prefs.get("target_search_col")
        if saved_target in all_columns:
            st.session_state.target_search_col = saved_target
        else:
            st.session_state.target_search_col = all_columns[default_search_idx]

    st.sidebar.markdown("---")
    target_search_col = st.sidebar.selectbox(
        "Select Search Column (Default is Column H / Local Service ID):",
        options=all_columns,
        key="target_search_col",
        on_change=save_settings_callback
    )

    if "selected_display_cols" not in st.session_state:
        saved_display = saved_prefs.get("selected_display_cols", [])
        valid_saved_cols = [c for c in saved_display if c in all_columns]
        
        if valid_saved_cols:
            st.session_state.selected_display_cols = valid_saved_cols
        else:
            st.session_state.selected_display_cols = all_columns[:6]

    st.sidebar.markdown("### Display Settings")
    selected_display_cols = st.sidebar.multiselect(
        "Choose Columns to Show in Results:",
        options=all_columns,
        key="selected_display_cols",
        on_change=save_settings_callback
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🌪️ Filter Data")

    filter_column = st.sidebar.selectbox(
        "Select Column to Filter By:",
        options=["-- No Filter --"] + all_columns,
        index=0
    )

    active_df = df.copy()

    if filter_column != "-- No Filter --":
        unique_vals = sorted(df[filter_column].dropna().astype(str).unique().tolist())
        selected_filter_vals = st.sidebar.multiselect(
            f"Select values for `{filter_column}`:",
            options=unique_vals,
            default=unique_vals
        )
        if selected_filter_vals:
            active_df = df[df[filter_column].astype(str).isin(selected_filter_vals)]
        else:
            active_df = df.iloc[0:0]

    st.write("### Paste Search Values")
    st.caption("Enter 10, 30, or more values below (one per line):")

    user_input = st.text_area(
        label="Search Queries",
        height=220,
        placeholder="2528848-001\n2527110-001\n2497014-001\n2515729-001\n..."
    )

    if user_input.strip():
        search_terms = [term.strip() for term in re.split(r'[\n,]+', user_input) if term.strip()]
        st.info(f"Searching across **{len(active_df):,}** filtered rows for **{len(search_terms)}** distinct value(s)...")
        
        cols_to_render = selected_display_cols if selected_display_cols else all_columns
        found_any = False
        matched_results_dict = {}
        summary_data = []

        for term in search_terms:
            mask = active_df[target_search_col].astype(str).str.contains(re.escape(term), case=False, na=False)
            term_results = active_df[mask]
            count = len(term_results)
            
            summary_data.append({"Service ID": term, "Total Repeated": count})
            
            if count > 0:
                found_any = True
                matched_results_dict[term] = term_results

        col_sort1, col_sort2 = st.columns([1, 2])
        with col_sort1:
            sort_option = st.selectbox(
                "🔀 Sort Results By:",
                options=[
                    "Total Repeated (High to Low)",
                    "Total Repeated (Low to High)",
                    "Service ID (A-Z)",
                    "Original Input Order"
                ],
                index=0
            )

        summary_df = pd.DataFrame(summary_data)

        if sort_option == "Total Repeated (High to Low)":
            summary_df = summary_df.sort_values(by="Total Repeated", ascending=False)
        elif sort_option == "Total Repeated (Low to High)":
            summary_df = summary_df.sort_values(by="Total Repeated", ascending=True)
        elif sort_option == "Service ID (A-Z)":
            summary_df = summary_df.sort_values(by="Service ID", ascending=True)

        with st.expander("📊 Summary Pivot Table (Total Repeated Counts)", expanded=True):
            col_pivot, col_space = st.columns([1, 2])
            with col_pivot:
                st.dataframe(summary_df, use_container_width=True, hide_index=True)
                pivot_csv = summary_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download Summary Pivot CSV",
                    data=pivot_csv,
                    file_name="summary_pivot.csv",
                    mime="text/csv"
                )

        st.markdown("---")
        st.markdown("### 📋 Detailed Matching Results")

        if found_any:
            combined_matched_list = []
            for term in summary_df["Service ID"]:
                if term in matched_results_dict:
                    term_results = matched_results_dict[term]
                    combined_matched_list.append(term_results)
                    st.markdown(f"#### 📌 `{term}` ({len(term_results)} record{'s' if len(term_results) > 1 else ''})")
                    st.dataframe(term_results[cols_to_render], use_container_width=True, hide_index=True)
                    st.markdown("---")
                
            combined_matched_df = pd.concat(combined_matched_list, ignore_index=True)
            csv_data = combined_matched_df[cols_to_render].to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download All Detailed Results as CSV",
                data=csv_data,
                file_name="detailed_search_results.csv",
                mime="text/csv"
            )
        else:
            st.warning("No records found for any of the entered search values under current filter conditions.")
    else:
        st.info("Paste your list of search values above to view the summary pivot table and detailed results.")


# ==========================================
# PAGE 2: WEEKLY FILTERED DATA (Updated for Debugging & Safe Matching)
# ==========================================
def page_two(df):
    st.title("📅 Weekly Filtered Report")
    st.caption("Auto-filtered data for Last Week's Mon-Sun based on specific column rules.")

    try:
        # 1. Calculate Last Week's Monday and Sunday dynamically
        today = datetime.today()
        days_to_subtract = today.weekday() + 7 
        last_monday = (today - timedelta(days=days_to_subtract)).date()
        last_sunday = last_monday + timedelta(days=6)
        
        st.info(f"**Applied Date Filter (Column A):** {last_monday.strftime('%d-%b-%Y')} (Monday) to {last_sunday.strftime('%d-%b-%Y')} (Sunday)")

        if len(df.columns) < 56: 
            st.error("The Google Sheet does not have enough columns to perform the requested filters.")
            return

        working_df = df.copy()

        # --- APPLYING FILTERS (With safe string matching) ---
        
        # 1. Filter Column A (Date)
        col_A_dt = pd.to_datetime(working_df.iloc[:, 0], errors="coerce")
        date_mask = (col_A_dt.dt.date >= last_monday) & (col_A_dt.dt.date <= last_sunday)

        # 2. Filter Column C (Contains 'TKT')
        c_mask = working_df.iloc[:, 2].astype(str).str.contains("TKT", case=False, na=False)

        # 3. Filter Column I (Contains 'FR-SLA' OR 'Biz')
        i_mask = working_df.iloc[:, 8].astype(str).str.contains("FR-SLA|Biz", case=False, na=False)

        # 4. Filter Column BD (Exact Match - Safe Mode)
        # နေရာလွတ် (Space) များကိုဖယ်ရှားပြီး၊ စာလုံးအကြီးအသေးပြဿနာမရှိစေရန် lowercase ပြောင်း၍စစ်ဆေးပါမည်
        allowed_statuses = ["resolved", "resolved (auto)", "resolved (no kpi)"]
        bd_mask = working_df.iloc[:, 55].astype(str).str.strip().str.lower().isin(allowed_statuses)

        # Combine all masks
        final_mask = date_mask & c_mask & i_mask & bd_mask
        filtered_df = working_df[final_mask]

        # --- 🔍 FILTER DEBUGGING SECTION ---
        # ဘယ်အဆင့်မှာ Data 0 ဖြစ်သွားလဲဆိုတာ စစ်ဆေးရန်
        with st.expander("🔍 Filter Debugging (Check which rule has no data)", expanded=True):
            st.markdown(f"""
            - Total Rows in Sheet: **{len(working_df):,}**
            - 1️⃣ Rows matching **Date** ({last_monday} to {last_sunday}): **{date_mask.sum():,}**
            - 2️⃣ Rows matching **'TKT'** (Col C): **{c_mask.sum():,}**
            - 3️⃣ Rows matching **'FR-SLA / Biz'** (Col I): **{i_mask.sum():,}**
            - 4️⃣ Rows matching **Status** (Col BD): **{bd_mask.sum():,}**
            - 🎯 **Rows matching ALL 4 criteria simultaneously:** **{len(filtered_df):,}**
            """)

        # --- SELECTING COLUMNS FOR DISPLAY ---
        requested_col_indices = [0, 2, 8, 14, 64, 50, 51, 52, 53, 54, 55, 56, 36, 58, 21]
        valid_indices = [idx for idx in requested_col_indices if idx < len(filtered_df.columns)]
        
        if not filtered_df.empty:
            display_df = filtered_df.iloc[:, valid_indices]
            st.success(f"Found **{len(display_df)}** records matching all criteria.")
            
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
            csv_data = display_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Filtered Data as CSV",
                data=csv_data,
                file_name=f"weekly_report_{last_monday}_to_{last_sunday}.csv",
                mime="text/csv"
            )
        else:
            st.warning("No records found matching ALL specific criteria at the exact same time.")

    except Exception as e:
        st.error(f"An error occurred while filtering data: {e}")


# ==========================================
# MAIN APP FLOW & SIDEBAR NAVIGATION
# ==========================================
st.sidebar.title("🧭 Navigation")
page = st.sidebar.radio("Go to:", ["1. Repeated Search Portal", "2. Weekly Filtered Report"])
st.sidebar.markdown("---")

st.sidebar.header("Data Controls")
st.sidebar.button("🔄 Refresh Data from Google Sheet", on_click=clear_cache_callback)

# Load data globally so it persists across pages
with st.spinner("Loading data from Google Sheets..."):
    try:
        df = load_all_tabs()
        st.sidebar.metric("Total Rows Loaded", f"{len(df):,}")
    except Exception as e:
        st.error(f"Error reading Google Sheet. Ensure General Access is set to 'Anyone with the link can view'. Details: {e}")
        st.stop()

all_columns = df.columns.tolist()
saved_prefs = load_saved_settings()

# Route to the selected page
if page == "1. Repeated Search Portal":
    page_one(df, all_columns, saved_prefs)
elif page == "2. Weekly Filtered Report":
    page_two(df)

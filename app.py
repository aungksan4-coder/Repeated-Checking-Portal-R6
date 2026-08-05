import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import re
import json
import os

# Set page configuration
st.set_page_config(page_title="Repeated Checking Portal", layout="wide")

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

st.title("📦 4 Months Repeated Search Portal")
st.caption("Searching across 4 Months of Data from Google Sheets")

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
    for tab_name, df_sheet in all_sheets.items():
        df_sheet["Source_Tab"] = tab_name
        combined_list.append(df_sheet)
    
    full_df = pd.concat(combined_list, ignore_index=True)
    
    # Format all Date columns to DD-Mon-YYYY (e.g., 5-Aug-2026, 15-Jul-2026)
    for col in full_df.columns:
        if "date" in str(col).lower():
            try:
                dt = pd.to_datetime(full_df[col], errors="coerce")
                formatted_dates = dt.dt.strftime("%d-%b-%Y").str.lstrip("0")
                full_df[col] = formatted_dates.fillna(full_df[col])
            except Exception:
                pass
                
    return full_df

# --- 4. SIDEBAR & CACHE CONTROL ---
def clear_cache_callback():
    st.cache_data.clear()

st.sidebar.header("Controls")
st.sidebar.button("🔄 Refresh Data from Google Sheet", on_click=clear_cache_callback)

with st.spinner("Loading data from Google Sheets..."):
    try:
        df = load_all_tabs()
        st.sidebar.metric("Total Rows Loaded Across All Tabs", f"{len(df):,}")
    except Exception as e:
        st.error(f"Error reading Google Sheet. Ensure General Access is set to 'Anyone with the link can view'. Details: {e}")
        st.stop()

all_columns = df.columns.tolist()

# --- 5. INITIALIZE DISPLAY SETTINGS FROM DISK ---
saved_prefs = load_saved_settings()

# Default Search Column (Local Service ID / Column H)
default_search_idx = 0
for idx, col in enumerate(all_columns):
    if "local service id" in str(col).lower() or idx == 7:
        default_search_idx = idx
        break

# Restore saved Search Column if valid
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

# Restore saved Display Columns if valid
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

# --- 6. DYNAMIC COLUMN VALUE FILTERING ---
st.sidebar.markdown("---")
st.sidebar.markdown("### 🌪️ Filter Data")

filter_column = st.sidebar.selectbox(
    "Select Column to Filter By:",
    options=["-- No Filter --"] + all_columns,
    index=0
)

# Filter dataset dynamically based on selection
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

# --- 7. BATCH SEARCH & SUMMARY PIVOT INTERFACE ---
st.write("### Paste Search Values")
st.caption("Enter 10, 30, or more values below (one per line):")

user_input = st.text_area(
    label="Search Queries",
    height=220,
    placeholder="2528848-001\n2527110-001\n2497014-001\n2515729-001\n..."
)

if user_input.strip():
    search_terms = [
        term.strip() 
        for term in re.split(r'[\n,]+', user_input) 
        if term.strip()
    ]
    
    st.info(f"Searching across **{len(active_df):,}** filtered rows for **{len(search_terms)}** distinct value(s)...")
    
    cols_to_render = selected_display_cols if selected_display_cols else all_columns
    found_any = False
    matched_results_dict = {}
    summary_data = []

    # Loop through search terms
    for term in search_terms:
        mask = active_df[target_search_col].astype(str).str.contains(re.escape(term), case=False, na=False)
        term_results = active_df[mask]
        count = len(term_results)
        
        summary_data.append({
            "Service ID": term,
            "Total Repeated": count
        })
        
        if count > 0:
            found_any = True
            matched_results_dict[term] = term_results

    # --- SORTING CONTROLS ---
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

    # Apply sorting choices to summary_df
    if sort_option == "Total Repeated (High to Low)":
        summary_df = summary_df.sort_values(by="Total Repeated", ascending=False)
    elif sort_option == "Total Repeated (Low to High)":
        summary_df = summary_df.sort_values(by="Total Repeated", ascending=True)
    elif sort_option == "Service ID (A-Z)":
        summary_df = summary_df.sort_values(by="Service ID", ascending=True)

    # --- SUMMARY PIVOT TABLE DISPLAY ---
    with st.expander("📊 Summary Pivot Table (Total Repeated Counts)", expanded=True):
        col_pivot, col_space = st.columns([1, 2])
        with col_pivot:
            st.dataframe(
                summary_df,
                use_container_width=True,
                hide_index=True
            )
            pivot_csv = summary_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Summary Pivot CSV",
                data=pivot_csv,
                file_name="summary_pivot.csv",
                mime="text/csv"
            )

    st.markdown("---")
    st.markdown("### 📋 Detailed Matching Results")

    # --- DETAILED MATCHED ROWS (SYNCHRONIZED WITH SUMMARY SORT ORDER) ---
    if found_any:
        combined_matched_list = []
        
        # Iterate in the order determined by summary_df
        for term in summary_df["Service ID"]:
            if term in matched_results_dict:
                term_results = matched_results_dict[term]
                combined_matched_list.append(term_results)
                
                st.markdown(f"#### 📌 `{term}` ({len(term_results)} record{'s' if len(term_results) > 1 else ''})")
                
                st.dataframe(
                    term_results[cols_to_render],
                    use_container_width=True,
                    hide_index=True
                )
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
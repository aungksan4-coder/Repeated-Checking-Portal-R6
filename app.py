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

# --- 3. LOAD & FORMAT ALL TABS (Cached for 24 Hours) ---
@st.cache_data(ttl=86400, show_spinner="Fetching Data from Google Sheets (Syncing Once)...")
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
# HELPER FUNCTION FOR COPY BUTTON (Must be at top level)
# ==========================================
def render_copy_button(df, button_id):
    """Generates a hidden textarea and a button to copy DataFrame to clipboard."""
    csv_string = df.to_csv(index=False, sep='\t')
    escaped_string = csv_string.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
    
    components.html(
        f"""
        <script>
        function copyToClipboard_{button_id}() {{
            const textToCopy = "{escaped_string}";
            navigator.clipboard.writeText(textToCopy).then(function() {{
                const btn = document.getElementById('copy_btn_{button_id}');
                const originalText = btn.innerHTML;
                btn.innerHTML = '✅ Copied!';
                btn.style.backgroundColor = '#d4edda';
                btn.style.color = '#155724';
                btn.style.borderColor = '#c3e6cb';
                setTimeout(function() {{
                    btn.innerHTML = originalText;
                    btn.style.backgroundColor = '';
                    btn.style.color = '';
                    btn.style.borderColor = '';
                }}, 2000);
            }}, function(err) {{
                console.error('Could not copy text: ', err);
            }});
        }}
        </script>
        <button id="copy_btn_{button_id}" onclick="copyToClipboard_{button_id}()" 
                style="padding: 0.25rem 0.5rem; font-size: 0.875rem; border-radius: 0.25rem; 
                       border: 1px solid #ccc; background-color: #f8f9fa; cursor: pointer; 
                       margin-bottom: 5px; float: right;">
            📋 Copy Table
        </button>
        """,
        height=40,
    )


# ==========================================
# PAGE 1: REPEATED SEARCH PORTAL
# ==========================================
def page_one(df, all_columns, saved_prefs):
    st.title("📦 4 Months Repeated Search Portal")
    st.caption("Searching across 4 Months of Data from Google Sheets")

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
# PAGE 2: WEEKLY FILTERED REPORT
# ==========================================
def page_two(df):
    st.title("📅 Weekly Repeated Report (4th Tab Only)")
    st.caption("Checking duplicates across different dates for Last Week's Mon-Sun on the 4th Tab.")

    try:
        unique_tabs = df["Source_Tab"].unique()
        if len(unique_tabs) < 4:
            st.error("⚠️ The Google Sheet does not have 4 tabs. Please ensure there are at least 4 tabs.")
            return
            
        tab4_name = unique_tabs[3]
        working_df = df[df["Source_Tab"] == tab4_name].copy()
        
        st.info(f"📁 **Data Source:** Fetching strictly from the 4th tab ➔ `{tab4_name}`")

        today = datetime.today()
        days_to_subtract = today.weekday() + 7 
        last_monday = (today - timedelta(days=days_to_subtract)).date()
        last_sunday = last_monday + timedelta(days=6)
        
        st.markdown(f"**🗓️ Applied Date Filter (Column A):** {last_monday.strftime('%d-%b-%Y')} to {last_sunday.strftime('%d-%b-%Y')}")

        if len(working_df.columns) < 56: 
            st.error("⚠️ The Google Sheet does not have enough columns (Needs at least up to Column BD).")
            return

        col_A_dt = pd.to_datetime(working_df.iloc[:, 0], errors="coerce")
        date_mask = (col_A_dt.dt.date >= last_monday) & (col_A_dt.dt.date <= last_sunday)

        c_mask = working_df.iloc[:, 2].astype(str).str.contains("TKT", case=False, na=False)

        allowed_statuses = ["resolved", "resolved (auto)", "resolved (no kpi)"]
        bd_mask = working_df.iloc[:, 55].astype(str).str.strip().str.lower().isin(allowed_statuses)

        base_mask = date_mask & c_mask & bd_mask
        base_filtered_df = working_df[base_mask].copy()

        requested_col_indices = [0, 2, 8, 14, 64, 50, 51, 52, 53, 54, 55, 56, 36, 58, 21]
        valid_indices = [idx for idx in requested_col_indices if idx < len(base_filtered_df.columns)]
        
        def render_section(section_name, keyword):
            st.markdown("---")
            st.markdown(f"### 📌 {section_name} Section (Column I Filter)")
            
            i_mask = base_filtered_df.iloc[:, 8].astype(str).str.contains(keyword, case=False, na=False)
            section_df = base_filtered_df[i_mask].copy()
            
            if section_df.empty:
                st.warning(f"No records found for '{keyword}' after applying Date, TKT, and Status filters.")
                return

            col_a_name = section_df.columns[0]
            col_h_name = section_df.columns[7]
            
            agg_df = section_df.groupby(col_h_name).agg(
                Total_Repeated=(col_h_name, 'count'),
                Distinct_Dates=(col_a_name, 'nunique')
            ).reset_index()
            
            dup_summary = agg_df[agg_df['Distinct_Dates'] > 1].copy()
            
            if dup_summary.empty:
                st.success(f"✅ No duplicate Service IDs found with different dates for '{keyword}'.")
                return
            
            dup_summary = dup_summary.sort_values(by="Total_Repeated", ascending=False)
            display_pivot = dup_summary.drop(columns=['Distinct_Dates'])
            
            with st.expander(f"📊 {keyword} - Summary Pivot Table", expanded=True):
                st.dataframe(display_pivot, use_container_width=True, hide_index=True)
            
            st.markdown(f"#### 📋 {keyword} - Detailed Matching Data")
            
            dup_ids_sorted = dup_summary[col_h_name].tolist()
            combined_matched_list = []
            
            for term in dup_ids_sorted:
                term_results = section_df[section_df[col_h_name] == term].copy()
                count = len(term_results)
                
                st.markdown(f"##### 🔹 `{term}` (Repeated {count} times)")
                term_display_df = term_results.iloc[:, valid_indices]
                st.dataframe(term_display_df, use_container_width=True, hide_index=True)
                st.markdown("<br>", unsafe_allow_html=True)
                
                combined_matched_list.append(term_display_df)
            
            combined_matched_df = pd.concat(combined_matched_list, ignore_index=True)
            csv_data = combined_matched_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label=f"📥 Download All {keyword} Detailed Results as CSV",
                data=csv_data,
                file_name=f"{keyword}_detailed_duplicates_{last_monday}_to_{last_sunday}.csv",
                mime="text/csv",
                key=f"dl_{keyword}"
            )

        render_section("FR-SLA", "FR-SLA")
        render_section("Biz", "Biz")

    except Exception as e:
        st.error(f"An error occurred while filtering data: {e}")


# ==========================================
# PAGE 3: KO PPO REPORT
# ==========================================
def page_three(df):
    st.title("📊 Ko PPO Report")
    st.caption("Filtering by Date, Naypyitaw (Column AS), and POI (Column C) on the 4th Tab.")

    try:
        unique_tabs = df["Source_Tab"].unique()
        if len(unique_tabs) < 4:
            st.error("⚠️ The Google Sheet does not have 4 tabs. Please ensure there are at least 4 tabs.")
            return
            
        tab4_name = unique_tabs[3]
        working_df = df[df["Source_Tab"] == tab4_name].copy()
        
        if len(working_df.columns) < 59:
            st.error(f"⚠️ The 4th tab ('{tab4_name}') does not have enough columns. (Needs at least up to Column BG)")
            return

        col_A_dt = pd.to_datetime(working_df.iloc[:, 0], errors="coerce")
        unique_dates = col_A_dt.dt.date.dropna().unique()
        unique_dates_sorted = sorted(list(unique_dates), reverse=True)

        if not unique_dates_sorted:
             st.warning("No valid dates found in Column A.")
             return

        selected_date = st.date_input("Select Date for Report:", value=unique_dates_sorted[0], min_value=min(unique_dates_sorted), max_value=max(unique_dates_sorted))

        date_mask = col_A_dt.dt.date == selected_date
        as_mask = working_df.iloc[:, 44].astype(str).str.contains("Naypyitaw", case=False, na=False)
        c_mask = working_df.iloc[:, 2].astype(str).str.contains("POI", case=False, na=False)
        
        filtered_df = working_df[date_mask & as_mask & c_mask].copy()

        if filtered_df.empty:
            st.warning(f"No records found for Date: {selected_date.strftime('%d-%b-%Y')}, Region: Naypyitaw, and containing 'POI' in Column C.")
            return

        st.markdown("### 📈 Task Status Summary")
        
        col_c_name = filtered_df.columns[2]
        col_bd_name = filtered_df.columns[55]
        col_ak_name = filtered_df.columns[36] # Column AK for Team

        # --- 1. Calculate Total Team Count ---
        # Get unique count of values in Column AK
        total_team_count = filtered_df[col_ak_name].nunique(dropna=True)
        total_team_row = pd.DataFrame([{'Task Status': 'Total Team', 'Count': total_team_count}])

        status_counts = filtered_df.groupby(col_bd_name)[col_c_name].count().reset_index()
        status_counts.columns = ['Task Status', 'Count']
        status_counts = status_counts.sort_values(by='Count', ascending=False)
        
        total_overall = status_counts['Count'].sum()
        grand_total_overall_row = pd.DataFrame([{'Task Status': 'Grand Total', 'Count': total_overall}])
        
        # Combine Total Team, Status Counts, and Grand Total
        status_counts = pd.concat([total_team_row, status_counts, grand_total_overall_row], ignore_index=True)

        col_sum1, col_sum2 = st.columns([1, 2])
        
        with col_sum1:
            st.markdown("#### Overall Task Status")
            st.markdown("<div style='height: 68px;'></div>", unsafe_allow_html=True) 
            render_copy_button(status_counts, "overall_status")
            st.table(status_counts.set_index('Task Status'))

        with col_sum2:
            st.markdown("#### Engr Visited Pending Breakdown")
            
            tech_cancel_list = [
                "OTB Need to Box Maintenance", "Port Full", "No Link/High Loss", 
                "No Fiber", "Cannot Install OTB", "OLT Issue", "Cable Stock Issue", 
                "Cabling Route Issue", "OTB Need to Port Check", "Need Pole", 
                "No MN Area", "Coverage Issue", "AP Issue", "Pole Remove", "Site Down"
            ]
            tech_cancel_lower = [v.lower().strip() for v in tech_cancel_list]
            
            cancel_type = st.radio("Select Cancel Type:", ["Technical Cancel", "Non Technical Cancel"], horizontal=True)
            
            evp_mask = filtered_df.iloc[:, 55].astype(str).str.strip().str.lower().isin(["engr visited pending", "engr visited - pending"])
            evp_df = filtered_df[evp_mask].copy()
            
            if not evp_df.empty:
                col_bb_name = evp_df.columns[53]
                
                is_tech_mask = evp_df.iloc[:, 53].astype(str).str.strip().str.lower().isin(tech_cancel_lower)
                
                if cancel_type == "Technical Cancel":
                    breakdown_df = evp_df[is_tech_mask].copy()
                else:
                    breakdown_df = evp_df[~is_tech_mask].copy()
                    
                if not breakdown_df.empty:
                    breakdown_counts = breakdown_df.groupby(col_bb_name)[col_c_name].count().reset_index()
                    breakdown_counts.columns = ['Reason (Col BB)', 'Count']
                    breakdown_counts = breakdown_counts.sort_values(by='Count', ascending=False)
                    
                    total_count = breakdown_counts['Count'].sum()
                    grand_total_row = pd.DataFrame([{'Reason (Col BB)': 'Grand Total', 'Count': total_count}])
                    breakdown_counts = pd.concat([breakdown_counts, grand_total_row], ignore_index=True)
                    
                    render_copy_button(breakdown_counts, "breakdown_status")
                    st.table(breakdown_counts.set_index('Reason (Col BB)'))
                else:
                    st.info(f"No {cancel_type} records found.")
            else:
                st.info("No 'Engr Visited Pending' records found for the selected date.")

        st.markdown("---")
        st.markdown("### 📋 Detail Data for Pending/Not Visited/Handover Statuses")

        detail_status_mask = filtered_df.iloc[:, 55].astype(str).str.strip().str.lower().isin([
            "not visited", "engr visited pending", "engr visited - pending", "handover to fttx"
        ])
        
        detail_df_base = filtered_df[detail_status_mask].copy()

        if not detail_df_base.empty:
             available_detail_statuses = detail_df_base.iloc[:, 55].astype(str).unique().tolist()
             selected_detail_status = st.multiselect("Filter Detail View by Status:", options=available_detail_statuses, default=available_detail_statuses)
             
             if selected_detail_status:
                 final_detail_df = detail_df_base[detail_df_base.iloc[:, 55].astype(str).isin(selected_detail_status)].copy()
                 
                 # Columns to display: C (2), AK (36), BE (56), AV (47), AW (48), AX (49), AZ (51), BA (52), BB (53), BC (54), BG (58)
                 cols_to_show_indices = [2, 36, 56, 47, 48, 49, 51, 52, 53, 54, 58]
                 valid_detail_indices = [i for i in cols_to_show_indices if i < len(final_detail_df.columns)]
                 display_detail_df = final_detail_df.iloc[:, valid_detail_indices]
                 
                 render_copy_button(display_detail_df, "detail_data_status")
                 st.table(display_detail_df.set_index(display_detail_df.columns[0]))
                 
                 csv_detail = display_detail_df.to_csv(index=False).encode('utf-8')
                 st.download_button(
                    label="📥 Download Detail Data CSV",
                    data=csv_detail,
                    file_name=f"Ko_PPO_Detail_Report_Status_{selected_date}.csv",
                    mime="text/csv"
                 )
             else:
                 st.info("Please select at least one status to view details.")
        else:
             st.info("No records found with status 'Not Visited', 'Engr Visited Pending', or 'Handover to FTTx' for the selected filters.")

        # --- 2. Detail Data by LAN Engineer (Team) ---
        st.markdown("---")
        st.markdown("### 📋 Detail Data by LAN Engineer (Team)")
        st.caption("Showing detail records grouped by individual Engineer from Column AK.")

        # Extract unique, non-null engineer names from Column AK
        engineer_names = filtered_df.iloc[:, 36].dropna().astype(str).unique().tolist()
        # Sort names alphabetically
        engineer_names = sorted([name for name in engineer_names if name.strip()])

        if engineer_names:
            # Loop through each engineer and display their own section
            for selected_engineer in engineer_names:
                st.markdown(f"#### 👷 {selected_engineer}")
                
                # Filter data where Col AK matches selected engineer
                eng_mask = filtered_df.iloc[:, 36].astype(str) == selected_engineer
                eng_detail_df = filtered_df[eng_mask].copy()

                # Display the requested columns: C (2), BE (56), AV (47), AW (48), AX (49), AZ (51), BA (52), BB (53), BC (54), BD (55), BG (58)
                cols_to_show_indices = [2, 56, 47, 48, 49, 51, 52, 53, 54, 55, 58]
                valid_detail_indices = [i for i in cols_to_show_indices if i < len(eng_detail_df.columns)]
                
                display_eng_df = eng_detail_df.iloc[:, valid_detail_indices]

                st.write(f"Showing **{len(display_eng_df)}** record(s) for **{selected_engineer}**:")
                
                # Create a unique ID for each copy button using a safe string
                safe_eng_name = re.sub(r'[^a-zA-Z0-9]', '_', selected_engineer)
                btn_id = f"detail_data_eng_{safe_eng_name}"
                
                render_copy_button(display_eng_df, btn_id)
                st.table(display_eng_df.set_index(display_eng_df.columns[0]))

                csv_eng_detail = display_eng_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                   label=f"📥 Download Data for {selected_engineer}",
                   data=csv_eng_detail,
                   file_name=f"Ko_PPO_{safe_eng_name}_{selected_date}.csv",
                   mime="text/csv",
                   key=f"dl_{safe_eng_name}" # Unique key for Streamlit download button
                )
                
                st.markdown("<br><br>", unsafe_allow_html=True) # Add space between tables
        else:
            st.info("No Engineer names found in Column AK for the selected filters.")

    except Exception as e:
        st.error(f"An error occurred in Ko PPO Report: {e}")
# ==========================================
# MAIN APP FLOW & SIDEBAR NAVIGATION
# ==========================================
st.sidebar.title("🧭 Navigation")
page = st.sidebar.radio("Go to:", ["1. Repeated Search Portal", "2. Weekly Filtered Report", "3. Ko PPO Report"])
st.sidebar.markdown("---")

st.sidebar.header("Data Controls")
st.sidebar.button("🔄 Refresh Data from Google Sheet", on_click=clear_cache_callback)

# Load data globally so it persists across pages 
# (Removed the explicit 'with st.spinner()' block so it doesn't flash on every UI interaction)
try:
    df = load_all_tabs()
    st.sidebar.metric("Total Rows Loaded", f"{len(df):,}")
except Exception as e:
    st.error(f"Error reading Google Sheet. Ensure General Access is set to 'Anyone with the link can view'. Details: {e}")
    st.stop()

all_columns = df.columns.tolist()
saved_prefs = load_saved_settings()

if page == "1. Repeated Search Portal":
    page_one(df, all_columns, saved_prefs)
elif page == "2. Weekly Filtered Report":
    page_two(df)
elif page == "3. Ko PPO Report":
    page_three(df)

# ==========================================
# PAGE 2: WEEKLY FILTERED REPORT (Duplicate Checking by Tab 4)
# ==========================================
def page_two(df):
    st.title("📅 Weekly Repeated Report (4th Tab Only)")
    st.caption("Checking duplicates across different dates for Last Week's Mon-Sun on the 4th Tab.")

    try:
        # --- 1. GET 4TH TAB DATA ONLY ---
        unique_tabs = df["Source_Tab"].unique()
        if len(unique_tabs) < 4:
            st.error("⚠️ The Google Sheet does not have 4 tabs. Please ensure there are at least 4 tabs.")
            return
            
        # 4th Tab Name (Index 3)
        tab4_name = unique_tabs[3]
        working_df = df[df["Source_Tab"] == tab4_name].copy()
        
        st.info(f"📁 **Data Source:** Fetching strictly from the 4th tab ➔ `{tab4_name}`")

        # --- 2. CALCULATE LAST WEEK'S DATES ---
        today = datetime.today()
        days_to_subtract = today.weekday() + 7 
        last_monday = (today - timedelta(days=days_to_subtract)).date()
        last_sunday = last_monday + timedelta(days=6)
        
        st.markdown(f"**🗓️ Applied Date Filter (Column A):** {last_monday.strftime('%d-%b-%Y')} to {last_sunday.strftime('%d-%b-%Y')}")

        if len(working_df.columns) < 56: 
            st.error("⚠️ The Google Sheet does not have enough columns (Needs at least up to Column BD).")
            return

        # --- 3. APPLY BASE FILTERS ---
        col_A_dt = pd.to_datetime(working_df.iloc[:, 0], errors="coerce")
        date_mask = (col_A_dt.dt.date >= last_monday) & (col_A_dt.dt.date <= last_sunday)

        c_mask = working_df.iloc[:, 2].astype(str).str.contains("TKT", case=False, na=False)

        allowed_statuses = ["resolved", "resolved (auto)", "resolved (no kpi)"]
        bd_mask = working_df.iloc[:, 55].astype(str).str.strip().str.lower().isin(allowed_statuses)

        base_mask = date_mask & c_mask & bd_mask
        base_filtered_df = working_df[base_mask].copy()

        requested_col_indices = [0, 2, 8, 14, 64, 50, 51, 52, 53, 54, 55, 56, 36, 58, 21]
        valid_indices = [idx for idx in requested_col_indices if idx < len(base_filtered_df.columns)]
        
        # --- 4. REUSABLE FUNCTION FOR FR-SLA & BIZ ---
        def render_section(section_name, keyword):
            st.markdown("---")
            st.markdown(f"### 📌 {section_name} Section (Column I Filter)")
            
            i_mask = base_filtered_df.iloc[:, 8].astype(str).str.contains(keyword, case=False, na=False)
            section_df = base_filtered_df[i_mask].copy()
            
            if section_df.empty:
                st.warning(f"No records found for '{keyword}' after applying Date, TKT, and Status filters.")
                return

            col_a_name = section_df.columns[0] # Date
            col_h_name = section_df.columns[7] # Local Service ID
            
            agg_df = section_df.groupby(col_h_name).agg(
                Total_Repeated=(col_h_name, 'count'),
                Distinct_Dates=(col_a_name, 'nunique')
            ).reset_index()
            
            # Keep only IDs that appeared on DIFFERENT DATES
            dup_summary = agg_df[agg_df['Distinct_Dates'] > 1].copy()
            
            if dup_summary.empty:
                st.success(f"✅ No duplicate Service IDs found with different dates for '{keyword}'.")
                return
            
            # Sort by highest repeat count
            dup_summary = dup_summary.sort_values(by="Total_Repeated", ascending=False)
            
            # Drop 'Distinct_Dates' column before displaying the pivot table
            display_pivot = dup_summary.drop(columns=['Distinct_Dates'])
            
            # 👉 1. DISPLAY SUMMARY PIVOT TABLE
            with st.expander(f"📊 {keyword} - Summary Pivot Table", expanded=True):
                st.dataframe(display_pivot, use_container_width=True, hide_index=True)
            
            st.markdown(f"#### 📋 {keyword} - Detailed Matching Data")
            
            # Get the list of duplicate IDs in the sorted order
            dup_ids_sorted = dup_summary[col_h_name].tolist()
            combined_matched_list = []
            
            # 👉 2. DISPLAY DETAILED RESULTS (Grouped by ID)
            for term in dup_ids_sorted:
                term_results = section_df[section_df[col_h_name] == term].copy()
                count = len(term_results)
                
                # Render ID header like Page 1
                st.markdown(f"##### 🔹 `{term}` (Repeated {count} times)")
                
                # Apply column selection
                term_display_df = term_results.iloc[:, valid_indices]
                st.dataframe(term_display_df, use_container_width=True, hide_index=True)
                st.markdown("<br>", unsafe_allow_html=True) # Adding a small space between tables
                
                combined_matched_list.append(term_display_df)
            
            # 👉 3. COMBINED DOWNLOAD BUTTON
            combined_matched_df = pd.concat(combined_matched_list, ignore_index=True)
            csv_data = combined_matched_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label=f"📥 Download All {keyword} Detailed Results as CSV",
                data=csv_data,
                file_name=f"{keyword}_detailed_duplicates_{last_monday}_to_{last_sunday}.csv",
                mime="text/csv",
                key=f"dl_{keyword}"
            )

        # --- 5. RENDER BOTH SECTIONS ---
        render_section("FR-SLA", "FR-SLA")
        render_section("Biz", "Biz")

    except Exception as e:
        st.error(f"An error occurred while filtering data: {e}")

import streamlit as st
import pandas as pd
import io
import math


def process_data(df_input, n_groups):

    df_input['Roll'] = df_input['Roll'].astype(str)

    unique_branches = df_input['Roll'].apply(lambda x: x[4:6]).unique().tolist()

    branch_dfs = {branch: df_input[df_input['Roll'].str[4:6] == branch].copy() for branch in unique_branches}

    branch_counts = {branch: len(branch_dfs[branch]) for branch in unique_branches}

    # Group-branch-wise mix 
    group_size = math.ceil(len(df_input) / n_groups)
    rr_groups = []
    current_branch_id = 0
    total_branches = len(unique_branches)
    current_group = []

    for i in range(len(df_input)):
        if len(current_group) == group_size:
            rr_groups.append(current_group)
            current_group = []
        while True:
            branch_code = unique_branches[current_branch_id % total_branches]
            df_curr = branch_dfs[branch_code]
            current_round = current_branch_id // total_branches
            if len(df_curr) > current_round:
                row = df_curr.iloc[current_round]
                current_branch_id += 1
                break
            else:
                current_branch_id += 1

        current_group.append(row)
        if i == len(df_input) - 1:
            rr_groups.append(current_group)
    
    group_branchwise_mix_files = {}
    for idx, grp in enumerate(rr_groups):
        df_grp = pd.DataFrame(grp).reset_index(drop=True)
        buf = io.StringIO()
        df_grp.to_csv(buf, index=False)
        group_branchwise_mix_files[f"group_branch_wise_g{idx+1}.csv"] = buf.getvalue()

    # Uniform mix allocation
    desc_branch_counts = sorted(branch_counts.items(), key=lambda x: x[1], reverse=True)
    uniform_group_allocations = [[] for _ in range(n_groups)]
    desc_branch_counts = sorted(branch_counts.items(), key=lambda x: x[1], reverse=True)

    for i in range(n_groups):
        remaining = group_size
        while remaining > 0 and sum(count for _, count in desc_branch_counts) > 0:
            desc_branch_counts.sort(key=lambda x: x[1], reverse=True)
            idx, count = desc_branch_counts[0]
            if count == 0:
                break
            take = min(count, remaining)
            uniform_group_allocations[i].append((idx, take))
            desc_branch_counts[0] = (idx, count - take)
            remaining -= take

    # Create uniform mix files
    branch_dfs_uniform = {branch: branch_dfs[branch].copy() for branch in unique_branches}
    uniform_mix_files = {}
    for idx, group in enumerate(uniform_group_allocations):
        df_new = pd.DataFrame(columns=df_input.columns)
        for branch, students in group:
            slice_df = branch_dfs_uniform[branch].iloc[:students]
            df_new = pd.concat([df_new, slice_df], axis=0)
            branch_dfs_uniform[branch] = branch_dfs_uniform[branch].iloc[students:].reset_index(drop=True)
        buf = io.StringIO()
        df_new.reset_index(drop=True).to_csv(buf, index=False)
        uniform_mix_files[f"group_uniform_g{idx+1}.csv"] = buf.getvalue()

    # Branch-wise distributed files
    branch_wise_files = {}
    for branch, df_b in branch_dfs.items():
        buf = io.StringIO()
        df_b.to_csv(buf, index=False)
        branch_wise_files[f"branch_{branch}.csv"] = buf.getvalue()

    # Stats files will generate for group-branch-wise mix
    stat_branchwise = []
    for idx in range(n_groups):
        counts = {branch: 0 for branch in unique_branches}
        df_temp = pd.read_csv(io.StringIO(group_branchwise_mix_files[f"group_branch_wise_g{idx+1}.csv"]))
        for roll in df_temp['Roll']:
            counts[roll[4:6]] += 1
        counts["group"] = f"g{idx+1}"
        stat_branchwise.append(counts)
    df_stat_branchwise = pd.DataFrame(stat_branchwise).set_index("group")

    buf = io.StringIO()
    df_stat_branchwise.to_csv(buf)
    branchwise_stat_csv = buf.getvalue()

    # Stats files will generate for uniform mix
    stat_uniform = []
    for idx in range(n_groups):
        counts = {branch: 0 for branch in unique_branches}
        df_temp = pd.read_csv(io.StringIO(uniform_mix_files[f"group_uniform_g{idx+1}.csv"]))
        for roll in df_temp['Roll']:
            counts[roll[4:6]] += 1
        counts["group"] = f"g{idx+1}"
        stat_uniform.append(counts)
    df_stat_uniform = pd.DataFrame(stat_uniform).set_index("group")

    buf = io.StringIO()
    df_stat_uniform.to_csv(buf)
    uniform_stat_csv = buf.getvalue()

    return branch_wise_files, group_branchwise_mix_files, uniform_mix_files, branchwise_stat_csv, uniform_stat_csv

# STREAMLIT APP Connection

st.title("Branch-wise Group & Mix Tool")

uploaded_file = st.file_uploader("Upload your input .csv or .xlsx file with 'Roll' 'column' ", type=["csv", "xlsx"])

if uploaded_file:
    try:
        if uploaded_file.name.endswith('.xlsx'):
            df_input = pd.read_excel(uploaded_file)
        else:
            df_input = pd.read_csv(uploaded_file)
    except Exception as e:
        st.error(f" Error reading file: {e}")
        st.stop()

    if 'Roll' not in df_input.columns:
        st.error("The uploaded file must contain a 'Roll' 'column'.")
        st.stop() 

    st.markdown("2. Set Grouping Parameters")
    col1, col2 = st.columns([1, 2])
    with col1:
        n_groups = st.number_input("Number of groups", min_value=1, step=1, value=1)
    with col2:
        st.write("Specify how many groups or batches you'd like to generate from your data.")

    process_btn = st.button("Process and Generate Files")

    if process_btn:
        with st.spinner("Processing your data"):
            branch_files, branch_group_files, uniform_group_files, branch_stats_csv, uniform_stats_csv = process_data(
                df_input, n_groups
            )
        st.success("Processing complete! See the results below.")

        with st.expander("Branch-wise Split Files", expanded=False):
            for fname, content in branch_files.items():
                st.download_button(label=f"Download {fname}", data=content, file_name=fname, mime="text/csv")

        with st.expander("Group-Branch-wise Mixed Groups", expanded=False):
            for fname, content in branch_group_files.items():
                st.download_button(label=f"Download {fname}", data=content, file_name=fname, mime="text/csv")

        with st.expander("Uniform Mixed Groups", expanded=False):
            for fname, content in uniform_group_files.items():
                st.download_button(label=f"Download {fname}", data=content, file_name=fname, mime="text/csv")

        with st.expander(" Download Stats CSVs", expanded=False):
            st.download_button(
                label="Download Group-Branch-wise Stats",
                data=branch_stats_csv,
                file_name=f"branchwise_stats_{n_groups}_groups.csv",
                mime="text/csv"
            )
            st.download_button(
                label="Download Uniform Group Stats",
                data=uniform_stats_csv,
                file_name=f"uniform_stats_{n_groups}_groups.csv",
                mime="text/csv"
            )
else:
    st.info(" Please upload input file with a 'Roll' and 'column' to begin.")

    
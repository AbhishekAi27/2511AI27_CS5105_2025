import streamlit as st
import pandas as pd
import os
import shutil
import zipfile
from collections import deque
from io import BytesIO

def generate_branchwise(df, base_dir):
    output_dir = os.path.join(base_dir, "full_branchwise")
    os.makedirs(output_dir, exist_ok=True)
    for branch in df['Branch'].unique():
        branch_df = df[df['Branch'] == branch]
        branch_df.drop(columns=['Branch']).to_csv(os.path.join(output_dir, f"{branch}.csv"), index=False)
    return output_dir

def generate_group_branchwise_mix(df, N, base_dir):
    output_dir = os.path.join(base_dir, "group_branch_wise_mix")
    os.makedirs(output_dir, exist_ok=True)

    total_students = len(df)
    q, r = divmod(total_students, N)
    group_sizes = [q + 1] * r + [q] * (N - r)

    branches = {branch: deque(df[df['Branch'] == branch].to_dict('records'))
                for branch in df['Branch'].unique()}

    groups = []
    branch_order = list(branches.keys())

    for g in range(N):
        group = []
        while len(group) < group_sizes[g] and any(branches.values()):
            for branch in branch_order:
                if branches[branch] and len(group) < group_sizes[g]:
                    student = branches[branch].popleft()
                    group.append(student)
        groups.append(group)

    for idx, group in enumerate(groups, start=1):
        gdf = pd.DataFrame(group).drop(columns=['Branch'])
        gdf.to_csv(os.path.join(output_dir, f"g{idx}.csv"), index=False)

    return output_dir


def generate_group_uniform_mix(df, N, base_dir):
    output_dir = os.path.join(base_dir, "group_uniform_mix")
    os.makedirs(output_dir, exist_ok=True)

    total_students = len(df)
    q, r = divmod(total_students, N)
    group_sizes = [q + 1] * r + [q] * (N - r)

    branch_students = {b: deque(g.to_dict('records')) for b, g in df.groupby('Branch')}

    groups = []
    for size in group_sizes:
        group = []
        remaining = size
        while remaining > 0 and branch_students:
            branch = max(branch_students.keys(), key=lambda b: (len(branch_students[b]), b))
            take = min(len(branch_students[branch]), remaining)
            for _ in range(take):
                group.append(branch_students[branch].popleft())
            remaining -= take
            if not branch_students[branch]:
                del branch_students[branch]
        groups.append(group)

    for idx, group in enumerate(groups, start=1):
        gdf = pd.DataFrame(group).drop(columns=['Branch']) if group else pd.DataFrame(columns=df.columns)
        gdf.to_csv(os.path.join(output_dir, f"g{idx}.csv"), index=False)

    return output_dir


def generate_combined_summary(mix_dir, uniform_dir, output_file):
    def make_summary(input_dir):
        summary = []
        for file in sorted(os.listdir(input_dir)):
            if file.endswith(".csv"):
                group_name = os.path.splitext(file)[0]
                df = pd.read_csv(os.path.join(input_dir, file))
                df['Branch'] = df['Roll'].astype(str).str[4:6]
                counts = df['Branch'].value_counts().to_dict()
                row = {"Group": group_name}
                row.update(counts)
                summary.append(row)

        df_summary = pd.DataFrame(summary).fillna(0)
        for col in df_summary.columns:
            if col != "Group":
                df_summary[col] = df_summary[col].astype(int)

        # Add total column
        branch_cols = [c for c in df_summary.columns if c != "Group"]
        df_summary["Total"] = df_summary[branch_cols].sum(axis=1)

        cols = ["Group"] + sorted(branch_cols) + ["Total"]
        return df_summary[cols]

    df_mix = make_summary(mix_dir)
    df_uniform = make_summary(uniform_dir)

    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        df_mix.to_excel(writer, sheet_name="Branchwise_Mix", index=False)
        df_uniform.to_excel(writer, sheet_name="Uniform_Mix", index=False)

    return output_file


def make_zip(base_dir):
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        for root, _, files in os.walk(base_dir):
            for file in files:
                filepath = os.path.join(root, file)
                arcname = os.path.relpath(filepath, base_dir)
                zf.write(filepath, arcname)
    zip_buffer.seek(0)
    return zip_buffer
st.title("Tut01")

uploaded_file = st.file_uploader("Upload Input CSV/Excel", type=["csv", "xlsx"])
N = st.number_input("Enter number of groups", min_value=1, step=1, value=2)

if uploaded_file:
    if st.button("Process"):
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)

        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        if 'Unique' in df.columns:
            df = df.drop(columns=['Unique'])
        df['Branch'] = df['Roll'].astype(str).str[4:6]

        base_dir = "outputs"
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)
        os.makedirs(base_dir, exist_ok=True)
        generate_branchwise(df, base_dir)
        mix_dir = generate_group_branchwise_mix(df, N, base_dir)
        uniform_dir = generate_group_uniform_mix(df, N, base_dir)
        summary_file = generate_combined_summary(mix_dir, uniform_dir, os.path.join(base_dir, "output.xlsx"))
        zip_file = make_zip(base_dir)

        st.success("Processing complete! Download your files below.")
        st.download_button("Download ZIP", data=zip_file, file_name="tut01.zip", mime="application/zip")

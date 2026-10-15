#!/usr/bin/env python3
"""将 data/inbox/2026-08-09/ 下的所有 xlsx 按登记时间拆分到对应日期目录"""
import pandas as pd
from pathlib import Path
from collections import defaultdict
import sys

SRC_DIR = Path("/home/c1/jianfu-tongbao/data/inbox/2026-08-09")
BASE_INBOX = Path("/home/c1/jianfu-tongbao/data/inbox")

for d in range(1, 10):
    (BASE_INBOX / f"2026-08-{d:02d}").mkdir(parents=True, exist_ok=True)

date_dfs = defaultdict(list)

files = list(SRC_DIR.glob("*.xlsx"))
print(f"共 {len(files)} 个文件", flush=True)

for i, xlsx_file in enumerate(files):
    print(f"[{i+1}/{len(files)}] 读取: {xlsx_file.name}", flush=True)
    df = pd.read_excel(xlsx_file, header=1)
    date_col = df.columns[12]
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    
    for dt, group in df.groupby(df[date_col].dt.date):
        if pd.isna(dt):
            continue
        date_dfs[dt].append(group)

print("合并并写入...", flush=True)
for dt, dfs in date_dfs.items():
    combined = pd.concat(dfs, ignore_index=True)
    target_dir = BASE_INBOX / f"2026-08-{dt.day:02d}"
    target_file = target_dir / f"appeals_{dt}.xlsx"
    combined.to_excel(target_file, index=False)
    print(f"  {target_dir.name}: {len(combined)} 行", flush=True)

print("完成", flush=True)
#!/usr/bin/env python3
"""将 /tmp/jianfu-826-831/ 的 xlsx 按登记时间拆分到 data/inbox/2026-08-26 ~ 2026-08-31"""
import pandas as pd
from pathlib import Path

SRC_DIR = Path("/tmp/jianfu-826-831")
BASE_INBOX = Path("/home/c1/jianfu-tongbao/data/inbox")

# 创建目标目录
for d in range(26, 32):
    (BASE_INBOX / f"2026-08-{d:02d}").mkdir(parents=True, exist_ok=True)

# 读取每个文件，按日期拆分
files = sorted(SRC_DIR.glob("*.xlsx"))
print(f"读取 {len(files)} 个 xlsx 文件...")

total_split = 0
for xlsx_file in files:
    try:
        df = pd.read_excel(xlsx_file, header=1)
        df['登记时间'] = pd.to_datetime(df['登记时间'], errors='coerce')
        
        for dt, group in df.groupby(df['登记时间'].dt.date):
            if pd.isna(dt) or dt.year != 2026 or dt.month != 8 or dt.day < 26 or dt.day > 31:
                continue
            target_dir = BASE_INBOX / f"2026-08-{dt.day:02d}"
            target_file = target_dir / xlsx_file.name
            
            if target_file.exists():
                existing = pd.read_excel(target_file, header=1)
                combined = pd.concat([existing, group], ignore_index=True)
                combined.to_excel(target_file, index=False)
            else:
                group.to_excel(target_file, index=False)
            total_split += len(group)
    except Exception as e:
        print(f"  跳过 {xlsx_file.name}: {e}")

print(f"拆分完成: 共 {total_split} 行")

# 统计每日行数
print("\n=== 每日数据统计 ===")
for d in range(26, 32):
    day_dir = BASE_INBOX / f"2026-08-{d:02d}"
    if day_dir.exists():
        total = 0
        for f in day_dir.glob("*.xlsx"):
            try:
                df = pd.read_excel(f, header=1)
                total += len(df)
            except:
                pass
        print(f"2026-08-{d:02d}: {total} 行")

#!/usr/bin/env python3
"""将 data/inbox/2026-08-09/ 下的所有 xlsx 按登记时间拆分到对应日期目录"""
import pandas as pd
import shutil
from pathlib import Path
from datetime import date

SRC_DIR = Path("/home/c1/jianfu-tongbao/data/inbox/2026-08-09")
BASE_INBOX = Path("/home/c1/jianfu-tongbao/data/inbox")

# 创建 8月1-9日 的目录
for d in range(1, 10):
    (BASE_INBOX / f"2026-08-{d:02d}").mkdir(parents=True, exist_ok=True)

# 读取每个文件，按日期拆分
for xlsx_file in SRC_DIR.glob("*.xlsx"):
    print(f"处理: {xlsx_file.name}")
    df = pd.read_excel(xlsx_file, header=1)
    df['登记时间'] = pd.to_datetime(df['登记时间'], errors='coerce')
    
    # 按日期分组
    for dt, group in df.groupby(df['登记时间'].dt.date):
        if pd.isna(dt):
            continue
        target_dir = BASE_INBOX / f"2026-08-{dt.day:02d}"
        target_file = target_dir / xlsx_file.name
        
        # 追加写入（保留表头）
        if target_file.exists():
            # 读取现有，合并
            existing = pd.read_excel(target_file, header=1)
            combined = pd.concat([existing, group], ignore_index=True)
            combined.to_excel(target_file, index=False)
        else:
            group.to_excel(target_file, index=False)
        print(f"  -> {target_dir.name}: {len(group)} 行")

print("拆分完成")

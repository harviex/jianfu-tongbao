#!/usr/bin/env python3
"""
Master 脚本：
1. 解压 4 个 ZIP 到 /tmp
2. 读取所有 xlsx，按登记时间拆分到 data/inbox/YYYY-MM-DD/
3. 每日目录生成 appeals_YYYY-MM-DD.xlsx（合并同一天的所有文件）
"""
import pandas as pd
import shutil
import zipfile
from pathlib import Path
from datetime import date

ZIP_FILES = [
    "/home/c1/Downloads/716-731.zip",  # 7月16-31
    "/home/c1/Downloads/701-715.zip",  # 7月1-15
    "/home/c1/Downloads/616-630.zip",  # 6月16-30
    "/home/c1/Downloads/601-615.zip",  # 6月1-15
]

TMP_DIR = Path("/tmp/jianfu_unzip")
INBOX_BASE = Path("/home/c1/jianfu-tongbao/data/inbox")

def detect_header_row(filepath):
    df0 = pd.read_excel(filepath, header=None, nrows=3)
    for i in range(min(3, len(df0))):
        if '登记时间' in ' '.join(df0.iloc[i].astype(str).tolist()):
            return i
    return 1

def main():
    # 清理临时目录
    if TMP_DIR.exists():
        shutil.rmtree(TMP_DIR)
    TMP_DIR.mkdir(parents=True)
    
    # 创建 6月1日 - 7月31日 目录
    for month in [6, 7]:
        for day in range(1, 32):
            try:
                d = date(2026, month, day)
                (INBOX_BASE / d.strftime("%Y-%m-%d")).mkdir(parents=True, exist_ok=True)
            except ValueError:
                pass  # 无效日期如 6月31日
    
    print("📦 解压 ZIP 文件...")
    for zip_path in ZIP_FILES:
        print(f"  解压: {Path(zip_path).name}")
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(TMP_DIR)
    
    # 读取所有 xlsx，按日期分组写入
    all_files = list(TMP_DIR.glob("*.xlsx"))
    print(f"\n📊 共 {len(all_files)} 个 xlsx 文件，开始按日期拆分...")
    
    date_groups = {}  # date_str -> list of (filepath, dataframe)
    
    for i, xlsx_file in enumerate(all_files, 1):
        if i % 20 == 0:
            print(f"  处理进度: {i}/{len(all_files)}")
        header_row = detect_header_row(xlsx_file)
        df = pd.read_excel(xlsx_file, header=header_row)
        df['登记时间'] = pd.to_datetime(df['登记时间'], errors='coerce')
        
        # 按日期分组
        for dt, group in df.groupby(df['登记时间'].dt.date):
            if pd.isna(dt):
                continue
            date_str = dt.strftime("%Y-%m-%d")
            if date_str not in date_groups:
                date_groups[date_str] = []
            date_groups[date_str].append(group)
    
    # 写入每日合并文件
    print(f"\n💾 写入 {len(date_groups)} 个日期的合并文件...")
    for date_str, groups in sorted(date_groups.items()):
        combined = pd.concat(groups, ignore_index=True)
        target_file = INBOX_BASE / date_str / f"appeals_{date_str}.xlsx"
        combined.to_excel(target_file, index=False)
        print(f"  {date_str}: {len(combined)} 行 -> {target_file.name}")
    
    # 清理临时文件
    shutil.rmtree(TMP_DIR)
    print("\n✅ Master 脚本完成！所有每日文件已就绪。")

if __name__ == "__main__":
    main()

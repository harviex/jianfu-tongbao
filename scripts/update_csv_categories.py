#!/usr/bin/env python3
"""将 clues_latest.csv 和各日 CSV 的分类更新为标准库映射"""
import csv
import json
from pathlib import Path

# 读取映射
with open('/home/c1/jianfu-tongbao/data/clues_test.json', 'r', encoding='utf-8') as f:
    clues = json.load(f)

mapping = {c['task_num']: {'category': c['clue_category'], 'subcategory': c['clue_subcategory']} for c in clues}

# 更新 clues_latest.csv
csv_path = Path('/home/c1/jianfu-tongbao/data/static/clues_latest.csv')
rows = []
with open(csv_path, 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    for row in reader:
        tid = row['appeal_id']
        if tid in mapping:
            row['category'] = mapping[tid]['category']
            row['subcategory'] = mapping[tid]['subcategory']
        rows.append(row)

with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
print(f"已更新: {csv_path}")

# 更新各日 high_confidence CSV
for day in ['20260801', '20260802', '20260803', '20260805', '20260806', '20260807', '20260808']:
    csv_path = Path(f'/home/c1/jianfu-tongbao/data/static/clues_high_confidence_{day}.csv')
    if csv_path.exists():
        rows = []
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for row in reader:
                tid = row['appeal_id']
                if tid in mapping:
                    row['category'] = mapping[tid]['category']
                    row['subcategory'] = mapping[tid]['subcategory']
                rows.append(row)
        with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"已更新: {csv_path}")

# 更新各日 raw CSV
for day in ['20260801', '20260802', '20260803', '20260805', '20260806', '20260807', '20260808']:
    csv_path = Path(f'/home/c1/jianfu-tongbao/data/static/clues_raw_{day}.csv')
    if csv_path.exists():
        rows = []
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for row in reader:
                tid = row['appeal_id']
                if tid in mapping:
                    row['category'] = mapping[tid]['category']
                    row['subcategory'] = mapping[tid]['subcategory']
                rows.append(row)
        with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"已更新: {csv_path}")

print("\n✅ 所有 CSV 分类已更新")

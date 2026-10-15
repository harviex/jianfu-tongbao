import json
import csv
from datetime import datetime

# 读取 CSV
csv_path = "/home/c1/jianfu-tongbao/data/static/clues_latest.csv"
with open(csv_path, 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    clues = list(reader)

# 转换为 clues_test.json 格式
output = []
for i, row in enumerate(clues, 1):
    clue = {
        "id": i,
        "seq_no": i,
        "task_num": row['appeal_id'],
        "title": row['title'],
        "content": row['content'],
        "publish_time": row['publish_time'],
        "region_city": row['region_city'] if row['region_city'] else "未知",
        "region_district": row['region_district'] if row['region_district'] else "未知",
        "complained_unit": row['complained_unit'] if row['complained_unit'] else "",
        "identity_card": "",
        "complainant_name": "",
        "phone": "",
        "clue_category": row['category'],
        "clue_subcategory": row['subcategory'],
        "root_cause": row['root_cause'],
        "is_typical": float(row['confidence']) >= 0.9,
        "tags": eval(row['tags']) if row['tags'] else [],
        "confidence": float(row['confidence']),
        "qualitative_analysis": row['qualitative_analysis'],
        "evidence_suggestion": row['evidence_suggestion'],
        "is_relevant": True,
        "llm_reason": row['llm_reason'],
        "created_at": row['created_at'],
        "updated_at": row['created_at']
    }
    output.append(clue)

# 写入 clues_test.json
with open("/home/c1/jianfu-tongbao/data/clues_test.json", 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"转换完成：{len(output)} 条线索已写入 data/clues_test.json")
for c in output:
    print(f"  {c['seq_no']}. {c['task_num']} - {c['title'][:50]}...")
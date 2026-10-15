#!/usr/bin/env python3
"""从标准映射直接生成正确的 clues_test.json"""
import json
import csv
from datetime import datetime

# 标准映射
MAPPING = {
    "PT26080820429": {"clue_category": "督查检查考核", "clue_subcategory": "计划备案不规范/以调研名行考核实/打包报计划执行拆分"},
    "FZ26080821173": {"clue_category": "会议文件泛滥", "clue_subcategory": "文件会议过多/层层陪会"},
    "XM26080722732": {"clue_category": "权责不清/甩锅", "clue_subcategory": "清单外事项下放/签责任状转嫁/属地管理甩锅"},
    "FZ26080722110": {"clue_category": "权责不清/甩锅", "clue_subcategory": "证明事项滥设/万能证明/社区盖章"},
    "FZ26080720413": {"clue_category": "督查检查考核", "clue_subcategory": "总量失控/多头重复/排名通报变相考核/县乡村考核未合并"},
    "QZ26080621546": {"clue_category": "督查检查考核", "clue_subcategory": "计划备案不规范/以调研名行考核实/打包报计划执行拆分"},
    "QZ26080621527": {"clue_category": "权责不清/甩锅", "clue_subcategory": "清单外事项下放/签责任状转嫁/属地管理甩锅"},
    "FJ26080620070": {"clue_category": "数据造假", "clue_subcategory": "统计造假-指令报数/代填代报/虚假审批"},
    "XM26080620366": {"clue_category": "督查检查考核", "clue_subcategory": "总量失控/多头重复/排名通报变相考核/县乡村考核未合并"},
    "FJ26080520223": {"clue_category": "数据造假", "clue_subcategory": "统计造假-指令报数/代填代报/虚假审批"},
    "FZ26080521973": {"clue_category": "指尖形式主义", "clue_subcategory": "强制打卡/积分排名/在线时长/上传照片视频轨迹"},
    "FJ26080420247": {"clue_category": "数据造假", "clue_subcategory": "统计造假-指令报数/代填代报/虚假审批"},
    "LY26080420534": {"clue_category": "指尖形式主义", "clue_subcategory": "政务APP泛滥/未整合/僵尸应用/多头建设"},
    "ND26080420463": {"clue_category": "督查检查考核", "clue_subcategory": "计划备案不规范/以调研名行考核实/打包报计划执行拆分"},
    "NP26080420342": {"clue_category": "权责不清/甩锅", "clue_subcategory": "证明事项滥设/万能证明/社区盖章"},
    "PT26080420594": {"clue_category": "督查检查考核", "clue_subcategory": "总量失控/多头重复/排名通报变相考核/县乡村考核未合并"},
    "XM26080420884": {"clue_category": "指尖形式主义", "clue_subcategory": "强制打卡/积分排名/在线时长/上传照片视频轨迹"},
    "XM26080323889": {"clue_category": "权责不清/甩锅", "clue_subcategory": "清单外事项下放/签责任状转嫁/属地管理甩锅"},
    "FJ26080320224": {"clue_category": "数据造假", "clue_subcategory": "统计造假-指令报数/代填代报/虚假审批"},
    "QZ26080321931": {"clue_category": "会议文件泛滥", "clue_subcategory": "文件会议过多/层层陪会"},
    "QZ26080321773": {"clue_category": "督查检查考核", "clue_subcategory": "计划备案不规范/以调研名行考核实/打包报计划执行拆分"},
    "FJ26080220115": {"clue_category": "数据造假", "clue_subcategory": "统计造假-指令报数/代填代报/虚假审批"},
    "FZ26080220228": {"clue_category": "数据造假", "clue_subcategory": "统计造假-指令报数/代填代报/虚假审批"},
    "FZ26080122016": {"clue_category": "会议文件泛滥", "clue_subcategory": "文件会议过多/层层陪会"},
    "QZ26080120516": {"clue_category": "督查检查考核", "clue_subcategory": "计划备案不规范/以调研名行考核实/打包报计划执行拆分"},
    "FZ26080723362": {"clue_category": "权责不清/甩锅", "clue_subcategory": "清单外事项下放/签责任状转嫁/属地管理甩锅"},
    "FZ26080623495": {"clue_category": "数据造假", "clue_subcategory": "统计造假-指令报数/代填代报/虚假审批"},
    "FZ26080621307": {"clue_category": "数据造假", "clue_subcategory": "统计造假-指令报数/代填代报/虚假审批"},
    "QZ26080620394": {"clue_category": "督查检查考核", "clue_subcategory": "计划备案不规范/以调研名行考核实/打包报计划执行拆分"},
    "FJ26080620065": {"clue_category": "数据造假", "clue_subcategory": "统计造假-指令报数/代填代报/虚假审批"},
    "XM26080620069": {"clue_category": "权责不清/甩锅", "clue_subcategory": "证明事项滥设/万能证明/社区盖章"},
    "FJ26080520164": {"clue_category": "权责不清/甩锅", "clue_subcategory": "清单外事项下放/签责任状转嫁/属地管理甩锅"},
    "PI26080520053": {"clue_category": "指尖形式主义", "clue_subcategory": "政务APP泛滥/未整合/僵尸应用/多头建设"},
    "NP26080520011": {"clue_category": "权责不清/甩锅", "clue_subcategory": "清单外事项下放/签责任状转嫁/属地管理甩锅"},
    "ND26080520005": {"clue_category": "指尖形式主义", "clue_subcategory": "强制打卡/积分排名/在线时长/上传照片视频轨迹"},
    "FZ26080423399": {"clue_category": "权责不清/甩锅", "clue_subcategory": "清单外事项下放/签责任状转嫁/属地管理甩锅"},
    "NP26080420469": {"clue_category": "权责不清/甩锅", "clue_subcategory": "证明事项滥设/万能证明/社区盖章"},
    "ND26080420146": {"clue_category": "指尖形式主义", "clue_subcategory": "政务APP泛滥/未整合/僵尸应用/多头建设"},
    "XM26080323398": {"clue_category": "会议文件泛滥", "clue_subcategory": "文件会议过多/层层陪会"},
    "FZ26080221734": {"clue_category": "指尖形式主义", "clue_subcategory": "政务APP泛滥/未整合/僵尸应用/多头建设"},
    "FZ26080221254": {"clue_category": "督查检查考核", "clue_subcategory": "总量失控/多头重复/排名通报变相考核/县乡村考核未合并"},
}

# 从 CSV 读取基础数据
with open('/home/c1/jianfu-tongbao/data/static/clues_latest.csv', 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    clues = list(reader)

output = []
for i, row in enumerate(clues, 1):
    tid = row['appeal_id']
    mapping = MAPPING.get(tid, {})
    
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
        "clue_category": mapping.get('clue_category', row['category']),
        "clue_subcategory": mapping.get('clue_subcategory', row['subcategory']),
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

with open('/home/c1/jianfu-tongbao/data/clues_test.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"✅ 生成完成：{len(output)} 条线索")
for c in output[:5]:
    print(f"  {c['task_num']}: {c['clue_category']} | {c['clue_subcategory']}")

# 验证
cat_counter = {}
sub_counter = {}
for c in output:
    cat_counter[c['clue_category']] = cat_counter.get(c['clue_category'], 0) + 1
    sub_counter[c['clue_subcategory']] = sub_counter.get(c['clue_subcategory'], 0) + 1

print("\n📊 一级分类分布:")
for k, v in sorted(cat_counter.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v}")
print("\n📊 细分类分布:")
for k, v in sorted(sub_counter.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v}")

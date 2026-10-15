#!/usr/bin/env python3
"""添加2026年8月新通报到notices.json并更新standards.json"""
import json

# 读取现有数据
with open('/home/c1/jianfu-tongbao/data/notices.json', 'r', encoding='utf-8') as f:
    notices = json.load(f)

with open('/home/c1/jianfu-tongbao/data/standards.json', 'r', encoding='utf-8') as f:
    standards = json.load(f)

# 现有ID最大值
max_id = max(n.get('id', 0) for n in notices)

# 新增通报
new_notices = [
    {
        "id": max_id + 1,
        "title": "重庆市市级层面整治形式主义为基层减负专项工作机制办公室 中共重庆市纪委办公厅关于整治形式主义为基层减负典型问题的情况通报",
        "source_url": "https://m.12371.gov.cn/content/2026-08/21/content_514960.html",
        "level_1": "市级",
        "level_2": ["盲目决策", "违规上马扶贫项目", "行业协会违规收费"],
        "publish_date": "2026-08-21",
        "content": "奉节县在园区已有厂房闲置和大量在建情况下，盲目扩大投资新建产业项目用房，加重地方债务负担。重庆农投集团良品公司盲目决策、违规上马扶贫智能专柜项目，因经营不善导致设备大量闲置、国有资金损失。重庆药学会违规举办论坛活动并收取费用，相关企业反映强烈。",
        "summary": "重庆通报3起典型问题：奉节县盲目投资建厂房、农投集团违规上马扶贫项目、药学会违规收费",
        "tags": ["盲目投资", "违规上马项目", "行业协会违规收费", "债务负担", "国有资金损失"],
        "provinces": ["重庆"],
        "case_count": 3,
        "source_site": "七一网（风正巴渝微信公众号）",
        "ai_processed": False,
        "content_preview": "奉节县盲目扩大投资新建产业项目用房，加重地方债务负担。重庆农投集团良品公司盲目决策、违规上马扶贫智能专柜项目。重庆药学会违规举办论坛活动并收取费用。",
        "categories": ["盲目决策/形象工程", "权责不清/甩锅"]
    },
    {
        "id": max_id + 2,
        "title": "省整治形式主义为基层减负专项工作机制办公室 省纪委办公厅关于2起整治形式主义为基层减负典型问题的情况通报",
        "source_url": "https://www.lnsjjjc.gov.cn/network/snyw/2026/08/07/940178381889082617.shtml",
        "level_1": "省级",
        "level_2": ["数据造假", "社会组织管理混乱"],
        "publish_date": "2026-08-07",
        "content": "锦州市太和区城市管理综合行政执法局制造假投诉，虚增回访满意率。省印章协会内部管理混乱，协会领导违规领取报酬。",
        "summary": "辽宁通报2起典型问题：锦州城管制造假投诉虚增满意率、省印章协会管理混乱",
        "tags": ["制造假投诉", "虚增满意率", "数据造假", "社会组织管理混乱", "违规领取报酬"],
        "provinces": ["辽宁"],
        "case_count": 2,
        "source_site": "辽宁纪检监察网",
        "ai_processed": False,
        "content_preview": "锦州市太和区城市管理综合行政执法局制造假投诉，虚增回访满意率。省印章协会内部管理混乱，协会领导违规领取报酬。",
        "categories": ["数据造假", "权责不清/甩锅"]
    },
    {
        "id": max_id + 3,
        "title": "福建省级层面整治形式主义为基层减负专项工作机制办公室公开通报1起整治形式主义为基层减负典型问题",
        "source_url": "https://www.fujian.gov.cn/xwdt/fjyw/202606/t20260626_7168077.htm",
        "level_1": "省级",
        "level_2": ["社会组织违规评比"],
        "publish_date": "2026-06-26",
        "content": "2024年3月，省民政厅、省委社会工作部对全省性社会组织评比表彰活动进行清理优化，清理后没有保留的活动项目。2025年10月，省电子商务促进会未经批准，在其十周年庆典大会上开展评比表彰活动，对参会企业和个人颁发13类奖项，有的奖项名称冠以福建字样，且评奖过程没有制定评选条件和具体方案，参会企业或个人均获得奖项。",
        "summary": "福建通报1起典型问题：省电商促进会未经批准开展评比表彰",
        "tags": ["未经批准", "评比表彰", "社会组织违规", "企业负担"],
        "provinces": ["福建"],
        "case_count": 1,
        "source_site": "福建省人民政府门户网站",
        "ai_processed": False,
        "content_preview": "省电子商务促进会未经批准，在其十周年庆典大会上开展评比表彰活动，对参会企业和个人颁发13类奖项。",
        "categories": ["创建示范/达标"]
    }
]

# 添加新通报
notices.extend(new_notices)

# 写回
with open('/home/c1/jianfu-tongbao/data/notices.json', 'w', encoding='utf-8') as f:
    json.dump(notices, f, ensure_ascii=False, indent=2)

print(f"通报已更新：{len(notices)} 条（新增 {len(new_notices)} 条）")

# 检查是否需要新增标准
existing_categories = set((s['category'], s['subcategory']) for s in standards)
print(f"\n当前标准数：{len(standards)}")

# 新通报涉及的新分类
new_standards_needed = [
    ("数据造假", "制造假投诉/虚增满意率/虚假工单/数据注水", "制造假投诉、虚增满意率、虚假工单、数据注水、满意度造假"),
    ("权责不清/甩锅", "社会组织管理混乱/未年检/违规发放报酬/内部治理失序", "社会组织管理混乱、未年检、违规发放报酬、内部治理失序、财务管理混乱"),
]

added = 0
for cat, sub, kws in new_standards_needed:
    if (cat, sub) not in existing_categories:
        standards.append({
            "category": cat,
            "subcategory": sub,
            "keywords": kws,
            "source": "2026-08新增通报"
        })
        existing_categories.add((cat, sub))
        added += 1
        print(f"  + 新增标准：{cat} / {sub}")

if added > 0:
    with open('/home/c1/jianfu-tongbao/data/standards.json', 'w', encoding='utf-8') as f:
        json.dump(standards, f, ensure_ascii=False, indent=2)
    print(f"\n标准已更新：{len(standards)} 条（新增 {added} 条）")
else:
    print("\n无需新增标准，现有标准已覆盖新通报类型")

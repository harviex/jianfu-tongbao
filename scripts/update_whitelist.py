#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基于更新后的 46 条认定标准，合并更新 whitelist.yaml
提取所有关键词，去重，合并到现有白名单
"""

import yaml
import re
import json

# Load existing whitelist
with open('/home/c1/jianfu-tongbao/config/whitelist.yaml', 'r', encoding='utf-8') as f:
    whitelist = yaml.safe_load(f)

print(f"Existing whitelist patterns: {len(whitelist['patterns'])}")
for p in whitelist['patterns']:
    print(f"  Category: {p['category']}, Weight: {p['weight']}")

# Load updated standards
with open('/home/c1/jianfu-tongbao/data/updated_standards.json', 'r', encoding='utf-8') as f:
    standards = json.load(f)

# Extract all keywords from standards
all_keywords = set()
for s in standards:
    kws = s['keywords'].split('、')
    for kw in kws:
        kw = kw.strip()
        if kw:
            all_keywords.add(kw)

print(f"\nTotal unique keywords from standards: {len(all_keywords)}")

# Also extract from caseLinks
for s in standards:
    # Extract location/date patterns from caseLink
    link = s.get('caseLink', '')
    # These are reference links, not keywords, so skip

# Now let's create new patterns from the standards categories
# Group keywords by category
from collections import defaultdict
cat_keywords = defaultdict(set)
for s in standards:
    cat = s['category']
    kws = s['keywords'].split('、')
    for kw in kws:
        kw = kw.strip()
        if kw:
            cat_keywords[cat].add(kw)

# Define new patterns to add/merge
new_patterns = []

# 1. 数据造假 - 新增细分
data_fake_kws = cat_keywords.get('数据造假', set())
if data_fake_kws:
    # Filter new ones not well covered
    new_data = [k for k in data_fake_kws if any(x in k for x in ['榜单', '百强', '购买.*数据', '异地.*数据', '外贸', '中介机构', '规上企业', '固投', '编造备案', '入库备案', '35亿元', '40余亿元'])]
    if new_data:
        new_patterns.append({
            'pattern': '|'.join(sorted(new_data, key=len, reverse=True)[:30]),
            'category': '数据造假-榜单/外贸/工业虚报',
            'weight': 10,
            'fields': ['title', 'content']
        })

# 2. 指尖形式主义 - 新增细分
finger_kws = cat_keywords.get('指尖形式主义', set())
new_finger = [k for k in finger_kws if any(x in k for x in ['一表通', '体外循环', '绕过系统', '多头填报', '重复填报', '指标口径', '统计标准', '村医通', '智能终端', '使用率排名', '周排名', '设备推广', '定位打卡', '上传日志', '驻村干部', '打卡异常', '权限交接', '系统改版', '功能隐藏', '旧数据', '签字确认', '微信报送'])]
if new_finger:
    new_patterns.append({
        'pattern': '|'.join(sorted(new_finger, key=len, reverse=True)[:30]),
        'category': '指尖形式主义-体外循环/智能终端/打卡细分',
        'weight': 9,
        'fields': ['title', 'content']
    })

# 3. 权责不清/甩锅 - 新增细分
duty_kws = cat_keywords.get('权责不清/甩锅', set())
new_duty = [k for k in duty_kws if any(x in k for x in ['议事协调机构', '办公室名义', '指令性公文', '向基层发文', '发文总量', '行业协会', '社会组织', '违规评比', '合作费', '品牌推介费', '会议费', '典型案例评选', '授牌', '商业保险', '补充保险', '村集体资金', '动员购买', '通报完成情况'])]
if new_duty:
    new_patterns.append({
        'pattern': '|'.join(sorted(new_duty, key=len, reverse=True)[:30]),
        'category': '权责不清-议事协调/行业协会/商业保险',
        'weight': 9,
        'fields': ['title', 'content']
    })

# 4. 创建示范/达标 - 新增细分
create_kws = cat_keywords.get('创建示范/达标', set())
new_create = [k for k in create_kws if any(x in k for x in ['社会组织违规创建', '行业协会违规评比', '清单外创建示范', '保留清单范围', '超出保留清单', '示范改领跑', '授牌命名', '领跑基地', '品牌孵化基地', '气候好产品', '评价认证服务费'])]
if new_create:
    new_patterns.append({
        'pattern': '|'.join(sorted(new_create, key=len, reverse=True)[:30]),
        'category': '创建示范-社会组织/行业协会/保留清单',
        'weight': 9,
        'fields': ['title', 'content']
    })

# 5. 盲目决策/形象工程 - 新增细分
blind_kws = cat_keywords.get('盲目决策/形象工程', set())
new_blind = [k for k in blind_kws if any(x in k for x in ['国企盲目投资', '偏离主责主业', '非主营业务', '康养旅游', '房地产项目', '公款印发个人著作', '挪用经营门面', '体彩中心', '农投集团', '耕地提质', '旱改水', '非农化', '非粮化', '水田指标', '水田指标交易', '欠租欠薪', '复种旱地', '弃耕弃收', '撂荒', '自然资源部标记退回', '集中开工', '集中签约', '重复开工', '反复开工', '论证不够', '用地手续不全', '前期研究', '开工仪式', '电子屏费用', '签约名不符实', '落地率偏低'])]
if new_blind:
    new_patterns.append({
        'pattern': '|'.join(sorted(new_blind, key=len, reverse=True)[:30]),
        'category': '盲目决策-国企投资/耕地改造/项目开工',
        'weight': 9,
        'fields': ['title', 'content']
    })

# 6. 精简文件 - 新增细分
doc_kws = cat_keywords.get('精简文件', set())
new_doc = [k for k in doc_kws if any(x in k for x in ['征求意见过频', '周五发周六回', '1-2个工作日', '临近下班', '次日反馈', '连续多次征求', '意见征求时间过紧', '迟迟不印发', '重复发文', '多头转发', '同一文件多次', '重复收文', '收文负担', '电子公文系统', '五分之一重复', '简报重复', '通报重复', '函件重复'])]
if new_doc:
    new_patterns.append({
        'pattern': '|'.join(sorted(new_doc, key=len, reverse=True)[:30]),
        'category': '精简文件-征求意见/重复发文',
        'weight': 8,
        'fields': ['title', 'content']
    })

# 7. 精简会议 - 新增细分
meeting_kws = cat_keywords.get('精简会议', set())
new_meeting = [k for k in meeting_kws if any(x in k for x in ['专班会议', '专项行动会议', '平价菜专班', '百日行动会议', '工作专班', '分会场参会', '主要领导参会', '参会范围过大', '会议规模规格管控不严'])]
if new_meeting:
    new_patterns.append({
        'pattern': '|'.join(sorted(new_meeting, key=len, reverse=True)[:30]),
        'category': '精简会议-专班/专项/平价菜',
        'weight': 8,
        'fields': ['title', 'content']
    })

# 8. 督查检查考核 - 新增细分
inspect_kws = cat_keywords.get('督查检查考核', set())
new_inspect = [k for k in inspect_kws if any(x in k for x in ['指标嵌套', '信息工作排名嵌入', '服务对象满意度', '第三方机构评价', '考评程序复杂', '业务部室评分', '佐证资料过多', '迎考压力', '专项考核超范围', '综合考核外设专项', '县乡村考核未合并', '违规自行组织考核', '社会工作服务站考核', '双拥考核加码', '市级指标套用区级', '计划备案挂空挡', '计划执行两张皮', '未纳入计划管理', '近90%', '备案管理空白', '同一事项反复督查', '全年19次', '2个月7次', '4个部门同一天'])]
if new_inspect:
    new_patterns.append({
        'pattern': '|'.join(sorted(new_inspect, key=len, reverse=True)[:30]),
        'category': '督查检查考核-指标嵌套/专项超范围/计划空白',
        'weight': 10,
        'fields': ['title', 'content']
    })

# 9. 借调干部 - 新增细分
borrow_kws = cat_keywords.get('借调干部', set())
new_borrow = [k for k in borrow_kws if any(x in k for x in ['共青团', '妇联', '工会', '群团组织', '社区工作者借调', '未报批', '超过2年', '范围广', '人数多', '计生协', '摊派保险'])]
if new_borrow:
    new_patterns.append({
        'pattern': '|'.join(sorted(new_borrow, key=len, reverse=True)[:30]),
        'category': '借调干部-群团组织/社区工作者',
        'weight': 9,
        'fields': ['title', 'content']
    })

print(f"\nNew patterns to add: {len(new_patterns)}")
for p in new_patterns:
    print(f"  {p['category']} (weight={p['weight']}): {p['pattern'][:80]}...")

# Now merge with existing whitelist - avoid duplicates by checking pattern overlap
# We'll add the new patterns to the existing list
for np in new_patterns:
    whitelist['patterns'].append(np)

# Update version and date
whitelist['version'] = '2.0'
whitelist['description'] = '白名单/高信号词 - 命中即高优先级送 LLM 判读，权重越高优先级越高 (v2.0 基于46条认定标准更新)'
whitelist['updated_at'] = '2026-08-07'

# Save
with open('/home/c1/jianfu-tongbao/config/whitelist.yaml', 'w', encoding='utf-8') as f:
    yaml.dump(whitelist, f, allow_unicode=True, sort_keys=False)

print(f"\n✅ Updated whitelist saved with {len(whitelist['patterns'])} total patterns")
print(f"   Added {len(new_patterns)} new patterns")
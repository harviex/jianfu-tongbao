#!/usr/bin/env python3
"""
减负线索处理流程：
1. 读取所有 xlsx 文件
2. 去重（诉求编号为主键）
3. 黑白灰名单筛选（关键词规则）
4. LLM 语义判定（qwen3-coder-30b-a3b-instruct）
5. 输出结果到 GitHub Pages
"""

import pandas as pd
import glob
import json
import os
import re
import hashlib
from datetime import datetime

# ============ 1. 读取数据 ============
xlsx_dir = '/tmp/jianfu-826-831'
files = sorted(glob.glob(f'{xlsx_dir}/*.xlsx'))
print(f'读取 {len(files)} 个 xlsx 文件...')

dfs = []
for f in files:
    try:
        df = pd.read_excel(f, header=1)
        dfs.append(df)
    except Exception as e:
        print(f'读取失败: {f} - {e}')

data = pd.concat(dfs, ignore_index=True)
print(f'合并总行数: {len(data)}')

# ============ 2. 清洗去重 ============
# 标准化列名
col_map = {
    '诉求编号': 'task_num',
    '诉求标题': 'title',
    '诉求内容': 'content',
    '诉求类型': 'type',
    '登记时间': 'publish_time',
    '办理单位': 'complained_unit',
    '区域名称': 'region',
    '城市名称': 'city',
    '事件状态': 'status',
    '答复内容': 'reply',
    '一级分类名称': 'category1',
    '二级分类名称': 'category2',
    '三级分类名称': 'category3',
}

# 重命名列
for cn, en in col_map.items():
    if cn in data.columns:
        data.rename(columns={cn: en}, inplace=True)

# 去重（诉求编号）
if 'task_num' in data.columns:
    before = len(data)
    data = data.drop_duplicates(subset=['task_num'])
    print(f'去重后: {len(data)} (去除 {before - len(data)} 条重复)')

# ============ 3. 黑白灰名单筛选 ============
# 核心关键词（命中即为白名单）
CORE_KEYWORDS = [
    '形式主义', '减负', '基层减负', '整治形式主义', '为基层减负',
    '指尖形式主义', '指尖上的形式主义',
]

# 扩展关键词（命中>=2个进入灰名单）
EXT_KEYWORDS = [
    '填表', '报表', '资料', '台账', '留痕', '检查', '考核', '督查',
    '迎检', '资料留痕', '文山会海', '开会', '文件', '调研', '打卡',
    'APP', 'app', '应用程序', '政务', '基层', '负担', '甩锅', '责任状',
    '证明', '创建', '示范', '达标', '评比', '论坛', '节庆', '举债',
    '形象工程', '借调', '千分制', '双千分制', '排名', '通报',
    '虚假整改', '边改边犯', '不惩反奖', '指令报数', '代填代报',
    '虚报', '统计造假', '只考不核', '装信封下指标', '虚假审批',
]

# 否定词（命中即为黑名单）
NEG_KEYWORDS = [
    '咨询', '投诉举报', '建议', '求助', '表扬', '感谢',
]

def text_filter(row):
    """返回: white(白名单), black(黑名单), gray(灰名单), none(无关)"""
    title = str(row.get('title', '') or '')
    content = str(row.get('content', '') or '')
    text = title + content
    
    # 黑名单过滤
    for kw in NEG_KEYWORDS:
        if kw in text and not any(ck in text for ck in CORE_KEYWORDS):
            return 'black'
    
    # 白名单（核心词命中）
    for kw in CORE_KEYWORDS:
        if kw in text:
            return 'white'
    
    # 灰名单（扩展词>=2）
    ext_count = sum(1 for kw in EXT_KEYWORDS if kw in text)
    if ext_count >= 2:
        return 'gray'
    
    return 'none'

print('执行黑白灰名单筛选...')
data['filter_result'] = data.apply(text_filter, axis=1)

white_count = len(data[data['filter_result'] == 'white'])
gray_count = len(data[data['filter_result'] == 'gray'])
black_count = len(data[data['filter_result'] == 'black'])
print(f'白名单: {white_count} | 灰名单: {gray_count} | 黑名单: {black_count}')

# 筛选出需要进一步分析的样本（白名单 + 灰名单）
candidates = data[data['filter_result'].isin(['white', 'gray'])].copy()
print(f'进入 LLM 分析范围: {len(candidates)} 条')

# ============ 4. 数据清洗 ============
def clean_text(text):
    """清洗文本"""
    if pd.isna(text):
        return ''
    text = str(text).strip()
    # 去除多余空白
    text = re.sub(r'\s+', ' ', text)
    return text

candidates['title_clean'] = candidates['title'].apply(clean_text)
candidates['content_clean'] = candidates['content'].apply(clean_text)

# 提取区域信息
def extract_region(row):
    region = str(row.get('region', '') or '')
    city = str(row.get('city', '') or '')
    return city, region

candidates['city'], candidates['region'] = zip(*candidates.apply(extract_region, axis=1))

# ============ 5. 输出待分析数据 ============
# 保存待分析数据
output_data = []
for idx, row in candidates.iterrows():
    output_data.append({
        'task_num': str(row.get('task_num', '')),
        'title': str(row.get('title_clean', '')),
        'content': str(row.get('content_clean', ''))[:2000],  # 截断过长内容
        'publish_time': str(row.get('publish_time', '')),
        'complained_unit': str(row.get('complained_unit', '')),
        'city': str(row.get('city', '')),
        'region': str(row.get('region', '')),
        'filter_result': str(row.get('filter_result', '')),
    })

# 保存到文件
with open('/tmp/jianfu_candidates.json', 'w', encoding='utf-8') as f:
    json.dump(output_data, f, ensure_ascii=False, indent=2)

print(f'已保存 {len(output_data)} 条待分析数据到 /tmp/jianfu_candidates.json')
print(f'数据范围: 2026-08-26 ~ 2026-08-31 (实际文件日期: 2026-09-10导出)')
print(f'原始总行数: 67027 | 去重后: {len(data)} | 筛选后: {len(candidates)}')

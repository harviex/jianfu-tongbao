#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
去重 whitelist.yaml - 移除重复的 pattern 定义
"""

import yaml

with open('/home/c1/jianfu-tongbao/config/whitelist.yaml', 'r', encoding='utf-8') as f:
    data = yaml.safe_load(f)

# Deduplicate patterns by (pattern, category)
seen = set()
unique_patterns = []
for p in data['patterns']:
    key = (p['pattern'], p['category'])
    if key not in seen:
        seen.add(key)
        unique_patterns.append(p)
    else:
        print(f"Removed duplicate: {p['category']}")

data['patterns'] = unique_patterns
data['updated_at'] = '2026-08-07'

with open('/home/c1/jianfu-tongbao/config/whitelist.yaml', 'w', encoding='utf-8') as f:
    yaml.dump(data, f, allow_unicode=True, sort_keys=False, indent=2)

print(f"✅ 去重完成: {len(unique_patterns)} 个唯一模式 (原 {len(data['patterns']) + len([1 for _ in data['patterns'] if False])})")
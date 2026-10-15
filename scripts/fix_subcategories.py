#!/usr/bin/env python3
"""
将 clues 表中已入库的非标准 subcategory 映射到 standards.json 的 46 个标准细分类。
使用关键词匹配 + 语义规则，必要时回退到 LLM 判读（但本脚本只做规则匹配）。
"""

import json
import re
from collections import defaultdict

import psycopg2
from psycopg2.extras import RealDictCursor


def load_standards():
    with open('/home/c1/jianfu-tongbao/data/standards.json', 'r', encoding='utf-8') as f:
        return json.load(f)


def build_keyword_index(standards):
    """为每个标准细分类提取关键词，构建反向索引"""
    index = []
    for s in standards:
        # 从 keywords 字段提取关键词（按、/、分割）
        kw_text = s.get('keywords', '')
        # 分割关键词：中文顿号、逗号、斜杠、空格
        keywords = re.split(r'[、,，/／\s]+', kw_text)
        keywords = [k.strip() for k in keywords if k.strip() and len(k.strip()) > 1]
        
        index.append({
            'category': s['category'],
            'subcategory': s['subcategory'],
            'keywords': keywords,
            'seq': s['seq']
        })
    return index


def match_subcategory(text, keyword_index, min_matches=1):
    """
    根据文本内容匹配最合适的标准细分类
    返回: (category, subcategory) 或 (None, None)
    """
    text_lower = text.lower()
    best_match = None
    best_score = 0
    
    for item in keyword_index:
        score = 0
        matched_kws = []
        for kw in item['keywords']:
            if kw in text_lower:
                score += 1
                matched_kws.append(kw)
        
        if score > best_score:
            best_score = score
            best_match = item
    
    if best_match and best_score >= min_matches:
        return best_match['category'], best_match['subcategory']
    return None, None


def build_mapping_rules():
    """基于当前 subcategory 名称的规则映射（作为关键词匹配的补充）"""
    return {
        # 当前subcategory -> (标准category, 标准subcategory)
        '层层加码/一刀切': ('权责不清/甩锅', '清单外事项下放/签责任状转嫁/属地管理甩锅'),
        '指尖形式主义': ('指尖形式主义', '强制打卡/积分排名/在线时长/上传照片视频轨迹'),
        '评比创建证明借调': ('创建示范/达标', '种类数量过多/未批准/运动式/作秀式/一阵风'),
        '台账留痕迎检': ('数据造假', '虚假整改/迎检突击/边改边犯/不惩反奖'),
        '台账/留痕/数据造假': ('数据造假', '虚假整改/迎检突击/边改边犯/不惩反奖'),
        '评比创建/证明/借调': ('创建示范/达标', '种类数量过多/未批准/运动式/作秀式/一阵风'),
        '会议文件泛滥/层层陪会': ('精简会议', '会议数量过多/层层召开/文山会海/年底扎堆/未批准直达基层'),
        '过度管控/盲目决策': ('盲目决策/形象工程', '不顾实际上项目/盲目举债/挖山造田/有轨电车/农旅烂尾/违规占地'),
        '层层陪会': ('精简会议', '规模规格失控/层层陪会/层级不合理/要求主要负责同志参会'),
        '平台转办=原单位自我结论': ('权责不清/甩锅', '清单外事项下放/签责任状转嫁/属地管理甩锅'),
        '工单流转问题': ('权责不清/甩锅', '清单外事项下放/签责任状转嫁/属地管理甩锅'),
        '形式主义': ('数据造假', '虚假整改/迎检突击/边改边犯/不惩反奖'),
        '审批单位违规干预': ('盲目决策/形象工程', '违规评比/论坛/节庆/规避审批/以会代收'),
    }


def main():
    # 连接数据库
    conn = psycopg2.connect(
        host='localhost', port=5432, database='tongbao',
        user='tongbao_user', password='tongbao_2026_secure',
        cursor_factory=RealDictCursor
    )
    
    # 加载标准
    standards = load_standards()
    keyword_index = build_keyword_index(standards)
    mapping_rules = build_mapping_rules()
    
    # 查询需修正的线索（6月+8月）
    with conn.cursor() as cur:
        cur.execute('''
            SELECT appeal_id, subcategory, category, title, content, 
                   qualitative_analysis, llm_reason, tags
            FROM clues
            WHERE DATE(publish_time) BETWEEN '2026-06-01' AND '2026-06-30'
               OR DATE(publish_time) BETWEEN '2026-08-01' AND '2026-08-31'
            ORDER BY publish_time
        ''')
        clues = cur.fetchall()
    
    print(f"待修正线索: {len(clues)} 条")
    
    # 统计
    stats = defaultdict(int)
    updated = 0
    
    for clue in clues:
        appeal_id = clue['appeal_id']
        old_subcat = clue['subcategory']
        old_cat = clue['category']
        
        # 组合文本用于关键词匹配
        combined_text = ' '.join(filter(None, [
            clue['title'] or '',
            clue['content'] or '',
            clue['qualitative_analysis'] or '',
            clue['llm_reason'] or '',
            ' '.join(clue['tags']) if clue['tags'] else ''
        ]))
        
        # 1. 先尝试规则映射
        new_cat, new_subcat = mapping_rules.get(old_subcat, (None, None))
        match_method = 'rule'
        
        # 2. 规则没有则用关键词匹配
        if not new_cat:
            new_cat, new_subcat = match_subcategory(combined_text, keyword_index, min_matches=1)
            match_method = 'keyword'
        
        # 3. 还没有则用原 category 推断（最后兜底）
        if not new_cat:
            # 保持原 category，找该 category 下第一个启用的 subcategory
            for s in standards:
                if s['category'] == old_cat and s.get('enabled', True):
                    new_cat = s['category']
                    new_subcat = s['subcategory']
                    match_method = 'fallback_cat'
                    break
        
        # 4. 实在没有则用第一个标准
        if not new_cat:
            new_cat = standards[0]['category']
            new_subcat = standards[0]['subcategory']
            match_method = 'fallback_first'
        
        # 更新数据库
        with conn.cursor() as cur:
            cur.execute('''
                UPDATE clues 
                SET category = %s, subcategory = %s
                WHERE appeal_id = %s
            ''', (new_cat, new_subcat, appeal_id))
        
        stats[f'{old_cat} -> {new_cat} | {old_subcat} -> {new_subcat} ({match_method})'] += 1
        updated += 1
    
    conn.commit()
    conn.close()
    
    print(f"\n已更新: {updated} 条")
    print("\n映射统计:")
    for k, v in sorted(stats.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")


if __name__ == '__main__':
    main()
#!/usr/bin/env python3
"""
rejudge.py — 重判指定日期范围的线索
用新 prompt 重新判读，对比新旧结果，更新 DB。

用法:
  python scripts/rejudge.py --start 2026-06-01 --end 2026-08-10
"""
import os
import sys
import json
import time
import argparse
import re
from datetime import datetime, date
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor
import httpx

# 配置
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://192.168.123.33:11434")
OLLAMA_MODEL = "qooba/qwen3-coder-30b-a3b-instruct:q3_k_m"
NUM_PREDICT = 1024
CONCURRENCY = 1

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", 5432)),
    "database": os.environ.get("DB_NAME", "tongbao"),
    "user": os.environ.get("DB_USER", "tongbao_user"),
    "password": os.environ.get("DB_PASS", "tongbao_2026_secure"),
}

# 加载 standards
def load_standards():
    """加载 46 类标准白名单"""
    std_path = Path(__file__).parent.parent / "config" / "standards.json"
    if not std_path.exists():
        print(f"ERROR: {std_path} not found")
        sys.exit(1)
    with open(std_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    whitelist = {}
    prompt_lines = []
    for cat in data.get("categories", []):
        for sub in cat.get("subcategories", []):
            name = sub["name"]
            keywords = sub.get("keywords", "")
            whitelist[name] = {"category": cat["name"], "keywords": keywords}
            prompt_lines.append(f"  - {name}（大类：{cat['name']} | 关键词：{keywords}）")
    
    return whitelist, "\n".join(prompt_lines)

STANDARDS_WHITELIST, STANDARDS_PROMPT_TEXT = load_standards()

def build_prompt(batch):
    """构建判读 prompt（新版，反模板套话）"""
    items = []
    for i, item in enumerate(batch):
        text = f"标题: {item['title']}\n内容: {item['content']}"
        if item.get('category_l3'):
            text += f"\n三级分类: {item['category_l3']}"
        items.append(f"=== 条目 {i+1} (ID: {item['appeal_id']}) ===\n{text}")
    
    names = []
    for l in STANDARDS_PROMPT_TEXT.splitlines():
        l = l.strip()
        if not l.startswith('- '):
            continue
        name = l[2:].split('（大类')[0].split(' | 关键词')[0].strip()
        names.append(name)
    short_standards = "、".join(names)
    
    return f"""<think:6124c78e>
</think:6124c78e>你是"形式主义为基层减负"专项线索识别专家。请逐条判读以下 {len(batch)} 条 12345 诉求。

## 任务
对每条诉求，判断其是否属于"形式主义为基层增加负担"的线索。

## 判断方法
不要先入为主地寻找"上级摊派"的证据。先真正理解诉求说了什么：
1. 这个人遇到了什么问题？
2. 这个问题是谁造成的？为什么要这么做？
3. 第2步的原因，是否属于"对上负责的形式要求"？

仅当问题根源是"为应付上级制定的检查/考核/指标/创建/迎检等要求"时才判相关。
正常工作量、服务供给不足、个人违规、纯业务纠纷不属此列。

## 【subcategory 必须从以下 46 个标准细分类中选择，严禁自造】
{short_standards}

## 明确排除（NOT 相关，判 false）
- 正常工作安排：创城常态化保洁、网格员日常巡查、社区常规值班——除非有"为应付特定检查"的硬性摊派证据
- 家校责任边界：学校让家长带教具/填档案/志愿服务
- 机关效能/服务态度：推诿扯皮、态度差、办事慢、流程繁（除非明确为迎检而弄虚作假）
- 劳动/工资/社保纠纷、物业/邻里/消费维权、医疗/交通/环境投诉、政策咨询
- 会议占用休息时间：普通校会/业务会不算

施压方不限党政机关：高校、行业协会、学校、医院、国企、事业单位均计。
受压方不限基层干部：村居社区、一线窗口、网格员、辅警、临时工均计。

## ⚠️ 反模板套话约束（违反则输出无效）
以下属于模型套话，禁止在 llm_reason / qualitative_analysis / root_cause 中出现：
- "为了应付上级检查/考核/指标而增加一线无谓负担"
- "反映了为了应付上级检查/考核/指标而增加"
- "属于为了应付上级检查"
- 其他把"上级检查/考核/指标"当作万金油的表述

**正确做法**：引用诉求原文的具体表述，说清楚这条诉求中**哪个具体行为**、**来自哪个具体部门/文件**、**为什么属于形式主义**。
如果诉求本身没有明确证据证明是上级摊派驱动，直接判 false——不要强行套模板。

## 边界裁决
- 有具体证据（文件名称、会议通知、考核通报、部门发文等）→ 纳入
- 仅有"基层忙/加班/负担重"但无上级驱动证据 → 排除
- 拿不准时，判 false（宁漏勿宽）

输出格式（严格 JSON 数组，每个对象对应一条）：
[
  {{
    "appeal_id": "ID",
    "is_relevant": true/false,
    "category": "对应的大类",
    "subcategory": "必须从上述 46 个标准细分类中精确选择，原文复制；不相关则填'无'",
    "root_cause": "核心根因（必须引用诉求原文具体表述，禁止模板套话）",
    "confidence": 0.0-1.0,
    "tags": ["标签1", "标签2"],
    "qualitative_analysis": "定性分析：引用诉求原文关键句，指出具体因果链条，不要泛泛而谈",
    "evidence_suggestion": "取证建议：如需核实，建议调取什么材料/找谁谈话/查什么系统",
    "llm_reason": "判读理由：用诉求原文具体表述佐证你的判断，禁止模板套话"
  }},
  ...
]

待判读条目：
{chr(10).join(items)}"""

def parse_response(response: str) -> list:
    """解析 LLM 返回的 JSON"""
    cleaned = response.strip()
    if cleaned.startswith('```'):
        lines = cleaned.split('\n')
        if lines[0].startswith('```'):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith('```'):
            lines = lines[:-1]
        cleaned = '\n'.join(lines).strip()
    
    if not cleaned.startswith('[') and not cleaned.startswith('{'):
        for marker in ('[', '{'):
            idx = cleaned.find(marker)
            if idx > 0:
                cleaned = cleaned[idx:].strip()
                if cleaned.endswith('```'):
                    cleaned = cleaned[:-3].strip()
                break
    
    try:
        data = json.loads(cleaned)
        if not isinstance(data, list):
            data = [data]
        return data
    except json.JSONDecodeError:
        print(f"  JSON parse error: {response[:200]}")
        return []

def call_ollama(prompt: str) -> str:
    """调用 Ollama API"""
    try:
        with httpx.Client(timeout=300.0) as client:
            resp = client.post(
                f"{OLLAMA_HOST}/api/chat",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "format": "json",
                    "options": {
                        "temperature": 0.1,
                        "num_predict": NUM_PREDICT,
                    }
                }
            )
            resp.raise_for_status()
            return resp.json()["message"]["content"]
    except Exception as e:
        print(f"  Ollama error: {e}")
        return ""

def get_old_clues(start_date: str, end_date: str) -> list:
    """获取旧判读结果"""
    conn = psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)
    cur = conn.cursor()
    cur.execute("""
        SELECT appeal_id, title, content, category, subcategory, 
               confidence, llm_reason, is_relevant
        FROM clues
        WHERE publish_time >= %s AND publish_time < %s::date + interval '1 day'
        ORDER BY publish_time DESC
    """, (start_date, end_date))
    clues = cur.fetchall()
    conn.close()
    return clues

def get_raw_data(appeal_ids: list) -> dict:
    """从 raw_appeals 获取原始数据"""
    conn = psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)
    cur = conn.cursor()
    # 需要查所有分区，用 UNION ALL 太麻烦，直接用主表查
    cur.execute("""
        SELECT appeal_id, title, content, category_l3
        FROM raw_appeals
        WHERE appeal_id = ANY(%s)
    """, (appeal_ids,))
    rows = {r['appeal_id']: r for r in cur.fetchall()}
    conn.close()
    return rows

def update_db(results: list, start_date: str, end_date: str):
    """更新 DB：删除旧记录，插入新记录"""
    conn = psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)
    cur = conn.cursor()
    
    # 删除旧记录
    cur.execute("""
        DELETE FROM clues 
        WHERE publish_time >= %s AND publish_time < %s::date + interval '1 day'
    """, (start_date, end_date))
    deleted = cur.rowcount
    
    # 插入新记录
    inserted = 0
    for r in results:
        if not r.get('is_relevant'):
            continue
        
        subcat = r.get('subcategory', '无')
        subcat_is_valid = subcat and subcat != '无' and subcat in STANDARDS_WHITELIST
        is_rel = bool(r.get('is_relevant', False)) or subcat_is_valid
        
        if not is_rel:
            continue
        
        category = STANDARDS_WHITELIST.get(subcat, {}).get('category', '') if subcat_is_valid else (r.get('category') or '')
        
        cur.execute("""
            INSERT INTO clues (appeal_id, title, content, publish_time, region_city, 
                             is_relevant, category, subcategory, root_cause, confidence,
                             tags, qualitative_analysis, evidence_suggestion, llm_reason, llm_model)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (appeal_id) DO UPDATE SET
                is_relevant = EXCLUDED.is_relevant,
                category = EXCLUDED.category,
                subcategory = EXCLUDED.subcategory,
                root_cause = EXCLUDED.root_cause,
                confidence = EXCLUDED.confidence,
                tags = EXCLUDED.tags,
                qualitative_analysis = EXCLUDED.qualitative_analysis,
                evidence_suggestion = EXCLUDED.evidence_suggestion,
                llm_reason = EXCLUDED.llm_reason,
                llm_model = EXCLUDED.llm_model,
                updated_at = NOW()
        """, (
            r['appeal_id'],
            r.get('title', ''),
            r.get('content', ''),
            r.get('publish_time'),
            r.get('region_city'),
            is_rel,
            category,
            subcat,
            r.get('root_cause', ''),
            float(r.get('confidence', 0)),
            r.get('tags', []),
            r.get('qualitative_analysis', ''),
            r.get('evidence_suggestion', ''),
            r.get('llm_reason', ''),
            OLLAMA_MODEL[:32],
        ))
        inserted += 1
    
    conn.commit()
    conn.close()
    return deleted, inserted

def main():
    parser = argparse.ArgumentParser(description="重判线索")
    parser.add_argument("--start", required=True, help="起始日期 YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="结束日期 YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true", help="只报告不更新 DB")
    args = parser.parse_args()
    
    print(f"重判范围: {args.start} 到 {args.end}")
    print(f"模型: {OLLAMA_MODEL}")
    print()
    
    # 1. 获取旧线索
    old_clues = get_old_clues(args.start, args.end)
    print(f"旧线索数: {len(old_clues)}")
    
    if not old_clues:
        print("无旧线索，退出")
        return
    
    # 2. 获取原始数据
    appeal_ids = [c['appeal_id'] for c in old_clues]
    raw_data = get_raw_data(appeal_ids)
    print(f"原始数据匹配: {len(raw_data)}/{len(appeal_ids)}")
    
    # 3. 逐条重判
    results = []
    changed = []
    errors = 0
    
    for i, clue in enumerate(old_clues):
        aid = clue['appeal_id']
        raw = raw_data.get(aid, {})
        
        batch = [{
            'appeal_id': aid,
            'title': raw.get('title', clue.get('title', '')),
            'content': raw.get('content', clue.get('content', '')),
            'category_l3': raw.get('category_l3', ''),
        }]
        
        prompt = build_prompt(batch)
        response = call_ollama(prompt)
        
        if not response:
            errors += 1
            continue
        
        parsed = parse_response(response)
        if not parsed:
            errors += 1
            continue
        
        new_result = parsed[0]
        new_result['appeal_id'] = aid
        new_result['title'] = raw.get('title', '')
        new_result['content'] = raw.get('content', '')
        new_result['publish_time'] = clue.get('publish_time')
        new_result['region_city'] = clue.get('region_city')
        
        results.append(new_result)
        
        # 对比
        old_rel = clue.get('is_relevant', False)
        new_rel = new_result.get('is_relevant', False)
        
        if old_rel != new_rel:
            changed.append({
                'appeal_id': aid,
                'old': old_rel,
                'new': new_rel,
                'old_subcat': clue.get('subcategory'),
                'new_subcat': new_result.get('subcategory'),
            })
        
        # 进度
        if (i + 1) % 10 == 0:
            print(f"  进度: {i+1}/{len(old_clues)} (变更: {len(changed)}, 错误: {errors})")
    
    print(f"\n重判完成:")
    print(f"  总计: {len(results)}")
    print(f"  变更: {len(changed)}")
    print(f"  错误: {errors}")
    
    if changed:
        print(f"\n变更详情:")
        for c in changed:
            print(f"  {c['appeal_id'][:16]}: {c['old']} -> {c['new']} | {c['old_subcat']} -> {c['new_subcat']}")
    
    # 4. 更新 DB
    if not args.dry_run:
        deleted, inserted = update_db(results, args.start, args.end)
        print(f"\nDB 更新: 删除 {deleted}, 插入 {inserted}")
    else:
        print("\n[dry-run] 未更新 DB")

if __name__ == "__main__":
    main()

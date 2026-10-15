#!/usr/bin/env python3
"""
LLM 线索判定：读取黑白灰名单筛选结果，调用 Ollama 进行46类精确匹配分类
输出：clues_output.json（可直接导入线索库）
"""

import json
import asyncio
import aiohttp
import time
import re
from datetime import datetime

# ============ 配置 ============
OLLAMA_URL = "http://192.168.123.33:11434"
MODEL = "qooba/qwen3-coder-30b-a3b-instruct:q3_k_m"
CONCURRENT = 15  # 并发数
NUM_PREDICT = 1024
TIMEOUT = 120  # 单条超时秒

# ============ 加载46类标准 ============
with open('/home/c1/jianfu-tongbao/data/updated_standards.json', 'r') as f:
    standards = json.load(f)

# 构建 short_standards（仅类名列表，节省 ctx）
short_standards = []
for s in standards:
    short_standards.append(f"{s['seq']}.{s['category']}-{s['subcategory']}")

standards_text = "\n".join(short_standards)

# ============ 加载待分析数据 ============
with open('/tmp/jianfu_candidates.json', 'r') as f:
    candidates = json.load(f)

print(f"待分析: {len(candidates)} 条")
print(f"并发数: {CONCURRENT}")

# ============ 构造 prompt ============
def build_prompt(item):
    return f"""<think:6124c78e>
</think:6124c78e>

你是一个基层减负线索研判专家。请分析以下12345诉求，判断是否为整治形式主义为基层减负相关线索。

## 46类分类标准（必须精确匹配以下类名）：
{standards_text}

## 诉求信息：
- 诉求编号：{item.get('task_num','')}
- 诉求标题：{item.get('title','')}
- 诉求内容：{item.get('content','')[:1500]}
- 登记时间：{item.get('publish_time','')}
- 被诉单位：{item.get('complained_unit','')}
- 区域：{item.get('city','')} {item.get('region','')}
- 初步筛选：{item.get('filter_result','')}

## 判定规则：
1. 核心逻辑：诉求反映的基层负担，其直接动因是"上级为检查/考核/指标/创建/迎检"向下摊派
2. 正常工作量、家校协同、服务态度问题（非为迎检）、劳资纠纷等不算
3. 拿不准时判 false（宁漏勿宽）

## 输出JSON（不要其他内容）：
{{"is_relevant":true/false,"confidence":0.0-1.0,"subcategory":"从46类中选一个精确类名或填'无'","evidence_suggestion":"一句话取证建议","root_cause":"政绩观偏差/制度缺失/监管缺位/考核异化/技术手段滥用/其他","is_typical":true/false,"tags":["标签1","标签2"]}}"""

# ============ 异步调用 Ollama ============
async def call_ollama(session, prompt, semaphore):
    async with semaphore:
        try:
            async with session.post(
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model": MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {"num_predict": NUM_PREDICT}
                },
                timeout=aiohttp.ClientTimeout(total=TIMEOUT)
            ) as resp:
                data = await resp.json()
                return data.get('message', {}).get('content', '')
        except Exception as e:
            return f"ERROR:{e}"

# ============ 解析 LLM 输出 ============
def parse_llm_output(text, item):
    """解析 LLM 输出为结构化数据"""
    result = {
        'task_num': item.get('task_num', ''),
        'title': item.get('title', ''),
        'content': item.get('content', ''),
        'publish_time': item.get('publish_time', ''),
        'complained_unit': item.get('complained_unit', ''),
        'city': item.get('city', ''),
        'region': item.get('region', ''),
        'filter_result': item.get('filter_result', ''),
        'is_relevant': False,
        'confidence': 0.0,
        'subcategory': '无',
        'evidence_suggestion': '',
        'root_cause': '',
        'is_typical': False,
        'tags': [],
        'raw_output': ''
    }
    
    if not text or text.startswith('ERROR:'):
        result['raw_output'] = text
        return result
    
    # 尝试提取 JSON
    # 方法1：直接匹配花括号
    json_match = re.search(r'\{[^{}]*"is_relevant"[^{}]*\}', text, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads(json_match.group())
            result['is_relevant'] = parsed.get('is_relevant', False)
            result['confidence'] = float(parsed.get('confidence', 0))
            result['subcategory'] = parsed.get('subcategory', '无')
            result['evidence_suggestion'] = parsed.get('evidence_suggestion', '')
            result['root_cause'] = parsed.get('root_cause', '')
            result['is_typical'] = parsed.get('is_typical', False)
            result['tags'] = parsed.get('tags', [])
            result['raw_output'] = text[:200]
            return result
        except json.JSONDecodeError:
            pass
    
    # 方法2：宽松匹配
    try:
        # 找到第一个 { 和最后一个 }
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1 and end > start:
            parsed = json.loads(text[start:end+1])
            result['is_relevant'] = parsed.get('is_relevant', False)
            result['confidence'] = float(parsed.get('confidence', 0))
            result['subcategory'] = parsed.get('subcategory', '无')
            result['evidence_suggestion'] = parsed.get('evidence_suggestion', '')
            result['root_cause'] = parsed.get('root_cause', '')
            result['is_typical'] = parsed.get('is_typical', False)
            result['tags'] = parsed.get('tags', [])
            result['raw_output'] = text[:200]
            return result
    except:
        pass
    
    result['raw_output'] = text[:500]
    return result

# ============ 主流程 ============
async def main():
    semaphore = asyncio.Semaphore(CONCURRENT)
    results = []
    
    start_time = time.time()
    
    async with aiohttp.ClientSession() as session:
        tasks = []
        for item in candidates:
            prompt = build_prompt(item)
            task = call_ollama(session, prompt, semaphore)
            tasks.append((item, task))
        
        # 执行所有任务
        for i, (item, task) in enumerate(tasks):
            output = await task
            parsed = parse_llm_output(output, item)
            results.append(parsed)
        
            # 每50条输出进度
            if (i + 1) % 50 == 0:
                elapsed = time.time() - start_time
                rate = (i + 1) / elapsed
                remaining = (len(tasks) - i - 1) / rate if rate > 0 else 0
                print(f"进度: {i+1}/{len(tasks)} ({rate:.1f}条/秒, 预计还需{remaining/60:.1f}分)")
    
    # 统计
    relevant_count = sum(1 for r in results if r['is_relevant'])
    error_count = sum(1 for r in results if r['raw_output'].startswith('ERROR:'))
    parse_fail = sum(1 for r in results if not r['is_relevant'] and not r['raw_output'].startswith('ERROR:') and r['confidence'] == 0 and r['raw_output'] != '')
    
    print(f"\n=== 处理完成 ===")
    print(f"总数: {len(results)}")
    print(f"相关线索: {relevant_count}")
    print(f"不相关: {len(results) - relevant_count - error_count}")
    print(f"请求失败: {error_count}")
    print(f"解析失败: {parse_fail}")
    print(f"总耗时: {time.time() - start_time:.1f}秒")
    
    # 保存结果
    output_path = '/tmp/jianfu_clues_result.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"结果已保存到: {output_path}")
    
    # 保存相关线索（供导入线索库）
    clues_relevant = [r for r in results if r['is_relevant']]
    clues_path = '/tmp/jianfu_clues_relevant.json'
    with open(clues_path, 'w', encoding='utf-8') as f:
        json.dump(clues_relevant, f, ensure_ascii=False, indent=2)
    print(f"相关线索保存到: {clues_path} ({len(clues_relevant)} 条)")

if __name__ == '__main__':
    asyncio.run(main())

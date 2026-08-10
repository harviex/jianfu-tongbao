#!/usr/bin/env python3
"""
每日诉求处理主流程
- 读取 Excel → 入库 raw_appeals
- 黑白名单路由 → daily_candidates
- LLM 判读 → clues 表
- 导出静态页数据
"""

import os
import sys
import re
import yaml
import json
import asyncio
import logging
import argparse
from datetime import datetime, date
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

# ==================== 配置 ====================

@dataclass
class DBConfig:
    host: str = "localhost"
    port: int = 5432
    database: str = "tongbao"
    user: str = "tongbao_user"
    password: str = "tongbao_2026_secure"

@dataclass
class OllamaConfig:
    base_url: str = "http://192.168.123.33:11434"
    model: str = "qwen2.5vl:7b"
    concurrency: int = 2  # 并发2，16GB显存支持
    batch_size: int = 3   # 减小批次
    timeout: int = 300    # 增加到 5 分钟

@dataclass
class PathConfig:
    project_root: Path = Path("/home/c1/jianfu-tongbao")
    inbox_dir: Path = Path("/home/c1/jianfu-tongbao/data/inbox")
    static_dir: Path = Path("/home/c1/jianfu-tongbao/data/static")
    config_dir: Path = Path("/home/c1/jianfu-tongbao/config")
    logs_dir: Path = Path("/home/c1/jianfu-tongbao/logs")

DB = DBConfig()
OLLAMA = OllamaConfig()
PATHS = PathConfig()

# 确保目录存在
for p in [PATHS.inbox_dir, PATHS.static_dir, PATHS.logs_dir]:
    p.mkdir(parents=True, exist_ok=True)

# ==================== 标准库（46 个标准细分类） ====================
def load_standards():
    """加载 standards.json，返回标准细分类白名单和 prompt 用文本"""
    standards_path = PATHS.config_dir / 'standards.json'
    if not standards_path.exists():
        # 回退到 data/standards.json
        standards_path = Path("/home/c1/jianfu-tongbao/data/standards.json")
    with open(standards_path, 'r', encoding='utf-8') as f:
        standards = json.load(f)
    
    # 只保留 enabled 的
    standards = [s for s in standards if s.get('enabled', True)]
    
    # 白名单：subcategory -> (category, keywords)
    whitelist = {}
    prompt_lines = []
    for s in standards:
        subcat = s['subcategory']
        whitelist[subcat] = {
            'category': s['category'],
            'keywords': s['keywords'],
            'caseLink': s.get('caseLink', '')
        }
        prompt_lines.append(f"  - {subcat}（大类：{s['category']} | 关键词：{s['keywords']}）")
    
    prompt_text = "\n".join(prompt_lines)
    return whitelist, prompt_text

# 全局加载一次
STANDARDS_WHITELIST, STANDARDS_PROMPT_TEXT = load_standards()

# ==================== 日志 ====================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(PATHS.logs_dir / f"process_{date.today().isoformat()}.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ==================== 数据结构 ====================

@dataclass
class RouteResult:
    appeal_id: str
    route: str          # 'full', 'sample', 'skip', 'excluded'
    priority: str       # 'HIGH', 'LOW', 'NONE'
    matched_keywords: List[str]
    matched_blacklist: List[str]

@dataclass
class LLMResult:
    appeal_id: str
    is_relevant: bool
    category: str
    subcategory: str
    root_cause: str
    confidence: float
    tags: List[str]
    qualitative_analysis: str
    evidence_suggestion: str
    llm_reason: str

# ==================== 工具函数 ====================

def load_yaml(path: Path) -> dict:
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def get_db_conn():
    return psycopg2.connect(
        host=DB.host, port=DB.port, database=DB.database,
        user=DB.user, password=DB.password, cursor_factory=RealDictCursor
    )

def ensure_partition(conn, process_date: date):
    """确保当天的分区表存在"""
    partition_name = f"raw_appeals_{process_date.strftime('%Y%m%d')}"
    start_date = process_date
    end_date = date.fromordinal(process_date.toordinal() + 1)
    
    with conn.cursor() as cur:
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {partition_name} PARTITION OF raw_appeals
            FOR VALUES FROM ('{start_date}') TO ('{end_date}');
        """)
    conn.commit()

def compile_patterns(patterns: List[dict], fields: List[str]) -> List[Tuple[re.Pattern, str, float, List[str]]]:
    """编译正则模式，返回 (compiled_regex, category, weight, fields)"""
    compiled = []
    for p in patterns:
        try:
            regex = re.compile(p['pattern'], re.IGNORECASE)
            compiled.append((
                regex,
                p.get('category', 'unknown'),
                p.get('weight', 1.0),
                p.get('fields', ['title', 'content'])
            ))
        except re.error as e:
            logger.warning(f"正则编译失败: {p['pattern']} - {e}")
    return compiled

# ==================== 核心处理类 ====================

class DailyProcessor:
    def __init__(self, process_date: date):
        self.process_date = process_date
        self.date_str = process_date.strftime('%Y%m%d')
        
        # 加载配置
        self.blacklist = compile_patterns(
            load_yaml(PATHS.config_dir / 'blacklist.yaml')['patterns'],
            ['title', 'content', 'category_l1', 'category_l2', 'category_l3']
        )
        self.whitelist = compile_patterns(
            load_yaml(PATHS.config_dir / 'whitelist.yaml')['patterns'],
            ['title', 'content', 'category_l1', 'category_l2', 'category_l3']
        )
        self.greylist = compile_patterns(
            load_yaml(PATHS.config_dir / 'greylist.yaml')['patterns'],
            ['title', 'content']
        )
        
        self.conn = get_db_conn()
        ensure_partition(self.conn, process_date)
        
        # 统计
        self.stats = {
            'total_raw': 0,
            'blacklist_excluded': 0,
            'candidate_total': 0,
            'candidate_high': 0,
            'candidate_low': 0,
            'candidate_none': 0,
            'llm_called': 0,
            'relevant_found': 0,
            'high_confidence': 0,
            'zero_keyword_sampled': 0,
            'zero_keyword_relevant': 0,
        }

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.close()

    # ----- 1. 导入原始数据 -----
    def import_raw_data(self) -> pd.DataFrame:
        """读取 inbox 目录下的 Excel 文件，入库 raw_appeals"""
        inbox_date_dir = PATHS.inbox_dir / self.process_date.strftime('%Y-%m-%d')
        if not inbox_date_dir.exists():
            raise FileNotFoundError(f"未找到数据目录: {inbox_date_dir}")
        
        all_dfs = []
        for f in sorted(inbox_date_dir.glob('*.xlsx')):
            logger.info(f"读取文件: {f.name}")
            # 尝试读取：新格式(直接header)或旧格式(第0行标题，第1行header)
            df = pd.read_excel(f, header=None, nrows=2)
            if df.iloc[0, 0] == '诉求查询明细结果':
                # 旧格式：第0行是标题，第1行是表头
                df = pd.read_excel(f, header=None, skiprows=1)
                df.columns = df.iloc[0]
                df = df.iloc[1:].reset_index(drop=True)
            else:
                # 新格式：第0行就是表头
                df = pd.read_excel(f, header=0)
            all_dfs.append(df)
        
        if not all_dfs:
            raise ValueError("没有读取到任何数据")
        
        full_df = pd.concat(all_dfs, ignore_index=True)
        self.stats['total_raw'] = len(full_df)
        logger.info(f"共读取 {len(full_df)} 条原始记录")
        
        # 数据清洗和字段映射
        full_df = self._clean_dataframe(full_df)
        
        # 批量 UPSERT 入库
        self._bulk_upsert_raw(full_df)
        
        return full_df

    def _clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """字段映射和清洗"""
        # 重命名为英文字段名
        col_map = {
            '诉求编号': 'appeal_id',
            '诉求来源': 'source',
            '诉求来源小类': 'source_sub',
            '诉求类型': 'appeal_type',
            '事件类型': 'event_type',
            '一级分类名称': 'category_l1',
            '二级分类名称': 'category_l2',
            '三级分类名称': 'category_l3',
            '诉求类别': 'appeal_category',
            '诉求标题': 'title',
            '诉求内容': 'content',
            '诉求性质': 'nature',
            '登记时间': 'register_time',
            '封存时间': 'seal_time',
            '事件状态': 'status',
            '城市名称': 'city',
            '区域名称': 'district',
            '街道名称': 'street',
            '事发区域': 'incident_area',
            '地址描述': 'address',
            '所有办理部门': 'handle_depts',
            '办理描述': 'handle_desc',
            '批转单位': 'transfer_unit',
            '退回部门': 'return_dept',
            '退回原因': 'return_reason',
            '诉求标签': 'tags',
            '事发时间': 'incident_time',
            '答复内容': 'reply_content',
            '评价满意度': 'satisfaction',
            '评价内容': 'evaluation',
            '部门办理截止时间': 'dept_deadline',
            '扬言件类型': 'rumor_type',
            '办理结束时间': 'handle_end_time',
        }
        df = df.rename(columns=col_map)
        
        # 处理时间字段
        for col in ['register_time', 'seal_time', 'incident_time', 'dept_deadline', 'handle_end_time']:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
                # 将 NaT 转为 None (PostgreSQL NULL)
                df[col] = df[col].where(pd.notnull(df[col]), None)
        
        # 合并全文本
        df['full_text'] = (df['title'].fillna('') + ' ' + df['content'].fillna('')).str.strip()
        
        # 处理 NaN
        for col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].fillna('')
        
        return df

    def _bulk_upsert_raw(self, df: pd.DataFrame):
        """批量 UPSERT 入 raw_appeals"""
        cols = [
            'appeal_id', 'source', 'source_sub', 'appeal_type', 'event_type',
            'category_l1', 'category_l2', 'category_l3', 'appeal_category',
            'title', 'content', 'nature', 'register_time', 'seal_time',
            'status', 'city', 'district', 'street', 'incident_area', 'address',
            'handle_depts', 'handle_desc', 'transfer_unit', 'return_dept',
            'return_reason', 'tags', 'incident_time', 'reply_content',
            'satisfaction', 'evaluation', 'dept_deadline', 'rumor_type',
            'handle_end_time', 'full_text'
        ]
        
        records = []
        for _, row in df.iterrows():
            rec = []
            for c in cols:
                val = row.get(c)
                # 处理时间字段：NaT -> None
                if c in ['register_time', 'seal_time', 'incident_time', 'dept_deadline', 'handle_end_time']:
                    if pd.isna(val):
                        rec.append(None)
                    else:
                        rec.append(val)
                else:
                    # 字符串字段：NaN/None -> 空字符串
                    if pd.isna(val):
                        rec.append('')
                    else:
                        rec.append(str(val))
            records.append(tuple(rec))

        with self.conn.cursor() as cur:
            execute_values(cur, f"""
                INSERT INTO raw_appeals ({', '.join(cols)})
                VALUES %s
                ON CONFLICT (appeal_id, register_time) DO UPDATE SET
                    {', '.join([f'{c}=EXCLUDED.{c}' for c in cols if c not in ['appeal_id', 'register_time']])}
            """, records, page_size=1000)
        self.conn.commit()
        logger.info(f"入库完成: {len(records)} 条")

    # ----- 2. 黑白名单路由 -----
    def apply_routing(self) -> List[RouteResult]:
        """对 raw_appeals 应用黑白名单，生成 daily_candidates"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT appeal_id, title, content, category_l1, category_l2, category_l3
                FROM raw_appeals
                WHERE register_time >= %s AND register_time < %s
            """, (self.process_date, date.fromordinal(self.process_date.toordinal() + 1)))
            rows = cur.fetchall()
        
        results = []
        for row in rows:
            result = self._route_single(row)
            results.append(result)
        
        # 批量入库 daily_candidates
        self._bulk_upsert_candidates(results)
        
        # 统计
        self.stats['blacklist_excluded'] = sum(1 for r in results if r.route == 'excluded')
        self.stats['candidate_total'] = sum(1 for r in results if r.route != 'excluded')
        self.stats['candidate_high'] = sum(1 for r in results if r.priority == 'HIGH')
        self.stats['candidate_low'] = sum(1 for r in results if r.priority == 'LOW')
        self.stats['candidate_none'] = sum(1 for r in results if r.priority == 'NONE')
        
        logger.info(f"路由完成: excluded={self.stats['blacklist_excluded']}, "
                    f"HIGH={self.stats['candidate_high']}, LOW={self.stats['candidate_low']}, "
                    f"NONE={self.stats['candidate_none']}")
        
        return results

    def _route_single(self, row: dict) -> RouteResult:
        appeal_id = row['appeal_id']
        title = row.get('title', '') or ''
        content = row.get('content', '') or ''
        cat_l1 = row.get('category_l1', '') or ''
        cat_l2 = row.get('category_l2', '') or ''
        cat_l3 = row.get('category_l3', '') or ''
        
        field_values = {
            'title': title,
            'content': content,
            'category_l1': cat_l1,
            'category_l2': cat_l2,
            'category_l3': cat_l3,
        }
        
        matched_blacklist = []
        matched_keywords = []
        
        # 1. 黑名单优先
        for regex, category, _, fields in self.blacklist:
            for field in fields:
                val = field_values.get(field, '')
                if regex.search(val):
                    matched_blacklist.append(category)
                    break
            if matched_blacklist:
                break
        
        if matched_blacklist:
            return RouteResult(appeal_id, 'excluded', 'NONE', [], matched_blacklist)
        
        # 2. 白名单（高信号词）
        max_weight = 0
        for regex, category, weight, fields in self.whitelist:
            for field in fields:
                val = field_values.get(field, '')
                if regex.search(val):
                    matched_keywords.append(category)
                    max_weight = max(max_weight, weight)
                    break
        
        if matched_keywords:
            return RouteResult(appeal_id, 'full', 'HIGH', matched_keywords, [])
        
        # 3. 灰度区
        grey_matched = []
        sample_rate = 0.0
        for regex, category, _, fields in self.greylist:
            for field in fields:
                val = field_values.get(field, '')
                if regex.search(val):
                    grey_matched.append(category)
                    sample_rate = max(sample_rate, 0.1)  # 灰度区默认 10%
                    break
        
        if grey_matched:
            import random
            if random.random() < sample_rate:
                return RouteResult(appeal_id, 'sample', 'LOW', grey_matched, [])
            return RouteResult(appeal_id, 'skip', 'NONE', grey_matched, [])
        
        # 4. 无命中：低概率采样兜底
        import random
        if random.random() < 0.05:
            self.stats['zero_keyword_sampled'] += 1
            return RouteResult(appeal_id, 'sample', 'NONE', [], [])
        
        return RouteResult(appeal_id, 'skip', 'NONE', [], [])

    def _bulk_upsert_candidates(self, results: List[RouteResult]):
        with self.conn.cursor() as cur:
            execute_values(cur, """
                INSERT INTO daily_candidates (appeal_id, route, priority, matched_keywords, matched_blacklist, process_date)
                VALUES %s
                ON CONFLICT (appeal_id, process_date) DO UPDATE SET
                    route = EXCLUDED.route,
                    priority = EXCLUDED.priority,
                    matched_keywords = EXCLUDED.matched_keywords,
                    matched_blacklist = EXCLUDED.matched_blacklist
            """, [
                (r.appeal_id, r.route, r.priority, r.matched_keywords, r.matched_blacklist, self.process_date)
                for r in results
            ], page_size=1000)
        self.conn.commit()

    # ----- 3. LLM 判读 -----
    async def run_llm_classification(self):
        """异步并发跑 LLM 判读"""
        # 取需要判读的候选
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT dc.appeal_id, dc.route, dc.priority, dc.matched_keywords,
                       ra.title, ra.content, ra.category_l3, ra.city, ra.district, ra.register_time,
                       ra.handle_depts, ra.reply_content
                FROM daily_candidates dc
                JOIN raw_appeals ra ON ra.appeal_id = dc.appeal_id
                WHERE dc.process_date = %s
                  AND dc.route IN ('full', 'sample')
                  AND NOT EXISTS (SELECT 1 FROM clues c WHERE c.appeal_id = dc.appeal_id)
            """, (self.process_date,))
            candidates = cur.fetchall()
        
        if not candidates:
            logger.info("无需判读的候选")
            return
        
        logger.info(f"开始 LLM 判读: {len(candidates)} 条")
        
        # 分批处理
        semaphore = asyncio.Semaphore(OLLAMA.concurrency)
        
        async def process_batch(batch: List[dict]):
            async with semaphore:
                results = await self._llm_batch_classify(batch)
                for r in results:
                    await self._save_clue(r)
        
        tasks = []
        for i in range(0, len(candidates), OLLAMA.batch_size):
            batch = candidates[i:i + OLLAMA.batch_size]
            tasks.append(process_batch(batch))
        
        await asyncio.gather(*tasks)
        
        self.stats['llm_called'] = len(candidates)
        logger.info(f"LLM 判读完成: {self.stats['llm_called']} 次调用")

    async def _llm_batch_classify(self, batch: List[dict]) -> List[LLMResult]:
        """单批次 LLM 调用"""
        prompt = self._build_batch_prompt(batch)
        
        @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
        async def call_ollama():
            async with httpx.AsyncClient(timeout=OLLAMA.timeout) as client:
                resp = await client.post(
                    f"{OLLAMA.base_url}/api/generate",
                    json={
                        "model": OLLAMA.model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": 0.1, "num_predict": 1024}
                    }
                )
                resp.raise_for_status()
                return resp.json()
        
        response = await call_ollama()
        return self._parse_llm_response(response['response'], batch)

    def _build_batch_prompt(self, batch: List[dict]) -> str:
        items = []
        for i, item in enumerate(batch):
            text = f"标题: {item['title']}\n内容: {item['content']}"
            if item['category_l3']:
                text += f"\n三级分类: {item['category_l3']}"
            items.append(f"=== 条目 {i+1} (ID: {item['appeal_id']}) ===\n{text}")
        
        return f"""你是"形式主义为基层减负"专项线索识别专家。请逐条判读以下 {len(batch)} 条 12345 诉求，识别是否属于形式主义为基层增加负担的线索。

核心判断逻辑：**只要存在"为了应付上级检查/考核/指标而增加一线无谓负担"，即为相关。**

【必须从以下 46 个标准细分类中选择 subcategory，严禁自造分类】：
{STANDARDS_PROMPT_TEXT}

施压方不限党政机关：高校部门、平台方、行业协会、学校、医院、国企、事业单位均计。
受压方不限基层干部：村居社区、一线窗口、网格员、辅警、临时工、外包人员均计。

输出格式（严格 JSON 数组，每个对象对应一条）:
[
  {{
    "appeal_id": "ID",
    "is_relevant": true/false,
    "category": "对应的大类（如: 数据造假、指尖形式主义、权责不清/甩锅、创建示范/达标、盲目决策/形象工程、精简文件、精简会议、督查检查考核、借调干部）",
    "subcategory": "必须从上述 46 个标准细分类中精确选择一个，原文复制",
    "root_cause": "核心根因(如: 为了应付上级检查/考核/指标而增加一线无谓负担)",
    "confidence": 0.0-1.0,
    "tags": ["标签1", "标签2"],
    "qualitative_analysis": "定性分析: 简述为什么相关/不相关，指出关键现象和因果链条",
    "evidence_suggestion": "取证建议: 如需核实，建议调取什么材料/找谁谈话/查什么系统",
    "llm_reason": "判读理由: 一句话总结核心判断依据"
  }},
  ...
]

待判读条目:
{chr(10).join(items)}"""

    def _parse_llm_response(self, response: str, batch: List[dict]) -> List[LLMResult]:
        # 去除可能的 markdown 代码围栏
        cleaned = response.strip()
        if cleaned.startswith('```'):
            # 去除首行 ```json 或 ```
            lines = cleaned.split('\n')
            if lines[0].startswith('```'):
                lines = lines[1:]
            # 去除尾行 ```
            if lines and lines[-1].strip().startswith('```'):
                lines = lines[:-1]
            cleaned = '\n'.join(lines).strip()
        
        try:
            data = json.loads(cleaned)
            if not isinstance(data, list):
                data = [data]
        except json.JSONDecodeError:
            logger.error(f"LLM 返回非 JSON: {response[:500]}")
            return []
        
        results = []
        for i, item in enumerate(data):
            if i >= len(batch):
                break
            try:
                result = LLMResult(
                    appeal_id=batch[i]['appeal_id'],
                    is_relevant=item.get('is_relevant', False),
                    category=item.get('category', ''),
                    subcategory=item.get('subcategory', ''),
                    root_cause=item.get('root_cause', ''),
                    confidence=float(item.get('confidence', 0)),
                    tags=item.get('tags', []),
                    qualitative_analysis=item.get('qualitative_analysis', ''),
                    evidence_suggestion=item.get('evidence_suggestion', ''),
                    llm_reason=item.get('llm_reason', '')
                )
                results.append(result)
            except Exception as e:
                logger.warning(f"解析第 {i} 条结果失败: {e}")
        
        return results

    def _validate_and_fix_subcategory(self, result: LLMResult) -> LLMResult:
        """验证并修正 subcategory，确保在标准白名单内"""
        if not result.is_relevant:
            return result
        
        original_subcat = result.subcategory.strip()
        
        # 精确匹配
        if original_subcat in STANDARDS_WHITELIST:
            # 同步 category
            result.category = STANDARDS_WHITELIST[original_subcat]['category']
            return result
        
        # 模糊匹配：关键词包含关系
        best_match = None
        best_score = 0
        for std_subcat, info in STANDARDS_WHITELIST.items():
            score = 0
            # 子类名包含关系
            if original_subcat in std_subcat or std_subcat in original_subcat:
                score += 3
            # 关键词匹配
            keywords = info['keywords'].split('、')
            for kw in keywords:
                if kw in original_subcat:
                    score += 2
                if kw in result.qualitative_analysis or kw in result.evidence_suggestion:
                    score += 1
            if score > best_score:
                best_score = score
                best_match = std_subcat
        
        if best_match and best_score >= 2:
            logger.info(f"[修正] {result.appeal_id}: '{original_subcat}' -> '{best_match}' (score={best_score})")
            result.subcategory = best_match
            result.category = STANDARDS_WHITELIST[best_match]['category']
            return result
        
        # 无法匹配：记录警告，设为空，后续人工复核
        logger.warning(f"[未匹配] {result.appeal_id}: subcategory='{original_subcat}' 不在标准白名单内，置空待人工复核")
        result.subcategory = ""
        result.category = ""
        return result

    async def _save_clue(self, result: LLMResult):
        """保存判读结果到 clues 表"""
        # 先验证并修正分类
        result = self._validate_and_fix_subcategory(result)
        
        if not result.is_relevant:
            return
        
        # 从 raw_appeals 取基础字段
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT title, content, register_time, city, district, handle_depts
                FROM raw_appeals WHERE appeal_id = %s
            """, (result.appeal_id,))
            base = cur.fetchone()
        
        if not base:
            return
        
        self.stats['relevant_found'] += 1
        if result.confidence >= 0.8:
            self.stats['high_confidence'] += 1
        
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO clues (appeal_id, title, content, publish_time, region_city, region_district,
                                   complained_unit, is_relevant, category, subcategory, root_cause,
                                   confidence, tags, qualitative_analysis, evidence_suggestion,
                                   llm_reason, llm_model, route, priority, matched_keywords)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                    updated_at = NOW()
            """, (
                result.appeal_id, base['title'], base['content'], base['register_time'],
                base['city'], base['district'], base['handle_depts'],
                result.is_relevant, result.category, result.subcategory, result.root_cause,
                result.confidence, result.tags, result.qualitative_analysis,
                result.evidence_suggestion, result.llm_reason,
                OLLAMA.model, 'full', 'HIGH', []  # matched_keywords 后续补全
            ))
        self.conn.commit()

    # ----- 4. 导出静态页数据 -----
    def export_static(self):
        """导出 CSV 供静态页使用"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT appeal_id, title, content, publish_time, region_city, region_district,
                       complained_unit, category, subcategory, root_cause, confidence,
                       tags, qualitative_analysis, evidence_suggestion, llm_reason,
                       llm_model, route, priority, matched_keywords, created_at
                FROM clues
                WHERE is_relevant = TRUE
                ORDER BY confidence DESC, publish_time DESC
            """)
            clues = cur.fetchall()
        
        if not clues:
            logger.warning("无线索可导出")
            return
        
        df = pd.DataFrame(clues)
        
        # 1. 原始快照（只读）
        raw_path = PATHS.static_dir / f"clues_raw_{self.date_str}.csv"
        df.to_csv(raw_path, index=False, encoding='utf-8-sig')
        
        # 2. 供编辑的最新版
        latest_path = PATHS.static_dir / "clues_latest.csv"
        df.to_csv(latest_path, index=False, encoding='utf-8-sig')
        
        # 3. 高置信度精选
        high_conf = df[df['confidence'] >= 0.8]
        high_path = PATHS.static_dir / f"clues_high_confidence_{self.date_str}.csv"
        high_conf.to_csv(high_path, index=False, encoding='utf-8-sig')
        high_conf.to_csv(PATHS.static_dir / "clues_high_confidence.csv", index=False, encoding='utf-8-sig')
        
        # 4. 统计报表
        stats_path = PATHS.static_dir / f"stats_{self.date_str}.json"
        with open(stats_path, 'w', encoding='utf-8') as f:
            json.dump({**self.stats, 'date': self.date_str, 'export_time': datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)
        
        logger.info(f"静态页导出完成: 总线索={len(df)}, 高置信度={len(high_conf)}")
        logger.info(f"  - {raw_path}")
        logger.info(f"  - {latest_path}")
        logger.info(f"  - {high_path}")

    # ----- 5. 保存统计 -----
    def save_stats(self):
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO daily_stats (process_date, total_raw, blacklist_excluded, candidate_total,
                                         candidate_high, candidate_low, candidate_none, llm_called,
                                         relevant_found, high_confidence, zero_keyword_sampled,
                                         zero_keyword_relevant, processing_time_seconds)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (process_date) DO UPDATE SET
                    total_raw = EXCLUDED.total_raw,
                    blacklist_excluded = EXCLUDED.blacklist_excluded,
                    candidate_total = EXCLUDED.candidate_total,
                    candidate_high = EXCLUDED.candidate_high,
                    candidate_low = EXCLUDED.candidate_low,
                    candidate_none = EXCLUDED.candidate_none,
                    llm_called = EXCLUDED.llm_called,
                    relevant_found = EXCLUDED.relevant_found,
                    high_confidence = EXCLUDED.high_confidence,
                    zero_keyword_sampled = EXCLUDED.zero_keyword_sampled,
                    zero_keyword_relevant = EXCLUDED.zero_keyword_relevant,
                    processing_time_seconds = EXCLUDED.processing_time_seconds
            """, (
                self.process_date,
                self.stats['total_raw'],
                self.stats['blacklist_excluded'],
                self.stats['candidate_total'],
                self.stats['candidate_high'],
                self.stats['candidate_low'],
                self.stats['candidate_none'],
                self.stats['llm_called'],
                self.stats['relevant_found'],
                self.stats['high_confidence'],
                self.stats['zero_keyword_sampled'],
                self.stats['zero_keyword_relevant'],
                0  # processing_time_seconds 暂时填 0
            ))
        self.conn.commit()

    # ----- 主流程 -----
    def run(self):
        start_time = datetime.now()
        logger.info(f"=== 开始处理 {self.process_date} ===")
        
        try:
            # 1. 导入原始数据
            self.import_raw_data()
            
            # 2. 黑白名单路由
            self.apply_routing()
            
            # 3. LLM 判读
            asyncio.run(self.run_llm_classification())
            
            # 4. 导出静态页
            self.export_static()
            
            # 5. 保存统计
            self.save_stats()
            
            elapsed = (datetime.now() - start_time).total_seconds()
            logger.info(f"=== 处理完成，耗时 {elapsed:.1f} 秒 ===")
            logger.info(f"统计: {json.dumps(self.stats, ensure_ascii=False)}")
            
        except Exception as e:
            logger.exception(f"处理失败: {e}")
            raise


# ==================== 入口 ====================

def main():
    parser = argparse.ArgumentParser(description="每日诉求处理")
    parser.add_argument('--date', type=str, help='处理日期 YYYY-MM-DD，默认今天')
    parser.add_argument('--import-only', action='store_true', help='仅导入数据')
    parser.add_argument('--route-only', action='store_true', help='仅路由')
    parser.add_argument('--llm-only', action='store_true', help='仅 LLM 判读')
    parser.add_argument('--export-only', action='store_true', help='仅导出静态页')
    args = parser.parse_args()
    
    if args.date:
        process_date = datetime.strptime(args.date, '%Y-%m-%d').date()
    else:
        process_date = date.today()
    
    with DailyProcessor(process_date) as processor:
        if args.import_only:
            processor.import_raw_data()
        elif args.route_only:
            processor.apply_routing()
        elif args.llm_only:
            asyncio.run(processor.run_llm_classification())
        elif args.export_only:
            processor.export_static()
        else:
            processor.run()

if __name__ == '__main__':
    main()
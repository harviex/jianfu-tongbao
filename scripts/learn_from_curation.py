#!/usr/bin/env python3
"""
从静态页复核结果学习，自动更新黑白名单
- 对比 clues_raw_YYYYMMDD.csv (原始快照) vs clues_curated.csv (人工留存)
- 被删除的 = FP (误判)
- 归因分析 → 更新 blacklist.yaml / whitelist.yaml
"""

import os
import sys
import re
import yaml
import json
import logging
import argparse
from datetime import datetime, date
from pathlib import Path
from typing import List, Dict, Any, Set, Tuple
from collections import Counter

import pandas as pd
from rapidfuzz import fuzz, process

# ==================== 配置 ====================

PROJECT_ROOT = Path("/home/c1/jianfu-tongbao")
STATIC_DIR = PROJECT_ROOT / "data/static"
CONFIG_DIR = PROJECT_ROOT / "config"
LOGS_DIR = PROJECT_ROOT / "logs"

LOGS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / f"learn_{date.today().isoformat()}.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ==================== 核心逻辑 ====================

class CurationLearner:
    def __init__(self, process_date: date):
        self.process_date = process_date
        self.date_str = process_date.strftime('%Y%m%d')
        
        # 加载现有名单
        self.blacklist = self._load_list('blacklist.yaml')
        self.whitelist = self._load_list('whitelist.yaml')
        self.greylist = self._load_list('greylist.yaml')
        
        # 统计
        self.stats = {
            'raw_total': 0,
            'curated_total': 0,
            'fp_count': 0,
            'new_blacklist': 0,
            'downgraded_whitelist': 0,
            'removed_whitelist': 0,
        }

    def _load_list(self, filename: str) -> dict:
        path = CONFIG_DIR / filename
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        return {'version': '1.0', 'patterns': []}

    def _save_list(self, filename: str, data: dict):
        path = CONFIG_DIR / filename
        # 备份旧版本
        if path.exists():
            backup = CONFIG_DIR / f"{filename}.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            path.rename(backup)
        
        data['version'] = f"{float(data.get('version', '1.0')) + 0.1:.1f}"
        data['updated_at'] = datetime.now().isoformat()
        
        with open(path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
        logger.info(f"已保存: {path} (v{data['version']})")

    def run(self):
        logger.info(f"=== 开始从复核结果学习: {self.process_date} ===")
        
        # 1. 读取原始快照和复核版本
        raw_path = STATIC_DIR / f"clues_raw_{self.date_str}.csv"
        curated_path = STATIC_DIR / "clues_curated.csv"
        
        if not raw_path.exists():
            raise FileNotFoundError(f"找不到原始快照: {raw_path}")
        if not curated_path.exists():
            raise FileNotFoundError(f"找不到复核文件: {curated_path}\n请先将 clues_latest.csv 另存为 clues_curated.csv 并删除 FP 行")
        
        raw_df = pd.read_csv(raw_path)
        curated_df = pd.read_csv(curated_path)
        
        self.stats['raw_total'] = len(raw_df)
        self.stats['curated_total'] = len(curated_df)
        
        # 2. 找出被删除的行 = FP
        raw_ids = set(raw_df['appeal_id'].astype(str))
        curated_ids = set(curated_df['appeal_id'].astype(str))
        fp_ids = raw_ids - curated_ids
        
        if not fp_ids:
            logger.info("无 FP 记录，无需更新名单")
            return
        
        fp_records = raw_df[raw_df['appeal_id'].astype(str).isin(fp_ids)]
        self.stats['fp_count'] = len(fp_records)
        logger.info(f"发现 {len(fp_records)} 条 FP 记录")
        
        # 3. 归因分析
        blacklist_candidates = self._analyze_fp_for_blacklist(fp_records)
        whitelist_downgrades = self._analyze_fp_for_whitelist_downgrade(fp_records, raw_df)
        
        # 4. 更新黑名单
        if blacklist_candidates:
            self._update_blacklist(blacklist_candidates)
        
        # 5. 更新白名单（降权/移除）
        if whitelist_downgrades:
            self._update_whitelist(whitelist_downgrades)
        
        # 6. 输出变更报告
        self._print_report(blacklist_candidates, whitelist_downgrades)
        
        logger.info("=== 学习完成 ===")

    def _analyze_fp_for_blacklist(self, fp_records: pd.DataFrame) -> List[Dict]:
        """从 FP 记录中挖掘黑名单候选词"""
        # 提取所有 FP 记录的文本
        fp_texts = []
        for _, row in fp_records.iterrows():
            text = f"{row.get('title', '')} {row.get('content', '')}"
            fp_texts.append(text)
        
        # 简单的高频词提取（基于分词和过滤）
        import jieba
        jieba.initialize()
        
        # 停用词
        stopwords = set(['的', '了', '是', '在', '有', '和', '与', '或', '但', '不', '没', '无', '为', '被', '把', '让', '使', '给', '向', '从', '到', '去', '来', '上', '下', '左', '右', '前', '后', '内', '外', '中', '里', '面', '边', '旁', '这', '那', '哪', '谁', '什', '么', '多', '少', '大', '小', '高', '低', '长', '短', '宽', '窄', '厚', '薄', '重', '轻', '快', '慢', '早', '晚', '新', '旧', '好', '坏', '对', '错', '真', '假', '是', '非', '正', '反', '进', '出', '入', '离', '开', '关', '启', '停', '始', '终', '头', '尾', '首', '末', '顶', '底', '左', '右', '东', '西', '南', '北', '中', '心', '中心', '中间', '周围', '附近', '旁边', '对面', '隔壁', '楼上', '楼下', '里面', '外面', '上面', '下面', '前面', '后面', '左边', '右边', '里边', '外边', '上边', '下边', '前边', '后边', '旁边', '跟前', '跟后', '跟左', '跟右'])
        
        word_counter = Counter()
        for text in fp_texts:
            words = jieba.lcut(text)
            for w in words:
                if len(w) >= 2 and w not in stopwords and not w.isdigit():
                    word_counter[w] += 1
        
        # 筛选：在 FP 中出现 ≥3 次，且不是已知的白名单词
        existing_whitelist_words = set()
        for p in self.whitelist.get('patterns', []):
            # 简单提取白名单中的关键词
            pat = p.get('pattern', '')
            for w in pat.split('|'):
                if len(w) >= 2:
                    existing_whitelist_words.add(w)
        
        candidates = []
        for word, count in word_counter.most_common(50):
            if count >= 3 and word not in existing_whitelist_words:
                # 检查是否已在黑名单中
                in_blacklist = False
                for p in self.blacklist.get('patterns', []):
                    if word in p.get('pattern', ''):
                        in_blacklist = True
                        break
                
                if not in_blacklist:
                    # 计算该词在 FP 中的覆盖率
                    coverage = sum(1 for t in fp_texts if word in t) / len(fp_texts)
                    candidates.append({
                        'word': word,
                        'count': count,
                        'coverage': coverage,
                        'sample_fp': fp_records.iloc[0]['appeal_id'] if len(fp_records) > 0 else ''
                    })
        
        logger.info(f"黑名单候选词: {[c['word'] for c in candidates[:10]]}")
        return candidates[:20]  # 取前 20 个

    def _analyze_fp_for_whitelist_downgrade(self, fp_records: pd.DataFrame, raw_df: pd.DataFrame) -> List[Dict]:
        """分析哪些白名单词导致了 FP，需要降权"""
        # 统计每个白名单词在 FP 中的命中率
        whitelist_stats = {}
        
        for p in self.whitelist.get('patterns', []):
            pattern = p.get('pattern', '')
            category = p.get('category', '')
            weight = p.get('weight', 1)
            
            # 编译正则
            try:
                regex = re.compile(pattern, re.IGNORECASE)
            except:
                continue
            
            # 在 FP 中命中数
            fp_hits = 0
            for _, row in fp_records.iterrows():
                text = f"{row.get('title', '')} {row.get('content', '')}"
                if regex.search(text):
                    fp_hits += 1
            
            # 在所有 raw 中命中数
            total_hits = 0
            for _, row in raw_df.iterrows():
                text = f"{row.get('title', '')} {row.get('content', '')}"
                if regex.search(text):
                    total_hits += 1
            
            if total_hits > 0:
                fp_rate = fp_hits / total_hits
                whitelist_stats[pattern] = {
                    'category': category,
                    'weight': weight,
                    'fp_hits': fp_hits,
                    'total_hits': total_hits,
                    'fp_rate': fp_rate
                }
        
        # 筛选：FP 率 > 0.5 且总命中 ≥ 3 次
        downgrades = []
        for pattern, stats in whitelist_stats.items():
            if stats['fp_rate'] > 0.5 and stats['total_hits'] >= 3:
                downgrades.append({
                    'pattern': pattern,
                    'category': stats['category'],
                    'current_weight': stats['weight'],
                    'fp_rate': stats['fp_rate'],
                    'total_hits': stats['total_hits'],
                    'fp_hits': stats['fp_hits'],
                    'action': 'downgrade' if stats['weight'] > 1 else 'remove'
                })
        
        logger.info(f"白名单降权候选: {len(downgrades)} 个")
        return downgrades

    def _update_blacklist(self, candidates: List[Dict]):
        """将候选词加入黑名单"""
        new_patterns = []
        for c in candidates:
            word = c['word']
            # 简单的模式：词边界匹配
            pattern = rf"\b{re.escape(word)}\b"
            
            new_patterns.append({
                'pattern': pattern,
                'category': f"自动归因-{c['sample_fp']}",
                'reason': f"FP高频词，出现{c['count']}次，覆盖率{c['coverage']:.1%}",
                'auto_added': True,
                'source_fp': c['sample_fp'],
                'added_at': datetime.now().isoformat()
            })
        
        # 合并到现有黑名单
        existing_patterns = self.blacklist.get('patterns', [])
        # 去重
        existing_patterns_str = set(p['pattern'] for p in existing_patterns)
        for np in new_patterns:
            if np['pattern'] not in existing_patterns_str:
                existing_patterns.append(np)
                self.stats['new_blacklist'] += 1
        
        self.blacklist['patterns'] = existing_patterns
        self._save_list('blacklist.yaml', self.blacklist)

    def _update_whitelist(self, downgrades: List[Dict]):
        """降权或移除白名单词"""
        patterns = self.whitelist.get('patterns', [])
        
        for d in downgrades:
            pattern = d['pattern']
            for p in patterns:
                if p.get('pattern') == pattern:
                    if d['action'] == 'remove':
                        patterns.remove(p)
                        self.stats['removed_whitelist'] += 1
                        logger.info(f"移除白名单: {pattern} (FP率 {d['fp_rate']:.1%})")
                    else:
                        old_weight = p.get('weight', 1)
                        new_weight = max(1, old_weight - 1)
                        p['weight'] = new_weight
                        p['downgraded_at'] = datetime.now().isoformat()
                        p['downgrade_reason'] = f"FP率 {d['fp_rate']:.1%} ({d['fp_hits']}/{d['total_hits']})"
                        self.stats['downgraded_whitelist'] += 1
                        logger.info(f"降权白名单: {pattern} {old_weight}→{new_weight} (FP率 {d['fp_rate']:.1%})")
                    break
        
        self.whitelist['patterns'] = patterns
        self._save_list('whitelist.yaml', self.whitelist)

    def _print_report(self, blacklist_candidates: List, whitelist_downgrades: List):
        print("\n" + "="*60)
        print(f"复核学习报告 - {self.date_str}")
        print("="*60)
        print(f"原始线索: {self.stats['raw_total']}")
        print(f"复核保留: {self.stats['curated_total']}")
        print(f"删除(FP): {self.stats['fp_count']}")
        print(f"新增黑名单: {self.stats['new_blacklist']}")
        print(f"白名单降权: {self.stats['downgraded_whitelist']}")
        print(f"白名单移除: {self.stats['removed_whitelist']}")
        
        if blacklist_candidates:
            print("\n新增黑名单词:")
            for c in blacklist_candidates[:10]:
                print(f"  - {c['word']} (FP中出现{c['count']}次, 覆盖率{c['coverage']:.1%})")
        
        if whitelist_downgrades:
            print("\n白名单调整:")
            for d in whitelist_downgrades:
                action = "移除" if d['action'] == 'remove' else f"降权 {d['current_weight']}→{max(1, d['current_weight']-1)}"
                print(f"  - [{action}] {d['pattern'][:50]}... (FP率 {d['fp_rate']:.1%})")
        
        print("="*60)


def main():
    parser = argparse.ArgumentParser(description="从复核结果学习更新黑白名单")
    parser.add_argument('--date', type=str, required=True, help='处理日期 YYYY-MM-DD')
    args = parser.parse_args()
    
    process_date = datetime.strptime(args.date, '%Y-%m-%d').date()
    
    learner = CurationLearner(process_date)
    learner.run()


if __name__ == '__main__':
    main()
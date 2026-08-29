#!/usr/bin/env python3
"""
复核工序：对 LLM 判读结果为 relevant 的线索进行二次筛查，
剔除 llm_reason 中明确表述"不构成形式主义/不符合标准"的误判。

核心逻辑：即使 subcategory 命中白名单，如果 llm_reason 明确否定，
说明模型内部自相矛盾，应以 reason 表述为准。

用法：
  python scripts/review_filter.py --date 2026-08-25
  python scripts/review_filter.py --start 2026-08-10 --end 2026-08-26
"""
import argparse
import os
import sys
import re
import psycopg2
from psycopg2.extras import RealDictCursor

# 明确否定形式主义的关键词模式（llm_reason 中出现即判定为不符合）
NEGATIVE_PATTERNS = [
    r'不构成形式主义',
    r'不符合形式主义',
    r'不构成形式主义增负',
    r'不构成形式主义为基层减负',
    r'未体现上级为(?:迎检|考核|检查|指标|创建)而向下摊派',
    r'未体现上级(?:发文|考核|检查)驱动',
    r'无上级(?:考核|检查|迎检)驱动证据',
    r'属于(?:技术|系统|平台)(?:问题|故障|缺陷|体验)',
    r'仅属(?:于)?(?:个别|正常|技术|系统)',
    r'不构成形式主义摊派',
]

COMPILED = [re.compile(p) for p in NEGATIVE_PATTERNS]


def is_false_positive(reason: str) -> bool:
    """判断 llm_reason 是否明确否定形式主义定性"""
    if not reason:
        return False
    return any(p.search(reason) for p in COMPILED)


def review_date(date_str: str, dry_run: bool = False) -> dict:
    """对指定日期的线索进行复核"""
    db_config = {
        'host': os.environ.get('DB_HOST', 'localhost'),
        'port': int(os.environ.get('DB_PORT', 5432)),
        'database': os.environ.get('DB_NAME', 'tongbao'),
        'user': os.environ.get('DB_USER', 'tongbao_user'),
        'password': os.environ.get('DB_PASS', 'tongbao_2026_secure'),
    }

    conn = psycopg2.connect(**db_config, cursor_factory=RealDictCursor)
    cur = conn.cursor()

    # 获取当天所有 relevant=True 的线索
    cur.execute("""
        SELECT appeal_id, title, subcategory, confidence, llm_reason
        FROM clues
        WHERE is_relevant = TRUE
          AND publish_time >= %s AND publish_time < %s::date + interval '1 day'
        ORDER BY confidence DESC
    """, (date_str, date_str))

    clues = cur.fetchall()
    to_remove = []
    to_keep = []

    for clue in clues:
        if is_false_positive(clue['llm_reason'] or ''):
            to_remove.append(clue)
        else:
            to_keep.append(clue)

    result = {
        'date': date_str,
        'total': len(clues),
        'to_remove': len(to_remove),
        'to_keep': len(to_keep),
        'removed_ids': [c['appeal_id'] for c in to_remove],
    }

    if to_remove and not dry_run:
        # 删除误判线索
        ids = [c['appeal_id'] for c in to_remove]
        cur.execute("DELETE FROM clues WHERE appeal_id = ANY(%s)", (ids,))
        conn.commit()
        print(f"  Deleted {cur.rowcount} false positives from DB")

    conn.close()
    return result


def main():
    parser = argparse.ArgumentParser(description='复核工序：剔除 llm_reason 自相矛盾的误判线索')
    parser.add_argument('--date', help='单日复核 YYYY-MM-DD')
    parser.add_argument('--start', help='起始日期 YYYY-MM-DD')
    parser.add_argument('--end', help='结束日期 YYYY-MM-DD')
    parser.add_argument('--dry-run', action='store_true', help='只报告不删除')
    args = parser.parse_args()

    if args.date:
        dates = [args.date]
    elif args.start and args.end:
        from datetime import datetime, timedelta
        start = datetime.strptime(args.start, '%Y-%m-%d')
        end = datetime.strptime(args.end, '%Y-%m-%d')
        dates = []
        while start <= end:
            dates.append(start.strftime('%Y-%m-%d'))
            start += timedelta(days=1)
    else:
        print("请指定 --date 或 --start + --end")
        sys.exit(1)

    total_removed = 0
    for date_str in dates:
        print(f"\n复核 {date_str}...")
        result = review_date(date_str, dry_run=args.dry_run)
        print(f"  总计: {result['total']}, 剔除: {result['to_remove']}, 保留: {result['to_keep']}")
        for aid in result['removed_ids']:
            print(f"    - {aid}")
        total_removed += result['to_remove']

    print(f"\n合计剔除: {total_removed} 条")


if __name__ == '__main__':
    main()

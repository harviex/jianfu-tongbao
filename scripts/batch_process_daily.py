#!/usr/bin/env python3
"""
批量处理多日 12345 投诉数据
- 支持日期范围、断点续跑、失败重试、进度持久化
- 单日调用 scripts/process_daily.py
"""
import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

PROGRESS_FILE = Path("/home/c1/jianfu-tongbao/data/batch_progress.json")
PROJECT_DIR = Path("/home/c1/jianfu-tongbao")
PROCESS_SCRIPT = PROJECT_DIR / "scripts/process_daily.py"


def load_progress():
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def save_progress(progress):
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    progress['updated_at'] = datetime.now().isoformat()
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def init_progress(start_date, end_date, resume=False):
    """初始化或恢复进度"""
    existing = load_progress() if resume else None
    
    if existing and existing.get('start_date') == start_date and existing.get('end_date') == end_date:
        print(f"📂 恢复现有进度: {PROGRESS_FILE}")
        return existing
    
    # 新建进度
    days = {}
    current = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    while current <= end:
        day_str = current.strftime("%Y-%m-%d")
        days[day_str] = {"status": "pending"}
        current += timedelta(days=1)
    
    progress = {
        "start_date": start_date,
        "end_date": end_date,
        "days": days,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }
    save_progress(progress)
    print(f"📝 新建进度文件: {PROGRESS_FILE}")
    return progress


def run_single_day(date_str, max_retries=3):
    """运行单日处理，带重试"""
    for attempt in range(1, max_retries + 1):
        print(f"  ▶ {date_str} 第 {attempt}/{max_retries} 次尝试...")
        result = subprocess.run(
            [sys.executable, str(PROCESS_SCRIPT), "--date", date_str],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=7200  # 2小时超时
        )
        if result.returncode == 0:
            # 解析输出获取线索数
            clues = 0
            for line in result.stdout.split('\n'):
                if '最终线索' in line or 'clues' in line.lower():
                    try:
                        clues = int(''.join(filter(str.isdigit, line.split()[-1])))
                    except:
                        pass
            return True, clues, result.stdout[-2000:]  # 最后2000字符
        else:
            print(f"    ❌ 失败 (码 {result.returncode}): {result.stderr[-500:] if result.stderr else '无错误输出'}")
            if attempt < max_retries:
                wait = 2 ** attempt * 10  # 20s, 40s, 80s
                print(f"    ⏳ {wait}s 后重试...")
                time.sleep(wait)
    return False, 0, "Max retries exceeded"


def main():
    parser = argparse.ArgumentParser(description="批量处理多日 12345 数据")
    parser.add_argument("--start-date", required=True, help="开始日期 YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="结束日期 YYYY-MM-DD")
    parser.add_argument("--resume", action="store_true", help="从进度文件续跑")
    parser.add_argument("--concurrency", type=int, default=1, help="并发数（建议 1）")
    parser.add_argument("--stop-on-error", action="store_true", help="遇错停止")
    parser.add_argument("--dry-run", action="store_true", help="仅打印计划")
    args = parser.parse_args()

    # 验证日期
    try:
        start = datetime.strptime(args.start_date, "%Y-%m-%d")
        end = datetime.strptime(args.end_date, "%Y-%m-%d")
        assert start <= end
    except Exception as e:
        print(f"❌ 日期格式错误: {e}")
        sys.exit(1)

    progress = init_progress(args.start_date, args.end_date, args.resume)

    if args.dry_run:
        print("\n📋 执行计划:")
        for day_str, info in progress['days'].items():
            print(f"  {day_str}: {info['status']}")
        return

    # 统计
    total_days = len(progress['days'])
    done_days = sum(1 for d in progress['days'].values() if d['status'] == 'done')
    print(f"\n🚀 开始批量处理: {args.start_date} ~ {args.end_date} ({total_days} 天, 已完成 {done_days})")

    # 串行执行（并发>1 需要进程池，暂不实现）
    for day_str, info in progress['days'].items():
        if info['status'] == 'done':
            print(f"⏭ {day_str} 已完成，跳过")
            continue
        if info['status'] == 'running':
            print(f"🔄 {day_str} 上次中断，重新跑")
        
        info['status'] = 'running'
        info['started_at'] = datetime.now().isoformat()
        save_progress(progress)

        success, clues, output = run_single_day(day_str)

        info['finished_at'] = datetime.now().isoformat()
        if success:
            info['status'] = 'done'
            info['clues'] = clues
            print(f"✅ {day_str} 完成，线索: {clues}")
        else:
            info['status'] = 'failed'
            info['error'] = output
            print(f"❌ {day_str} 失败: {output[:200]}")
            if args.stop_on_error:
                print("🛑 --stop-on-error 生效，停止执行")
                save_progress(progress)
                sys.exit(1)
        
        save_progress(progress)
        time.sleep(2)  # 避免 API 限流

    # 汇总
    done = sum(1 for d in progress['days'].values() if d['status'] == 'done')
    failed = sum(1 for d in progress['days'].values() if d['status'] == 'failed')
    total_clues = sum(d.get('clues', 0) for d in progress['days'].values())
    print(f"\n🎉 批量处理结束: 成功 {done}, 失败 {failed}, 总线索 {total_clues}")
    print(f"📊 进度文件: {PROGRESS_FILE}")


if __name__ == "__main__":
    main()
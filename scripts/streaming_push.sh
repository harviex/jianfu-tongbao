#!/bin/bash
# 流式推送：每当 batch_progress.json 有新增完成天数，就把全部线索数据推送到 GitHub Pages
# 阈值改为 1（只要有 >=1 天新增进度即推送；批量跑完 15 天会触发 1 次推送）
set -e
cd /home/c1/jianfu-tongbao
PY=/home/c1/.hermes/hermes-agent/venv/bin/python
STATE=/tmp/stream_push_state.txt

# 统计已完成天数
DONE=$($PY -c "
import json
d=json.load(open('data/batch_progress.json'))
print(sum(1 for v in d['days'].values() if v.get('status')=='done'))")

LAST=$(cat $STATE 2>/dev/null || echo 0)
if [ $((DONE - LAST)) -lt 1 ]; then
    echo "done=$DONE last_push=$LAST 无新增进度，跳过"
    exit 0
fi

echo "检测到 $((DONE-LAST)) 天新进度（done=$DONE），开始导出并推送..."
mkdir -p docs
# 重新生成网页数据源 clues_test.json（clues.html 读取的就是它）
/home/c1/.hermes/hermes-agent/venv/bin/python scripts/update_clues_json.py > /dev/null
# 导出最新全量线索 CSV + 每日高置信度文件
cp data/static/clues_latest.csv docs/clues_latest.csv
cp data/static/clues_high_confidence.csv docs/clues_high_confidence.csv
cp data/static/clues_high_confidence_2026*.csv docs/ 2>/dev/null || true
# 进度快照
$PY -c "
import json
d=json.load(open('data/batch_progress.json'))
days={k:v for k,v in d['days'].items() if v.get('status')=='done'}
meta={'completed_days':len(days),'range':[min(days),max(days)] if days else None,'updated':__import__('datetime').datetime.now().isoformat()}
json.dump(meta,open('docs/batch_meta.json','w'),ensure_ascii=False,indent=2)
print('meta:',meta)"

git add docs/ data/clues_test.json
git commit -m "流式更新：累计 ${DONE} 天线索数据（截至 $(date +%H:%M)）" || echo "无变更"
git push origin main
echo $DONE > $STATE
echo "✅ 推送完成：${DONE} 天"

#!/bin/bash
# c1 上运行：检查 CA 上的 distill 模型，就绪则改配置并跑一天测试
CA="ca@100.121.38.118"
KEY="$HOME/.ssh/id_ed25519"
LOG=/tmp/check_distill.log

MODEL=$(ssh -i $KEY -o StrictHostKeyChecking=no -o ConnectTimeout=10 -p 22 $CA "ollama list 2>/dev/null | grep -i distill | awk '{print \$1}' | head -1" 2>/dev/null)

if [ -z "$MODEL" ]; then
    echo "[$(date +%H:%M)] distill 未就绪" | tee -a $LOG
    exit 1
fi

echo "[$(date +%H:%M)] ✅ 发现 distill: $MODEL，开始切换..." | tee -a $LOG

cd /home/c1/jianfu-tongbao
# 1. 改模型名
sed -i "s|model: str = .*|model: str = \"$MODEL\"|" scripts/process_daily.py
# 2. 关闭思考（加 enable_thinking: false）
if ! grep -q "enable_thinking" scripts/process_daily.py; then
    sed -i 's/"num_predict": 2048/"num_predict": 2048, "enable_thinking": false/' scripts/process_daily.py
fi

echo "配置已更新：" | tee -a $LOG
grep -n "model: str\|enable_thinking" scripts/process_daily.py | tee -a $LOG

# 3. 跑一天测试（04-25）
echo "[$(date +%H:%M)] 开始跑 04-25 测试..." | tee -a $LOG
./scripts/process_daily.py --date 2026-04-25 2>&1 | tee /tmp/qwen38_distill_test.log

echo "[$(date +%H:%M)] 测试完成" | tee -a $LOG

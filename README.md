# 基层减负舆情线索挖掘系统

每日处理 12345 诉求数据，通过 黑白名单预筛 + 本地 LLM (qwen3.5:9b) 语义判读，产出形式主义为基层增加负担线索，生成静态页数据供 GitHub Pages 展示。

## 目录结构

```
jianfu-tongbao/
├── config/
│   ├── blacklist.yaml      # 黑名单 - 直接剔除
│   ├── whitelist.yaml      # 白名单 - 高优先级送 LLM
│   └── greylist.yaml       # 灰度区 - 低优先级采样送 LLM
├── data/
│   ├── inbox/              # 👉 每日原始 Excel 放这里
│   │   └── 2026-08-04/*.xlsx
│   └── static/             # 👉 Git 管理，静态页数据源
│       ├── clues_raw_20260804.csv       # 脚本生成，只读快照
│       ├── clues_latest.csv             # 固定名，供编辑/网页读取
│       ├── clues_curated.csv            # 👉 人工复核后另存为这个
│       ├── clues_high_confidence.csv    # 高置信度线索，首页展示
│       └── stats_20260804.json          # 每日统计
├── scripts/
│   ├── db_init.sql                 # 建表脚本
│   ├── process_daily.py            # 主流程
│   └── learn_from_curation.py      # 从复核结果学习
├── logs/                           # 运行日志
└── requirements.txt                # Python 依赖
```

## 环境准备

### 1. PostgreSQL (已有 1Panel 管理)
```bash
# 创建数据库和用户（在 1Panel 或 psql 中执行）
CREATE DATABASE tongbao;
CREATE USER tongbao_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE tongbao TO tongbao_user;

# 安装中文分词扩展（可选，提升全文搜索）
# CREATE EXTENSION IF NOT EXISTS zhparser;
```

### 2. 本地 Ollama (192.168.123.33:11434)
```bash
# 确保已拉取模型
ollama pull qwen3.5:9b
# 显存需求 ~8GB，16GB 可跑 2 并发
```

### 3. Python 依赖
```bash
cd /home/c1/jianfu-tongbao
pip install -r requirements.txt
```

### 4. 数据库建表
```bash
# 修改 scripts/db_init.sql 中的连接信息，或用环境变量
export PGHOST=localhost
export PGPORT=5432
export PGDATABASE=tongbao
export PGUSER=tongbao_user
export PGPASSWORD=your_password

psql -h $PGHOST -U $PGUSER -d $PGDATABASE -f scripts/db_init.sql
```

### 5. 配置数据库连接
编辑 `scripts/process_daily.py` 顶部的 `DBConfig`：
```python
@dataclass
class DBConfig:
    host: str = "localhost"
    port: int = 5432
    database: str = "tongbao"
    user: str = "tongbao_user"
    password: str = "your_password"
```

## 日常操作流程

### 第 1 天：首次跑数（以 2026-08-04 为例）

```bash
# 1. 放入原始数据
mkdir -p /home/c1/jianfu-tongbao/data/inbox/2026-08-04
cp ~/Downloads/诉求查询明细结果_2026-08-04.xlsx /home/c1/jianfu-tongbao/data/inbox/2026-08-04/

# 2. 运行全流程（入库 → 路由 → LLM判读 → 导出静态页）
cd /home/c1/jianfu-tongbao
python scripts/process_daily.py --date 2026-08-04

# 3. 查看结果
# 生成的文件在 data/static/：
# - clues_raw_20260804.csv     (原始快照，100条左右)
# - clues_latest.csv           (同内容，固定文件名)
# - clues_high_confidence.csv  (高置信度，~30条)
# - stats_20260804.json        (统计报表)
```

### 第 2 天：人工复核 + 学习

```bash
# 1. 打开 clues_latest.csv 审核（Excel / VS Code / 在线表格）
# 删除与"形式主义为基层减负"无关的行（FP）
# 另存为 clues_curated.csv 放在同目录

# 2. 运行学习脚本，自动更新黑白名单
python scripts/learn_from_curation.py --date 2026-08-04

# 输出示例：
# 新增黑名单: 医保报销, 异地放贷, 档案查询...
# 降权白名单: 评比创建 (FP率 60%), 会议泛滥 (FP率 55%)...
```

### 第 3+ 天：日常增量

```bash
# 每天重复：
# 1. 放入新数据到 data/inbox/YYYY-MM-DD/
# 2. python scripts/process_daily.py --date YYYY-MM-DD
# 3. 审核 clues_latest.csv → 另存为 clues_curated.csv
# 4. python scripts/learn_from_curation.py --date YYYY-MM-DD
```

## 部分运行模式

```bash
# 仅导入数据
python scripts/process_daily.py --date 2026-08-05 --import-only

# 仅路由（黑白名单分类）
python scripts/process_daily.py --date 2026-08-05 --route-only

# 仅 LLM 判读（补跑漏掉的）
python scripts/process_daily.py --date 2026-08-05 --llm-only

# 仅导出静态页
python scripts/process_daily.py --date 2026-08-05 --export-only
```

## 静态页部署 (GitHub Pages)

```bash
# 1. 创建仓库并启用 Pages
# Settings → Pages → Deploy from branch → main / docs

# 2. 将 data/static/ 映射为 docs/ 目录（或用软链接）
ln -s /home/c1/jianfu-tongbao/data/static /home/c1/jianfu-tongbao/docs

# 3. 推送
git add docs/
git commit -m "Update static data 2026-08-04"
git push origin main

# 4. 访问
# https://<username>.github.io/<repo>/clues_latest.csv
# https://<username>.github.io/<repo>/clues_high_confidence.csv
```

## 黑白名单维护

### 手动调整
直接编辑 `config/*.yaml`，格式：
```yaml
patterns:
  - pattern: "正则表达式"
    category: "分类名"
    reason: "理由"
    weight: 10  # 仅白名单
```

### 自动学习
复核后运行 `learn_from_curation.py` 自动：
- FP 高频词 → 加入黑名单
- 白名单词 FP 率 > 50% → 降权/移除

## 关键指标预估 (12,390 条/天)

| 阶段 | 输入 | 输出 | 耗时 |
|------|------|------|------|
| 入库 | 12,390 | 12,390 | ~30秒 |
| 黑名单剔除 | 12,390 | ~4,000 剩余 | ~5秒 |
| 白名单路由 | ~4,000 | 候选池 ~1,800 | ~5秒 |
| LLM判读 | ~1,800 | 线索 ~120 | ~2小时 |
| 静态页生成 | - | 3个文件 | ~10秒 |

## 故障排查

### LLM 连不上
```bash
# 检查 Ollama 服务
curl http://192.168.123.33:11434/api/tags

# 检查模型
curl http://192.168.123.33:11434/api/show -d '{"name": "qwen3.5:9b"}'
```

### 数据库连不上
```bash
# 检查 1Panel PostgreSQL 端口、防火墙、pg_hba.conf
psql -h localhost -U tongbao_user -d tongbao -c "SELECT 1;"
```

### 导入报错：列名不匹配
检查 Excel 表头行，脚本默认 `skiprows=1` 后第 1 行为表头。如表头位置不同，调整 `process_daily.py` 中的 `_clean_dataframe`。

## 版本历史

- v1.0 (2026-08-06): 初版，含黑白名单、LLM判读、静态页导出、复核学习闭环
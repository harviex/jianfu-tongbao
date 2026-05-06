# 整治形式主义为基层减负公开通报典型问题数据库

[![Crawl Notices](https://github.com/harviex/jiansu-tongbao/actions/workflows/crawl.yml/badge.svg)](https://github.com/harviex/jiansu-tongbao/actions/workflows/crawl.yml)

📋 政府公开通报数据库 - 收集中央及各地整治形式主义为基层减负专项工作机制办公室通报的典型问题

## 访问地址

🌐 **[https://harviex.github.io/jiansu-tongbao/tongbao/public/](https://harviex.github.io/jiansu-tongbao/tongbao/public/)**

## 功能特性

- 📊 **数据统计**: 实时显示通报总数、涉及省份等关键指标
- 🔍 **智能搜索**: 支持关键词全文搜索
- 🏷️ **多维筛选**: 按分类、问题类型、涉及省份筛选
- 📄 **详情查看**: 点击卡片查看通报全文
- 🔄 **自动更新**: GitHub Actions 每日定时爬取最新通报

## 技术架构

- **前端**: 纯静态HTML + JavaScript (无框架)
- **数据源**: 人民网专题页
- **爬虫**: Python + Firecrawl API
- **托管**: GitHub Pages
- **更新**: GitHub Actions 定时任务

## 数据来源

- 中央层面整治形式主义为基层减负专项工作机制办公室通报
- 各省市整治形式主义为基层减负专项工作机制办公室通报

## 本地开发

```bash
# 克隆仓库
git clone https://github.com/harviex/jiansu-tongbao.git
cd jiansu-tongbao/tongbao

# 安装依赖
pip install requests

# 设置Firecrawl API Key
export FIRECRAWL_API_KEY="your_api_key"

# 运行爬虫
python scraper_static.py

# 启动本地服务器
cd public
python -m http.server 8080
```

## GitHub Actions 配置

需要在仓库 Settings → Secrets and variables → Actions 中添加:

- `FIRECRAWL_API_KEY`: Firecrawl API密钥

## 项目结构

```
jiansu-tongbao/
├── tongbao/
│   ├── public/
│   │   ├── index.html          # 主页面
│   │   ├── report.html         # 情况反映入口
│   │   └── data/               # JSON数据文件
│   │       ├── notices.json     # 通报数据
│   │       └── stats.json       # 统计数据
│   ├── scraper_static.py       # 静态版爬虫
│   ├── data_sources.json       # 数据源配置
│   └── 项目立项方案.md
└── .github/
    └── workflows/
        └── crawl.yml           # GitHub Actions工作流
```

## License

MIT License

## 更新日志

- 2026-05-06: 项目迁移至GitHub Pages，实现完全静态化

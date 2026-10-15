#!/usr/bin/env python3
"""
验证环境和配置的快速测试脚本
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path("/home/c1/jianfu-tongbao")

def check_files():
    """检查关键文件存在"""
    required = [
        "config/blacklist.yaml",
        "config/whitelist.yaml",
        "config/greylist.yaml",
        "scripts/process_daily.py",
        "scripts/learn_from_curation.py",
        "scripts/db_init.sql",
        "requirements.txt",
    ]
    print("=== 文件检查 ===")
    for f in required:
        path = PROJECT_ROOT / f
        status = "✅" if path.exists() else "❌"
        print(f"  {status} {f}")
    
def check_yaml():
    """检查 YAML 语法"""
    import yaml
    print("\n=== YAML 语法检查 ===")
    for f in ["config/blacklist.yaml", "config/whitelist.yaml", "config/greylist.yaml"]:
        path = PROJECT_ROOT / f
        try:
            with open(path, 'r', encoding='utf-8') as fp:
                data = yaml.safe_load(fp)
            print(f"  ✅ {f}: version={data.get('version')}, patterns={len(data.get('patterns', []))}")
        except Exception as e:
            print(f"  ❌ {f}: {e}")

def check_python_imports():
    """检查 Python 依赖"""
    print("\n=== Python 依赖检查 ===")
    modules = [
        'pandas', 'openpyxl', 'psycopg2', 'yaml', 'httpx', 
        'tenacity', 'rapidfuzz', 'jieba'
    ]
    for m in modules:
        try:
            __import__(m)
            print(f"  ✅ {m}")
        except ImportError:
            print(f"  ❌ {m} (需安装)")

def check_ollama():
    """检查 Ollama 连通性"""
    import httpx
    print("\n=== Ollama 连通性 ===")
    try:
        resp = httpx.get("http://192.168.123.33:11434/api/tags", timeout=5)
        if resp.status_code == 200:
            models_data = resp.json()
            models = [m['name'] for m in models_data.get('models', [])] if models_data else []
            print(f"  ✅ 连接成功，可用模型: {models}")
            if 'qwen3.8-9b-uncensored-iq4xs' in models:
                print("  ✅ qwen3.8-9b-uncensored-iq4xs 已就绪")
            else:
                print("  ⚠️  qwen3.8-9b-uncensored-iq4xs 未找到，需 pull")
        else:
            print(f"  ❌ HTTP {resp.status_code}")
    except Exception as e:
        print(f"  ❌ 连接失败: {e}")

def check_postgres():
    """检查 PostgreSQL 连通性"""
    import psycopg2
    print("\n=== PostgreSQL 连通性 ===")
    try:
        conn = psycopg2.connect(
            host="localhost", port=5432, 
            database="tongbao", user="tongbao_user", password="tongbao_2026_secure"
        )
        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            print(f"  ✅ 连接成功: {cur.fetchone()[0][:60]}...")
        conn.close()
    except Exception as e:
        print(f"  ❌ 连接失败: {e}")
        print("     请检查 1Panel PostgreSQL 配置、密码、pg_hba.conf")

def check_inbox():
    """检查 inbox 数据"""
    print("\n=== Inbox 数据检查 ===")
    inbox = PROJECT_ROOT / "data/inbox"
    if inbox.exists():
        for d in sorted(inbox.iterdir()):
            if d.is_dir():
                xlsx_files = list(d.glob("*.xlsx"))
                print(f"  📁 {d.name}: {len(xlsx_files)} 个 xlsx 文件")
                for f in xlsx_files:
                    print(f"      - {f.name} ({f.stat().st_size/1024/1024:.1f} MB)")
    else:
        print("  ⚠️  inbox 目录不存在")

if __name__ == "__main__":
    check_files()
    check_yaml()
    check_python_imports()
    check_ollama()
    check_postgres()
    check_inbox()
    print("\n=== 检查完成 ===")
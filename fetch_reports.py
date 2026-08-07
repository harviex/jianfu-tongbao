#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
减负通报爬虫 - 抓取各地和中央通报最新内容
用法: python3 fetch_reports.py
"""

import json
import time
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# 配置
DATA_DIR = Path(__file__).parent / "data"
NOTICES_FILE = DATA_DIR / "notices.json"
STATS_FILE = DATA_DIR / "stats.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# 已知源站解析规则
PARSERS = {
    "people_cn": {
        "selector": "div.content, div.article, div#content, .content-body, .article-content, #fontzoom",
        "title_selector": "h1, .title, .article-title",
        "date_selector": ".time, .date, .pub-time, .info",
        "remove_selectors": ["script", "style", ".share", ".related", ".prev-next", "iframe", ".ad"]
    },
    "gzjjjc": {
        "selector": ".content, .article-content, #content, .detail-content",
        "title_selector": "h1, .title",
        "date_selector": ".time, .date",
        "remove_selectors": ["script", "style", ".share", ".related"]
    },
    "shjjjc": {
        "selector": ".content, .article-content, #content, .detail-con",
        "title_selector": "h1, .title",
        "date_selector": ".time, .date, .info",
        "remove_selectors": ["script", "style", ".share", ".related"]
    },
    "jjc.cq.gov.cn": {
        "selector": ".content, .article-content, #content, .TRS_Editor",
        "title_selector": "h1, .title",
        "date_selector": ".time, .date, .info",
        "remove_selectors": ["script", "style", ".share", ".related"]
    },
    "szns.gov.cn": {
        "selector": ".content, .article-content, #content, .detail",
        "title_selector": "h1, .title",
        "date_selector": ".time, .date",
        "remove_selectors": ["script", "style", ".share", ".related"]
    },
    "fzmq.gov.cn": {
        "selector": ".content, .article-content, #content, .detail",
        "title_selector": "h1, .title",
        "date_selector": ".time, .date",
        "remove_selectors": ["script", "style", ".share", ".related"]
    },
    "moj.gov.cn": {
        "selector": ".content, .article-content, #content, .detail",
        "title_selector": "h1, .title",
        "date_selector": ".time, .date",
        "remove_selectors": ["script", "style", ".share", ".related"]
    },
    "news.cn": {
        "selector": ".content, .article-content, #content, .article",
        "title_selector": "h1, .title",
        "date_selector": ".time, .date, .h-time",
        "remove_selectors": ["script", "style", ".share", ".related"]
    },
    "default": {
        "selector": "div.content, div.article, div#content, .content-body, .article-content, .detail-content, .TRS_Editor, #fontzoom, main, article",
        "title_selector": "h1, .title, .article-title, h2",
        "date_selector": ".time, .date, .pub-time, .info, .meta",
        "remove_selectors": ["script", "style", ".share", ".related", ".prev-next", "iframe", ".ad", "nav", "header", "footer"]
    }
}

def get_parser_key(url):
    """根据域名获取解析器配置"""
    domain = urlparse(url).netloc.lower()
    for key in PARSERS:
        if key in domain:
            return key
    return "default"

def fetch_page(url, timeout=15):
    """抓取页面"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, verify=False)
        resp.encoding = resp.apparent_encoding or 'utf-8'
        return resp.text
    except Exception as e:
        print(f"  ❌ 抓取失败 {url}: {e}")
        return None

def extract_content(html, parser_key):
    """从HTML提取正文内容"""
    soup = BeautifulSoup(html, 'html.parser')
    parser = PARSERS[parser_key]
    
    # 移除不需要的元素
    for sel in parser["remove_selectors"]:
        for el in soup.select(sel):
            el.decompose()
    
    # 尝试多种选择器提取内容
    content = ""
    for sel in parser["selector"].split(", "):
        el = soup.select_one(sel.strip())
        if el:
            content = el.get_text("\n", strip=True)
            break
    
    # 如果都没找到，尝试body
    if not content:
        body = soup.find('body')
        if body:
            content = body.get_text("\n", strip=True)
    
    # 清理文本
    content = re.sub(r'\n{3,}', '\n\n', content)
    content = re.sub(r'[ \t]{2,}', ' ', content)
    # Fix escaped newlines and other escape sequences
    content = content.replace('\\n', '\n').replace('\\t', '\t').replace('\\r', '\r')
    
    return content

def extract_title(html, parser_key):
    """提取标题"""
    soup = BeautifulSoup(html, 'html.parser')
    parser = PARSERS[parser_key]
    
    for sel in parser["title_selector"].split(", "):
        el = soup.select_one(sel.strip())
        if el and el.get_text(strip=True):
            return el.get_text(strip=True)
    
    # 尝试<title>
    title_tag = soup.find('title')
    if title_tag:
        return title_tag.get_text(strip=True)
    
    return ""

def extract_date(html, parser_key, url):
    """提取发布日期"""
    soup = BeautifulSoup(html, 'html.parser')
    parser = PARSERS[parser_key]
    
    # 从页面提取
    for sel in parser["date_selector"].split(", "):
        el = soup.select_one(sel.strip())
        if el:
            text = el.get_text(strip=True)
            # 尝试解析日期
            date_match = re.search(r'(\d{4}[-年]\d{1,2}[-月]\d{1,2})', text)
            if date_match:
                return date_match.group(1).replace('年', '-').replace('月', '-').replace('日', '')
    
    # 从URL提取
    url_date = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', url)
    if url_date:
        return f"{url_date.group(1)}-{url_date.group(2)}-{url_date.group(3)}"
    
    url_date2 = re.search(r'(\d{4})(\d{2})(\d{2})', url)
    if url_date2:
        return f"{url_date2.group(1)}-{url_date2.group(2)}-{url_date2.group(3)}"
    
    return ""

def load_existing():
    """加载现有数据"""
    if NOTICES_FILE.exists():
        with open(NOTICES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_data(notices):
    """保存数据"""
    # 更新时间戳
    stats = compute_stats(notices)
    stats["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with open(NOTICES_FILE, 'w', encoding='utf-8') as f:
        json.dump(notices, f, ensure_ascii=False, indent=2)
    
    with open(STATS_FILE, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 已保存 {len(notices)} 条通报，统计信息已更新")

def compute_stats(notices):
    """计算统计信息"""
    tags_set = set()
    provinces_set = set()
    level1_set = set()
    source_sites = set()
    by_level = {}
    
    for n in notices:
        for tag in n.get("tags", []):
            tags_set.add(tag)
        for prov in n.get("provinces", []):
            provinces_set.add(prov)
        level1 = n.get("level_1", "未知")
        level1_set.add(level1)
        by_level[level1] = by_level.get(level1, 0) + 1
        source_sites.add(n.get("source_site", "未知"))
    
    tags_list = [{"tag": t, "count": sum(1 for n in notices if t in n.get("tags", []))} for t in tags_set]
    tags_list.sort(key=lambda x: x["count"], reverse=True)
    
    provinces_list = [{"province": p, "count": sum(1 for n in notices if p in n.get("provinces", []))} for p in provinces_set]
    provinces_list.sort(key=lambda x: x["count"], reverse=True)
    
    by_level_list = [{"level_1": k, "count": v} for k, v in by_level.items()]
    by_level_list.sort(key=lambda x: x["count"], reverse=True)
    
    return {
        "total": len(notices),
        "tags": tags_list,
        "provinces": provinces_list,
        "byLevel": by_level_list,
        "source_sites": list(source_sites)
    }

def fetch_single(notice):
    """抓取单条通报详情"""
    url = notice.get("source_url", "")
    if not url:
        return notice
    
    print(f"  📥 抓取: {url}")
    html = fetch_page(url)
    if not html:
        return notice
    
    parser_key = get_parser_key(url)
    
    # 提取内容
    content = extract_content(html, parser_key)
    if content and len(content) > len(notice.get("content", "")):
        notice["content"] = content
        notice["content_preview"] = content[:200] + "..." if len(content) > 200 else content
    
    # 提取标题（如果现有标题太短或为空）
    title = extract_title(html, parser_key)
    if title and len(title) > len(notice.get("title", "")):
        notice["title"] = title
    
    # 提取日期
    date = extract_date(html, parser_key, url)
    if date and not notice.get("publish_date"):
        notice["publish_date"] = date
    
    notice["source_site"] = urlparse(url).netloc
    notice["fetched_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    return notice

def main():
    print("=" * 60)
    print("🚀 减负通报爬虫启动")
    print("=" * 60)
    
    # 加载现有数据
    notices = load_existing()
    print(f"📚 已加载 {len(notices)} 条现有通报")
    
    # 为每条通报抓取详情（只抓取内容为空或较短的）
    updated = 0
    for i, notice in enumerate(notices):
        # 跳过已有完整内容的
        if notice.get("content") and len(notice["content"]) > 500:
            continue
        
        print(f"\n[{i+1}/{len(notices)}] 处理: {notice.get('title', '')[:50]}...")
        updated_notice = fetch_single(notice)
        if updated_notice != notice:
            notices[i] = updated_notice
            updated += 1
        
        # 礼貌延迟
        time.sleep(1.5)
    
    if updated > 0:
        save_data(notices)
        print(f"\n✨ 更新了 {updated} 条通报详情")
    else:
        print("\n✅ 所有通报已有完整内容，无需更新")
    
    print("=" * 60)
    print("🏁 爬虫任务完成")
    print("=" * 60)

if __name__ == "__main__":
    # 禁用SSL警告
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    main()
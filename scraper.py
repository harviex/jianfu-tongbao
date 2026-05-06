#!/usr/bin/env python3
"""
政府通报爬虫 - 从人民政协网抓取整治形式主义通报
增量抓取：只抓取数据库中不存在的新文章
"""
import json
import re
import sys
import time
import urllib.request
import subprocess
import psycopg2
from datetime import datetime

# Config
LIST_URL = "http://zzxszy.people.cn/GB/458759/index.html"
KEYWORD = "中央层面整治形式主义为基层减负专项工作机制办公室"
DB_CONFIG = dict(host="localhost", port=5432, user="user_EjB5yH", 
                 password="password_QXyMXR", dbname="notices")

# Problem category keywords for classification
PROBLEM_CATEGORIES = {
    "层层加码": ["层层加码", "加码", "指标任务", "摊派任务"],
    "数据造假": ["数据造假", "弄虚作假", "虚报", "伪造", "充数"],
    "形式主义": ["形式主义", "走过场", "形式大于内容", "重形式"],
    "官僚主义": ["官僚主义", "脱离群众", "不作为", "乱作为"],
    "脱离实际": ["脱离实际", "不切实际", "不顾实际", "盲目"],
    "考核泛滥": ["考核", "评比", "排名", "通报排名", "月调度"],
    "资源浪费": ["浪费", "利用率低", "资金浪费", "闲置"],
    "强制摊派": ["强制", "摊派", "强推", "行政命令", "硬性"]
}

# Province mapping
PROVINCES = [
    "北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江",
    "上海", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南",
    "湖北", "湖南", "广东", "广西", "海南", "重庆", "四川", "贵州",
    "云南", "西藏", "陕西", "甘肃", "青海", "宁夏", "新疆"
]


def fetch_page(url):
    """Fetch a page using Firecrawl for better content extraction"""
    try:
        import subprocess
        result = subprocess.run([
            'curl', '-s', '-m', '15',
            '-X', 'POST', 'https://api.firecrawl.dev/v1/scrape',
            '-H', 'Authorization: Bearer fc-48384079b1e64fcd8fc044c00edc7880',
            '-H', 'Content-Type: application/json',
            '-d', json.dumps({"url": url, "formats": ["markdown"]})
        ], capture_output=True, text=True, timeout=20)
        
        data = json.loads(result.stdout)
        if data.get('success'):
            return data['data'].get('markdown', ''), data['data'].get('metadata', {})
    except Exception as e:
        print(f"  Firecrawl failed, fallback to curl: {e}")
    
    # Fallback to direct curl
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode('utf-8', errors='replace'), {}
    except Exception as e:
        print(f"  Fetch error: {e}")
        return '', {}


def parse_list_page(html):
    """Extract article links from the list page"""
    articles = []
    # Pattern: links with target keyword in title
    pattern = r'<a[^>]+href="([^"]+)"[^>]*>([^<]*' + re.escape(KEYWORD[:10]) + r'[^<]*)</a>'
    for match in re.finditer(pattern, html, re.DOTALL):
        url, title = match.group(1), match.group(2).strip()
        # Clean title
        title = re.sub(r'<[^>]+>', '', title).strip()
        if KEYWORD in title and url:
            if not url.startswith('http'):
                url = 'http://zzxszy.people.cn' + url
            articles.append({'url': url, 'title': title})
    
    # Also try markdown format from Firecrawl
    if not articles:
        md_pattern = r'\[([^\]]*' + re.escape(KEYWORD[:15]) + r'[^\]]*)\]\(([^)]+)\)'
        for match in re.finditer(md_pattern, html, re.DOTALL):
            title, url = match.group(1).strip(), match.group(2).strip()
            if KEYWORD in title:
                if not url.startswith('http'):
                    url = 'http://zzxszy.people.cn' + url
                articles.append({'url': url, 'title': title})
    
    # Deduplicate by URL
    seen = set()
    unique = []
    for a in articles:
        if a['url'] not in seen:
            seen.add(a['url'])
            unique.append(a)
    
    return unique


def extract_date(title, content):
    """Extract publish date from title or content"""
    # Try patterns like 2024年04月08日
    for text in [content, title]:
        match = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', text)
        if match:
            return f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
    # Try URL pattern like /n1/2024/0408/
    match = re.search(r'/n1/(\d{4})/(\d{2})(\d{2})/', title + content)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    return None


def classify_content(content, title):
    """Classify content into problem categories and provinces"""
    full_text = title + ' ' + content
    
    tags = []
    for category, keywords in PROBLEM_CATEGORIES.items():
        for kw in keywords:
            if kw in full_text:
                tags.append(category)
                break
    
    provinces = []
    for prov in PROVINCES:
        if prov in full_text and prov not in provinces:
            provinces.append(prov)
    
    # Count cases (X起)
    case_count = None
    match = re.search(r'(\d+)\s*起', title)
    if match:
        case_count = int(match.group(1))
    
    return tags, provinces, case_count


def extract_article_content(markdown):
    """Extract main content from Firecrawl markdown"""
    # Remove header/footer/nav content
    lines = markdown.split('\n')
    content_lines = []
    skip = True
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Start collecting after the date line
        if re.search(r'\d{4}年\d{1,2}月\d{1,2}日\d{2}:\d{2}', line):
            skip = False
            continue
        if skip:
            continue
        # Stop at footer
        if '版权' in line or '人民网' in line or '责任编辑' in line or '责编' in line:
            break
        if line.startswith('!['):
            continue
        content_lines.append(line)
    
    return '\n'.join(content_lines).strip()


def process_with_ai(content, title):
    """Use Ollama to generate summary and refine tags"""
    try:
        prompt = f"""分析以下政府通报，返回JSON格式:
标题: {title}
正文: {content[:1500]}

返回格式:
{{"summary": "一句话概括（50字内）", "tags": ["标签1", "标签2"]}}

标签可选范围: 层层加码、数据造假、形式主义、官僚主义、脱离实际、考核泛滥、资源浪费、强制摊派
只返回JSON，不要其他内容。"""

        import http.client
        conn = http.client.HTTPConnection("192.168.123.33", 11434, timeout=15)
        conn.request("POST", "/api/generate", json.dumps({
            "model": "qwen3.5:9b",
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0}
        }), {"Content-Type": "application/json"})
        resp = conn.getresponse()
        data = json.loads(resp.read())
        conn.close()
        
        text = data.get('response', '')
        match = re.search(r'\{[^}]+\}', text)
        if match:
            return json.loads(match.group(0))
    except Exception as e:
        print(f"  AI processing failed: {e}")
    return None


def get_existing_urls(conn):
    """Get set of URLs already in database"""
    cur = conn.cursor()
    cur.execute("SELECT source_url FROM notices")
    return {row[0] for row in cur.fetchall()}


def insert_notice(conn, notice):
    """Insert a notice into the database"""
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO notices (title, source_url, level_1, level_2, publish_date, 
                           content, summary, tags, provinces, case_count, source_site, ai_processed)
        VALUES (%(title)s, %(source_url)s, %(level_1)s, %(level_2)s, %(publish_date)s,
                %(content)s, %(summary)s, %(tags)s, %(provinces)s, %(case_count)s, %(source_site)s, %(ai_processed)s)
        ON CONFLICT (source_url) DO NOTHING
    """, notice)
    conn.commit()
    return cur.rowcount


def main():
    print(f"🔍 通报爬虫启动 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"   目标: {LIST_URL}")
    print(f"   关键词: {KEYWORD}")
    
    # Connect to DB
    conn = psycopg2.connect(**DB_CONFIG)
    existing_urls = get_existing_urls(conn)
    print(f"   数据库已有: {len(existing_urls)} 条")
    
    # Fetch list page
    print(f"\n📄 抓取列表页...")
    html, _ = fetch_page(LIST_URL)
    if not html:
        print("❌ 列表页抓取失败")
        return
    
    articles = parse_list_page(html)
    print(f"   找到 {len(articles)} 篇文章链接")
    
    # Filter new articles
    new_articles = [a for a in articles if a['url'] not in existing_urls]
    print(f"   新文章: {len(new_articles)} 篇")
    
    if not new_articles:
        print("✅ 没有新文章需要抓取")
        conn.close()
        return
    
    # Process each new article
    inserted = 0
    for i, article in enumerate(new_articles):
        print(f"\n[{i+1}/{len(new_articles)}] {article['title'][:50]}...")
        
        # Fetch article
        content_md, meta = fetch_page(article['url'])
        if not content_md:
            print("  ⚠️ 抓取失败，跳过")
            continue
        
        # Extract content
        content = extract_article_content(content_md)
        if not content:
            # Fallback: use raw content
            content = content_md
        
        # Extract date
        pub_date = extract_date(article['title'], content)
        print(f"  日期: {pub_date}")
        
        # Classify
        tags, provinces, case_count = classify_content(content, article['title'])
        print(f"  标签: {tags}")
        print(f"  省份: {provinces}")
        
        # AI processing
        ai_result = process_with_ai(content, article['title'])
        summary = ''
        if ai_result:
            summary = ai_result.get('summary', '')
            ai_tags = ai_result.get('tags', [])
            # Merge AI tags with rule-based tags
            for t in ai_tags:
                if t not in tags:
                    tags.append(t)
            print(f"  AI摘要: {summary}")
        
        # Insert
        notice = {
            'title': article['title'],
            'source_url': article['url'],
            'level_1': '中央',
            'level_2': tags,
            'publish_date': pub_date,
            'content': content,
            'summary': summary,
            'tags': tags,
            'provinces': provinces,
            'case_count': case_count,
            'source_site': '人民网',
            'ai_processed': bool(ai_result)
        }
        
        if insert_notice(conn, notice):
            inserted += 1
            print(f"  ✅ 已入库")
        else:
            print(f"  ⏭️ 已存在")
        
        time.sleep(1)  # Be polite
    
    print(f"\n{'='*40}")
    print(f"✅ 完成！新增 {inserted} 条通报")
    print(f"   数据库总计: {len(existing_urls) + inserted} 条")
    
    conn.close()


if __name__ == "__main__":
    main()

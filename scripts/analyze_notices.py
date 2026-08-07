#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析 46 条通报，对比 25 条 DEFAULT_STANDARDS，
提取新的分类/细分/关键词，生成差异报告
"""

import json
import re
from collections import Counter

# Load notices
with open('/home/c1/jianfu-tongbao/data/notices.json', 'r', encoding='utf-8') as f:
    notices = json.load(f)

# Load DEFAULT_STANDARDS from clues.html by extracting the JS array properly
with open('/home/c1/jianfu-tongbao/clues.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Extract DEFAULT_STANDARDS - the JS is valid enough to use a simple regex approach
match = re.search(r'const DEFAULT_STANDARDS = (\[.*?\]);', html, re.DOTALL)
if match:
    js = match.group(1)
    # Convert JS object notation to JSON
    # Replace unquoted property names with quoted
    js = re.sub(r'(\w+):\s*', r'"\1": ', js)
    # Fix single quotes to double
    js = js.replace("'", '"')
    # Fix trailing commas
    js = re.sub(r',\s*}', '}', js)
    js = re.sub(r',\s*]', ']', js)
    standards = json.loads(js)
else:
    standards = []

print(f"DEFAULT_STANDARDS: {len(standards)} categories")
for s in standards:
    print(f"  {s['category']} / {s['subcategory']}")

# Build existing keyword map
existing_keywords = {}
for s in standards:
    key = (s['category'], s['subcategory'])
    kws = s['keywords'].split('、')
    existing_keywords[key] = set(k.strip() for k in kws if k.strip())

print(f"\nTotal existing keyword sets: {len(existing_keywords)}")

# Extract all content from notices
all_content = []
for n in notices:
    content = n.get('content', '')
    if content:
        all_content.append(content)
    summary = n.get('summary', '')
    if summary:
        all_content.append(summary)
    for tag in n.get('tags', []):
        all_content.append(tag)

full_text = '\n'.join(all_content)
print(f"\nTotal text length: {len(full_text)} chars")

# Define comprehensive problem keywords to search for
problem_keywords = [
    # 数据造假类
    '统计造假', '虚报产值', '虚报投资', '虚报招商', '经营主体充数', 'PPT项目', '走账造假',
    '指令报数', '代填代报', '虚假审批', '指导数', '半停产', '只考不核', '购买.*数据', '异地.*数据',
    '虚报.*固投', '虚报.*工业', '虚报.*出口', '造假', '数据失真', '数据不实', '编造数据', '虚假佐证',
    
    # 指尖形式主义类
    '政务APP', '僵尸应用', '多头建设', '数据不共享', '面向基层APP', '功能交叉重复', '未整合', '清理整合',
    '强制打卡', '积分排名', '在线时长', '上传照片', '上传视频', '轨迹', '不上传扣分', '日均积分',
    '考核安装率', '登录率', '点赞转发', '学习时长', '学习强国积分', '约谈', '每日30分',
    '强制下载', '安装率', '登录率',
    
    # 权责不清/甩锅类
    '清单外下放', '签责任状', '分解指标', '考核验收转嫁', '属地管理甩锅', '无执法权无经费', '网格化管理',
    '证明事项', '万能证明', '社区盖章', '金融机构要求证明', '无违建证明', '无纠纷证明', '家庭关系证明',
    '工作机制', '挂牌过多', '随意设立', '领导小组', '工作站', '协会', '督查考核跟着多', '配备力量',
    
    # 创建示范/达标类
    '创建示范', '达标', '运动式', '作秀式', '一阵风', '创建结果排名', '不顾资源禀赋', '氛围营造', '未列入清单',
    '变相收费', '摊派费用', '社会组织违规收费', '绕道国企办展', '以会代收', '展会活动清单外',
    '基层达标', '乡镇达标', '村社区达标', '学校达标', '期满不取消', '验收标准繁多', '台账资料堆积',
    '违规创建', '清单外创建', '保留清单',
    
    # 盲目决策/形象工程类
    '盲目决策', '形象工程', '盲目举债', '挖山造田', '有轨电车', '农旅项目', '烂尾', '违规占用基本农田', '挖湖造景', '资金链断裂',
    '违规评比', '论坛', '节庆', '规避审批', '以会代收', '品牌推介费', '合作费', '会议费', '摊派',
    '超标准建设', '豪华装修', '高档材料', '景观工程', '楼顶亮化', '进口石材', '羊毛地毯', '会议中心', '面子工程',
    
    # 精简文件类
    '文件数量超标', '规避管理', '临时性文件', '红头变白头', '多文合一', '计划管理失效', '发文计划超标', '白头文件',
    '文件质量低', '照搬转发', '不结合实际', '阐述背景过多', '上下一般粗', '重复率', '短实新文风',
    '评估审查缺失', '减负一致性评估', '违规设定考核', '征求意见过频', '周五发周六回',
    
    # 精简会议类
    '会议数量过多', '层层召开', '文山会海', '年底扎堆', '未批准直达基层', '层层陪会', '多头召开',
    '规模规格失控', '主要负责同志参会', '规格虚高', '视频会议随意延伸', '邀请方式变相要求', '扩大参会',
    '会议质量低', '形式大于内容', '讲长话', '空话套话', '表态发言', '兜圈子', '夜猫子会', '传达贯彻型', '部署推进型',
    
    # 督查检查考核类
    '计划备案不规范', '以调研名行考核实', '打包报计划', '执行拆分', '调研结果问责', '调研扎堆', '统筹不力', '层层陪同',
    '考核指标繁杂', '千分制', '双千分制', '三千分制', '指标过细', '月度季度排名', '指标层级3级', '小数点后赋分', '留痕型指标',
    '总量失控', '多头重复', '排名通报变相考核', '县乡村考核未合并', '向同一地方反复安排', '频繁通报排名', '信息宣传排名纳入考核',
    '以业务指导名行督查', '隐形变异', '名合实不合', '随意设置指标', '发文开会作为考核', '督查检查考核',
    '调研扎堆', '层层陪同', '打包报计划', '执行搞拆分', '未经报备', '计划外',
    
    # 借调干部类
    '借调', '跟班学习', '交流锻炼', '专班名义', '长期不归', '占比超标', '超过6+6个月', '借调比例过高', '占比60%', '20年不归',
    '违规借调', '县级及以下', '社区工作者', '变相借调',
    
    # 其他
    '层层加码', '一刀切', '提级管控', '过度管控', '随意提级', '层层分解', '指标分解', '指标摊派',
    '摊派任务', '摊派指标', '摊派工作', '摊派责任', '摊派压力', '摊派负担',
    '甩锅给基层', '推给基层', '推卸责任', '推卸压力', '推卸负担',
    '不属于.*职责', '超职权', '越权', '部门.*甩', '甩给基层',
    '临时任务', '突击任务', '阶段性任务', '专项任务', '专项行动', '百日行动', '专项整治', '集中整治',
    '重复发文', '多头发文', '文件重复', '转发重复', '文风不实', '篇幅过长', '内容重复',
    '数据体外循环', '一表通', '填表报数', '多头填报', '重复填报',
    '评比表彰', '创建示范活动', '违规开展', '清单范围以外',
]

# Count occurrences
found = []
for kw in problem_keywords:
    count = len(re.findall(kw, full_text, re.IGNORECASE))
    if count > 0:
        found.append((kw, count))

found.sort(key=lambda x: x[1], reverse=True)
print(f"\n=== Found {len(found)} problem keywords in notices ===")
for kw, count in found[:80]:
    print(f"  {kw}: {count}")

# Extract individual cases from notices
print("\n=== Individual cases extracted from notices ===")
all_cases = []
for n in notices:
    content = n.get('content', '')
    # Try to find numbered cases
    cases = re.findall(r'\d+[\.、]\s*([^\n]+)', content)
    for c in cases:
        if len(c) > 20:
            all_cases.append({
                'notice_title': n['title'],
                'publish_date': n.get('publish_date', ''),
                'level_1': n.get('level_1', ''),
                'case': c[:300]
            })

print(f"Total cases extracted: {len(all_cases)}")
for i, c in enumerate(all_cases[:30]):
    print(f"\n{i+1}. [{c['publish_date']} {c['level_1']}] {c['notice_title'][:60]}")
    print(f"   {c['case'][:200]}")

# Save for next step
with open('/home/c1/jianfu-tongbao/data/analysis_cases.json', 'w', encoding='utf-8') as f:
    json.dump({
        'total_notices': len(notices),
        'total_cases_extracted': len(all_cases),
        'keyword_counts': found,
        'cases': all_cases,
        'existing_categories': {f"{k[0]}/{k[1]}": list(v) for k, v in existing_keywords.items()}
    }, f, ensure_ascii=False, indent=2)

print("\n✅ Analysis saved to data/analysis_cases.json")
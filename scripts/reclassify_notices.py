#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重新分类通报库：基于 46 条认定标准的分类体系，更新 tags 和 provinces
"""

import json
import re

# Load notices
with open('/home/c1/jianfu-tongbao/data/notices.json', 'r', encoding='utf-8') as f:
    notices = json.load(f)

# 46个标准分类映射到标准化 tag
STANDARD_TAGS = {
    # 数据造假 (6)
    "统计造假-指令报数/代填代报/虚假审批": ["数据造假", "统计造假", "指令报数", "代填代报"],
    "虚报产值/投资/招商引资指标/经营主体充数": ["数据造假", "虚报产值", "虚报投资", "经营主体充数"],
    "虚假整改/迎检突击/边改边犯/不惩反奖": ["数据造假", "虚假整改", "迎检突击", "不惩反奖"],
    "榜单评价造假/购买咨询进位/百强县榜单": ["数据造假", "榜单评价", "百强县", "购买咨询"],
    "异地数据购买/外贸数据造假/购买出口数据": ["数据造假", "异地数据", "外贸造假", "购买数据"],
    "工业产值虚报/固投虚报/规上企业造假/中介机构编造备案": ["数据造假", "工业产值虚报", "固投虚报", "中介机构造假"],
    
    # 指尖形式主义 (6)
    "政务APP泛滥/未整合/僵尸应用/多头建设": ["指尖形式主义", "APP泛滥", "僵尸应用", "多头建设"],
    "强制打卡/积分排名/在线时长/上传照片视频轨迹": ["指尖形式主义", "强制打卡", "积分排名", "在线时长"],
    "推广使用强制化/考核异化/学习强国积分/点赞转发": ["指尖形式主义", "强制推广", "学习强国", "点赞转发"],
    "一表通外搞体外循环/绕过系统填报/多头重复填报": ["指尖形式主义", "体外循环", "一表通", "多头填报"],
    "智能终端/APP排名通报/使用率考核/村医通类": ["指尖形式主义", "智能终端", "村医通", "使用率排名"],
    "强制打卡/定位打卡/上传日志/驻村干部/打卡异常/权限交接": ["指尖形式主义", "定位打卡", "驻村干部", "权限交接"],
    
    # 权责不清/甩锅 (6)
    "清单外事项下放/签责任状转嫁/属地管理甩锅": ["权责不清", "清单外下放", "责任状", "甩锅基层"],
    "证明事项滥设/万能证明/社区盖章": ["权责不清", "证明事项", "万能证明", "社区盖章"],
    "工作机制/挂牌过多/随意设立领导小组": ["权责不清", "挂牌过多", "领导小组", "工作机制"],
    "议事协调机构违规发文/指令性公文下基层/办公室名义发文": ["权责不清", "议事协调机构", "指令性公文", "违规发文"],
    "行业协会/社会组织违规评比收费/以会代收/合作费": ["权责不清", "行业协会", "社会组织", "违规收费", "以会代收"],
    "商业保险摊派/补充保险指标/村集体资金购买/动员购买": ["权责不清", "商业保险", "摊派保险", "村集体资金"],
    
    # 创建示范/达标 (4)
    "种类数量过多/未批准/运动式/作秀式/一阵风": ["创建示范", "运动式创建", "作秀式", "未批准创建"],
    "变相收费/摊派费用/社会组织违规收费/绕道国企办展": ["创建示范", "摊派费用", "绕道国企", "违规收费"],
    "基层搞达标活动/乡镇村校达标/期满不取消": ["创建示范", "达标活动", "乡镇达标", "期满不取消"],
    "社会组织违规创建/行业协会违规评比/清单外创建示范": ["创建示范", "社会组织创建", "行业协会评比", "清单外创建"],
    
    # 盲目决策/形象工程 (6)
    "不顾实际上项目/盲目举债/挖山造田/有轨电车/农旅烂尾/违规占地": ["盲目决策", "盲目举债", "挖山造田", "有轨电车", "农旅烂尾", "违规占地"],
    "违规评比/论坛/节庆/规避审批/以会代收": ["盲目决策", "违规评比", "论坛节庆", "规避审批"],
    "超标准建设装修/豪华办公/办公楼亮化/景观工程浪费": ["盲目决策", "豪华装修", "办公楼亮化", "景观浪费"],
    "国企盲目投资/偏离主业/公款印发个人著作/挪用资金": ["盲目决策", "国企盲目投资", "偏离主业", "公款印发", "挪用资金"],
    "耕地提质改造/旱改水/挖湖造景/非农化/非粮化/水田指标": ["盲目决策", "耕地非农化", "旱改水", "挖湖造景", "非粮化"],
    "项目集中开工/集中签约/重复开工/论证不够/用地手续不全/场面主义": ["盲目决策", "集中开工", "集中签约", "重复开工", "场面主义"],
    
    # 精简文件 (5)
    "文件数量超标/规避管理/临时性文件多/红头变白头": ["精简文件", "文件超标", "红头变白头", "临时性文件"],
    "文件质量低/照搬转发/不结合实际/阐述背景过多": ["精简文件", "文件质量低", "照搬转发", "上下一般粗"],
    "评估审查缺失/未做减负一致性评估/文件中违规设定考核": ["精简文件", "减负评估", "一致性评估", "违规设定考核"],
    "征求意见过频过急/周五发周六回/时间压缩/反馈期限过短": ["精简文件", "征求意见过急", "周五发周六回", "反馈期限短"],
    "文件重复发文/多头转发/同一文件多次下发/收文负担": ["精简文件", "重复发文", "多头转发", "收文负担"],
    
    # 精简会议 (4)
    "会议数量过多/层层召开/文山会海/年底扎堆/未批准直达基层": ["精简会议", "文山会海", "层层开会", "年底扎堆"],
    "规模规格失控/层层陪会/层级不合理/要求主要负责同志参会": ["精简会议", "层层陪会", "会议规格失控", "主要领导参会"],
    "会议质量低/形式大于内容/讲长话/空话套话/夜猫子会": ["精简会议", "会议质量低", "空话套话", "夜猫子会"],
    "专班/专项行动会议多/平价菜专班/百日行动会议/工作专班会议": ["精简会议", "专班会议", "平价菜专班", "百日行动"],
    
    # 督查检查考核 (7)
    "计划备案不规范/以调研名行考核实/打包报计划执行拆分": ["督查检查考核", "计划备案不规范", "以调研代考核", "打包报计划"],
    "考核指标繁杂/千分制/双千分制/三千分制/指标过细/月度季度排名": ["督查检查考核", "千分制", "双千分制", "指标繁杂", "排名考核"],
    "总量失控/多头重复/排名通报变相考核/县乡村考核未合并": ["督查检查考核", "考核总量失控", "多头重复", "考核未合并"],
    "考核指标嵌套/信息工作排名嵌入/满意度评价嵌套/第三方评价": ["督查检查考核", "指标嵌套", "满意度评价", "第三方评价"],
    "调研扎堆/层层陪同/统筹不力/以调研名行考核实/业务指导隐形变异": ["督查检查考核", "调研扎堆", "层层陪同", "统筹不力"],
    "专项考核超范围/综合考核外设专项/县乡考核未合并/违规自行组织考核": ["督查检查考核", "专项考核超范围", "违规组织考核", "县乡考核未合并"],
    "督查检查计划备案挂空挡/计划执行两张皮/近90%未纳入计划/随意开展集中扎堆": ["督查检查考核", "计划空白", "计划执行两张皮", "随意督查"],
    
    # 借调干部 (2)
    "违规向县以下借调/变相借调/跟班学习/专班名义/长期不归/占比超标": ["借调干部", "违规借调", "变相借调", "跟班学习", "专班借调"],
    "群团组织违规借调/共青团/妇联/工会/跟班学习名义/社区工作者借调": ["借调干部", "群团借调", "共青团借调", "妇联借调", "工会借调", "社区工作者借调"],
}

# Create a lookup: keyword -> tags
KEYWORD_TO_TAGS = {}
for std_tags in STANDARD_TAGS.values():
    for tag in std_tags:
        KEYWORD_TO_TAGS[tag] = std_tags

# Province normalization
PROVINCE_MAP = {
    '北京': '北京', '天津': '天津', '河北': '河北', '山西': '山西', '内蒙古': '内蒙古',
    '辽宁': '辽宁', '吉林': '吉林', '黑龙江': '黑龙江', '上海': '上海', '江苏': '江苏',
    '浙江': '浙江', '安徽': '安徽', '福建': '福建', '江西': '江西', '山东': '山东',
    '河南': '河南', '湖北': '湖北', '湖南': '湖南', '广东': '广东', '广西': '广西',
    '海南': '海南', '重庆': '重庆', '四川': '四川', '贵州': '贵州', '云南': '云南',
    '西藏': '西藏', '陕西': '陕西', '甘肃': '甘肃', '青海': '青海', '宁夏': '宁夏', '新疆': '新疆',
    '中央': '中央', '国家': '中央', '新华社': '中央', '中办': '中央', '国办': '中央',
}

def extract_provinces(text):
    """从文本中提取省份"""
    found = set()
    for prov, norm in PROVINCE_MAP.items():
        if prov in text:
            found.add(norm)
    return list(found)

def classify_notice(notice):
    """根据内容和标准给通报打标签"""
    text = (notice.get('title', '') + ' ' + notice.get('content', '') + ' ' + notice.get('summary', '')).lower()
    
    tags = set()
    matched_categories = set()
    
    # Match against standard categories
    for category, std_tags in STANDARD_TAGS.items():
        matched = False
        for tag in std_tags:
            if tag in text:
                matched = True
                break
        if matched:
            matched_categories.add(category)
            tags.update(std_tags)
    
    # Add level-based tags
    level1 = notice.get('level_1', '')
    if '中央' in level1 or '中央' in notice.get('title', ''):
        tags.add('中央通报')
    elif '省级' in level1:
        tags.add('省级通报')
    elif '市级' in level1:
        tags.add('市级通报')
    elif '县级' in level1:
        tags.add('县级通报')
    
    # Add source-based tags
    source = notice.get('source_site', '')
    if 'xinhua' in source or 'news.cn' in source:
        tags.add('新华社')
    if 'gov.cn' in source:
        tags.add('政府网站')
    
    # Extract provinces
    provinces = extract_provinces(text)
    if not provinces:
        # Fallback to existing provinces
        provinces = notice.get('provinces', [])
        provinces = [PROVINCE_MAP.get(p, p) for p in provinces]
    
    # Ensure '中央' is in provinces for central reports
    if '中央通报' in tags and '中央' not in provinces:
        provinces.append('中央')
    
    return list(tags), provinces, list(matched_categories)

# Process all notices
for n in notices:
    tags, provinces, categories = classify_notice(n)
    n['tags'] = tags
    n['provinces'] = provinces
    n['categories'] = categories  # New field for standard categories

# Save
with open('/home/c1/jianfu-tongbao/data/notices.json', 'w', encoding='utf-8') as f:
    json.dump(notices, f, ensure_ascii=False, indent=2)

print(f"✅ 重新分类完成: {len(notices)} 条通报")

# Stats
all_tags = {}
all_provinces = {}
all_cats = {}

for n in notices:
    for t in n.get('tags', []):
        all_tags[t] = all_tags.get(t, 0) + 1
    for p in n.get('provinces', []):
        all_provinces[p] = all_provinces.get(p, 0) + 1
    for c in n.get('categories', []):
        all_cats[c] = all_cats.get(c, 0) + 1

print("\n=== 标签分布 ===")
for t, c in sorted(all_tags.items(), key=lambda x: -x[1]):
    print(f"  {t}: {c}")

print("\n=== 省份分布 ===")
for p, c in sorted(all_provinces.items(), key=lambda x: -x[1]):
    print(f"  {p}: {c}")

print("\n=== 标准分类命中 ===")
for c, cnt in sorted(all_cats.items(), key=lambda x: -x[1]):
    print(f"  {c}: {cnt}")
#!/usr/bin/env python3
"""将 clues_test.json 的分类重映射为 DEFAULT_STANDARDS 标准库"""
import json

# 标准库分类映射：task_num -> {clue_category, clue_subcategory}
# 基于 DEFAULT_STANDARDS 的 6 大一级分类 + 精确细分
MAPPING = {
    # 1. PT26080820429 - 12345平台强制基层回复材料
    "PT26080820429": {"clue_category": "督查检查考核", "clue_subcategory": "计划备案不规范/以调研名行考核实/打包报计划执行拆分"},
    
    # 2. FZ26080821173 - 成立业主大会筹备组（创建类评比）
    "FZ26080821173": {"clue_category": "会议文件泛滥", "clue_subcategory": "文件会议过多/层层陪会"},
    
    # 3. XM26080722732 - 公司强制基层员工名下不能有个体户
    "XM26080722732": {"clue_category": "权责不清/甩锅", "clue_subcategory": "清单外事项下放/签责任状转嫁/属地管理甩锅"},
    
    # 4. FZ26080722110 - 审批单位违规干预民生改造项目
    "FZ26080722110": {"clue_category": "权责不清/甩锅", "clue_subcategory": "证明事项滥设/万能证明/社区盖章"},
    
    # 5. FZ26080720413 - 12345中心以"已转信访"拒绝转办
    "FZ26080720413": {"clue_category": "督查检查考核", "clue_subcategory": "总量失控/多头重复/排名通报变相考核/县乡村考核未合并"},
    
    # 6. QZ26080621546 - 洪濑镇政府处理围墙敷衍处置
    "QZ26080621546": {"clue_category": "督查检查考核", "clue_subcategory": "计划备案不规范/以调研名行考核实/打包报计划执行拆分"},
    
    # 7. QZ26080621527 - 霞美镇政府不作为乱作为
    "QZ26080621527": {"clue_category": "权责不清/甩锅", "clue_subcategory": "清单外事项下放/签责任状转嫁/属地管理甩锅"},
    
    # 8. FJ26080620070 - 孤独症初筛任务基数虚高
    "FJ26080620070": {"clue_category": "数据造假", "clue_subcategory": "统计造假-指令报数/代填代报/虚假审批"},
    
    # 9. XM26080620366 - 12345未落实督办规定草率办结
    "XM26080620366": {"clue_category": "督查检查考核", "clue_subcategory": "总量失控/多头重复/排名通报变相考核/县乡村考核未合并"},
    
    # 10. FJ26080520223 - 鼓楼区信访数据造假
    "FJ26080520223": {"clue_category": "数据造假", "clue_subcategory": "统计造假-指令报数/代填代报/虚假审批"},
    
    # 11. FZ26080521973 - 催告工单（指尖形式主义）
    "FZ26080521973": {"clue_category": "指尖形式主义", "clue_subcategory": "强制打卡/积分排名/在线时长/上传照片视频轨迹"},
    
    # 12. FJ26080420247 - 同10，信访数据造假
    "FJ26080420247": {"clue_category": "数据造假", "clue_subcategory": "统计造假-指令报数/代填代报/虚假审批"},
    
    # 13. LY26080420534 - 村干部重复摸排户籍信息（多头建设）
    "LY26080420534": {"clue_category": "指尖形式主义", "clue_subcategory": "政务APP泛滥/未整合/僵尸应用/多头建设"},
    
    # 14. ND26080420463 - 学校建设长期推诿请求督查
    "ND26080420463": {"clue_category": "督查检查考核", "clue_subcategory": "计划备案不规范/以调研名行考核实/打包报计划执行拆分"},
    
    # 15. NP26080420342 - 村委拒盖章（证明事项滥设）
    "NP26080420342": {"clue_category": "权责不清/甩锅", "clue_subcategory": "证明事项滥设/万能证明/社区盖章"},
    
    # 16. PT26080420594 - 12345违规合并工单敷衍办结
    "PT26080420594": {"clue_category": "督查检查考核", "clue_subcategory": "总量失控/多头重复/排名通报变相考核/县乡村考核未合并"},
    
    # 17. XM26080420884 - 垃圾分类拍照合影（指尖留痕）
    "XM26080420884": {"clue_category": "指尖形式主义", "clue_subcategory": "强制打卡/积分排名/在线时长/上传照片视频轨迹"},
    
    # 18. XM26080323889 - 学校过度管控
    "XM26080323889": {"clue_category": "权责不清/甩锅", "clue_subcategory": "清单外事项下放/签责任状转嫁/属地管理甩锅"},
    
    # 19. FJ26080320224 - 同10/12，信访数据造假
    "FJ26080320224": {"clue_category": "数据造假", "clue_subcategory": "统计造假-指令报数/代填代报/虚假审批"},
    
    # 20. QZ26080321931 - 暑假教师加班整理消防台账
    "QZ26080321931": {"clue_category": "会议文件泛滥", "clue_subcategory": "文件会议过多/层层陪会"},
    
    # 21. QZ26080321773 - 消防过度整改
    "QZ26080321773": {"clue_category": "督查检查考核", "clue_subcategory": "计划备案不规范/以调研名行考核实/打包报计划执行拆分"},
    
    # 22. FJ26080220115 - 12345平台三月三换号用"处理完毕"遮丑
    "FJ26080220115": {"clue_category": "数据造假", "clue_subcategory": "统计造假-指令报数/代填代报/虚假审批"},
    
    # 23. FZ26080220228 - 12345纵容信访打包规避实质办理
    "FZ26080220228": {"clue_category": "数据造假", "clue_subcategory": "统计造假-指令报数/代填代报/虚假审批"},
    
    # 24. FZ26080122016 - 加梯违规协调会（会议泛滥）
    "FZ26080122016": {"clue_category": "会议文件泛滥", "clue_subcategory": "文件会议过多/层层陪会"},
    
    # 25. QZ26080120516 - 劳动安全卫生层层加码
    "QZ26080120516": {"clue_category": "督查检查考核", "clue_subcategory": "计划备案不规范/以调研名行考核实/打包报计划执行拆分"},
    
    # 26. FZ26080723362 - 街道违规主导业委会合并
    "FZ26080723362": {"clue_category": "权责不清/甩锅", "clue_subcategory": "清单外事项下放/签责任状转嫁/属地管理甩锅"},
    
    # 27. FZ26080623495 - 水务地下暗漏水费异议（数据造假）
    "FZ26080623495": {"clue_category": "数据造假", "clue_subcategory": "统计造假-指令报数/代填代报/虚假审批"},
    
    # 28. FZ26080621307 - 江南水都悦湖小区物业（数据造假）
    "FZ26080621307": {"clue_category": "数据造假", "clue_subcategory": "统计造假-指令报数/代填代报/虚假审批"},
    
    # 29. QZ26080620394 - 洪濑镇政府敷衍处置围墙问题
    "QZ26080620394": {"clue_category": "督查检查考核", "clue_subcategory": "计划备案不规范/以调研名行考核实/打包报计划执行拆分"},
    
    # 30. FJ26080620065 - 孤独症初筛任务数虚高强行赶进度
    "FJ26080620065": {"clue_category": "数据造假", "clue_subcategory": "统计造假-指令报数/代填代报/虚假审批"},
    
    # 31. XM26080620069 - 业委会选聘第三方屏蔽业主（证明事项滥设）
    "XM26080620069": {"clue_category": "权责不清/甩锅", "clue_subcategory": "证明事项滥设/万能证明/社区盖章"},
    
    # 32. FJ26080520164 - 违规占地12345推诿（甩锅）
    "FJ26080520164": {"clue_category": "权责不清/甩锅", "clue_subcategory": "清单外事项下放/签责任状转嫁/属地管理甩锅"},
    
    # 33. PI26080520053 - 物业强制人脸门禁采集生物信息（指尖多头建设）
    "PI26080520053": {"clue_category": "指尖形式主义", "clue_subcategory": "政务APP泛滥/未整合/僵尸应用/多头建设"},
    
    # 34. NP26080520011 - 林权证办证长期推诿（甩锅）
    "NP26080520011": {"clue_category": "权责不清/甩锅", "clue_subcategory": "清单外事项下放/签责任状转嫁/属地管理甩锅"},
    
    # 35. ND26080520005 - 公共厕所卫生差缺厕纸（指尖留痕）
    "ND26080520005": {"clue_category": "指尖形式主义", "clue_subcategory": "强制打卡/积分排名/在线时长/上传照片视频轨迹"},
    
    # 36. FZ26080423399 - 城管住建推诿仅转社区（甩锅）
    "FZ26080423399": {"clue_category": "权责不清/甩锅", "clue_subcategory": "清单外事项下放/签责任状转嫁/属地管理甩锅"},
    
    # 37. NP26080420469 - 卫生计生办开具证明推诿
    "NP26080420469": {"clue_category": "权责不清/甩锅", "clue_subcategory": "证明事项滥设/万能证明/社区盖章"},
    
    # 38. ND26080420146 - 加装电梯住建局多头推诿（指尖多头建设）
    "ND26080420146": {"clue_category": "指尖形式主义", "clue_subcategory": "政务APP泛滥/未整合/僵尸应用/多头建设"},
    
    # 39. XM26080323398 - 农田烧东西（会议/留痕）
    "XM26080323398": {"clue_category": "会议文件泛滥", "clue_subcategory": "文件会议过多/层层陪会"},
    
    # 40. FZ26080221734 - 智慧鼓楼平台越权拒派（指尖多头建设）
    "FZ26080221734": {"clue_category": "指尖形式主义", "clue_subcategory": "政务APP泛滥/未整合/僵尸应用/多头建设"},
    
    # 41. FZ26080221254 - 人社局12345履职不作避实就虚
    "FZ26080221254": {"clue_category": "督查检查考核", "clue_subcategory": "总量失控/多头重复/排名通报变相考核/县乡村考核未合并"},
}

# 读取并更新
with open('/home/c1/jianfu-tongbao/data/clues_test.json', 'r', encoding='utf-8') as f:
    clues = json.load(f)

updated = 0
for c in clues:
    tid = c['task_num']
    if tid in MAPPING:
        c['clue_category'] = MAPPING[tid]['clue_category']
        c['clue_subcategory'] = MAPPING[tid]['clue_subcategory']
        updated += 1
    else:
        print(f"⚠️ 无映射: {tid} - {c['clue_category']} | {c['clue_subcategory']}")

# 写回
with open('/home/c1/jianfu-tongbao/data/clues_test.json', 'w', encoding='utf-8') as f:
    json.dump(clues, f, ensure_ascii=False, indent=2)

print(f"\n✅ 已更新 {updated} 条线索")

# 统计分布
from collections import Counter
cat_counter = Counter(c['clue_category'] for c in clues)
sub_counter = Counter(c['clue_subcategory'] for c in clues)
print("\n📊 一级分类分布:")
for k, v in cat_counter.most_common():
    print(f"  {k}: {v}")
print("\n📊 细分类分布:")
for k, v in sub_counter.most_common():
    print(f"  {k}: {v}")

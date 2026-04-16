import json
from string import Template
from .simple_tools import safe_json_loads,get_result_path_from_state_uuid
import os
from .ParateraQwenClient import ParateraQwenClient
from ..remote_api.remote_api import getUnitSearchData,getUnitDimensionSearchData,getBasicUnitSearchData


# 通过一个unit找到与数据库中相匹配的unit
def unit_alignment(unit_to_align):
  client = ParateraQwenClient()
  basic_unit_data = getBasicUnitSearchData()
  basic_unit_data_map = basic_unit_data.get("data",{})
  basic_unit_content_list = []
  for basic_unit_uuid, basic_unit_info in basic_unit_data_map.items():
    basic_unit_content_list.append("{}[{}] -> {}".format(basic_unit_info.get("unit_name"),basic_unit_info.get("unit_symbol"),basic_unit_info.get("dimension_str")))
  prompt_1 = unit_analysis_prompt_template.substitute(input=unit_to_align,unit_table="\n".join(basic_unit_content_list))
  response = client.simple_chat(prompt_1)
  data = safe_json_loads(response)
  # print(data)
  dimensions = data.get("dimension", {})
  unit_list = getUnitSearchData(dimensions)
  # print(unit_list)
  unit_list = unit_list.get("data", {}).get("units", [])
  # 去掉里面所有的root_unit_symbol，conversion_factor'， conversion_offset
  for unit in unit_list:
    if "root_unit_symbol" in unit:
      del unit["root_unit_symbol"]
    if "conversion_factor" in unit:
      del unit["conversion_factor"]
    if "conversion_offset" in unit:
      del unit["conversion_offset"]
      
  prompt_2 =  prompt_template_for_unit_choose.substitute(unit_to_align=unit_to_align,candidates=json.dumps(unit_list, ensure_ascii=False))
  response_2 = client.simple_chat(prompt_2)
  data_2 = safe_json_loads(response_2)
  return data_2
  
    
unit_analysis_prompt_template = Template("""
你是一个【单位量纲计算器（严格模式）】。

你的唯一任务是：

根据输入单位 + 基础单位表，严格计算其 SI 量纲向量。

---

# 一、输入

单位：
$input

---

# 二、基础单位表（唯一可信来源）

$unit_table

格式示例：

W -> 功率 -> [L^2][M][T^-3]

m -> 长度 -> [L]

kg -> 质量 -> [M]

---

# 三、计算目标

输出该单位的 SI 基本量纲向量：

维度固定为 7 个：

- L（长度）
- M（质量）
- T（时间）
- I（电流）
- Theta（温度）
- N（物质的量）
- J（光强）

---

# 四、严格计算步骤（必须执行）

## Step 1：结构解析

解析输入单位结构：

- 乘法（· *）
- 除法 (/)
- 幂次（² ^2 ⁻¹ 等）
- 括号

---

## Step 2：单位展开

将所有单位替换为基础单位表达式：

例如：

W → [L^2][M][T^-3]
m² → [L^2]
sr → [1]（无量纲）

---

## Step 3：指数运算

规则：

- 乘法 → 指数相加
- 除法 → 指数相减
- 幂 → 指数乘法

---

## Step 4：合并为最终量纲向量

必须输出完整 7 维向量。

---

# 五、强约束（非常重要）

## 1. 禁止猜测维度

- 不允许根据名称补维度
- 不允许“联想补全”

---

## 2. 未出现的维度必须为 0

例如：

如果没有光强相关内容：

J 必须是 0

---

## 3. 不允许遗漏字段

必须输出完整结构：

L, M, T, I, Theta, N, J

---

## 4. sr 处理规则

- sr = 无量纲 = [1]
- 不影响任何维度

---

## 5. 输出必须严格 JSON

---

# 六、输出格式

{
  "unit_analysis": "",
  "dimension": {
    "L": 0,
    "M": 0,
    "T": 0,
    "I": 0,
    "Theta": 0,
    "N": 0,
    "J": 0
  }
}

---

# 七、禁止行为

- ❌ 不允许输出解释
- ❌ 不允许输出额外字段
- ❌ 不允许漏维度
- ❌ 不允许猜测维度
- ❌ 不允许基于名称推断物理量

""")
    
    
    
prompt_template_for_unit_choose = Template("""
你是一个【单位语义选择与归一化计算器】。

你的任务是：

在同一量纲的候选单位中，选择一个最合适的目标单位，并计算 scale。

---

# 输入

unit_to_align：
$unit_to_align

---

候选单位列表：

$candidates

---

# 输出目标

返回：

- analysis
- target_uuid（可为 None）
- scale（float）

---

# 核心定义（非常重要）

统一采用以下严格定义：

unit_to_align = scale × target_unit

也就是说：

👉 scale 表示：target_unit 相对于 unit_to_align 的缩放系数  
👉 不允许反向解释  
👉 不允许自行改变方向

---

# 选择规则

1. 在候选中选择一个最合适的 target_uuid

2. 选择依据：
   - 语义表达最自然
   - 最常见的单位形式优先（国际单位制优先）
   - 数值表达更稳定（避免极端大/小尺度优先）

3. 如果 unit_to_align 本身在候选中：
   - 直接选择自身
   - scale = 1.0

---

# scale 计算规则（严格）

由定义：

unit_to_align = scale × target_unit

因此：

scale = unit_to_align ÷ target_unit

注意：
- 必须按照该方向计算
- 不允许反向
- 不允许猜测单位换算方向

---

# 限制

- 只能选择一个 target_uuid
- scale 必须是 float
- 不允许使用候选之外的信息
- 不允许返回多个结果
- 不允许改变公式方向

---

# 输出格式（严格 JSON）

{
  "analysis": "",
  "target_uuid": "string or None",
  "scale": float
}

---

# analysis 要求

必须说明：

- 为什么选择该 target_unit
- 为什么不选其他单位
- scale 如何由公式计算（必须写清公式代入过程）
""")

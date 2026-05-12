import re
from typing import List, Dict, Any
import os
import json
from string import Template
from .ParateraQwenClient import ParateraQwenClient
from .simple_tools import normalize_html_whitespace, extract_first_n_trs, strip_code_fence, get_result_path_from_state_uuid, safe_json_loads,get_first_n_json_records
from ..models import *
from collections import defaultdict
from .compound_alignment import align_compound
from .phase_alignment import phase_alignment
from .unit_alignment import unit_alignment
from .property_variable_alignment import property_variable_alignment



def data_alignment_util(prev_uuid):
    data_layer_split_result_dir = get_result_path_from_state_uuid(prev_uuid,"data_layer_split")
    data_layer_split_result_file = os.path.join(data_layer_split_result_dir, "devided_dataset.json")  
    with open(data_layer_split_result_file, "r") as f:
        data_layer_split_result = json.load(f)
    # print(data_layer_split_result_file)
    
    compound_set = set()
    property_name_description_item_map = {}
    variable_name_description_item_map = {}
    phase_name_description_item_map = {}
    configurations_name_description_item_map = {}
    for item in data_layer_split_result:
        experiment_phase_info = item.get("experiment_phase_info", {})
        if experiment_phase_info.get("name","") != "":
            phase_str = "{}: {}".format(experiment_phase_info.get("name",""), experiment_phase_info.get("brief_description",""))
            if phase_str not in phase_name_description_item_map:
                phase_name_description_item_map[phase_str] = []
            phase_name_description_item_map[phase_str].append(experiment_phase_info)
        final_datasets = item.get("final_datasets", [])
        for dataset in final_datasets:
            compounds = dataset.get("compounds", [])
            for compound in compounds:
                compound_set.add(compound)
            variable_headers = dataset.get("variable_headers", [])
            for variable_header in variable_headers:
                variable_name = variable_header.get("name","")
                variable_description = variable_header.get("description","")
                variable_str = "{}: {}".format(variable_name, variable_description)
                if variable_str not in variable_name_description_item_map:
                    variable_name_description_item_map[variable_str] = []
                variable_name_description_item_map[variable_str].append(variable_header)
                
            property_headers = dataset.get("property_headers", [])
            for property_header in property_headers:
                property_name = property_header.get("name","")
                property_description = property_header.get("description","")
                property_str = "{}: {}".format(property_name, property_description)
                if property_str not in property_name_description_item_map:
                    property_name_description_item_map[property_str] = []
                property_name_description_item_map[property_str].append(property_header)
                
            configurations = dataset.get("configurations", [])
            for configuration in configurations:
                configuration_name = configuration.get("name","")
                configuration_description = configuration.get("description","")
                configuration_str = "{}: {}".format(configuration_name, configuration_description)
                if configuration_str not in configurations_name_description_item_map:
                    configurations_name_description_item_map[configuration_str] = []
                configurations_name_description_item_map[configuration_str].append(configuration)
                
    compound_alignment_result = compound_alignment_function(compound_set)
    phase_alignment_result = phase_alignment_function(phase_name_description_item_map)
    property_alignment_result = property_alignment_function(property_name_description_item_map)
    variable_alignment_result = variable_alignment_function(variable_name_description_item_map)
    configuration_alignment_result = configuration_alignment_function(configurations_name_description_item_map)
    
    # 将对齐后的数据与原数据进行填充
    # 先填充compounds
    for item in data_layer_split_result:
        final_datasets = item.get("final_datasets", [])
        for dataset in final_datasets:
            compounds = dataset.get("compounds",[])
            aligned_compounds = {}
            for compound in compounds:
                aligned_compound = compound_alignment_result.get(compound,{})
                aligned_compounds[compound] = aligned_compound
            dataset["aligned_compounds"] = aligned_compounds
    # 填充相态
    for key, aligned_phase in phase_alignment_result.items():
        phase_items = phase_name_description_item_map.get(key,[])
        for phase_item in phase_items:
            phase_item["aligned_phase"] = aligned_phase
    # 填充物性
    for key, aligned_property_info in property_alignment_result.items():
        property_items = property_name_description_item_map.get(key,[])
        for property_item in property_items:
            property_item["origin_unit"] = aligned_property_info.get("origin_unit","")
            property_item["aligned_unit"] = aligned_property_info.get("aligned_unit",{})
            property_item["aligned_property"] = aligned_property_info.get("aligned_property",{})
    # 填充变量
    for key, aligned_variable_info in variable_alignment_result.items():
        variable_items = variable_name_description_item_map.get(key,[])
        for variable_item in variable_items:
            variable_item["origin_unit"] = aligned_variable_info.get("origin_unit","")
            variable_item["aligned_unit"] = aligned_variable_info.get("aligned_unit",{})
            variable_item["aligned_variable"] = aligned_variable_info.get("aligned_variable",{})
    # 填充配置项
    for key, aligned_configuration_info in configuration_alignment_result.items():
        configuration_items = configurations_name_description_item_map.get(key,[])
        for configuration_item in configuration_items:
            configuration_item["origin_unit"] = aligned_configuration_info.get("origin_unit","")
            configuration_item["aligned_unit"] = aligned_configuration_info.get("aligned_unit",{})
            configuration_item["aligned_variable"] = aligned_configuration_info.get("aligned_variable",{})
    return data_layer_split_result
    
    
    
        
    
# 组分对齐    
def compound_alignment_function(compound_set):
    compound_alignment_result = {}
    for compound in compound_set:
        try:
            aligned_compound = align_compound(compound)
            compound_alignment_result[compound] = aligned_compound
        except Exception as e:
            print(f"Error aligning compound {compound}: {e}")
            compound_alignment_result[compound] = {}
    return compound_alignment_result

# 相态对齐
def phase_alignment_function(phase_name_description_item_map):
    phase_alignment_result = {}
    for phase_str, phase_items in phase_name_description_item_map.items():
        try:
            first_phase_item = phase_items[0]
            aligned_phase = phase_alignment({"phase_name":first_phase_item.get("name",""), "phase_description":first_phase_item.get("brief_description","")})
            phase_alignment_result[phase_str] = aligned_phase
        except Exception as e:
            print(f"Error aligning phase {phase_str}: {e}")
            phase_alignment_result[phase_str] = {}
    return phase_alignment_result

# 物性对齐
def property_alignment_function(property_name_description_item_map):
    client = ParateraQwenClient()
    property_alignment_result = {}
    for property_str, property_items in property_name_description_item_map.items():
        try:
            first_property_item = property_items[0]
            raw_header_name = first_property_item.get("raw_header_name","")
            description = first_property_item.get("description","")
            name = first_property_item.get("name","")
            unti_extract_prompt = prompt_template_extract_unit.substitute(input=json.dumps({"raw_header_name": raw_header_name, "description": description, "name": name}, ensure_ascii=False))
            response = client.simple_chat(unti_extract_prompt)
            response_json = safe_json_loads(response)
            unit = response_json.get("unit","")
            align_result = {}
            align_result["origin_unit"] = unit
            align_result["aligned_unit"] = unit_alignment(unit)
            property_align_data = {
                "alignment_type":"property",
                "unit": unit,
                "property_name" : name,
                "property_description": description
            }
            align_result["aligned_property"] = property_variable_alignment(property_align_data)
            property_alignment_result[property_str] = align_result
        except Exception as e:
            print(f"Error aligning property {property_str}: {e}")
            property_alignment_result[property_str] = {}
    return property_alignment_result
        
        
# 变量对齐
def variable_alignment_function(variable_name_description_item_map):
    client = ParateraQwenClient()
    variable_alignment_result = {}
    for variable_str, variable_items in variable_name_description_item_map.items():
        try:
            first_variable_item = variable_items[0]
            raw_header_name = first_variable_item.get("raw_header_name","")
            description = first_variable_item.get("description","")
            name = first_variable_item.get("name","")
            unit_extract_prompt = prompt_template_extract_unit.substitute(input=json.dumps({"raw_header_name": raw_header_name, "description": description, "name": name}, ensure_ascii=False))
            response = client.simple_chat(unit_extract_prompt)
            response_json = safe_json_loads(response)
            unit = response_json.get("unit","")
            align_result = {}
            align_result["origin_unit"] = unit
            align_result["aligned_unit"] = unit_alignment(unit)
            property_align_data = {
                "alignment_type":"variable",
                "unit": unit,
                "variable_name" : name,
                "variable_description": description
            }
            align_result["aligned_variable"] = property_variable_alignment(property_align_data)
            variable_alignment_result[variable_str] = align_result
        except Exception as e:
            print(f"Error aligning variable {variable_str}: {e}")
            variable_alignment_result[variable_str] = {}
    return variable_alignment_result


# 配置项对齐
def configuration_alignment_function(configurations_name_description_item_map):
    client = ParateraQwenClient()
    configuration_alignment_result = {}
    for configuration_str, configuration_items in configurations_name_description_item_map.items():
        try:
            first_configuration_item = configuration_items[0]
            name = first_configuration_item.get("name","")
            description = first_configuration_item.get("description","")
            value = first_configuration_item.get("value","")
            unit = first_configuration_item.get("unit","")
            config_determine_prompt = prompt_template_for_config_determine.substitute(name=name, description=description, value=value, unit=unit)
            response = client.simple_chat(config_determine_prompt)
            determine_result = safe_json_loads(response)
            variable_flag = determine_result.get("variable_flag", False)
            if not variable_flag:
                configuration_alignment_result[configuration_str] = {}
                continue
            align_result = {}
            origin_unit = determine_result.get("unit","")
            align_result["origin_unit"] = origin_unit
            align_result["aligned_unit"] = unit_alignment(origin_unit)
            variable_align_data = {
                "alignment_type":"variable",
                "unit": origin_unit,
                "variable_name" : name,
                "variable_description": description
            }
            align_result["aligned_variable"] = property_variable_alignment(variable_align_data)
            configuration_alignment_result[configuration_str] = align_result
            
        except Exception as e:
            print(f"Error aligning configuration {configuration_str}: {e}")
            configuration_alignment_result[configuration_str] = {}
    return configuration_alignment_result





prompt_template_extract_unit = Template("""
你是一个数据字段解析助手，需要从给定字段信息中提取“单位（unit）”。

输入是一个 JSON 对象，包含以下字段：
- raw_header_name: 原始字段名（可能包含单位）
- description: 字段描述（可能包含单位）
- name: 标准化字段名（可能包含单位，如 pressure_MPa）

----------------------------------------
你的任务：提取该字段的“单位 unit”
----------------------------------------

## 判断优先级：

1. 优先从 raw_header_name 提取：
   - 如果包含括号，例如 (MPa)、(kg/m3)、(°C)，提取括号内内容

2. 如果 raw_header_name 没有单位，则从 name 提取：
   - 例如 pressure_MPa → MPa
   - density_kg_m3 → kg/m3
   - m_per_s → m/s
   - km_h → km/h

3. 如果仍未找到，则从 description 推断

4. 如果是无量纲变量（比例、分数、系数、标志位等）：
   - 返回 "1" 或 "%"

5. 如果无法判断：
   - 返回 ""

----------------------------------------
## ⚠️ 输出强约束（非常重要）

你必须严格返回 JSON，且只能返回 JSON，不允许任何解释、换行或额外文本。

格式如下：

{
  "unit": "MPa"
}

或

{
  "unit": ""
}

----------------------------------------
## 🚫 禁止行为：

- 不允许输出解释
- 不允许输出句子
- 不允许输出 Markdown
- 不允许输出多个字段
- 不允许输出除 JSON 外任何字符

----------------------------------------
输入数据：

$input

输出：
""")

prompt_template_for_config_determine = Template("""
你是一个石油化工实验数据解析助手。

我会提供一个配置项，包含以下字段：
- name: 参数名称
- description: 参数描述
- value: 参数值
- unit: 原始单位（可能为空）

你的任务是判断该配置项是否为“可量化变量”，并提取合理单位。

判断规则：
1. 如果该参数表示实验条件中的“可测量物理量”（例如温度、压力、浓度、密度、时间等），则：
   - variable_flag = true
   - 且 value 应该可以是数值（或数值形式字符串）
2. 如果该参数只是“实验说明、方法、参考文献、类别描述等”，不可量化，则：
   - variable_flag = false

单位提取规则：
1. 优先从 value 或 description 中识别单位
2. 如果给定的 unit 合理，可以直接使用
3. 如果是无量纲（例如比例、分数等），可使用：
   - "1" 或 "%"
4. 如果确实没有单位，则返回空字符串 ""

⚠️ 注意：
- 不要输出任何解释
- 只返回 JSON
- JSON 格式必须严格如下：

{
  "variable_flag": true/false,
  "unit": ""
}

以下是输入：

name: $name
description: $description
value: $value
unit: $unit

请给出结果：
""")
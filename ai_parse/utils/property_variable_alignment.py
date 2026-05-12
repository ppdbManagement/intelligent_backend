import json
from string import Template
from .simple_tools import safe_json_loads,get_result_path_from_state_uuid
import os
from .ParateraQwenClient import ParateraQwenClient
from ..remote_api.remote_api import getPropertySearchByUnit,getVariableSearchByUnit
from .unit_alignment import unit_alignment

def property_alignment(data_to_align):
    client = ParateraQwenClient()
    unit = data_to_align.get("unit","")
    property_name = data_to_align.get("property_name","")
    property_description = data_to_align.get("property_description","")
    if unit == "":
        # 先用property_name和property_description生成可能的单位
        prompt_1 = prompt_template_for_unit_generate.substitute(property_name=property_name,property_description=property_description)
        response = client.simple_chat(prompt_1)
        unit = response.strip()
    # 进行单位对齐
    aligned_unit = unit_alignment(unit)
    # print(f"原始单位：{unit}，对齐后的单位：{aligned_unit}")
    target_uuid = aligned_unit.get("target_uuid","")
    if target_uuid != "" and aligned_unit is not None:
        response = getPropertySearchByUnit(target_uuid)
        # 使用大模型，挑选出最合适的物性uuid
        data = response.get("data",{})
        properties = data.get("properties",[])
        property_str_list = []
        for prop in properties:
            prop_name = prop.get("name","")
            prop_name_en = prop.get("name_en","")
            prop_description = prop.get("description","")
            prop_uuid = prop.get("uuid","")
            prop_name_to_show = prop_name_en if prop_name_en != "" else prop_name
            property_str_list.append(
                "{} => {}: {}".format(prop_uuid,prop_name_to_show,prop_description)
            )
        property_str = "\n".join(property_str_list)
        property_to_align = {
            "name": property_name,
            "description": property_description,
            "unit": unit
        }
        prompt_2 = prompt_template_for_property_align.substitute(property_content=json.dumps(property_to_align,ensure_ascii=False),candidates=property_str)
        response_2 = client.simple_chat(prompt_2)
        response_2_json = safe_json_loads(response_2)
        return response_2_json
    else:
        return {
            "analysis": "无法对齐到任何单位，无法进行物性匹配",
            "target_uuid": ""
        }

        


def variable_alignment(data_to_align):
    client = ParateraQwenClient()
    unit = data_to_align.get("unit","")
    variable_name = data_to_align.get("variable_name","")
    variable_description = data_to_align.get("variable_description","")
    if unit == "":
        # 先用variable_name和variable_description生成可能的单位
        prompt_1 = prompt_template_for_condition_unit_generate.substitute(condition_name=variable_name,condition_description=variable_description)
        response = client.simple_chat(prompt_1)
        unit = response.strip()
    # 进行单位对齐
    aligned_unit = unit_alignment(unit)
    target_uuid = aligned_unit.get("target_uuid","")
    if target_uuid != "" and aligned_unit is not None:
        response = getVariableSearchByUnit(target_uuid)
        # 使用大模型，挑选出最合适的变量uuid
        data = response.get("data",{})
        variables = data.get("variables",[])
        variable_str_list = []
        for var in variables:
            var_name = var.get("name","")
            var_name_en = var.get("name_en","")
            var_description = var.get("description","")
            var_uuid = var.get("uuid","")
            var_name_to_show = var_name_en if var_name_en != "" else var_name
            variable_str_list.append(
                "{} => {}: {}".format(var_uuid,var_name_to_show,var_description)
            )
        variable_str = "\n".join(variable_str_list)
        variable_to_align = {
            "name": variable_name,
            "description": variable_description,
            "unit": unit
        }
        prompt_2 = prompt_template_for_condition_align.substitute(condition_content=json.dumps(variable_to_align,ensure_ascii=False),candidates=variable_str)
        response_2 = client.simple_chat(prompt_2)
        response_2_json = safe_json_loads(response_2)
        return response_2_json
    else:
        return {
            "analysis": "无法对齐到任何单位，无法进行变量匹配",
            "target_uuid": ""
        }

def property_variable_alignment(data_to_align):
    alignment_type = data_to_align.get("alignment_type","")
    if alignment_type == "property":
        return property_alignment(data_to_align)
    elif alignment_type == "variable":
        return variable_alignment(data_to_align)
    else:
        return None
    
    
    
    
prompt_template_for_unit_generate = Template("""
你是一个专门做物理量维度分析的科学助手。

任务：
根据给定的物性名称和物性描述，判断它对应的 SI 标准单位。

规则：
1. 只能输出一个 SI 单位，不要解释，不要输出任何多余内容。
2. 如果该物性是无量纲的，请返回 "1"。
3. 使用标准 SI 单位（例如：m, kg, s, A, K, mol, cd, N, Pa, J, W, Hz, C, V, Ω 等）。
4. 优先使用 SI 导出单位（例如用 Pa 而不是 kg·m⁻¹·s⁻²）。
5. 如果存在多个可能单位，请选择最常用、最标准的 SI 表达方式。

输入：
物性名称：$property_name
物性描述：$property_description

输出：
""")

prompt_template_for_property_align = Template("""
你是一个专业的物性匹配与分类助手。

任务：
根据输入的“物性描述内容”，从候选项中选择最匹配的一个 UUID。

规则：
1. 仔细理解物性内容的物理含义、适用范围和定义。
2. 在候选项中选择“最匹配”的一个 UUID。
3. 如果所有候选项都不匹配，请返回空字符串 "" 作为 target_uuid。
4. 必须输出严格 JSON，不要输出任何额外文字、解释或 Markdown。

输出格式必须严格如下：
{
  "analysis": "你对物性的简要分析，以及为什么选择该 UUID（或为什么无法匹配）",
  "target_uuid": "选中的 UUID 或空字符串"
}

输入：
物性内容：
$property_content

候选项：
$candidates

输出：
""")

prompt_template_for_condition_unit_generate = Template("""
你是一个专门做实验条件物理量维度分析的科学助手。

任务：
根据给定的“实验条件名称”和“实验条件描述”，判断其对应的 SI 标准单位。

规则：
1. 只能输出一个 SI 单位，不要解释，不要输出任何多余内容。
2. 如果该实验条件是无量纲的，请返回 "1"。
3. 使用标准 SI 单位（例如：m, kg, s, A, K, mol, cd, N, Pa, J, W, Hz, C, V, Ω 等）。
4. 优先使用 SI 导出单位（例如用 Pa 而不是 kg·m⁻¹·s⁻²）。
5. 如果存在多个可能单位，请选择最常用、最标准的 SI 表达方式。
6. 实验条件通常包括：温度、压力、时间、流量、浓度、湿度、速度、功率等物理环境变量。

输入：
实验条件名称：$condition_name
实验条件描述：$condition_description

输出：
""")

prompt_template_for_condition_align = Template("""
你是一个专业的实验条件匹配与分类助手。

任务：
根据输入的“实验条件描述内容”，从候选项中选择最匹配的一个 UUID。

规则：
1. 仔细理解实验条件的物理意义（如温度、压力、湿度、流速、时间等）。
2. 在候选项中选择“最匹配”的一个 UUID。
3. 如果所有候选项都不匹配，请返回空字符串 "" 作为 target_uuid。
4. 必须输出严格 JSON，不要输出任何额外文字、解释或 Markdown。

输出格式必须严格如下：
{
  "analysis": "你对实验条件的简要分析，以及为什么选择该 UUID（或为什么无法匹配）",
  "target_uuid": "选中的 UUID 或空字符串"
}

输入：
实验条件内容：
$condition_content

候选项：
$candidates

输出：
""")
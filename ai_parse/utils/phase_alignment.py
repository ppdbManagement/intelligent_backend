
import json
from string import Template
from .simple_tools import safe_json_loads,get_result_path_from_state_uuid
import os
from .ParateraQwenClient import ParateraQwenClient
from ..remote_api.remote_api import getPhaseSearch

def phase_alignment(phase_to_alignment):
    phase_name = phase_to_alignment.get("phase_name")
    phase_description = phase_to_alignment.get("phase_description")
    phase_search = getPhaseSearch()
    phase_search_result = phase_search.get("data",{}).get("phases",[])
    phase_str_list = []
    for phase in phase_search_result:
        phase_str_list.append(
            "{} => {}: {}".format(phase.get("uuid",""), phase.get("name",""), phase.get("description",""))
        )
    phase_candidates = "\n".join(phase_str_list)
    prompt = prompt_template_for_phase_align.substitute(
        phase_name=phase_name,
        phase_description=phase_description,
        phase_candidates=phase_candidates
    )
    client = ParateraQwenClient()
    response = client.simple_chat(prompt)
    response_json = safe_json_loads(response)
    return response_json



prompt_template_for_phase_align = Template("""
你是一个专业的相态（phase）匹配与分类助手。

任务：
根据输入的“相态名称”和“相态描述”，从候选相态中选择最匹配的一个 UUID。

相态通常包括但不限于：
固态、液态、气态、超临界流体、等离子体、多相流、晶相、非晶相等。

规则：
1. 仔细理解相态的物理含义、结构特征与存在条件。
2. 在候选项中选择“最匹配”的一个 UUID。
3. 如果所有候选项都不匹配，请返回空字符串 "" 作为 target_uuid。
4. 必须输出严格 JSON，不要输出任何额外文字、解释或 Markdown。

输出格式必须严格如下：
{
  "analysis": "你对相态的简要分析，以及为什么选择该 UUID（或为什么无法匹配）",
  "target_uuid": "选中的 UUID 或空字符串"
}

输入：
相态名称：
$phase_name

相态描述：
$phase_description

候选项：
$phase_candidates

输出：
""")
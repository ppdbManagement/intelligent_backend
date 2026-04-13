import re
from typing import List, Dict, Any
import os
import json
from string import Template
from .ParateraQwenClient import ParateraQwenClient
from .simple_tools import normalize_html_whitespace, extract_first_n_trs, strip_code_fence, get_result_path_from_state_uuid, safe_json_loads,get_first_n_json_records
from ..models import *
from collections import defaultdict


def extract_columns(data, cols):
    return [[row[i] for i in cols] for row in data]


def extract_column_except_columns(data, cols):
    return [[row[i] for i in range(len(row)) if i not in cols] for row in data]


def cluster_by_columns(data, col_indices):
    """
    根据指定的多个列的组合值对二维数组进行聚类。

    参数:
        data (list of list): 二维数组，每一行是一个列表。
        col_indices (list of int): 需要用于聚类的列索引列表。

    返回:
        list of list of list: 三维数组，每个子列表包含在指定列上具有相同值组合的所有行。
    """
    clusters = defaultdict(list)

    for row in data:
        # 提取用于聚类的键：将指定列的值组成一个元组（可哈希）
        key = tuple(row[i] for i in col_indices)
        clusters[key].append(row)

    # 返回所有聚类组（顺序不保证；如需排序可进一步处理）
    return list(clusters.values())


def cluster_table_data_util(prev_uuid):
    context_extract_result_dir = get_result_path_from_state_uuid(prev_uuid,"context_extract")
    context_extract_result_path = os.path.join(context_extract_result_dir,"context_data.json")
    with open(context_extract_result_path,"r") as f:
        context_extract_result = json.load(f)
    # 先确认组分定义来源（header/configuration/raw），并进行相应的清洗和标注
    context_extract_result = determine_cluster_compounds_definitions(context_extract_result)
    cluster_table_data =  cluster_table_data_rows(context_extract_result)
    return replace_header_name_key(cluster_table_data)
    
    
# 把cluster_table_data里面headers里面所有的header_name这个key替换为name
def replace_header_name_key(cluster_table_data):
    for table_part in cluster_table_data:
        datasets = table_part.get("datasets", [])
        for dataset in datasets:
            headers = dataset.get("headers", [])
            for header in headers:
                if "header_name" in header:
                    header["name"] = header.get("header_name", "")
                    del header["header_name"]
    return cluster_table_data
    
    
def cluster_table_data_rows(context_extract_result):
    clustered_data = []
    for table_part in context_extract_result:
        # 这些是这个table共有的信息
        new_table_part = {}
        table_uuid = table_part.get("table_uuid", "")
        caption = table_part.get("caption", "")
        related_experiment_setting_segments = table_part.get(
            "related_segments", [])
        # 填充共有信息
        new_table_part["table_uuid"] = table_uuid
        new_table_part["caption"] = caption
        new_table_part["related_experiment_setting_segments"] = related_experiment_setting_segments
        #

        # 处理table的compounds
        compounds_define = table_part.get("compounds_define", {})
        # 情况1：compounds在header中定义，
        if compounds_define.get("compounds_define_source") == "header":
            # 说明是从header中定义的compounds，需要根据header的数据进行聚合
            compounds_ref_header_name = compounds_define.get(
                "compounds_ref_header_name", "")
            # 找到对应的header index
            headers = table_part.get("header", [])
            header_index = -1
            for idx, header in enumerate(headers):
                if header.get("name", "") == compounds_ref_header_name:
                    header_index = idx
                    break
            if header_index == -1:
                # 没有找到对应的header，直接跳过
                continue
            # 根据header index进行聚合
            data_rows = table_part.get("data", [])
            quantitative_experimental_configurations = table_part.get(
                "quantitative_experimental_configurations", [])
            clustered_rows = cluster_by_columns(data_rows, [header_index])
            datasets = []
            for cluster in clustered_rows:
                # 需要抽取出compound name，并且header和data rows需要移除这一列
                compound_name = cluster[0][header_index]
                reduced_headers = extract_column_except_columns(
                    [headers], [header_index])[0]
                reduced_data_rows = extract_column_except_columns(
                    cluster, [header_index])
                dataset = {
                    "compounds": [compound_name],
                    "headers": reduced_headers,
                    "data_rows": reduced_data_rows,
                    "configurations": quantitative_experimental_configurations
                }
                datasets.append(dataset)
            new_table_part["datasets"] = datasets

        elif compounds_define.get("compounds_define_source") == "configuration":
            # 说明是从configuration中定义的compounds，也不需要特殊处理
            datasets = []
            headers = table_part.get("header", [])
            data_rows = table_part.get("data", [])
            quantitative_experimental_configurations = table_part.get(
                "quantitative_experimental_configurations", [])
            compounds = compounds_define.get("compounds", [])
            dataset = {
                "compounds": compounds,
                "headers": headers,
                "data_rows": data_rows,
                "configurations": quantitative_experimental_configurations
            }
            datasets.append(dataset)
            new_table_part["datasets"] = datasets

        else:
            # 说明直接使用的raw compounds，不需要额外处理
            datasets = []
            headers = table_part.get("header", [])
            data_rows = table_part.get("data", [])
            dataset = {
                "compounds": compounds_define.get("compounds", []),
                "headers": headers,
                "data_rows": data_rows,
                "configurations": table_part.get("quantitative_experimental_configurations", [])
            }
            datasets.append(dataset)
            new_table_part["datasets"] = datasets
        clustered_data.append(new_table_part)
    return clustered_data
    
    
    
def determine_cluster_compounds_definitions(context_extract_result):
    llm_client = ParateraQwenClient()
    for table_part in context_extract_result:
        headers = table_part["header"]
        compounds_ref_header_name = table_part["compounds_ref_header_name"]
        raw_compounds = table_part["compounds"]
        quantitative_experimental_configurations = table_part.get(
            "quantitative_experimental_configurations", {})
        data_preview = table_part.get("data_preview", [])
        # 1. 先从header里面找
        prompt_1 = determine_compounds_from_headers_prompt.substitute(
            enhanced_table_headers=json.dumps(headers, ensure_ascii=False, indent=2),
            table_data_rows_preview=json.dumps(data_preview, ensure_ascii=False, indent=2),
            compounds_ref_header_name=compounds_ref_header_name
        )
        response_1 = llm_client.simple_chat(user_message=prompt_1)
        response_1_json = safe_json_loads(response_1)
        header_compounds_name = response_1_json.get("name", "").strip()
        
        # 2. 再从configuration里面找
        prompt_2 = extract_participating_compounds_config_prompt.substitute(
            quantitative_experimental_configurations=json.dumps(
                quantitative_experimental_configurations, indent=2, ensure_ascii=False),
        )
        response_2 = llm_client.simple_chat(user_message=prompt_2)
        response_2_json = safe_json_loads(response_2)
        config_compounds_name = response_2_json.get("names", [])
        config_compounds_compounds = response_2_json.get("compounds", [])
        compounds_define = {}
        if header_compounds_name:
            compounds_define["compounds_ref_header_name"] = header_compounds_name
            compounds_define["compounds_define_source"] = "header"
            if len(config_compounds_name) != 0:
                # 去除quantitative_experimental_configurations里面的冗余
                filtered_configurations = []
                for config in quantitative_experimental_configurations:
                    if config["name"] not in config_compounds_name:
                        filtered_configurations.append(config)
                table_part["quantitative_experimental_configurations"] = filtered_configurations
        elif len(config_compounds_name) != 0:
            compounds_define["compounds_ref_config_names"] = config_compounds_name
            compounds_define["compounds_define_source"] = "configuration"
            compounds_define["compounds"] = config_compounds_compounds
            # 去除quantitative_experimental_configurations里面的冗余
            filtered_configurations = []
            for config in quantitative_experimental_configurations:
                if config["name"] not in config_compounds_name:
                    filtered_configurations.append(config)
            table_part["quantitative_experimental_configurations"] = filtered_configurations
        else:
            compounds_define["compounds_define_source"] = "raw"
            compounds_define["compounds"] = raw_compounds
        table_part["compounds_define"] = compounds_define
    return context_extract_result
        
        
        
        
determine_compounds_from_headers_prompt = Template("""
You are an expert in scientific table header interpretation.

Your task is to determine whether the table headers explicitly state
which chemical compounds participate in the experiment.

---

### Inputs

1. enhanced_table_headers:
$enhanced_table_headers

2. table_data_rows_preview (for reference only, do NOT infer compounds from numbers):
$table_data_rows_preview

3. candidate_compounds_ref_header_name (may be empty):
$compounds_ref_header_name

---

### Definition (VERY IMPORTANT)

A header explicitly defines participating compounds ONLY IF:
- It directly names the compounds involved in the experiment
  (e.g., "Carbon dioxide–methane mixture", "Binary system of A and B",
   "Isobutane + Squalane system").

The following do NOT count:
- Composition / mole fraction / mass fraction / ratio
- Single-compound fraction (e.g., "x_methane")
- Indirect/statistical implication
- Any inference from numerical values

---

### Decision Strategy

Step 1 — Validate candidate (if provided):
- If `candidate_compounds_ref_header_name` is NOT empty:
  - Check whether it EXISTS in the headers AND satisfies the definition above.
  - If YES → select it.
  - If NO → ignore it and continue to Step 2.

Step 2 — Search all headers:
- Examine all headers.
- If ONE OR MORE headers explicitly define participating compounds:
  - Select the MOST representative one.

Step 3 — Fallback:
- If NONE qualify → return empty string.

---

### Output (JSON ONLY)

{
  "name": ""
}

Return ONLY valid JSON. Do not include explanations.
""")

extract_participating_compounds_config_prompt = Template("""
You are an expert in experimental metadata parsing.

Your task is to extract information from quantitative experimental configurations
that explicitly state WHICH chemical compounds participate in the experiment.

### Input
quantitative_experimental_configurations:
$quantitative_experimental_configurations

---

### Core Criterion

A configuration SHOULD be selected IF AND ONLY IF:
- It explicitly declares the participating chemical compounds in the experiment.
- It answers the question: "What substances are involved in this experiment?"

A configuration SHOULD NOT be selected IF:
- It describes composition, fraction, ratio, concentration, or content
  as a variable or parameter (i.e., "how much of each component is present")  
- UNLESS it declares a PURE SUBSTANCE (see exception below)

### Important Exception

- If a configuration describes the system as a PURE SUBSTANCE
  (e.g., "pure carbon dioxide", "the system consists of methane"),
  it MUST be selected as defining participating compounds,
  even if the configuration name or wording includes the term "composition".

---

### Task
1. Examine each configuration independently.
2. Identify ALL configurations that explicitly declare participating compounds.
3. Collect:
   - `names`: the `name` field of such configurations
   - `compounds`: the chemical compound names explicitly mentioned
4. If NO configuration qualifies:
   - Return empty lists for BOTH `names` and `compounds`.

---

### Output Rules (STRICT)
- If `names` is empty, `compounds` MUST also be an empty list.
- Do NOT infer or normalize compound names.
- Use ONLY compounds explicitly stated in the configurations.

---

### Output (JSON ONLY)
{
  "names": [],
  "compounds": []
}

Return ONLY valid JSON. Do not include explanations.
""")
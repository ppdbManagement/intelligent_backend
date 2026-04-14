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


def devide_dataset_util(clustered_table_data):
    # 抽取实验的相态信息
    clustered_data = extract_experiment_phase_info(clustered_table_data)
    # 增强表头的组分关系
    clustered_data = enhance_table_header_component_relationships(
        clustered_data)
    final_datasets = further_divide_dataset_info(clustered_data)
    return final_datasets
    
    
    
    
def extract_experiment_phase_info(clustered_data):
    llm_client = ParateraQwenClient()
    for table_part in clustered_data:
        table_caption = table_part.get("caption", "")
        table_related_segments = table_part.get(
            "related_experiment_setting_segments", [])
        prompt = user_prompt_for_phase_extraction.substitute(
            table_caption=table_caption,
            related_text=json.dumps(table_related_segments, ensure_ascii=False)
        )
        response = llm_client.simple_chat(user_message=prompt)
        phase_info = safe_json_loads(response)
        table_part["experiment_phase_info"] = phase_info.get("phase", {})
    return clustered_data

def enhance_table_header_component_relationships(clustered_data):
    llm_client = ParateraQwenClient()
    for table_part in clustered_data:
        caption = table_part.get("caption", "")
        # 遍历里面的datasets
        for dataset in table_part.get("datasets", []):
            compounds = dataset.get("compounds", [])
            headers = dataset.get("headers", [])
            configurations = dataset.get("configurations", [])
            brief_headers = [{"name": h.get("name", ""), "description": h.get(
                "description", "")} for h in headers]
            brief_configurations = [{"name": c.get("name", ""), "description": c.get(
                "description", "")} for c in configurations]

            prompt_1 = user_prompt_for_table_structuring.substitute(
                header=json.dumps(brief_headers, ensure_ascii=False, indent=2),
                caption=caption,
                compounds=json.dumps(compounds, ensure_ascii=False, indent=2),
                configurations=json.dumps(
                    brief_configurations, ensure_ascii=False, indent=2)
            )
            response_1 = llm_client.simple_chat(user_message=prompt_1)
            structured_info = safe_json_loads(response_1)
            # print("Structured Info:", structured_info)
            enhanced_compounds = structured_info.get("compounds", [])
            enhanced_headers = structured_info.get("header", [])

            enhanced_header_name_to_info = {
                h["name"]: h for h in enhanced_headers if h.get("name", "") != ""
            }

            enhanced_configurations = structured_info.get("configurations", [])
            enhanced_configuration_name_to_info = {
                c["name"]: c for c in enhanced_configurations if c.get("name", "") != ""
            }

            # 将增强的信息回填到dataset中
            for header in headers:
                header_name = header.get("name", "")
                if header_name in enhanced_header_name_to_info:
                    enhanced_info = enhanced_header_name_to_info[header_name]
                    related_compounds = enhanced_info.get("related_compounds", [])
                    # 过滤掉不在原始compounds列表中的相关化合物
                    related_compounds = [c for c in related_compounds if c in compounds]
                    header["related_compounds"] = related_compounds
                    header["condition"] = enhanced_info.get("condition", [])
            for configuration in configurations:
                config_name = configuration.get("name", "")
                if config_name in enhanced_configuration_name_to_info:
                    enhanced_info = enhanced_configuration_name_to_info[config_name]
                    related_compounds = enhanced_info.get("related_compounds", [])
                    # 过滤掉不在原始compounds列表中的相关化合物
                    related_compounds = [c for c in related_compounds if c in compounds]
                    configuration["related_compounds"] = related_compounds
                    configuration["condition"] = enhanced_info.get(
                        "condition", [])
    return clustered_data


def further_divide_dataset_info(clustered_data):
    llm_client = ParateraQwenClient()
    for table_part in clustered_data:
        final_datasets = []
        caption = table_part.get("caption","")
        table_related_segments = table_part.get(
            "related_experiment_setting_segments", [])
        # 因为数据集的表头都是一样的，所以只需要看第一个数据集
        datasets = table_part.get("datasets", [])
        if len(datasets) == 0:
            continue
        first_dataset = datasets[0]
        headers = first_dataset.get("headers", [])
        brief_headers = [{"name": h.get("name", ""), "brief_description": h.get(
            "brief_description", "")} for h in headers]
        
        prompt = user_prompt_for_table_dataset_split.substitute(
            header=json.dumps(brief_headers, ensure_ascii=False, indent=2),
            caption=caption,
            related_text=json.dumps(table_related_segments, ensure_ascii=False, indent=2)
        )
        response = llm_client.simple_chat(user_message=prompt)
        dataset_splits = safe_json_loads(response)
        # 根据划分结果，生成新的数据集
        for dataset in datasets:
            for split in dataset_splits:
                new_dataset = {
                    "variable_headers": [],
                    "property_headers": [],
                    "compounds": dataset.get("compounds", []),
                    "configurations": dataset.get("configurations", []),
                    "data_rows": []
                }
                variable_names = split.get("variable", [])
                property_names = split.get("property", [])
                needed_row_indices = []
                for idx, header in enumerate(dataset.get("headers", [])):
                    header_name = header.get("name", "")
                    if header_name in variable_names:
                        new_dataset["variable_headers"].append(header)
                        needed_row_indices.append(idx)
                    if header_name in property_names:
                        new_dataset["property_headers"].append(header)
                        needed_row_indices.append(idx)
                # 抽取数据集的列
                new_dataset["data_rows"] = extract_columns(
                    dataset.get("data_rows", []), needed_row_indices)
                final_datasets.append(new_dataset)
        table_part["final_datasets"] = final_datasets
    return clustered_data

    

user_prompt_for_phase_extraction = Template("""
You are an expert in experimental data interpretation.

Your task is to extract the **phase information** of the experiment from the following inputs.  
The phase information refers to the physical state of the substance(s) involved.

### Inputs
1. Table caption:
$table_caption

2. Related text:
$related_text

---

### Task
- Identify the **main phase(s)** of the experiment from the caption and related text.
- The possible phase values are strictly:
  - "gas" (气态)
  - "liquid" (液态)
  - "solid" (固态)
  - "gas-liquid equilibrium" (气液平衡)
  - "liquid-solid equilibrium" (液固平衡)
  - "solid-gas equilibrium" (固气平衡)
- If the phase is not explicitly stated, return empty strings.

### Output format (JSON ONLY)
{
  "phase": {
    "name": "",               # One of the allowed phase values above, or "" if unknown
    "brief_description": ""   # Short description or context from caption/related text
  }
}

### Important Rules
- Use only information explicitly stated in the caption or related text.
- Do NOT infer the phase beyond what is explicitly mentioned.
- Return valid JSON only.
- Do not include any extra explanation or text outside JSON.
""")

user_prompt_for_table_structuring = Template("""
You are an expert in scientific table normalization and data parsing.

Your task is to process the following inputs and produce a structured JSON output.

### Inputs
1. Table header information:
$header

2. Table caption:
$caption

3. Compounds list:
$compounds

4. Quantitative experimental configurations:
$configurations

---

### Rules

1. **Compounds Parsing**
   - Split concatenated compounds into individual elements.
   - Produce a flat list.

2. **Header Processing**
   - For each header, extract:
     - `name`: the physical quantity
     - `related_compounds`: list of compounds that this quantity explicitly refers to.
       - Only bind a compound if the header clearly refers to that specific compound (e.g., "molar mass of A", "X1").
       - System-wide properties (e.g., temperature, pressure, total density, heat capacity, thermal conductivity) **should not** bind any compounds.
     - `condition`: list of experimental conditions under which this quantity was measured.
       - Extract only from explicit annotations in the header, e.g., `(T=298 K)`, `(P=0.1 MPa)`.
       - Each condition includes:
         - `name`: condition variable (T, P, etc.)
         - `value`: numeric value (leave empty if not specified)
         - `unit`: unit of the condition
         - `brief_description`: short description

3. **Configuration Processing**
   - For each configuration, extract:
     - `name`
     - `related_compounds`: **only include compounds that the configuration value specifically refers to.**
       - Example: `"mole fraction of methane"` → `["methane"]`
       - `"composition of mixture"` → `[]` (no binding)
     - `condition`: list of experimental conditions under which this configuration applies.
       - Extract only from explicit annotations, e.g., `(T=298 K)`, `(P=0.1 MPa)`

4. **Important**
   - Do not use the physical quantity itself as a condition.
   - Only bind a compound when the value clearly refers to it.
   - If there are no explicit measurement conditions, `condition` = `[]`.
   - Do not infer additional compounds or conditions beyond what is explicitly provided.

5. **Related Compounds Constraint (STRICT RULE)**

   - The field `related_compounds` MUST be selected ONLY from the provided **Compounds list**.
   - Treat the Compounds list as a CLOSED SET. No external compounds are allowed under any condition.

   - Matching rules:
     - Only exact string match is allowed.
     - Do NOT use synonyms, abbreviations, chemical variants, or inferred entities.
     - Do NOT extract compounds from the caption unless they appear EXACTLY in the Compounds list.

   - Caption constraint:
     - The caption is CONTEXT ONLY and must NOT be used as a source for introducing new compounds.

   - If a compound mentioned in headers, captions, or configurations is NOT explicitly present in the Compounds list:
     → It MUST be ignored completely.

   - If no valid compounds from the Compounds list apply:
     → Return an empty list `[]`.

   - Under NO circumstances should new compounds be introduced into `related_compounds`, even if they appear in scientific context or captions.

---

### Output Format (JSON ONLY)

{
  "compounds": [],
  "header": [
    {
      "name": "",
      "related_compounds": [],
      "condition": [
        {
          "name": "",
          "value": "",
          "unit": "",
          "brief_description": ""
        }
      ]
    }
  ],
  "configurations": [
    {
      "name": "",
      "related_compounds": [],
      "condition": [
        {
          "name": "",
          "value": "",
          "unit": "",
          "brief_description": ""
        }
      ]
    }
  ]
}

- Return ONLY valid JSON.
- Do not include explanations or extra text.
""")

user_prompt_for_table_dataset_split = Template('''
You are an expert in experimental data structuring and dataset decomposition.

Your task is to split a table into one or more **independent datasets**
based on the **experimental properties being measured**.

---

### Inputs

1. Table headers (each header has a name and a brief_description):
$header

2. Table caption:
$caption

3. Related text (surrounding experimental description):
$related_text

---

### Core Definitions (STRICT — DO NOT VIOLATE)

#### 1. Experimental Property
A property is a physical or thermophysical quantity that:
- is experimentally measured, calculated from measurements, or reported as a system response,
- represents the scientific outcome or state-dependent behavior of the material.

Typical properties include:
- density, thermal conductivity, viscosity, heat capacity, diffusion coefficient, molar volume, refractive index

⚠️ A quantity is a property EVEN IF:
- it depends on temperature or pressure,
- it is labeled “nominal”, “reference”, “calculated”, or “derived”,
- it is constant across rows (e.g., for a pure substance).

> **Hard Rule (Contextual)**:  
> In tables reporting thermophysical or transport properties (the typical context of this task), **density must always be classified as an experimental property**, regardless of phrasing like “nominal”, “target”, or “reference”.  
> This is because such tables document system responses—not experimental protocols where density is actively controlled as an independent input (a scenario that is exceptionally rare in standard property data).

---

#### 2. Experimental Variable
A variable is a quantity that:
- is **directly controlled, set, or scanned by the experimenter** as an independent input condition,
- defines the initial or boundary state **before measurement occurs**,
- would appear in the experimental protocol (e.g., “measure at T = 300 K, P = 1 MPa, x₁ = 0.5”).

Typical variables include:
- temperature
- pressure
- mole fraction or mass fraction (only when describing the **initial mixture composition**)

⚠️ A quantity is **NOT a variable** if:
- it results from the system’s physical response (even if used for indexing),
- it is derived, inferred, or reported as a data point,
- it is a physical property labeled as “nominal” or “fixed”.

> **Key Principle**: Variables are **inputs**; properties are **outputs or state descriptors**.

---

#### 3. Explicit Exclusions
The following MUST be completely ignored and MUST NOT appear anywhere:
- uncertainty, relative expanded uncertainty, standard deviation, confidence interval, error, deviation, repeatability

These are metadata, NOT variables and NOT properties.

---

### Dataset Splitting Rules

1. **One dataset = one experimental property**  
   Split the table if multiple unrelated properties are present.

2. **Variables are shared**  
   Temperature, pressure, composition, etc., may appear in multiple datasets—but never define a dataset.

3. **No inference beyond explicit content**  
   Use ONLY the headers, caption, and related text. Do NOT assume unstated intent.

4. **Never reclassify a property as a variable**  
   Even if a property appears constant or “preset”, it remains a property in this context.

---

### Task

1. Identify all experimental properties (respecting the hard rule on density).
2. For EACH property, create ONE dataset.
3. For each dataset:
   - List **only** the headers that are experimental variables.
   - List **only** the header that is the experimental property.
4. Exclude all uncertainty-related headers completely.

---

### Output Format (JSON ONLY — DO NOT CHANGE)

[
  {
    "variable": ["var1_name", "var2_name"],
    "property": ["prop1_name"]
  }
]

---

### Hard Constraints (VIOLATION = INVALID OUTPUT)

- If "density" appears in any form, it **MUST** be in a "property" list.
- Variables **MUST NOT** appear in "property".
- Properties **MUST NOT** appear in "variable".
- Uncertainty-related headers **MUST NOT** appear anywhere.
- Each dataset must have exactly one property.
- Output must be valid JSON. No extra text, comments, or fields.
''')

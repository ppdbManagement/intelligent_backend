import re
from typing import List, Dict, Any
import os
import json
from string import Template
from .ParateraQwenClient import ParateraQwenClient
from .simple_tools import normalize_html_whitespace, extract_first_n_trs, strip_code_fence, get_result_path_from_state_uuid, safe_json_loads,get_first_n_json_records
from ..models import *

def extract_context_data(prev_uuid):
    llm_client = ParateraQwenClient()
    filled_result_dir = get_result_path_from_state_uuid(prev_uuid, "data_filling")
    # 读取里面的信息
    filled_tables_file = os.path.join(filled_result_dir, "filled_tables.json")
    with open(filled_tables_file,"r", encoding="utf-8") as f:
        filled_tables = json.load(f)
    # 先从上一步的结果中获取tag-segment的映射，imagepath和content的映射
    table_locate_result_dir = get_result_path_from_state_uuid(prev_uuid, "table_locate")
    segments_with_tags_file = os.path.join(table_locate_result_dir, "segments_with_tags.json")
    # {"tag":"seg"}
    with open(segments_with_tags_file, "r") as f:
        segments_with_tags = json.load(f)
    # 开始遍历filled_tables
    context_data = []
    for table_info in filled_tables:
        caption = table_info.get("caption", "")
        headers = table_info.get("header", [])
        headers_str = json.dumps(headers, ensure_ascii=False)
        table_uuid = table_info.get("table_uuid", "")
        table_data_rows = table_info.get("data", [])
        preview_data_rows = get_first_n_json_records(table_data_rows, 3)
        singleFlatParseResult  =SingleFlatParseResult.objects.filter(uuid = table_uuid).first()
        singleExperimentTableResult = singleFlatParseResult.origin_table
        related_segment_tags = json.loads(singleExperimentTableResult.related_segment_tags)
        related_segments = [segments_with_tags.get(tag, "") for tag in related_segment_tags]
        # Step 1: Enhance table headers and get compounds information
        prompt_1 = user_prompt_for_compounds.substitute(
            caption=caption,
            related_text="\n".join(related_segments),
            table_headers=headers_str,
            table_data_previews=json.dumps(preview_data_rows, ensure_ascii=False)
        )
        response_1 = llm_client.simple_chat(
            user_message=prompt_1,
        )
        enhanced_result_1 = safe_json_loads(response_1)
        compounds_ref_header_name = enhanced_result_1.get("compounds_ref_header_name", "")
        compounds = enhanced_result_1.get("compounds", [])
        # Step 2: Extract quantitative experimental configurations
        prompt_2 = user_prompt_for_quantitative_experimental_configurations.substitute(
            caption=caption,
            related_text="\n".join(related_segments),
            table_headers=headers_str,
            table_data_previews=json.dumps(preview_data_rows, ensure_ascii=False)
        )
        response_2 = llm_client.simple_chat(
            user_message=prompt_2,
        )
        enhanced_result_2 = safe_json_loads(response_2)
        related_segments_tag_2_segment_mapping = {tag: segments_with_tags.get(tag, "") for tag in related_segment_tags}
        # 将结果保存到context_data中
        context_data.append({
            "table_uuid": table_uuid,
            "caption": caption,
            "header": headers,
            "data_preview": preview_data_rows,
            "data" : table_data_rows,
            "compounds_ref_header_name": compounds_ref_header_name,
            "compounds": compounds,
            "quantitative_experimental_configurations": enhanced_result_2,
            "related_segments" : related_segments_tag_2_segment_mapping,
        })
    return context_data
    

user_prompt_for_compounds = Template("""
You are an expert in scientific table interpretation.

Your task is to determine the experimental compounds represented in THIS table.

============================================================
INPUT
============================================================

Table caption:
$caption

Related text:
$related_text

Table headers (JSON array):
$table_headers

Table data previews:
$table_data_previews

============================================================
TASK: Identify experimental compounds (TABLE-SCOPED)
============================================================

You must determine:

1) Whether any table header explicitly specifies the chemical identity of the experimental components (i.e., what substances are used in the experiment).

2) If such a header exists:
   - Return its exact name as "compounds_ref_header_name"

3) If NO such header exists:
   - Set "compounds_ref_header_name" to ""
   - Extract all experimental compounds from the caption, related text, or table data previews

------------------------------------------------------------
IMPORTANT RULES
------------------------------------------------------------

- Only consider headers that indicate chemical identity, such as:
  "compound", "species", "component", "fluid", "solute", "glycol", etc.

- DO NOT treat the following as compound identifiers:
  - temperature
  - pressure
  - density
  - mole fraction
  - mass fraction
  - any experimental condition

- Compounds must be listed as individual pure substances:
  ✔ Correct: ["carbon dioxide", "methane"]
  ✘ Incorrect: ["CO2-CH4 mixture (x=0.3)"]

- Do NOT include composition, ratios, or conditions in compound names.

- If mixtures are present, list each base component separately.

============================================================
FINAL OUTPUT FORMAT
============================================================

Return ONE JSON object:

{
  "compounds_ref_header_name": "",
  "compounds": []
}

Return JSON ONLY. No explanations.
""")

user_prompt_for_quantitative_experimental_configurations = Template("""
You are an expert in scientific table analysis.

Your task is to extract quantitative experimental configurations
that DEFINE THE PHYSICAL OR CHEMICAL STATE of the system represented
by EACH DATA ROW in THIS table.

============================================================
INPUT
============================================================

Table caption:
$caption

Related text:
$related_text

Table headers (JSON array):
$table_headers

Table data previews:
$table_data_previews

============================================================
CRITICAL DEFINITION (READ CAREFULLY)
============================================================

A quantitative experimental configuration is NOT:
- any number mentioned in the paper
- any summary, range, minimum, or maximum of table variables
- any measurement protocol, instrument setting, or validation detail
- any paper-level statistic

A quantitative experimental configuration IS:
- a FIXED condition that applies to ALL rows in the table
- a condition that DEFINES the thermodynamic or chemical STATE
  of the system whose property is reported
- a condition that is NOT already represented by a table header

If a value does NOT change the physical meaning of the reported property,
it MUST NOT be extracted.

============================================================
MANDATORY ACCEPTANCE CRITERIA (ALL MUST HOLD)
============================================================

You may extract a configuration ONLY IF ALL conditions below are satisfied:

A. State-defining
   - The configuration defines the thermodynamic or chemical state
     of the system (e.g., composition, background medium).
   - Example: fixed mixture composition ✔
   - Counterexample: number of measurements ✘

B. Header-exclusive
   - The configuration is NOT represented by any table header
     and is NOT a summary or range of a header variable.
   - Use table_data_previews to verify whether a variable actually varies across rows.
   - Example: composition when no composition column exists ✔
   - Counterexample: temperature range when T(K) is a column ✘

C. Table-invariant
   - The configuration applies IDENTICALLY to all rows in the table.
   - Use table_data_previews to confirm invariance (i.e., same value across rows).
   - Ranges describing data coverage do NOT qualify.

D. Programmatically usable
   - The configuration could be used as a condition for filtering,
     grouping, or interpreting the data.

============================================================
EXPLICITLY FORBIDDEN (MUST NEVER APPEAR)
============================================================

- number_of_measurements
- number_of_isotherms
- temperature ranges if temperature is a table column
- pressure ranges if pressure is a table column
- minimum / maximum / limit values of table variables
- heat production, temperature increase, power, time intervals
- uncertainty, confidence level, validation statements
- any methodological or procedural description

============================================================
OUTPUT FORMAT
============================================================

Return a JSON ARRAY.

Each item MUST have EXACTLY this structure:

{
  "name": "",
  "value": "",
  "unit": "",
  "description": ""
}

- value MUST be a single numeric value or fixed categorical value.
- Numeric ranges are NOT allowed unless the quantity is NOT a table variable
  and the range itself defines the state.
- If NO valid configuration exists, return an EMPTY array.

============================================================
FINAL INSTRUCTION
============================================================

Use table_data_previews as supporting evidence, not as a primary source
of new variables.

If you are uncertain whether a value truly defines the physical or chemical
state of the system represented by each data row, DO NOT extract it.

Return JSON ONLY. No explanations.
""")
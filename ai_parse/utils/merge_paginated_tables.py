import json
from string import Template
from typing import Any, Dict, List
from .simple_tools import safe_json_loads,get_result_path_from_state_uuid
import os
from .ParateraQwenClient import ParateraQwenClient



def merge_paginated_tables(prev_uuid : str):
    # 合并分页表格
    mineru_dir = get_result_path_from_state_uuid(prev_uuid,"doc_parse")
    result_subdir = os.listdir(mineru_dir)[0]
    parse_result_dir = os.path.join(mineru_dir,result_subdir,"vlm")
    content_list_file = os.path.join(parse_result_dir,f"{result_subdir}_content_list.json")
    raw_table_items: List[Dict[str, Any]] = []
    # 读取content_list.json，提取所有表格项
    with open(content_list_file, "r", encoding="utf-8") as f:
        content_items = json.load(f)
        for item in content_items:
            if item.get("type") == "table":
                raw_table_items.append(item)
                
    table_entries: List[Dict[str, Any]] = []
    last_caption = ""
    table_counter = 1
    for item in raw_table_items:
        caption_list = item.get("table_caption", [])
        table_footnote_list = item.get("table_footnote", [])

        if not caption_list or not caption_list[0].strip():
            caption_text = last_caption
        else:
            caption_text = ";".join(caption_list).strip()
            last_caption = caption_text

        table_entries.append({
            "table_id": table_counter,
            "caption": caption_text,
            "img_path": item["img_path"],
            "table_content": item["table_body"],
            "footnote": table_footnote_list,
        })

        table_counter += 1
    table_lookup = {t["table_id"]: t for t in table_entries}
    table_info_text = ""
    for t in table_entries:
        table_info_text += f'{t["table_id"]}. {t["caption"]}\n'
    user_prompt = user_prompt_for_table_merge.substitute(
        tables_info=table_info_text
    )

    llm_client = ParateraQwenClient()
    llm_response = llm_client.simple_chat(
        user_message=user_prompt,
        system_prompt=system_prompt_for_table_merge,
    )
    grouped_tables = safe_json_loads(llm_response)
    merged_tables: List[Dict[str, Any]] = []
    new_table_id = 1

    for group in grouped_tables:
        merged_contents = []
        footnote_contents = []

        for tid in group["table_id"]:
            table_data = table_lookup.get(tid)
            if table_data:
                merged_contents.append({
                    "img_path": table_data["img_path"],
                    "mineru_content": table_data["table_content"],
                })
                footnote_contents.extend(table_data.get("footnote", []))

        # 将footnote保持原有顺序并去重
        seen_footnotes = set()
        unique_footnotes = []
        for fn in footnote_contents:
            if fn not in seen_footnotes:
                seen_footnotes.add(fn)
                unique_footnotes.append(fn)

        merged_tables.append({
            "table_id": new_table_id,
            "table_caption": group["table_caption"],
            "table_content": merged_contents,
            "table_footnote": unique_footnotes,
        })

        new_table_id += 1
    return merged_tables
    
    
    
    
    
    
    
# ======================prompt for table merge start======================
# system prmopt for determining whether to merge tables
system_prompt_for_table_merge = '''
You are an expert in academic table reconstruction and data analysis.

Your task is to determine whether multiple extracted tables originate from the same original table, which may have been split due to pagination, layout constraints, or page breaks.

Important principles:
1. Only merge tables automatically if there is a clear continuation marker in the caption, such as "Continued", "Continued on next page", "(continued)", or similar.
2. Do NOT merge tables solely based on similar wording or semantic similarity.
3. If two table captions differ only in numerical parameters (e.g., pressure, temperature, concentration, sample ID), treat them as separate tables unless an explicit continuation marker exists.
4. Consider structural, positional, and formatting cues as secondary evidence only; never override explicit numeric or experimental differences.
5. Preserve input order and table IDs when grouping.
'''


# user prompt for determining whether to merge tables
user_prompt_for_table_merge = Template('''
You will be given a list of tables, each with a "table_id" and a "table_caption".

Some tables were originally a single table but were split due to page breaks, layout constraints, or formatting.

Your task:
- Group tables only if there is an explicit continuation marker in the caption 
  (e.g., "Continued", "Continued on next page", "(continued)").
- Tables with titles that differ **only in numeric values or experimental parameters** (e.g., pressure, temperature, concentration) must **NOT** be merged unless there is a continuation marker.
- Do not modify any provided captions.
- For each group, choose the main title as the first non-continuation caption in that group.
- Preserve the original input order:
    * Groups must appear in the order of the first table in each group.
    * Table IDs within each group must follow the input order.


Return the result strictly in the following JSON format:
[
  {
    "table_caption": "Main title of the group",
    "table_id": [1, 2, 3, ...]
  },
  ...
]

Here are the tables to analyze (in order):
$tables_info
''')


# ======================prompt for table merge end======================

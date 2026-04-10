import re
from typing import List, Dict, Any
import os
import json
from string import Template
from .ParateraQwenClient import ParateraQwenClient
from .simple_tools import normalize_html_whitespace, extract_first_n_trs, strip_code_fence,get_result_path_from_state_uuid


# =========================
# 🔥 High-level pipeline
# =========================
def find_related_segment(
    prev_uuid,
    paginated_merged_tables
) -> List[Dict[str, Any]]:
    mineru_dir = get_result_path_from_state_uuid(prev_uuid,"doc_parse")
    result_subdir = os.listdir(mineru_dir)[0]
    parse_result_dir = os.path.join(mineru_dir,result_subdir,"vlm")
    content_list_file = os.path.join(parse_result_dir,f"{result_subdir}_content_list.json")
    model_file = os.path.join(parse_result_dir,f"{result_subdir}_model.json")
    
    # 将文本进行tag标签
    text_with_tags = extract_text_data(model_file)
    # 获取表格可能出现的引用词
    table_references = extract_table_reference_words(paginated_merged_tables)
    # 根据表格引用词找到可能包含表格引用的段落
    table_references = find_paragraphs_with_table_references(
        text_with_tags, table_references
    )
    find_experiment_setting_paragraphs(
        table_references, text_with_tags
    )
    table_references = identify_experiment_setting_paragraphs(
        table_references, paginated_merged_tables
    )
    return table_references

# =========================
# Text extraction
# =========================
def extract_text_data(model_file: str) -> List[List[Dict[str, str]]]:
    """
    Extract text blocks from MinerU VLM output and assign hierarchical tags.
    """
    segments = []
    current_segment = []
    first_tag = 1
    second_tag = 1
    with open(model_file, 'r', encoding='utf-8') as f:
        model_data = json.load(f)
    for page in model_data:
        for block in page:
            if block["type"] == "text":
                current_segment.append({
                    "tag": f"{first_tag}-{second_tag}",
                    "content": block["content"]
                })
                second_tag += 1
            elif block["type"] == "title":
                if current_segment:
                    segments.append(current_segment)
                first_tag += 1
                second_tag = 1
                current_segment = []
    if current_segment:
        segments.append(current_segment)
    return segments

# 构造一个特殊的函数，用于返回tag-content的映射关系，方便后续查找
def build_tag_content_map(prev_uuid) -> Dict[str, str]:
    mineru_dir = get_result_path_from_state_uuid(prev_uuid,"doc_parse")
    result_subdir = os.listdir(mineru_dir)[0]
    parse_result_dir = os.path.join(mineru_dir,result_subdir,"vlm")
    model_file = os.path.join(parse_result_dir,f"{result_subdir}_model.json")
    text_data =  extract_text_data(model_file)
    tag_content_map = {}
    for segment in text_data:
        for block in segment:
            tag_content_map[block["tag"]] = block["content"]
    return tag_content_map

# =========================
# Table reference extraction
# =========================
def extract_table_reference_words(paginated_merged_tables: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Use LLM to extract table reference words (e.g., Table 1, Table S2) from captions.
    """
    caption_entries = []
    for table in paginated_merged_tables:
        table_id = table.get("table_id", "")
        caption = table.get("table_caption", "")
        if caption:
            caption_entries.append(f"ID: {table_id}\nCaption: {caption}")
    if not caption_entries:
        return []
    client = ParateraQwenClient()
    prompt = user_prompt_for_caption_extraction.substitute(
        entries="\n".join(caption_entries)
    )
    response = client.simple_chat(
        system_prompt=system_prompt_for_caption_extraction,
        user_message=prompt
    )
    return json.loads(response)

def find_paragraphs_with_table_references(
    text_with_tags: List[List[Dict[str, str]]],
    table_references: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:

    for ref in table_references:
        ref["found_in_paragraphs"] = []

    for segment in text_with_tags:
        for para in segment:
            for ref in table_references:
                for ref_word in ref.get("reference", []):
                    if is_table_ref_in_text(ref_word, para["content"]):
                        ref["found_in_paragraphs"].append(para["tag"])

    return table_references


TABLE_PREFIX_PATTERN = r'(?:Table|Tables|Tab\.|Tbl\.)'

TABLE_REF_IN_TEXT_PATTERN = re.compile(
    rf'\b{TABLE_PREFIX_PATTERN}\s+'
    r'([A-Z]?\d+|[IVXLCDM]+)'
    r'(?:\s*[–\-]\s*([A-Z]?\d+|[IVXLCDM]+))?',
    re.IGNORECASE
)

ROMAN_MAP = {
    'I': 1, 'V': 5, 'X': 10,
    'L': 50, 'C': 100, 'D': 500, 'M': 1000
}


def roman_to_int(s: str) -> int:
    s = s.upper()
    total = 0
    prev = 0
    for c in reversed(s):
        v = ROMAN_MAP[c]
        if v < prev:
            total -= v
        else:
            total += v
            prev = v
    return total

def is_table_ref_in_text(ref_word: str, text: str) -> bool:
    """
    Determine whether `text` references the table indicated by `ref_word`,
    allowing for plural forms and ranges like 'Tables 2–4'.
    """

    # Step 1: parse target table index from ref_word
    m = re.search(r'([A-Z]?\d+|[IVXLCDM]+)$', ref_word.strip())
    if not m:
        return False

    raw = m.group(1)

    def parse(x):
        if x.isdigit():
            return int(x)
        if re.fullmatch(r'[IVXLCDM]+', x):
            return roman_to_int(x)
        return x  # S1 / A1

    target = parse(raw)

    # Step 2: scan all table-like references in text
    for m in TABLE_REF_IN_TEXT_PATTERN.finditer(text):
        start, end = m.group(1), m.group(2)
        start_v = parse(start)

        # Case 1: single reference
        if end is None:
            if start_v == target:
                return True

        # Case 2: range reference
        else:
            end_v = parse(end)
            if isinstance(start_v, int) and isinstance(end_v, int):
                if isinstance(target, int) and start_v <= target <= end_v:
                    return True

    return False


def find_experiment_setting_paragraphs(
    table_references: List[Dict[str, Any]],
    text_with_tags: List[List[Dict[str, str]]],
    window_before: int = 5,
    window_after: int = 2
) -> None:

    flat = [p for seg in text_with_tags for p in seg]
    tag_to_index = {p["tag"]: i for i, p in enumerate(flat)}

    for ref in table_references:
        candidate_tags = set()
        found_tags = ref.get("found_in_paragraphs", [])

        # TODO:可选优化：只使用首次引用（更聚焦）
        if found_tags:
            found_tags = [found_tags[0]]
        for tag in found_tags:
            if tag not in tag_to_index:
                continue

            idx = tag_to_index[tag]
            start = max(0, idx - window_before)
            end = min(len(flat), idx + window_after + 1)

            for i in range(start, end):
                candidate_tags.add(flat[i]["tag"])

        ref["candidate_experiment_setting_paragraphs"] = [
            p for p in flat if p["tag"] in candidate_tags
        ]

# =========================
# LLM identification
# =========================

def identify_experiment_setting_paragraphs(
    table_references: List[Dict[str, Any]],
    merged_table_data: Dict[str, Any]
) -> List[Dict[str, Any]]:
    client = ParateraQwenClient()
    table_map = {
        str(t["table_id"]): t
        for t in merged_table_data
    }
    for ref in table_references:
        table_id = str(ref.get("id", ""))
        table = table_map.get(table_id)
        if not table:
            continue
        caption = table.get("table_caption", "")
        data_preview = ""
        if len(table.get("table_content", [])) > 0:
            first_mineru_content = table["table_content"][0].get(
                "mineru_content", "")
            data_preview = extract_first_n_trs(
                normalize_html_whitespace(
                    strip_code_fence(first_mineru_content)),
                n=8
            )
        paragraphs_text = ""
        for p in ref.get("candidate_experiment_setting_paragraphs", []):
            paragraphs_text += f'Tag: {p["tag"]}\nContent: {p["content"]}\n\n'

        prompt = user_prompt_for_identify_experiment_setting.substitute(
            caption=table.get("table_caption", ""),
            data_preview=data_preview,
            paragraphs=paragraphs_text
        )
        response = client.simple_chat(
            system_prompt=system_prompt_for_identify_experiment_setting,
            user_message=prompt
        )
        result = json.loads(response)
        ref["identified_experiment_setting_paragraph_tags"] = result.get(
            "relevant_tags", [])
    return table_references


# 将related_segment整合进返回结果中
def integrate_related_segments(
    merged_table_data: Dict[str, Any],
    related_segments: List[Dict[str, Any]]
) -> Dict[str, Any]:
    table_id_to_related = {
        str(item["id"]): item
        for item in related_segments
    }
    for table in merged_table_data:
        table_id = str(table.get("table_id", ""))
        related = table_id_to_related.get(table_id, {})
        # 需要是列表形式，包含段落tag和具体内容
        tags = related.get("identified_experiment_setting_paragraph_tags", [])
        candidate_paragraphs = related.get("candidate_experiment_setting_paragraphs", [])
        tag_to_content = {p["tag"]: p["content"] for p in candidate_paragraphs}
        related_segments_info = [
            {"tag": tag, "content": tag_to_content.get(tag, "")
            } for tag in tags
        ]
        table["related_experiment_setting_segments"] = related_segments_info
    return merged_table_data

# =========================
# Prompt definitions
# =========================
system_prompt_for_caption_extraction = '''
You are a precise data extraction tool. Your task is to extract table identifiers (e.g., "Table 1", "Table 2") from academic table captions. 
Always output valid JSON in the exact format requested—no explanations, no extra text.
'''

user_prompt_for_caption_extraction = Template('''
Extract table identifiers from the following list of {id: caption} entries.

For each entry:
- Look at the caption.
- If it starts with a pattern like "Table X" (where X is a number or alphanumeric label), extract that full phrase (e.g., "Table 1", "Table S3").
- Place the extracted phrase in a list under the key "reference".
- If no such pattern is found, use an empty list: "reference": [].

Return a JSON array of objects in this exact format:
[
  {
    "id": "original_id",
    "reference": ["Table X"]
  }
]

Input entries:
$entries

Output (JSON only, no markdown, no commentary):
''')

# ========================= prompt for identifying experiment setting paragraphs =========================

system_prompt_for_identify_experiment_setting = '''
You are an expert academic assistant. Your task is to identify which paragraphs describe the experimental configuration, column definitions, or data context of a given table.
Return only a JSON object with a key "relevant_tags" containing a list of paragraph tags.
Do not explain, do not output anything else.
'''


user_prompt_for_identify_experiment_setting = Template('''
You are given:

1. A table demo consisting of:
   - Caption: $caption
   - Table preview: $data_preview
     (The preview is an HTML snippet containing the first n rows of the table,
      including the table header row(s) and a subset of data rows.)

2. A list of paragraphs, each with a unique "tag" and "content".

Your task:
Identify which paragraphs provide information that is NECESSARY to understand or reproduce the data in this table.

Specifically, select paragraphs that describe ONE OR BOTH of the following:

A. Experimental configuration and data generation
- Experimental materials, sample sources, purity, and preparation,
- Measurement instruments, calibration procedures, and operating conditions,
- Experimental parameters (e.g., temperature, pressure, composition range, repetitions),
- Measurement accuracy, precision, uncertainty, and data averaging.

B. Definitions or explanations of table columns
- Explicit definitions or physical meanings of the quantities listed in the table,
- Units, symbols, abbreviations, or conventions used in the table columns,
- Clarifications needed to correctly interpret the column headers seen in the table preview.

IMPORTANT NOTES:
- Column headers and partial data must be interpreted directly from the HTML table preview.
- Select a paragraph only if it contains information essential for understanding
  the meaning, units, or experimental origin of the table data.

IMPORTANT EXCLUSIONS:
Do NOT select paragraphs that:
- Provide mathematical derivations or detailed calculation formulas,
- Analyze or interpret trends or implications of the data,
- Merely state that results are presented in the table without adding contextual meaning.

Return ONLY the tags of the selected paragraphs.

Input paragraphs:
$paragraphs

Output format:
{
  "relevant_tags": ["tag1", "tag2"]
}
''')

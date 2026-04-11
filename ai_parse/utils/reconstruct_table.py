import re
from typing import List, Dict, Any
import os
import json
from string import Template
from .ParateraQwenClient import ParateraQwenClient
from .simple_tools import normalize_html_whitespace, extract_first_n_trs, strip_code_fence,get_result_path_from_state_uuid,safe_json_loads
from ..models import *


def reconstruct_table(prev_uuid):
    # 先从上一步的结果中获取tag-segment的映射，imagepath和content的映射
    table_locate_result_dir = get_result_path_from_state_uuid(prev_uuid, "table_locate")
    segments_with_tags_file = os.path.join(table_locate_result_dir, "segments_with_tags.json")
    # {"tag":"seg"}
    with open(segments_with_tags_file, "r") as f:
        segments_with_tags = json.load(f)
    paginated_merged_tables_file = os.path.join(table_locate_result_dir, "paginated_merged_tables.json")
    # [{"table_content":[{"img_path":"","mineru_content":""}]}]
    # 获取img_path和mineru_content的映射关系
    with open(paginated_merged_tables_file, "r") as f:
        paginated_merged_tables = json.load(f)
    img_path_to_content = {}
    for table in paginated_merged_tables:
        for cell in table["table_content"]:
            img_path = cell["img_path"]
            mineru_content = cell["mineru_content"]
            img_path_to_content[img_path] = mineru_content    
    
    # 先获得处理之后的表格定位后的数据，从数据库中
    documentParseStatus = DocumentParseStatus.objects.filter(uuid=prev_uuid).first()
    experimentTableResult = documentParseStatus.parse_result.experiment_table_result
    tableResults = experimentTableResult.single_table_results.all()
    table_with_related_segments = []
    for tableResult in tableResults:
        table_dict = {
            "table_id": tableResult.table_order,
            "table_caption": tableResult.caption,
            "table_order": tableResult.table_order,
            "table_result_uuid":str(tableResult.uuid),
        }
        related_experiment_setting_segments = []
        tags = json.loads(tableResult.related_segment_tags)
        for tag in tags:
            if tag in segments_with_tags:
                related_experiment_setting_segments.append({"tag": tag, "content": segments_with_tags[tag]})
        table_dict["related_experiment_setting_segments"] = related_experiment_setting_segments
        table_contents = []
        experimentTablePictures = tableResult.pictures.all()
        for picture in experimentTablePictures:
            img_path = picture.image_path
            img_order = picture.image_order
            if img_path in img_path_to_content:
                mineru_content = img_path_to_content[img_path]
                table_contents.append({"img_path": img_path, "mineru_content": mineru_content, "img_order": img_order})
        # 根据img_order排序
        table_contents = sorted(table_contents, key=lambda x: x["img_order"])
        table_dict["table_content"] = table_contents
        table_with_related_segments.append(table_dict)
        
    # 利用table_order对table_with_related_segments进行排序
    table_with_related_segments = sorted(table_with_related_segments, key=lambda x: x["table_order"])
    # 先对表格的类型进行分析
    tables_with_type = analysis_table_type(
        table_with_related_segments)
    # 对表格的表头进行分析
    tables_with_table_format = analysis_table_format(
        tables_with_type)
    # 对表格的表头进行二次分析，补充一下遗漏的数据
    table_with_enhanced_format = enhance_table_format(
        tables_with_table_format)
    # 对表格的表头进行三次分析，去除一些错误的数据
    table_with_deduplicated_format = deduplicate_table_format(
        table_with_enhanced_format)
    return table_with_deduplicated_format
    
    
    
    
    
    
def analysis_table_type(tables_with_related_segments: List[Dict[str, Any]]) -> Dict[str, Any]:
    # 对表格的结构进行解析,主要需要分析表格的基本信息和结构信息
    llm_client = ParateraQwenClient()
    for table_part in tables_with_related_segments:
        table_caption = table_part.get("table_caption", "")
        table_footnote = table_part.get("table_footnote", [])
        table_footnote_text = "\n".join(table_footnote)
        table_content = table_part.get("table_content", [])
        if not table_content:
            # 表格内容为空，跳过
            continue
        first_mineru_content = table_content[0].get("mineru_content", [])
        first_n_mineru_strs = extract_first_n_trs(
            normalize_html_whitespace(strip_code_fence(first_mineru_content)), n=8)
        context = ",".join(
            [seg.get("content", "") for seg in table_part.get(
                "related_experiment_setting_segments", [])]
        )
        # 先进行表格类型的判断
        # 只能是五种类型之一：component,experience,literature,experience and literature,parameter
        user_prompt = user_prompt_for_analysis_table_type.substitute(
            caption=table_caption,
            footnote=table_footnote_text,
            rows=first_n_mineru_strs,
            context=context,
        )
        table_type_response = llm_client.simple_chat(
            user_message=user_prompt,
            system_prompt=system_prompt_for_analysis_table_type,
        ).strip()
        table_type_response_json = safe_json_loads(
            strip_code_fence(table_type_response))
        table_part["analysis_table_type"] = table_type_response_json.get(
            "type", "")
        table_part["analysis_table_type_brief_reason"] = table_type_response_json.get(
            "brief_reason", "")
    return tables_with_related_segments


def analysis_table_format(tables_with_type: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    llm_client = ParateraQwenClient()
    # 对表格的表头进行解析,主要需要分析表格的表头信息
    for table_part in tables_with_type:
        # 只对实验数据表格进行表头分析【实验数据表格包括：experience, experience and literature】
        if table_part.get("analysis_table_type", "") in ["experience", "experience and literature"]:
            table_caption = table_part.get("table_caption", "")
            table_footnote = table_part.get("table_footnote", [])
            table_footnote_text = "\n".join(table_footnote)
            table_related_segments = table_part.get(
                "related_experiment_setting_segments", [])
            related_text = ",".join(
                [seg.get("content", "") for seg in table_related_segments]
            )
            # table content一定是有的，否则不会进入到这里，只取前几行进行表头分析
            table_content = table_part.get("table_content", [])
            first_mineru_content = table_content[0].get("mineru_content", "")
            first_mineru_content_preview = normalize_html_whitespace(
                strip_code_fence(extract_first_n_trs(first_mineru_content, n=8)))

            table_format_prompt = user_prompt_for_analysis_table_format.substitute(
                caption=table_caption,
                related_text=related_text,
                table_html_snippet=first_mineru_content_preview,
            )
            llm_response = llm_client.simple_chat(
                user_message=table_format_prompt,
            ).strip()
            table_format_template = safe_json_loads(
                strip_code_fence(llm_response))
            table_part["analysis_table_format"] = table_format_template
    return tables_with_type

def enhance_table_format(tables_with_table_format: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    llm_client = ParateraQwenClient()
    # 对初步分析的表头进行解析，主要是补充遗漏的信息
    for table_part in tables_with_table_format:
        if table_part.get("analysis_table_type", "") in ["experience", "experience and literature"]:
            table_id = table_part.get("table_id", "")
            table_caption = table_part.get("table_caption", "")
            table_footnote = table_part.get("table_footnote", [])
            table_footnote_text = "\n".join(table_footnote)
            table_related_segments = table_part.get(
                "related_experiment_setting_segments", [])
            related_text = ",".join(
                [seg.get("content", "") for seg in table_related_segments]
            )
            # table content一定是有的，否则不会进入到这里，只取前几行进行表头分析
            table_content = table_part.get("table_content", [])
            first_mineru_content = table_content[0].get("mineru_content", "")
            first_mineru_content_preview = normalize_html_whitespace(
                strip_code_fence(extract_first_n_trs(first_mineru_content, n=8)))
            analysis_table_format = table_part.get("analysis_table_format", [])
            enhance_table_format_prompt = user_prompt_for_analysis_table_format_enhance.substitute(
                table_html_snippet=first_mineru_content_preview,
                existing_headers=json.dumps(
                    analysis_table_format, ensure_ascii=False),
            )
            llm_response = llm_client.simple_chat(
                user_message=enhance_table_format_prompt,
            ).strip()
            enhance_table_format_template = safe_json_loads(
                strip_code_fence(llm_response))
            # if len(enhance_table_format_template) > 0:
            #     print("header enhance:", table_id)
            #     print("enhanced_header:", enhance_table_format_template)
            table_part["analysis_table_format_enhance"] = analysis_table_format + \
                enhance_table_format_template
    return tables_with_table_format

def deduplicate_table_format(tables_with_table_format: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    llm_client = ParateraQwenClient()
    for table_part in tables_with_table_format:
        if table_part.get("analysis_table_type", "") in ["experience", "experience and literature"]:
            table_id = table_part.get("table_id", "")
            table_caption = table_part.get("table_caption", "")
            table_footnote = table_part.get("table_footnote", [])
            table_footnote_text = "\n".join(table_footnote)
            table_related_segments = table_part.get(
                "related_experiment_setting_segments", [])
            related_text = ",".join(
                [seg.get("content", "") for seg in table_related_segments]
            )
            # table content一定是有的，否则不会进入到这里，只取前几行进行表头分析
            table_content = table_part.get("table_content", [])
            first_mineru_content = table_content[0].get("mineru_content", "")
            first_mineru_content_preview = normalize_html_whitespace(
                strip_code_fence(extract_first_n_trs(first_mineru_content, n=8)))
            analysis_table_format = table_part.get("analysis_table_format_enhance", [])
            deduplicate_table_format_prompt = user_prompt_for_header_deduplication.substitute(
                enhanced_headers=json.dumps(
                    analysis_table_format, ensure_ascii=False),
                table_html_snippet=first_mineru_content_preview,
            )
            llm_response = llm_client.simple_chat(
                user_message=deduplicate_table_format_prompt,
            ).strip()
            deduplicated_table_format_template = safe_json_loads(
                strip_code_fence(llm_response))
            # if len(deduplicated_table_format_template) != len(analysis_table_format):
            #     print("header deduplicate:", table_id)
            #     print("deduplicate rows len:", len(analysis_table_format), "->", len(deduplicated_table_format_template))
            table_part["analysis_table_format_final"] = deduplicated_table_format_template
    return tables_with_table_format

# ======================prompt for analysis table type start======================

system_prompt_for_analysis_table_type = '''
You are an expert in chemical engineering and scientific data analysis. Your task is to classify a chemistry-related table into exactly one of the following five categories, based only on its caption, footnote, the first n rows of data, and any additional table-related text provided.

Category definitions:

1. Component Details – Lists chemical components, species, mixtures, or intrinsic identifiers/compositions.
   Includes component names, mole/mass fractions, critical constants, etc.
   Excludes measured experimental values or model-generated results.

2. Experimental Data from This Paper – Contains real, directly measured data obtained by the authors.
   Examples: temperature, pressure, density, viscosity, thermal conductivity, phase equilibrium, solubility, diffusivity.
   Must be original experimental observations, not calculated, fitted, or predicted values.

3. Data from Other Literature – Exclusively reports experimental data from prior publications, with no original measurements.

4. Experimental Data from This Paper and Other Literature – Mixture of original experimental data and literature experimental data.

5. Model-Related Data – Data obtained through equations, correlations, regression, simulation, or fitting.
   Includes:
   - Parameters or coefficients in equations/correlations
   - Fitted/regressed constants
   - Equation-of-state parameters
   - Kinetic, thermodynamic, or transport-model constants
   - Any quantity described as calculated, fitted, regressed, predicted, optimized, or obtained from an equation/model
   These data are classified as model-related **only when generated by a model/fitting process**, not when directly measured.

Output format:

Your output MUST be a single valid JSON object with exactly two keys:

{
  "type": "",
  "brief_reason": ""
}

Rules for output:
- "type" must be one of: component, experience, literature, experience and literature, model related
- "brief_reason" must be a concise single sentence explaining the key evidence, directly referencing cues such as "measured", "Best Estimates", "Eq.", "fitting", "coefficients", or "compiled from literature"
- Do NOT include explanations, formatting, markdown, or any additional text outside the JSON object
'''


user_prompt_for_analysis_table_type = Template('''
Caption:
$caption

Footnote:
$footnote

Table-related text:
$context

First n rows of the table:
$rows
''')


# ======================prompt for analysis table type end======================

# User prompt template
user_prompt_for_analysis_table_format = Template("""
You are an expert in scientific table normalization. Your task is to infer the flattened column headers from a complex HTML table structure.

### Critical Rules:
1. ONLY use content from the provided `table_html` snippet. IGNORE `caption` and `related_text` for extraction (they are context only).
2. The flattened table must have one column per distinct semantic dimension:
   - Experimental conditions (e.g., temperature, composition) should be **abstracted** into a single column per type, not repeated for each value.
   - Measured or reported variables (e.g., pressure, thermal conductivity) should have one column per variable.
3. For each output column:
   - If it represents a **condition** (e.g., from a row with `colspan>1` like "Nominal temperature 300 K" or "Nominal temperature 325 K"), then:
       - `name` = machine-readable abstract name (e.g., "temperature_K")
       - `raw_name` = high-level description of the condition (e.g., "Nominal temperature")
       - `single_example` = example value(s) if present (e.g., "300 K / 325 K")
   - If it represents a **variable/property** (e.g., from a header like "p(MPa)"), then:
       - `name` = clean, machine-readable name (e.g., "pressure_MPa")
       - `raw_name` = exact header text (e.g., "p(MPa)")
       - `single_example` = same as `raw_name`
4. DO NOT generate multiple columns for different values of the same condition. Only one column per condition type.
5. Output a JSON list of objects with exactly:
   - "name": unique machine-readable name
   - "raw_name": exact or abstracted text from ONE cell
   - "brief_description": short plain-English description (<15 words)
   - "single_example": example value(s) or same as `raw_name` for variables

### Input:

Caption:
$caption

Related text:
$related_text

Table HTML snippet (first few rows):
$table_html_snippet

### Output:
Return ONLY a valid JSON list. No other text, explanation, or formatting.
""")


user_prompt_for_analysis_table_format_enhance = Template("""
You are an expert in scientific table flattening and header normalization.

Your task is to determine whether the existing flattened table headers
are sufficient to represent ALL data in the table, and if not,
to ADD missing header-level semantic dimensions.

### Inputs:
1. `table_html_snippet`: the first N rows of the table (including headers and header-like rows).
2. `existing_headers`: the already extracted flattened table headers. These are FINAL.

### Core Goal:
Ensure the table can be safely FLATTENED such that:
- Each column corresponds to ONE and ONLY ONE semantic dimension.
- All data cells in the table can be described using the flattened headers.

### Critical Constraints (MUST FOLLOW):

1. **Immutability**
   - DO NOT modify, rename, merge, split, or delete any object in `existing_headers`.

2. **Additive Only**
   - ONLY add new headers if they represent a semantic dimension
     that is REQUIRED to explain the table data
     and is COMPLETELY missing from `existing_headers`.

3. **Single-Dimension Rule**
   - Each header MUST represent exactly ONE semantic dimension.
   - DO NOT create headers that combine multiple dimensions
     (e.g., "compound + temperature", "system at T").

4. **No Semantic Duplication**
   - DO NOT add any header whose meaning overlaps with,
     refines, or rephrases an existing header.
   - If a candidate header can be semantically mapped to an existing one,
     it MUST be ignored.

5. **Dimension vs Value**
   - Headers describe WHAT varies, not specific values.
   - Individual values, value lists, ranges, or grouped values
     MUST NOT be added as headers.

6. **Same-Dimension Aggregation**
   - Multiple entities belonging to the SAME dimension
     (e.g., multiple compounds, materials, components)
     MUST be represented by ONE abstract header.
   - Multi-row or multi-column values do NOT create new headers.
   - For example, Mono-ethylene glycol / Di-ethylene glycol
     only generates ONE "glycol" header.

7. **Different Dimensions MAY Be Split**
   - If a text contains information from DIFFERENT dimensions
     (e.g., "A + B (300 K)"),
     extract ONLY the missing dimensions separately
     (e.g., "composition" and "temperature").

8. **Repeated Column Group Rule**
   - If the table contains horizontally repeated column groups
     with identical internal structure,
     the group labels represent VALUES of ONE shared dimension,
     NOT multiple dimensions.

9. **Header-Level Scope**
   - Missing dimensions may be implied by:
       - Column headers
       - Colspan / rowspan header rows
       - Header-like rows describing experimental context
   - They MUST apply to the table data as a whole.

10. **Rowspan / Multi-row Values**
    - If a semantic dimension is represented by multiple rows (e.g., via rowspan or stacked values),
      all row labels / row values belong to ONE dimension.
    - DO NOT create a separate column for each row value.
    - Only create a single abstracted header representing the dimension.

11. **Ignore Completely**
    - Numeric-only cells
    - Enumerations of values
    - Component indexing (e.g., (1), (2))
    - Chemical parsing beyond explicit text
    - Any downstream interpretation

### Output Rules:
- If NO headers are missing, return:
  []
- If headers ARE missing, return ONLY the additional headers.
- Each header object MUST contain exactly:
  - "name"
  - "raw_name"
  - "brief_description"
  - "single_example"

### Input:

Table HTML snippet:
$table_html_snippet

Existing flattened headers:
$existing_headers

### Output:
Return ONLY a valid JSON list.
No explanations.
No extra text.
""")


user_prompt_for_header_deduplication = Template("""
You are an expert in scientific table header normalization and semantic deduplication.

Your task is to analyze the provided table headers and table snippet,
and REMOVE or MERGE any headers that are **semantically duplicate or overlapping**,
while keeping only the minimal set of distinct semantic dimensions.

### Inputs:
1. `enhanced_headers`: the list of previously enhanced table headers.
2. `table_html_snippet`: the first N rows of the table (including headers).

### Core Goal:
- Ensure each semantic dimension is represented **only once** in the final header list.
- Remove any header that is:
    - Redundant with another header
    - Represents the same underlying dimension as another
    - A duplicate of what can already be inferred from the table or other headers

### Rules (MUST FOLLOW):

1. **Do NOT modify original header meaning**
   - Keep `name`, `raw_name`, `brief_description`, `single_example` intact for non-duplicate headers.
   - Do NOT rename or split existing headers.

2. **Semantic Deduplication**
   - If two headers represent the same dimension (e.g., `glycol` and `compound`), keep only one.
   - Multi-value headers (e.g., `Mono-ethylene glycol / Di-ethylene glycol`) are enough to cover all instances—do not create separate headers for each value.

3. **Multi-row / Multi-column Coverage**
   - Headers already accounting for multi-row (rowspan) or repeated column groups should not be duplicated.

4. **Atomic Dimension Enforcement**
   - Only remove headers if their semantic content is entirely covered by another header.
   - Do NOT remove headers that represent distinct dimensions, even if they are related.

5. **No New Headers**
   - This step is only for deduplication.
   - Do NOT create new headers here.

### Output Rules:
- Return ONLY the deduplicated headers as a JSON list.
- Keep the same structure as `enhanced_headers`:
  - "name"
  - "raw_name"
  - "brief_description"
  - "single_example"
- Do NOT include explanations, comments, or extra text.

### Input:

Enhanced headers:
$enhanced_headers

Table HTML snippet:
$table_html_snippet

### Output:
Return ONLY the deduplicated header list in valid JSON.
""")
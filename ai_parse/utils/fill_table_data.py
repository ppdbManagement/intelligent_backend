import re
from typing import List, Dict, Any
import os
import json
from string import Template
from .ParateraQwenClient import ParateraQwenClient
from .simple_tools import normalize_html_whitespace, extract_first_n_trs, strip_code_fence, get_result_path_from_state_uuid, safe_json_loads
from ..models import *


def fill_table_data(prev_uuid):
    # imagepath和content的映射
    client = ParateraQwenClient()
    table_locate_result_dir = get_result_path_from_state_uuid(
        prev_uuid, "table_locate")
    paginated_merged_tables_file = os.path.join(
        table_locate_result_dir, "paginated_merged_tables.json")
    with open(paginated_merged_tables_file, "r") as f:
        paginated_merged_tables = json.load(f)
    img_path_to_content = {}
    for table in paginated_merged_tables:
        for cell in table["table_content"]:
            img_path = cell["img_path"]
            mineru_content = cell["mineru_content"]
            img_path_to_content[img_path] = mineru_content

    documentParseStatus = DocumentParseStatus.objects.filter(
        uuid=prev_uuid).first()
    flatParseResult = documentParseStatus.parse_result.flat_parse_result
    singleFlatParseResults = flatParseResult.single_flat_results.all()
    filled_table_data = []
    for single_result in singleFlatParseResults:
        origin_table = single_result.origin_table
        table_caption = origin_table.caption
        # 获取所有的header
        singleFlatParseTableHeaders = single_result.headers.all()
        headers = []
        for header in singleFlatParseTableHeaders:
            headers.append(
                {
                    "header_name": header.header_name,
                    "raw_header_name": header.raw_header_name,
                    "description": header.description,
                    "header_order": header.header_order
                }
            )
        # 按照header_order排序
        headers = sorted(headers, key=lambda x: x["header_order"])
        # 去掉header_order
        for header in headers:
            header.pop("header_order")

        experimentTablePictures = origin_table.pictures.all()
        table_contents = []
        for picture in experimentTablePictures:
            img_path = picture.image_path
            img_order = picture.image_order
            if img_path in img_path_to_content:
                mineru_content = img_path_to_content[img_path]
                table_contents.append(
                    {"img_path": img_path, "mineru_content": mineru_content, "img_order": img_order})
        # 根据img_order排序
        table_contents = sorted(table_contents, key=lambda x: x["img_order"])
        filled_datas = []
        prev_context_html = ""
        # 遍历table contents
        for content in table_contents:
            mineru_content = content["mineru_content"]
            header_len = len(headers)
            prompt_filled = user_prompt_for_fill_table_continuation_final.substitute(
                caption=table_caption,
                header=json.dumps(headers, ensure_ascii=False),
                len_header=header_len,
                prev_context_html=prev_context_html,
                current_html=mineru_content
            )
            response = client.simple_chat(
                user_message=prompt_filled
            )
            response_json = safe_json_loads(response)
            data_rows = response_json.get("data", [])
            last_content_html = response_json.get("last_content_html", "")
            filled_datas.extend(data_rows)
            prev_context_html = last_content_html
        filled_table_data.append({
            "caption": table_caption,
            "header": headers,
            "data": filled_datas,
            "table_uuid":str(single_result.uuid)
        })
    return filled_table_data


user_prompt_for_fill_table_continuation_final = Template('''
You are a precise scientific table data filler operating with an explicit experimental context.

Inputs:
- Table caption: "$caption"
- Header (ordered field names): $header
- Header length: $len_header
- Previous active context row (HTML, may be empty):
$prev_context_html
- Current HTML table:
$current_html

Your task:
1. Extract tabular data rows from the current HTML table.
2. Fill them into a structured data frame aligned to the given header.
3. Track the most recent active context row at the END of the current HTML.

Output format (STRICT):
Return a single JSON object with exactly two keys:
{
  "data": [ [...], [...], ... ],
  "last_content_html": "<tr>...</tr>" or ""
}

Definitions:
- A **context row** is an HTML row of the form:
  <tr><td colspan="N">System description (conditions)</td></tr>
- Context rows define global experimental conditions (e.g., system, composition, temperature)
  that apply to all following data rows until a new context row appears.

Rules:

1. **Preserve all text exactly** as it appears in the HTML or caption.
   - Do NOT normalize, clean, translate, or reinterpret any value.

2. **Context handling**:
   - Initialize the active context as `Previous active context row`.
   - While scanning the current HTML top to bottom:
     - If a new context row appears, it becomes the active context.
     - All subsequent data rows inherit this active context.
   - At the end of processing, `last_content_html` MUST be:
     - The last context row encountered in the current HTML, if any;
     - Otherwise, an empty string "".

3. **Row extraction**:
   - Only extract true data rows (rows consisting of multiple data cells).
   - Skip header rows and context rows themselves.

4. **For each output data row and each header field (in order)**:
   a) If the field matches a column header in the current HTML table
      (by semantic meaning of the header text), use the corresponding cell value.
   b) Else, if the field can be inferred from the currently active context row
      (e.g., system name, component indices, temperature), use that value.
   c) Else, if the field can be inferred from the table caption, use that value.
   d) Otherwise, output an empty string ("").

5. **Semantic matching only**:
   - Do NOT rely on column position.
   - Do NOT infer meaning from numeric appearance (e.g., do NOT assume 298.15 is temperature
     unless explicitly stated in a context row or caption).

6. **Context scope rules**:
   - A previous context applies ONLY until replaced by a new context row
     appearing in the current HTML.
   - A new context row always overrides any previous context.

7. **Output shape constraints**:
   - Each row in `"data"` MUST contain exactly `$len_header` string elements.
   - The order MUST exactly match the provided header list.

8. **Output constraints**:
   - Output ONLY valid JSON.
   - No markdown, no comments, no extra text.
   - `"data"` may be an empty list if no data rows are present.
   - `"last_content_html"` may be an empty string if no context row appears.

Now generate the result.
''')

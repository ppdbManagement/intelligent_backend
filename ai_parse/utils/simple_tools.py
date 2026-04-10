import json
from pathlib import Path
import re
from typing import Dict
from ..models import DocumentParseStatus
from config.backendSettings import MEDIA_ROOT
import os
from bs4 import BeautifulSoup

# 一个更健壮的 JSON 解析函数，处理非标准转义字符
def safe_json_loads(s: str):
    # 先尝试直接解析
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass

    # 将所有 \x（x 不是标准转义字符）替换为 \\x
    def escape_backslash(match):
        char = match.group(1)
        if char in '"\\/bfnrtu':
            return match.group(0)  # 保留合法转义
        else:
            return '\\\\' + char   # 把 \x → \\x

    fixed = re.sub(r'\\(.)', escape_backslash, s)
    return json.loads(fixed)


# 从当前的state uuid回溯到某一个状态下的结果存储路径
def get_result_path_from_state_uuid(state_uuid:str,stage:str):
    # 获取当前的状态对象，一定存在
    current_status = DocumentParseStatus.objects.filter(uuid=state_uuid).first()
    if not current_status:
        return None
    # 回溯到指定阶段的状态对象
    while current_status and not (current_status.status == stage and current_status.start_end_flag == "end"):
        # print(f"回溯中，当前状态对象: {current_status}, 阶段: {current_status.status}, 结束标志: {current_status.start_end_flag}")
        current_status = current_status.previous_status
    # 如果找到了指定阶段的状态对象，返回其结果存储路径
    if current_status:
        result_path = current_status.parse_result.result_path
        store_uid = current_status.document.store_uid
        final_dir = os.path.join(MEDIA_ROOT,store_uid,result_path)
        return final_dir
        
    return None

def strip_code_fence(text: str) -> str:
    """
    去除 LLM 返回结果最外层的 ```、```json、```html 等 code fence
    """
    if not text:
        return ""

    cleaned = text.strip()

    # 匹配 ```lang\n ... \n```
    fence_pattern = r'^```(?:json|html|xml|text)?\s*([\s\S]*?)\s*```$'
    match = re.match(fence_pattern, cleaned, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()

    return cleaned


def extract_last_n_trs(html: str, n: int = 4) -> str:
    """
    提取 HTML <table> 中末尾 n 个 <tr>，保留 table 结构
    """
    html = strip_code_fence(html)
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        return ""

    rows = table.find_all("tr")
    selected_rows = rows[-n:] if n > 0 else []

    new_soup = BeautifulSoup("<table></table>", "html.parser")
    new_table = new_soup.table

    for row in selected_rows:
        new_table.append(row)

    return str(new_table)

def extract_first_n_trs(html: str, n: int = 4) -> str:
    """
    提取 HTML <table> 中开头 n 个 <tr>，保留 table 结构
    """
    html = strip_code_fence(html)
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        return ""

    rows = table.find_all("tr")
    selected_rows = rows[:n] if n > 0 else []

    new_soup = BeautifulSoup("<table></table>", "html.parser")
    new_table = new_soup.table

    for row in selected_rows:
        new_table.append(row)

    return str(new_table)

def normalize_html_whitespace(html: str) -> str:
    """
    压缩 HTML 中无意义的换行和多余空白
    不破坏标签结构
    """
    html = strip_code_fence(html)

    # 标签之间的换行 → 单空格
    html = re.sub(r'>\s+<', '><', html)

    # 文本内部连续空白压缩
    html = re.sub(r'\s{2,}', ' ', html)

    return html.strip()


def get_first_n_json_records(parsed_data, n: int = 4):
    """
    获取 JSON（list）开头 n 条
    """
    if not isinstance(parsed_data, list):
        return parsed_data

    return parsed_data[:n]


def get_last_n_json_records(parsed_data, n: int = 4):
    """
    获取 JSON（list）末尾 n 条
    """
    if not isinstance(parsed_data, list):
        return parsed_data

    return parsed_data[-n:] if len(parsed_data) > n else parsed_data

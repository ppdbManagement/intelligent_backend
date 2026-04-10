import json
from string import Template
from .simple_tools import safe_json_loads,get_result_path_from_state_uuid
import os
from .ParateraQwenClient import ParateraQwenClient

# 将一个dict里面的元素填充到另一个dict里面
# 最终的结构如下：
# {
#   "title": "论文标题",
#   "doi": "",
#   "pubName": "",
#   "pubDate": "",
#   "pubVolume": "",
#   "pubPage": "",
#   "abstract": "摘要内容",
#   "authors": ["作者1", "作者2"],
#   "keywords": ["关键词1", "关键词2"]
# }
def merge_dicts(dict1: dict, dict2: dict) -> dict:
    merged = dict1.copy()  # Create a copy of dict1
    # 将dict2中的元素填充到dict1中，如果dict2中的value为空，包括空字符串、None、空列表、空字典等，则不进行填充
    for key, value in dict2.items():
        if value not in [None, '', [], {}]:
            merged[key] = value
    return merged

def metadata_extract_flow(prev_uuid : str):
    mineru_dir = get_result_path_from_state_uuid(prev_uuid,"doc_parse")
    result_subdir = os.listdir(mineru_dir)[0]
    parse_result_dir = os.path.join(mineru_dir,result_subdir,"vlm")
    metadata = {}
    # 解析标题
    title_result = parse_paper_title(parse_result_dir,result_subdir)
    metadata = merge_dicts(metadata, title_result)
    # 解析基础信息
    basic_info_result = parse_basic_info(parse_result_dir,result_subdir)
    metadata = merge_dicts(metadata, basic_info_result)
    # 解析摘要
    abs_result = parse_paper_abs(parse_result_dir,result_subdir)
    metadata = merge_dicts(metadata, abs_result)
    return metadata
    




############# 解析标题 ##############
# 输出格式如下：
# {
#   "title": "论文标题"
# }
system_prompt_title_extract= '''You will be given text that contains the title and/or subtitle information of an academic paper. Your task is to identify and extract the main title of the paper. Ignore subtitles, section headers, footnotes, or any non-title text. If multiple candidate titles appear, select the most complete and representative main paper title. Do not add, remove, or modify any wording—preserve the title exactly as it appears in the input. Return your response strictly in the following JSON format with no additional text or explanation: {"title": ""}
'''

user_prompt_title_extract= Template(
    'Input text: $text'
)
# 解析标题
def parse_paper_title(parse_result_dir,result_subdir):
    title_content = get_title_paragraphs(parse_result_dir,result_subdir)
    user_prompt_filled = user_prompt_title_extract.substitute(text=title_content)
    client = ParateraQwenClient()
    title_content = client.simple_chat(
        system_prompt=system_prompt_title_extract,
        user_message=user_prompt_filled
    )
    try:
        title_dict = safe_json_loads(title_content)
        return title_dict
    except Exception as e:
        return {"error_title": "Failed to parse JSON from the response whilt extracting paper title.", "exception_title": str(e)}

# 获取所有tag为title的段落
def get_title_paragraphs(parse_result_dir,result_subdir):
    title_content_list = []
    # 使用model.json
    model_file = os.path.join(parse_result_dir,f"{result_subdir}_model.json")
    with open(model_file, 'r', encoding='utf-8') as f:
        model_data = json.load(f)
    for page_item in model_data:
            for block_item in page_item:
                if block_item["type"] == "title":
                    title_content_list.append(block_item["content"])
    
    duplicate_removed_list = list(dict.fromkeys(title_content_list))
    title_content = "\n\n".join(duplicate_removed_list)
    
    return title_content

############# 解析基础信息 ##############
# 输出格式如下：
# {
#   "doi": "",
#   "pubName": "",
#   "pubDate": "",
#   "pubVolume": "",
#   "pubPage": ""
# }

system_prompt_basic_info_extract= '''
You are an expert bibliographic data extractor. When given header, footer, or other bibliographic information from a scholarly document, extract only the following fields if they appear explicitly in the input: the DOI (Digital Object Identifier) of the document, the name of the journal or conference where it was published, the publication date, the volume number, and the page range. Preserve all extracted text exactly as it appears—do not paraphrase, reformat, or normalize. If a field is not present in the input, leave its value as an empty string. Return your response strictly in the following JSON format with no additional text or explanation: {\"doi\": \"\", \"pubName\": \"\", \"pubDate\": \"\", \"pubVolume\": \"\", \"pubPage\": \"\"}
'''

user_prompt_basic_info_extract= Template(
    "Here is the bibliographic excerpt from a scholarly document: $prepare_header_data"
)

def parse_basic_info(parse_result_dir,result_subdir):
    header_data = get_header_paragraphs(parse_result_dir,result_subdir)
    user_prompt_filled = user_prompt_basic_info_extract.substitute(prepare_header_data=header_data)
    client = ParateraQwenClient()
    basic_info_content = client.simple_chat(
        system_prompt=system_prompt_basic_info_extract,
        user_message=user_prompt_filled
    )
    try:
        basic_info_dict = safe_json_loads(basic_info_content)
        return basic_info_dict
    except Exception as e:
        return {"error_basic_info": "Failed to parse JSON from the response while extracting basic bibliographic information.", "exception_basic_info": str(e)}

# 获取所有tag为title的段落
def get_header_paragraphs(parse_result_dir,result_subdir):
    header_content_list = []
    # 使用model.json
    model_files = os.path.join(parse_result_dir,f"{result_subdir}_model.json")
    with open(model_files, 'r', encoding='utf-8') as f:
        model_data = json.load(f)
    for page_item in model_data:
            for block_item in page_item:
                if block_item["type"] == "header":
                    header_content_list.append(block_item["content"])
    
    duplicate_removed_list = list(dict.fromkeys(header_content_list))
    header_content = "\n\n".join(duplicate_removed_list)
    return header_content

############ 解析摘要 ##############
# 返回结果结构如下：
# {
#   "abstract": "摘要内容",
#   "authors": ["作者1", "作者2"],
#   "keywords": ["关键词1", "关键词2"]
# }

def parse_paper_abs(parse_result_dir,result_subdir) -> dict:
    # 抽取结构化的元信息（摘要、作者、关键词）是一个复杂的任务，尤其是当PDF文档较长时。为了提高抽取的准确性和完整性，我们可以将PDF文本分块处理，并使用LLM进行多轮交互式抽取。以下是一个示例实现：
    text_blocks = get_text_paragraph_list(parse_result_dir,result_subdir)
    max_iterations = 3
    blocks_per_iteration = 5
    extracted_results = []
    target_keys = ["abstract", "authors", "keywords"]
    conversation_history = []
    iteration = 0
    client = ParateraQwenClient()
    successful_json_parsing_count = 0

    while iteration < max_iterations:
        iteration += 1
        prompt = build_extraction_prompt(
            text_blocks, blocks_per_iteration, iteration)
        if not prompt:
            print("No more text data to process.")
            break

        current_messages = [{"role": "system", "content": system_prompt_abstract_extract}]
        if iteration > 1:
            current_messages.extend(conversation_history)
        current_messages.append({"role": "user", "content": prompt})

        response = client.chat(messages=current_messages, max_tokens=2000)

        conversation_history.append({"role": "user", "content": prompt})
        conversation_history.append({"role": "assistant", "content": response})

        try:
            response_json = safe_json_loads(response)
            extracted_results.append(response_json)
            successful_json_parsing_count += 1
        except json.JSONDecodeError:
            print(f"Failed to parse JSON response in iteration {iteration}.")
            continue

        is_complete, merged_result = is_extraction_complete(
            extracted_results, target_keys)
        if is_complete:
            print("All required keys have been extracted successfully.")
            break

    if successful_json_parsing_count == 0:
        return {"error": "Failed to parse JSON from the response."}

    _, final_result = is_extraction_complete(extracted_results, target_keys)
    return final_result

def is_extraction_complete(extracted_list, required_keys):
    # 合并多个迭代的提取结果，优先保留非空的值，如果有冲突则打印警告
    merged = {}
    for item in extracted_list:
        for key, value in item.items():
            if key not in required_keys:
                continue
            if value in [None, "", [], {}]:
                continue
            if key not in merged:
                merged[key] = value
            else:
                if isinstance(merged[key], str) and isinstance(value, str):
                    if merged[key] != value:
                        # TODO: handle conflict
                        print(
                            f"Conflict for key '{key}': '{merged[key]}' vs '{value}'")
                elif isinstance(merged[key], list) and isinstance(value, list):
                    merged[key].extend(value)
                else:
                    # TODO: handle type conflict
                    print(
                        f"Type conflict for key '{key}': {type(merged[key])} vs {type(value)}")
    # Check completeness
    for key in required_keys:
        if key not in merged:
            return False, merged
    return True, merged


# 获取所有tag为text的段落
def get_text_paragraph_list(parse_result_dir,result_subdir):
    text_content_list = []
    # 使用model.json
    model_files = os.path.join(parse_result_dir,f"{result_subdir}_model.json")
    with open(model_files, 'r', encoding='utf-8') as f:
        model_data = json.load(f)
    for page_item in model_data:
            for block_item in page_item:
                if block_item["type"] == "text":
                    text_content_list.append(block_item["content"])
    
    return text_content_list


def build_extraction_prompt(text_blocks, blocks_per_iter, iteration):
    # 构造当前迭代的文本块
    start_idx = (iteration - 1) * blocks_per_iter
    end_idx = start_idx + blocks_per_iter
    current_blocks = text_blocks[start_idx:end_idx]

    if not current_blocks:
        return None

    joined_text = "\n\n".join(current_blocks)
    if iteration == 1:
        return first_chat_user_prompt_abstract_extract.substitute(text=joined_text)
    else:
        return next_chat_user_prompt_abstract_extract.substitute(text=joined_text)





# System prompt
system_prompt_abstract_extract= '''You are an expert data extractor. Your task is to extract specific information from the provided text data. 
Please ensure that the extracted information is accurate and formatted correctly in JSON.'''

# First chat template
first_chat_user_prompt_abstract_extract= Template('''
You will be given the full text of an academic paper.
Your task is to extract the following information exactly as it appears in the original text, without rewriting, paraphrasing, or normalizing the content.
Fields to extract:

1. Abstract — the paper’s abstract text

2. Authors — the list of author names

3. Keywords — the list of keywords provided in the paper

Extraction rules:
- Do not modify the original wording, punctuation, capitalization, or formatting.
- If a field is not found, return an empty string ("") or empty list ([]) as appropriate.
- Do not infer or generate missing information.

Input text:
$text

Output requirements:
Return the result strictly in the following JSON format, with no additional text or explanation:

{
  "abstract": "",
  "authors": [],
  "keywords": []
}
''')

# Subsequent chat template
next_chat_user_prompt_abstract_extract= Template('''
The previously provided paper content was incomplete.
I will now give you the remaining part of the document.

Your task is to continue extracting the required information from the new content and supplement or update the previously extracted results only if new relevant information is found.

Rules:
- Extract information strictly from the newly provided text.
- Do not repeat or modify previously extracted content unless the new text provides missing or more complete information.
- Do not infer or fabricate information that does not explicitly appear in the text.

New input text:
$text
''')

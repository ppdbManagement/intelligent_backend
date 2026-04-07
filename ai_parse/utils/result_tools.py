from config.backendSettings import MEDIA_ROOT
from ..models import *
import os


# 获取文档解析结果
def get_doc_parse_result(parse_status):
    # 获取解析最终结果的路径
    result_dir = os.path.join(MEDIA_ROOT,parse_status.document.store_uid, parse_status.parse_result.result_path)
    # 该目录下只会有一个文件夹，获取该文件夹的路径
    result_subdir = os.listdir(result_dir)[0]
    markdown_path = os.path.join(result_dir, result_subdir, 'vlm',result_subdir+'.md')
    if os.path.exists(markdown_path):
        with open(markdown_path, 'r', encoding='utf-8') as f:
            markdown_content = f.read()
        return {'markdown_content': markdown_content}
    return {}
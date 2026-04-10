import json

from config.backendSettings import MEDIA_ROOT
from ..models import *
import os
from .simple_tools import *


# 获取文档解析结果
def get_doc_parse_result(parse_status):
    # 获取解析最终结果的路径
    result_dir = os.path.join(MEDIA_ROOT,parse_status.document.store_uid, parse_status.parse_result.result_path)
    # 该目录下只会有一个文件夹，获取该文件夹的路径
    result_subdir = os.listdir(result_dir)[0]
    markdown_path = os.path.join(result_dir, result_subdir, 'vlm',result_subdir+'.md')
    # print(f"markdown_path: {markdown_path}")
    if os.path.exists(markdown_path):
        with open(markdown_path, 'r', encoding='utf-8') as f:
            markdown_content = f.read()
        return {'markdown_content': markdown_content}
    return {}

# 获取元数据解析结果
def get_metadata_extract_result(parse_status):
    # 直接从库里读取
    literature_info = parse_status.parse_result.literature_info
    meta_data = {
        'title': literature_info.title,
        'authors': json.loads(literature_info.authors),
        'pubName': literature_info.journal,
        'abstract': literature_info.abstract,
        'doi'   : literature_info.doi,
        'keywords': json.loads(literature_info.keywords),
        'pubDate': literature_info.publication_date,
        'pubVolume': literature_info.volume,
        'pubPage': literature_info.page,
    }
    return meta_data


# 获取表格定位后的数据
def get_table_locate_result(parse_status):
    res = {}
    # 从数据库里面读取数据
    experimentTableResults = parse_status.parse_result.experiment_table_result
    # 获取里面的所有表格
    singleExperimentTableResults = experimentTableResults.single_table_results.all()
    tables = []
    for singleResult in singleExperimentTableResults:
        table_info = {
            'table_id': singleResult.uuid,
            'caption': singleResult.caption,
            'table_order': singleResult.table_order,
            'tags':json.loads(singleResult.related_segment_tags)
        }
        # 获取里面的表格信息
        experimentTablePictures = singleResult.pictures.all()
        pictures = []
        for picture in experimentTablePictures:
            picture_info = {
                'pic_id': picture.uuid,
                'pic_order': picture.image_order,
            }
            pictures.append(picture_info)
        # 将图片信息按照顺序排序
        pictures.sort(key=lambda x: x['pic_order'])
        table_info['pictures'] = pictures
        tables.append(table_info)
    # 将表格信息按照顺序排序
    tables.sort(key=lambda x: x['table_order'])
    res['tables'] = tables
    # 获取tags的所有信息
    result_dir = get_result_path_from_state_uuid(str(parse_status.uuid), 'table_locate')
    # 读取里面的"segments_with_tags.json"
    segments_with_tags_path = os.path.join(result_dir, 'segments_with_tags.json')
    segments_with_tags = []
    with open(segments_with_tags_path, 'r', encoding='utf-8') as f:
        segments_with_tags = json.load(f)
    res['segments_with_tags'] = segments_with_tags
    
    return res
    
    
    
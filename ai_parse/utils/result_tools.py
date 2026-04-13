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
    
    
def get_table_reconstruct_result(parse_status):
    res = {}
    flatParseResults = parse_status.parse_result.flat_parse_result
    single_flat_parse_results = flatParseResults.single_flat_results.all()

    tables = []

    for singleResult in single_flat_parse_results:
        origin_table = singleResult.origin_table

        table = {
            "table_id": origin_table.uuid,
            "caption": origin_table.caption,  # ✅ 和第一个页面一致
            "table_order": origin_table.table_order,
        }

        # ================= 图片 =================
        experimentTablePictures = origin_table.pictures.all()
        pictures = []

        for picture in experimentTablePictures:
            picture_info = {
                "pic_id": picture.uuid,        # ✅ 保持一致
                "pic_order": picture.image_order,
            }
            pictures.append(picture_info)

        pictures.sort(key=lambda x: x["pic_order"])
        table["pictures"] = pictures

        # ================= 表头 =================
        singleFlatParseTableHeaders = singleResult.headers.all()
        headers = []

        for header in singleFlatParseTableHeaders:
            header_info = {
                "id": header.uuid,  # ✅ 可选（前端一般不依赖）
                "name": header.header_name,  # ✅ 改名
                "raw_name": header.raw_header_name,  # ✅ 改名
                "brief_description": header.description,  # ✅ 改名
                "order": header.header_order,
            }
            headers.append(header_info)

        headers.sort(key=lambda x: x["order"])
        table["headers"] = headers

        tables.append(table)

    tables.sort(key=lambda x: x["table_order"])
    res["tables"] = tables

    return res

def get_data_filling_result(parse_status):
    res = {}
    flat_status = parse_status.previous_status.previous_status
    flatParseResults = flat_status.parse_result.flat_parse_result
    single_flat_parse_results = flatParseResults.single_flat_results.all()
    fillings = []
    # 获取表格填充的所有结果
    result_dir = get_result_path_from_state_uuid(str(parse_status.uuid), 'data_filling')
    data_fill_file_path = os.path.join(result_dir, 'filled_tables.json')
    # 从里面获得table_uuid到data的映射关系
    table_data_mapping = {}
    with open(data_fill_file_path, 'r', encoding='utf-8') as f:
        table_datas = json.load(f)
        for item in table_datas:
            table_uuid = item['table_uuid']
            data = item['data']
            table_data_mapping[table_uuid] = data
    
    
    for singleResult in single_flat_parse_results:
        origin_table = singleResult.origin_table

        filling = {
            "table_id": origin_table.uuid,
            "caption": origin_table.caption,  # ✅ 和第一个页面一致
            "table_order": origin_table.table_order,
        }

        # ================= 图片 =================
        experimentTablePictures = origin_table.pictures.all()
        pictures = []

        for picture in experimentTablePictures:
            picture_info = {
                "pic_id": picture.uuid,        # ✅ 保持一致
                "pic_order": picture.image_order,
            }
            pictures.append(picture_info)

        pictures.sort(key=lambda x: x["pic_order"])
        filling["pictures"] = pictures
        
        # 获取表头
        singleDataFillingTableHeaders = singleResult.headers.all()
        headers = []
        for header in singleDataFillingTableHeaders:
            header_info = {
                "id": header.uuid,  # ✅ 可选（前端一般不依赖）
                "name": header.header_name,  # ✅ 改名
                "raw_name": header.raw_header_name,  # ✅ 改名
                "brief_description": header.description,  # ✅ 改名
                "order": header.header_order,
            }
            headers.append(header_info)
        headers.sort(key=lambda x: x["order"])
        filling["headers"] = headers
        # 获取填充的数据
        filling["data"] = table_data_mapping.get(str(singleResult.uuid), [])
        fillings.append(filling)

    fillings.sort(key=lambda x: x["table_order"])
    res["fillings"] = fillings

    return res

def get_context_extract_result(parse_status):
    res = {}
    # 直接读取存储的context_data
    result_dir = get_result_path_from_state_uuid(str(parse_status.uuid), 'context_extract')
    context_data_path = os.path.join(result_dir, 'context_data.json')
    context_data = {}
    with open(context_data_path, 'r', encoding='utf-8') as f:
        context_data = json.load(f)
    # 遍历一下context_data，如果里面有data这个key，去除
    for item in context_data:
        if 'data' in item:
            del item['data']
    res['context_data'] = context_data
    return res

def get_data_layer_split_result(parse_status):
    res = {}
    # 直接读取存储的split_data
    result_dir = get_result_path_from_state_uuid(str(parse_status.uuid), 'data_layer_split')
    split_data_path = os.path.join(result_dir, 'devided_dataset.json')
    split_data = {}
    with open(split_data_path, 'r', encoding='utf-8') as f:
        split_data = json.load(f)
    for item in split_data:
        # 去除datasets字段，里面数据太大了
        if "datasets" in item:
            del item["datasets"]
        if "related_experiment_setting_segments" in item:
            del item["related_experiment_setting_segments"]
        
        table_uuid = item.get("table_uuid")
        # 获得图片
        singleFlatParseResult = SingleFlatParseResult.objects.filter(uuid = table_uuid).first()
        singleExperimentTableResult = singleFlatParseResult.origin_table
        experimentTablePictures = singleExperimentTableResult.pictures.all()
        pictures = []
        for picture in experimentTablePictures:
            picture_info = {
                "pic_id": picture.uuid,        # ✅ 保持一致
                "pic_order": picture.image_order,
            }
            pictures.append(picture_info)
        pictures.sort(key=lambda x: x["pic_order"])
        item["pictures"] = pictures
    res['split_data'] = split_data
    return res
import json

from config.backendSettings import MEDIA_ROOT
from ..models import *
import os
from .simple_tools import *
from ..remote_api.remote_api import getAlignedShowNameByUUID,literatureDatasetGet


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
            "table_id": singleResult.uuid,
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
            "table_id": singleResult.uuid,
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
    # 遍历一下context_data
    for item in context_data:
        if 'data_preview' in item:
            del item['data_preview']
        data_preview = get_first_n_json_records(item.get('data', []), 3)
        if 'data' in item:
            del item['data']
        item['data_preview'] = data_preview
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

def get_data_alignment_result(parse_status):
    res = {}
     # 直接读取存储的alignment_data
    result_dir = get_result_path_from_state_uuid(str(parse_status.uuid), 'data_alignment')
    alignment_data_path = os.path.join(result_dir, 'alignment_data.json')
    alignment_data = {}
    with open(alignment_data_path, 'r', encoding='utf-8') as f:
        alignment_data = json.load(f)
    results = []
    aligned_compounds_uuid_set = set()
    aligned_unit_uuid_set = set()
    aligned_variable_uuid_set = set()
    aligned_phase_uuid_set = set()
    aligned_property_uuid_set = set()
    for item in alignment_data:
        single_result = {}
        single_result['table_uuid'] = item.get('table_uuid', '')
        single_result['caption'] = item.get('caption', '')
        experiment_phase_info = {}
        if item.get('experiment_phase_info', {}) != {}:
            experiment_phase_info["name"] = item['experiment_phase_info'].get('name', '')
            experiment_phase_info["brief_description"] = item['experiment_phase_info'].get('brief_description', '')
            experiment_phase_info["target_uuid"] = item["experiment_phase_info"].get("aligned_phase",[]).get("target_uuid", "")
            if experiment_phase_info["target_uuid"] != "":
                aligned_phase_uuid_set.add(experiment_phase_info["target_uuid"])
        single_result['experiment_phase_info'] = experiment_phase_info
        # 获得图片
        table_uuid = item.get("table_uuid")
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
        single_result["pictures"] = pictures
        final_datasets = []
        origin_final_datasets = item.get('final_datasets', [])
        for dataset in origin_final_datasets:
            processed_dataset = {}
            variable_headers = dataset.get('variable_headers', [])
            processed_variable_headers = []
            for header in variable_headers:
                processed_header = {}
                processed_header['name'] = header.get('name', '')
                processed_header['description'] = header.get('description', '')
                processed_header['related_compounds'] = header.get('related_compounds', [])
                processed_header['unit_target_uuid'] = header.get('aligned_unit',{}).get('target_uuid', '')
                processed_header['unit_scale'] = header.get('aligned_unit',{}).get('scale', 1.0)
                processed_header['variable_target_uuid'] = header.get('aligned_variable',{}).get('target_uuid', '')
                processed_variable_headers.append(processed_header)
                if processed_header['variable_target_uuid'] != '':
                    aligned_variable_uuid_set.add(processed_header['variable_target_uuid'])
                if processed_header['unit_target_uuid'] != '':
                    aligned_unit_uuid_set.add(processed_header['unit_target_uuid'])
            processed_dataset['variable_headers'] = processed_variable_headers
            property_headers = dataset.get('property_headers', [])
            processed_property_headers = []
            for header in property_headers:
                processed_header = {}
                processed_header['name'] = header.get('name', '')
                processed_header['description'] = header.get('description', '')
                processed_header['related_compounds'] = header.get('related_compounds', [])
                processed_header['unit_target_uuid'] = header.get('aligned_unit',{}).get('target_uuid', '')
                processed_header['unit_scale'] = header.get('aligned_unit',{}).get('scale', 1.0)
                processed_header['property_target_uuid'] = header.get('aligned_property',{}).get('target_uuid', '')
                processed_property_headers.append(processed_header)
                if processed_header['property_target_uuid'] != '':
                    aligned_property_uuid_set.add(processed_header['property_target_uuid'])
                if processed_header['unit_target_uuid'] != '':
                    aligned_unit_uuid_set.add(processed_header['unit_target_uuid'])
            processed_dataset['property_headers'] = processed_property_headers
            processed_dataset['compounds'] = dataset.get('compounds', [])
            processed_dataset['aligned_compounds'] = dataset.get('aligned_compounds', {})
            for compound_key,compound_value in dataset.get('aligned_compounds', {}).items():
                if compound_value.get('target_uuid', '') != '':
                    aligned_compounds_uuid_set.add(compound_value.get('target_uuid', ''))
            configurations = dataset.get('configurations', [])
            processed_configurations = []
            for config in configurations:
                processed_config = {}
                processed_config['name'] = config.get('name', '')
                processed_config['value'] = config.get('value', '')
                processed_config['unit'] = config.get('unit', '')
                if "target_value" in processed_config:
                    processed_config['target_value'] = config.get('target_value', '')
                else:
                    processed_config['target_value'] = processed_config['value']
                processed_config['description'] = config.get('description', '')
                processed_config['related_compounds'] = config.get('related_compounds', [])
                processed_config['unit_target_uuid'] = config.get('aligned_unit',{}).get('target_uuid', '')
                processed_config['variable_target_uuid'] = config.get('aligned_variable', {}).get('target_uuid', '')
                processed_configurations.append(processed_config)
                if processed_config['variable_target_uuid'] != '':
                    aligned_variable_uuid_set.add(processed_config['variable_target_uuid'])
                if processed_config['unit_target_uuid'] != '':
                    aligned_unit_uuid_set.add(processed_config['unit_target_uuid'])
            processed_dataset['configurations'] = processed_configurations
            final_datasets.append(processed_dataset)
        single_result['final_datasets'] = final_datasets
        results.append(single_result)
    # 调用接口查找所以uuid对应的show name
    query_data = {
        "compounds": list(aligned_compounds_uuid_set),
        "units": list(aligned_unit_uuid_set),
        "variables": list(aligned_variable_uuid_set),
        "phases": list(aligned_phase_uuid_set),
        "properties": list(aligned_property_uuid_set)
    }
    response = getAlignedShowNameByUUID(query_data)
    uuid_to_show_name_mapping = response.get("data",{}).get("uuid_to_show_name_mapping", {})
    # 格式也还是
    # uuid_to_show_name_mapping : {
    #     "compounds": {}
    #     "units": {}
    #     "variables": {}
    #     "phases": {}
    #     "properties": {}
    # }
    # 将show name添加到结果里
    for single_result in results:
        for dataset in single_result.get('final_datasets', []):
            # 相态的show name
            phase_uuid = single_result.get('experiment_phase_info', {}).get('target_uuid', '')
            if phase_uuid != '':
                single_result['experiment_phase_info']['phase_show_name'] = uuid_to_show_name_mapping.get('phases', {}).get(phase_uuid, '')
            for header in dataset.get('variable_headers', []):
                variable_uuid = header.get('variable_target_uuid', '')
                unit_uuid = header.get('unit_target_uuid', '')
                if variable_uuid != '':
                    header['variable_show_name'] = uuid_to_show_name_mapping.get('variables', {}).get(variable_uuid, '')
                else:
                    header['variable_show_name'] = ''
                if unit_uuid != '':
                    header['unit_show_name'] = uuid_to_show_name_mapping.get('units', {}).get(unit_uuid, '')
                else:
                    header['unit_show_name'] = ''
            for header in dataset.get('property_headers', []):
                property_uuid = header.get('property_target_uuid', '')
                unit_uuid = header.get('unit_target_uuid', '')
                if property_uuid != '':
                    header['property_show_name'] = uuid_to_show_name_mapping.get('properties', {}).get(property_uuid, '')
                else:
                    header['property_show_name'] = ''
                if unit_uuid != '':
                    header['unit_show_name'] = uuid_to_show_name_mapping.get('units', {}).get(unit_uuid, '')
                else:
                    header['unit_show_name'] = ''
            for config in dataset.get('configurations', []):
                variable_uuid = config.get('variable_target_uuid', '')
                unit_uuid = config.get('unit_target_uuid', '')
                if variable_uuid != '':
                    config['variable_show_name'] = uuid_to_show_name_mapping.get('variables', {}).get(variable_uuid, '')
                else:
                    config['variable_show_name'] = ''
                if unit_uuid != '':
                    config['unit_show_name'] = uuid_to_show_name_mapping.get('units', {}).get(unit_uuid, '')
                else:
                    config['unit_show_name'] = ''
            for compound_key,compound_value in dataset.get('aligned_compounds', {}).items():
                compound_uuid = compound_value.get('target_uuid', '')
                if compound_uuid != '':
                    compound_value['compound_show_name'] = uuid_to_show_name_mapping.get('compounds', {}).get(compound_uuid, '')
                else:
                    compound_value['compound_show_name'] = ''
    res['alignment_results'] = results
    return res
        
def get_data_storage_result(parse_status):
    res = {}
    # 直接读取存储的storage_data
    result_dir = get_result_path_from_state_uuid(str(parse_status.uuid), 'data_storage')
    storage_data_path = os.path.join(result_dir, 'storage_result.json')
    storage_data = {}
    with open(storage_data_path, 'r', encoding='utf-8') as f:
        storage_data = json.load(f)
    res = literatureDatasetGet(storage_data)
    if res.get("code", -1) != 200:
        return {}
    return res.get("data", {}).get("literature_dataset_info", {})
    
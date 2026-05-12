
import re
from typing import List, Dict, Any
import os
import json
from string import Template
from .ParateraQwenClient import ParateraQwenClient
from .simple_tools import  get_result_path_from_state_uuid, get_status_object_from_state_uuid
from ..models import *
from ..remote_api.remote_api import dataStotagePost


# 先检查能够入库
def check_can_store_in_db(prev_uuid):
    result_dir = get_result_path_from_state_uuid(prev_uuid, 'data_alignment')
    alignment_data_path = os.path.join(result_dir, 'alignment_data.json')
    alignment_data = {}
    with open(alignment_data_path, 'r', encoding='utf-8') as f:
        alignment_data = json.load(f)
    for item in alignment_data:
        # 检查相态对齐
        if item.get('experiment_phase_info', {}) != {}:
            phase_name = item['experiment_phase_info'].get('name', '')
            if phase_name != "" and (item.get('experiment_phase_info', {}).get("aligned_phase",{})=={} or item.get('experiment_phase_info', {}).get("aligned_phase",{}).get("target_uuid","")==""):
                return False, "相态对齐不完整，无法入库"
        final_datasets = item.get('final_datasets', [])
        for dataset in final_datasets:
            # 组分
            compounds = dataset.get('compounds', [])
            aligned_compounds = dataset.get("aligned_compounds",{})
            for compound_name in compounds:
                if compound_name not in aligned_compounds:
                    return False, f"组分{compound_name}没有进行对齐，无法入库"
                if aligned_compounds[compound_name].get("target_uuid","") == "" or aligned_compounds[compound_name].get("target_uuid","") == None:
                    return False, f"组分{compound_name}没有对齐到数据库中的实体，无法入库"
            # 反应条件
            variable_headers = dataset.get('variable_headers', [])
            for header in variable_headers:
                if header.get("aligned_unit",{}).get("target_uuid","") == "":
                    return False, "反应条件的单位没有对齐到数据库中的实体，无法入库"
                if header.get("aligned_variable",{}).get("target_uuid","") == "":
                    return False, "反应条件的变量没有对齐到数据库中的实体，无法入库"
            # 实验物性
            property_headers = dataset.get('property_headers', [])
            for header in property_headers:
                if header.get("aligned_unit",{}).get("target_uuid","") == "":
                    return False, "实验物性的单位没有对齐到数据库中的实体，无法入库"
                if header.get("aligned_property",{}).get("target_uuid","") == "":
                    return False, "实验物性的物性名称没有对齐到数据库中的实体，无法入库"
    return True,None
        
            
            



def data_storage_util(prev_uuid):
    result_dir = get_result_path_from_state_uuid(prev_uuid, 'data_alignment')
    alignment_data_path = os.path.join(result_dir, 'alignment_data.json')
    if os.path.exists(alignment_data_path):
        with open(alignment_data_path, 'r') as f:
            alignment_data = json.load(f)
    else:
        alignment_data = []
    # 进行一些数据处理和舍弃
    for item in alignment_data:
        if "related_experiment_setting_segments" in item:
            del item["related_experiment_setting_segments"]
        if "datasets" in item:
            del item["datasets"]
        for dataset in item.get('final_datasets', []):
            scale_list = []
            variable_headers = dataset.get('variable_headers', [])
            for header in variable_headers:
                scale = header.get("aligned_unit",{}).get("scale", 1.0)
                scale_list.append(scale)
            property_headers = dataset.get('property_headers', [])
            for header in property_headers:
                scale = header.get("aligned_unit",{}).get("scale", 1.0)
                scale_list.append(scale)
            # 对data_rows进行处理，里面的都是字符串，乘以scale后变成数值，再转为字符串
            data_rows = dataset.get('data_rows', [])
            new_data_rows = []
            for row in data_rows:
                new_row = []
                for i,cell in enumerate(row):
                    try:
                        value = float(cell) * (scale_list[i] if i < len(scale_list) else 1.0)
                        new_row.append(str(value))
                    except:
                        new_row.append(cell)
                new_data_rows.append(new_row)
            dataset['data_rows'] = new_data_rows
    # 读取基础信息metadata_extract
    metadata_extract_status = get_status_object_from_state_uuid(prev_uuid, 'metadata_extract')
    literature_info = metadata_extract_status.parse_result.literature_info
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
    post_data = {
        'meta_data': meta_data,
        'alignment_data': alignment_data
    }
    
    resultData = dataStotagePost(post_data)
    literature_uuid = resultData.get("data",{}).get('literature_uuid', '')
    return {
        'literature_uuid': literature_uuid
    }
    
    
    
            
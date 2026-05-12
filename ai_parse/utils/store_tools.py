import json

from config.backendSettings import MEDIA_ROOT
from ..models import *
import os
from .simple_tools import *


def store_doc_parse_result(parse_status,rb_data):
    # TODO：暂时不处理这个结果
    # 存储解析结果
    return None

def store_metadata_extract_result(parse_status,rb_data):
    parse_result = parse_status.parse_result
    literature_info = parse_result.literature_info
    result = rb_data.get('result', {})
    # 更新文献信息
    literature_info.title = result.get('title', '')
    # 作者信息是一个list，进行strip然后去除空字符串
    authors = result.get('authors', [])
    authors = [author.strip() for author in authors if author.strip()]
    literature_info.authors = json.dumps(authors, ensure_ascii=False)
    literature_info.journal = result.get('pubName', '')
    literature_info.abstract = result.get('abstract', '')
    literature_info.doi = result.get('doi', '')
    keywords = result.get('keywords', [])
    keywords = [keyword.strip() for keyword in keywords if keyword.strip()]
    literature_info.keywords = json.dumps(keywords, ensure_ascii=False)
    literature_info.publication_date = result.get('pubDate', '')
    literature_info.volume = result.get('pubVolume', '')
    literature_info.page = result.get('pubPage', '')
    literature_info.save()
    return None

def store_table_locate_result(parse_status, rb_data):
    # 打印一下路径
    parse_result = parse_status.parse_result
    experiment_table_result = parse_result.experiment_table_result
    result = rb_data.get('tables', [])

    # ✅ 转 UUID
    table_id_list = [uuid.UUID(item.get('table_id')) for item in result]

    single_qs = experiment_table_result.single_table_results.all()
    # ✅ 1. 删除多余的（CASCADE 自动删 pictures）
    single_qs.exclude(uuid__in=table_id_list).delete()

    # ✅ 2. 一次性查出所有需要更新的对象（避免 N+1）
    table_map = {
        obj.uuid: obj
        for obj in single_qs.filter(uuid__in=table_id_list)
    }
    # ✅ 3. 更新字段
    update_list = []
    for item in result:
        table_id = uuid.UUID(item.get('table_id'))
        table_obj = table_map.get(table_id)

        if not table_obj:
            continue  # 防御性写法

        segment_tags = item.get('tags', [])
        segment_tags = [tag.strip() for tag in segment_tags if tag.strip()]

        table_obj.related_segment_tags = json.dumps(segment_tags, ensure_ascii=False)
        update_list.append(table_obj)

    # ✅ 4. 批量更新（性能更好）
    if update_list:
        type(update_list[0]).objects.bulk_update(
            update_list,
            ['related_segment_tags']
        )

    return None
    
    
import uuid
from django.db import models

def store_table_reconstruct_result(parse_status, rb_data):
    parse_result = parse_status.parse_result
    flat_parse_result = parse_result.flat_parse_result

    result = rb_data.get('tables', [])

    # ========= 1. UUID 统一 =========
    table_id_list = [
        uuid.UUID(item.get('table_id'))
        for item in result
        if item.get('table_id')
    ]
    # ========= 2. Flat result 删除 =========
    single_qs = flat_parse_result.single_flat_results.all()
    # 打印一下现有的 UUID 列表
    existing_uuids = list(single_qs.values_list('uuid', flat=True))
    to_delete_qs = single_qs.exclude(uuid__in=table_id_list)
    to_delete_qs.delete()

    # ========= 3. Headers 同步（核心新增） =========
    for item in result:
        table_id = item.get("table_id")
        headers_data = item.get("headers", [])

        if not table_id:
            continue

        try:
            table_uuid = uuid.UUID(table_id)
        except:
            continue

        # 当前 table
        table_obj = single_qs.filter(uuid=table_uuid).first()
        if not table_obj:
            continue

        # ========= headers sync =========
        existing_qs = table_obj.headers.all()
        existing_map = {str(h.uuid): h for h in existing_qs}
        existing_ids = set(existing_map.keys())

        payload_ids = set()

        max_order = existing_qs.aggregate(
            max_order=models.Max("header_order")
        )["max_order"] or -1

        to_create = []
        to_update = []

        for h in headers_data:
            hid = h.get("id")
            name = (h.get("name") or "").strip()

            # ❌ 空 name 不处理
            if not name:
                continue

            # ========= update =========
            if hid and hid in existing_map:
                obj = existing_map[hid]
                payload_ids.add(hid)

                obj.header_name = name
                obj.raw_header_name = h.get("raw_name")
                obj.description = h.get("brief_description")

                to_update.append(obj)

            # ========= create =========
            else:
                max_order += 1

                to_create.append(
                    SingleFlatParseTableHeader(
                        single_flat_parse_result=table_obj,
                        header_name=name,
                        raw_header_name=h.get("raw_name"),
                        description=h.get("brief_description"),
                        header_order=max_order,
                    )
                )

        # ========= delete =========
        to_delete_ids = existing_ids - payload_ids
        if to_delete_ids:
            table_obj.headers.filter(uuid__in=to_delete_ids).delete()

        # ========= bulk ops =========
        if to_create:
            SingleFlatParseTableHeader.objects.bulk_create(to_create)

        if to_update:
            SingleFlatParseTableHeader.objects.bulk_update(
                to_update,
                ["header_name", "raw_header_name", "description"]
            )

    return None

def store_data_filling_result(parse_status, rb_data):
    fillings_data = rb_data.get('fillings', [])
    result_dir = get_result_path_from_state_uuid(str(parse_status.uuid), "data_filling")
    data_fill_file_path = os.path.join(result_dir, 'filled_tables.json')
    # 读取原有数据
    if os.path.exists(data_fill_file_path):
        with open(data_fill_file_path, 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
    else:
        existing_data = []
    # 将fillings_data变成一个dict，key是table_uuid，value是对应的填充数据data
    fillings_dict = {}
    for item in fillings_data:
        table_id = item.get('table_id')
        data = item.get('data', [])
        if table_id:
            fillings_dict[table_id] = data
        # 先对数据进行处理，data是一个二维数组，遍历每一行，如果这一行的所有单元格都是空字符串或者null，就把这一行删除掉
        processed_data = []
        for row in data:
            if any(cell for cell in row if cell not in [None, ""]):
                processed_data.append(row)
        fillings_dict[table_id] = processed_data
    # 遍历existing_data
    for item in existing_data:
        table_uuid = item.get('table_uuid')
        if table_uuid in fillings_dict:
            print(f"Updating table_uuid {table_uuid} with new data.")
            item['data'] = fillings_dict[table_uuid]
    # 将更新后的数据写回文件
    with open(data_fill_file_path, 'w', encoding='utf-8') as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=2)
    
    return None

def store_context_extract_result(parse_status, rb_data):
    result_dir = get_result_path_from_state_uuid(str(parse_status.uuid), "context_extract")
    context_file_path = os.path.join(result_dir, 'context_data.json')
    context_data = rb_data.get('context_data', [])
    # 读取原有数据
    if os.path.exists(context_file_path):
        with open(context_file_path, 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
    else:
        existing_data = []
    # 将context_data变成一个dict，key是table_uuid，value是这个item
    context_dict = {}
    for item in context_data:
        table_uuid = item.get('table_uuid')
        if table_uuid:
            context_dict[table_uuid] = item
    for item in existing_data:
        table_uuid = item.get('table_uuid')
        if table_uuid in context_dict:
            print(f"Updating context for table_uuid {table_uuid}.")
            # 更新compounds_ref_header_name，compounds，quantitative_experimental_configurations
            item['compounds_ref_header_name'] = context_dict[table_uuid].get('compounds_ref_header_name', "")
            compounds = context_dict[table_uuid].get('compounds', [])
            # 处理一下compounds，去掉其中的空字符串或者null
            processed_compounds = []
            for compound in compounds:
                if compound not in [None, ""]:
                    processed_compounds.append(compound)
            item['compounds'] = processed_compounds
            # 处理一下quantitative_experimental_configurations，里面的name和value必须同时存在且不为空字符串或者null，否则就删除这一项
            quantitative_experimental_configurations = context_dict[table_uuid].get('quantitative_experimental_configurations', [])
            processed_qec = []
            for qec in quantitative_experimental_configurations:
                name = qec.get('name')
                value = qec.get('value')
                if name and value and name not in [None, ""] and value not in [None, ""]:
                    processed_qec.append(qec)
            item['quantitative_experimental_configurations'] = processed_qec
    # 将更新后的数据写回文件
    with open(context_file_path, 'w', encoding='utf-8') as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=2)
    return None

def store_data_layer_split_result(parse_status, rb_data):
    result_dir = get_result_path_from_state_uuid(str(parse_status.uuid), "data_layer_split")
    print(f"Storing data layer split result to {result_dir}")
    split_file_path = os.path.join(result_dir, 'devided_dataset.json')
    split_data = rb_data.get('split_data', [])
    # 读取原有数据
    if os.path.exists(split_file_path):
        with open(split_file_path, 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
    else:
        existing_data = []
    # 将split_data变成一个dict，key是table_uuid，value是这个item
    split_dict = {}
    for item in split_data:
        table_uuid = item.get('table_uuid')
        if table_uuid:
            split_dict[table_uuid] = item
    
    # 遍历existing_data
    for item in existing_data:
        # 肯定在的
        table_uuid = item.get('table_uuid')
        if table_uuid not in split_dict:
            continue
        item['final_datasets'] = split_dict[table_uuid].get('final_datasets', [])
        # 最后确认一下，related_compounds是否都来自于compounds
        
        for dataset in item['final_datasets']:
            compounds = dataset.get('compounds', [])
            # 去除里面strip之后的空字符串或者null
            compounds = [c for c in compounds if c and c.strip()]
            variable_headers = dataset.get('variable_headers', [])
            for variable in variable_headers:
                related_compounds = variable.get('related_compounds', [])
                # 只保留那些在compounds中的
                related_compounds = [rc for rc in related_compounds if rc in compounds]
                variable['related_compounds'] = related_compounds
            property_headers = dataset.get('property_headers', [])
            for prop in property_headers:
                related_compounds = prop.get('related_compounds', [])
                # 只保留那些在compounds中的
                related_compounds = [rc for rc in related_compounds if rc in compounds]
                prop['related_compounds'] = related_compounds
            configurations = dataset.get('configurations', [])
            for config in configurations:
                related_compounds = config.get('related_compounds', [])
                # 只保留那些在compounds中的
                related_compounds = [rc for rc in related_compounds if rc in compounds]
                config['related_compounds'] = related_compounds
        
    # 将更新后的数据写回文件
    with open(split_file_path, 'w', encoding='utf-8') as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=2)
    return None
        
        
        
def store_data_alignment_result(parse_status, rb_data):
    result_dir = get_result_path_from_state_uuid(str(parse_status.uuid), "data_alignment")
    print(f"Storing data alignment result to {result_dir}")
    alignment_file_path = os.path.join(result_dir, 'alignment_data.json')
    alignment_data = rb_data.get('alignment_results', [])
    # 读取原有数据
    if os.path.exists(alignment_file_path):
        with open(alignment_file_path, 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
    else:
        existing_data = []
    # 遍历地读取每一个数据，因为会是对应的
    for origin_item,updated_item in zip(existing_data, alignment_data):
        # 直接更新aligned_datasets字段
        # 先更新experiment_phase_info
        if 'experiment_phase_info' in origin_item and origin_item['experiment_phase_info'] != {}:
            if "aligned_phase" in origin_item['experiment_phase_info'] and origin_item['experiment_phase_info']["aligned_phase"] != {}:
                origin_item['experiment_phase_info']["aligned_phase"]["target_uuid"] = updated_item.get('experiment_phase_info', {}).get("target_uuid", "")
        origin_final_datasets = origin_item.get('final_datasets', [])
        updated_final_datasets = updated_item.get('final_datasets', [])
        for origin_dataset, updated_dataset in zip(origin_final_datasets, updated_final_datasets):
            # 更新aligned_compounds
            origin_dataset['aligned_compounds'] = updated_dataset.get('aligned_compounds', {})
            # 更新variable_headers
            origin_variable_headers = origin_dataset.get('variable_headers', [])
            updated_variable_headers = updated_dataset.get('variable_headers', [])
            for origin_variable, updated_variable in zip(origin_variable_headers, updated_variable_headers):
                if "aligned_unit" not in origin_variable:
                    origin_variable['aligned_unit'] = {}
                origin_variable["aligned_unit"]["target_uuid"] = updated_variable.get("unit_target_uuid", "")
                origin_variable["aligned_unit"]["scale"] = updated_variable.get("unit_scale",1.0)
                if "aligned_variable" not in origin_variable:
                    origin_variable['aligned_variable'] = {}
                origin_variable["aligned_variable"]["target_uuid"] = updated_variable.get("variable_target_uuid","")
            # 更新property_headers
            origin_property_headers = origin_dataset.get('property_headers', [])
            updated_property_headers = updated_dataset.get('property_headers', [])
            for origin_prop, updated_prop in zip(origin_property_headers, updated_property_headers):
                if "aligned_unit" not in origin_prop:
                    origin_prop['aligned_unit'] = {}
                origin_prop["aligned_unit"]["target_uuid"] = updated_prop.get("unit_target_uuid", "")
                origin_prop["aligned_unit"]["scale"] = updated_prop.get("unit_scale",1.0)
                if "aligned_property" not in origin_prop:
                    origin_prop['aligned_property'] = {}
                origin_prop["aligned_property"]["target_uuid"] = updated_prop.get("property_target_uuid","")
            # 更新configurations
            origin_configurations = origin_dataset.get('configurations', [])
            for origin_config, updated_config in zip(origin_configurations, updated_item.get('final_datasets', [])[0].get('configurations', [])):
                if "target_value" in updated_config:
                    origin_config["aligned_value"] = updated_config.get("target_value", "")
                else:
                    origin_config["aligned_value"] = origin_config.get("value", "")
                if "aligned_unit" not in origin_config:
                    origin_config['aligned_unit'] = {}
                origin_config["aligned_unit"]["target_uuid"] = updated_config.get("unit_target_uuid", "")
                if "aligned_variable" not in origin_config:
                    origin_config['aligned_variable'] = {} 
                origin_config["aligned_variable"]["target_uuid"] = updated_config.get("variable_target_uuid","")
    # 将更新后的数据写回文件    
    with open(alignment_file_path, 'w', encoding='utf-8') as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=2)
    return None
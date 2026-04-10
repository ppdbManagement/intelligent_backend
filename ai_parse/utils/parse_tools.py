import json
import subprocess

from ..models import *
from config.backendSettings import MEDIA_ROOT
import os
from .metadata_extract import metadata_extract_flow
from .merge_paginated_tables import merge_paginated_tables
from .find_related_segment import find_related_segment,integrate_related_segments,build_tag_content_map

# 获取一个doc的原始文件路径
def get_raw_pdf_path(doc):
    path = os.path.join(MEDIA_ROOT,str(doc.store_uid),doc.file_name)
    return path

# 生成一个doc的解析目录
def make_parse_dir(doc):
    path_uid = str(uuid.uuid4())
    dir = os.path.join(MEDIA_ROOT,str(doc.store_uid),path_uid)
    os.makedirs(dir, exist_ok=True)
    return dir, path_uid
    


def async_parse(doc,stage,prev):
    #["doc_parse","metadata_extract","table_locate","table_reconstruct","data_filling","header_split","data_layer_split","data_alignment","data_storage"]:
    # 先将doc的状态改为正在解析
    print(f"Starting {stage} for document ")
    doc.current_status = "Parsing"
    doc.save()
    if stage == "doc_parse":
        # 进行文档解析
        # 解析完成后，更新文档状态为解析完成
        doc_parse(doc)
    elif stage == "metadata_extract":
        # 进行元数据提取
        metadata_extract(doc,prev)
    elif stage == "table_locate":
        # 进行表格定位
        table_locate(doc,prev)
    elif stage == "table_reconstruct":
        # 进行表格重建
        pass
    elif stage == "data_filling":
        # 进行数据填充
        pass
    elif stage == "header_split":
        # 进行表头拆分
        pass
    elif stage == "data_layer_split":
        # 进行数据层拆分
        pass
    elif stage == "data_alignment":
        # 进行数据对齐
        pass
    elif stage == "data_storage":
        # 进行数据存储
        pass
    
    
# 第一步：文档解析
def doc_parse(doc):
    # 进行文档解析的具体实现
    # 创建一个parse status
    startParseStatus = DocumentParseStatus.objects.create(document=doc, status="doc_parse",start_end_flag="start")
    # 生成一个路径的uuid
    path_dir, path_uid = make_parse_dir(doc)
    # 构建mineru的指令
    cmd = [
        "/data_extend/qjk_workspace/anacondaSpace/envs/mineru/bin/mineru",
        "-p",  get_raw_pdf_path(doc),
        "-o", path_dir,
        "-b", "vlm-http-client",
        "-u", "http://127.0.0.1:30000"
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=600  # 10分钟超时，防止卡死
        )
        # 成果了
        docParseResult = DocumentParseResult.objects.create(result_path=path_uid)
        endParseStatus = DocumentParseStatus.objects.create(document=doc, status="doc_parse",start_end_flag="end",previous_status=startParseStatus,parse_result=docParseResult)
        doc.current_status = "Stopping"
        doc.save()
        print(f"Document parsing completed successfully for document {doc}")
        
    except Exception as e:
        # 创建一个失败的status
        failEndParseStatus = DocumentParseStatus.objects.create(document=doc, status="doc_parse",start_end_flag="end",previous_status=startParseStatus,error_message=str(e))        
        doc.current_status = "Failed"
        doc.save()


# 第二步：元数据提取
def metadata_extract(doc,prev):
    prev_status = DocumentParseStatus.objects.filter(uuid=prev).first()
    startParseStatus = DocumentParseStatus.objects.create(document=doc, status="metadata_extract",start_end_flag="start",previous_status=prev_status)
    try:
        # 进行元数据提取的具体实现
        meta_data = metadata_extract_flow(prev)
        # 成功了，先把结果存储到一个文件里
        path_dir, path_uid = make_parse_dir(doc)
        result_path = os.path.join(path_dir,"metadata.json")
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(meta_data, f, ensure_ascii=False, indent=4)
        # 创建一个LiteratureInfo
        literature_info = LiteratureInfo.objects.create(
            title=meta_data.get("title", ""),
            authors = json.dumps(meta_data.get("authors", []), ensure_ascii=False),
            journal=meta_data.get("pubName", ""),
            abstract=meta_data.get("abstract", ""),
            doi=meta_data.get("doi", ""),
            keywords = json.dumps(meta_data.get("keywords", []), ensure_ascii=False),
            publication_date=meta_data.get("pubDate", ""),
            volume=meta_data.get("pubVolume", ""),
            page=meta_data.get("pubPage", ""),
        )
        # 创建一个DocumentParseResult
        docParseResult = DocumentParseResult.objects.create(result_path=path_uid,literature_info=literature_info)
        endParseStatus = DocumentParseStatus.objects.create(document=doc, status="metadata_extract",start_end_flag="end",previous_status=startParseStatus,parse_result=docParseResult)
        doc.current_status = "Stopping"
        doc.save()
        print(f"Metadata extraction completed successfully for document {doc}")
    except Exception as e:
        # 创建一个失败的status
        failEndParseStatus = DocumentParseStatus.objects.create(document=doc, status="metadata_extract",start_end_flag="end",previous_status=startParseStatus,error_message=str(e))        
        doc.current_status = "Failed"
        doc.save()
    
# 第三步：表格定位
def table_locate(doc,prev):
    prev_status = DocumentParseStatus.objects.filter(uuid=prev).first()
    startParseStatus = DocumentParseStatus.objects.create(document=doc, status="table_locate",start_end_flag="start",previous_status=prev_status)
    try:
        # 先创建一个解析结果的目录
        path_dir, path_uid = make_parse_dir(doc)
        paginated_merged_tables = merge_paginated_tables(prev)
        # 将结果存储到一个文件里
        result_path = os.path.join(path_dir,"paginated_merged_tables.json")
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(paginated_merged_tables, f, ensure_ascii=False, indent=4)
        # 开始表格定位的具体实现
        related_segments = find_related_segment(prev,paginated_merged_tables)
        with open(os.path.join(path_dir,"related_segments.json"), "w", encoding="utf-8") as f:
            json.dump(related_segments, f, ensure_ascii=False, indent=4)
        # 将结果进行融合
        tables_with_related_segments = integrate_related_segments(paginated_merged_tables, related_segments)
        with open(os.path.join(path_dir,"tables_with_related_segments.json"), "w", encoding="utf-8") as f:
            json.dump(tables_with_related_segments, f, ensure_ascii=False, indent=4)
        # 为了结果展示，还将tag和段落的映射单独做一个文件
        segments_with_tags = build_tag_content_map(prev)
        with open(os.path.join(path_dir,"segments_with_tags.json"), "w", encoding="utf-8") as f:
            json.dump(segments_with_tags, f, ensure_ascii=False, indent=4)

        # 1️⃣ 创建父对象
        experiment_table_result = ExperimentTableResults.objects.create()

        single_table_list = []
        picture_list = []

        # 2️⃣ 先构造 SingleExperimentTableResult（不入库）
        for idx, table in enumerate(tables_with_related_segments):
            segments = table.get("related_experiment_setting_segments", [])

            single = SingleExperimentTableResult(
                caption=table.get("table_caption", ""),
                table_order=idx,
                related_segment_tags=json.dumps(
                    [item.get("tag") for item in segments if "tag" in item],
                    ensure_ascii=False
                ),
                experiment_table_results=experiment_table_result
            )

            single_table_list.append(single)

        # 3️⃣ 批量创建 SingleExperimentTableResult
        SingleExperimentTableResult.objects.bulk_create(single_table_list)

        # ⚠️ 关键点：bulk_create 后对象才有 id

        # 4️⃣ 再构造图片（依赖已保存的 single）
        for single, table in zip(single_table_list, tables_with_related_segments):
            table_contents = table.get("table_content", [])

            for pic_idx, pic in enumerate(table_contents):
                picture_list.append(
                    ExperimentTablePicture(
                        image_path=pic.get("img_path", ""),
                        image_order=pic_idx,
                        table_result=single
                    )
                )

        # 5️⃣ 批量创建图片
        ExperimentTablePicture.objects.bulk_create(picture_list)
                
        docParseResult = DocumentParseResult.objects.create(result_path=path_uid,experiment_table_result=experiment_table_result)
        endParseStatus = DocumentParseStatus.objects.create(document=doc, status="table_locate",start_end_flag="end",previous_status=startParseStatus,parse_result=docParseResult)
        doc.current_status = "Stopping"
        doc.save()
        print(f"Table locate completed successfully for document {doc}")
    except Exception as e:
        # 创建一个失败的status
        print(f"Error during table locate for document {doc.uuid}: {str(e)}")
        failEndParseStatus = DocumentParseStatus.objects.create(document=doc, status="table_locate",start_end_flag="end",previous_status=startParseStatus,error_message=str(e))        
        doc.current_status = "Failed"
        doc.save()
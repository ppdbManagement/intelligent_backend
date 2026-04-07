import subprocess

from ..models import *
from config.backendSettings import MEDIA_ROOT
import os

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
    doc.status = "Parsing"
    doc.save()
    if stage == "doc_parse":
        # 进行文档解析
        # 解析完成后，更新文档状态为解析完成
        doc_parse(doc)
    elif stage == "metadata_extract":
        # 进行元数据提取
        pass
    elif stage == "table_locate":
        # 进行表格定位
        pass
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
        doc.status = "Stopping"
        doc.save()
        
    except FileNotFoundError:
        doc.status = "Failed"
        doc.error_message = "Parse file not found"
        doc.save()
    except subprocess.TimeoutExpired:
        doc.status = "Failed"
        doc.error_message = "Parsing timed out"
        doc.save()
    except Exception as e:
        doc.status = "Failed"
        doc.error_message = str(e)
        doc.save()

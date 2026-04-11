import json
import os
import traceback
import uuid
from django.http import JsonResponse
from django.views import View
from utils.responseContentUtil import *
from ..models import Document, DocumentParseStatus
from django.db.models import Q
from django.core.paginator import Paginator
from ..serializers.parseTotalStatusSerializers import ParseTotalStatusListSerializer
from config.backendSettings import MEDIA_ROOT
from django.http import FileResponse, Http404
from threading import Thread
from ..utils.parse_tools import async_parse
from ..utils.result_tools import *
from ..utils.simple_tools import get_result_path_from_state_uuid




class ParseTotalStatusView(View):
    def get(self, request):
        try:
            data = request.GET

            file_name = data.get("file_name", "").strip()
            parse_status = data.get("parse_status", "[]").strip()
            # 这个需要json.loads解析成列表
            try:
                parse_status = json.loads(parse_status)
                if not isinstance(parse_status, list):
                    parse_status = []
            except:
                parse_status = []
            if len(parse_status) == 0:
                parse_status = None
            else:
                parse_status = parse_status[0]

            page_size = data.get("page_size", 10)
            current_page = data.get("current_page", 1)

            try:
                page_size = min(int(page_size), 50)
            except:
                page_size = 10

            try:
                current_page = int(current_page)
            except:
                current_page = 1

            query = Q(valid_flag=True)

            if file_name:
                query &= Q(file_name__icontains=file_name)

            if parse_status:
                query &= Q(current_status=parse_status)

            documents = Document.objects.filter(query)

            paginator = Paginator(documents, page_size)

            if current_page > paginator.num_pages:
                current_page = paginator.num_pages or 1

            page_obj = paginator.get_page(current_page)

            res_data = {
                "current_page": current_page,
                "page_size": page_size,
                "total_count": documents.count(),
                "objects": ParseTotalStatusListSerializer(page_obj, many=True).data
            }

            return make_get_success_response(data=res_data)

        except Exception as e:
            traceback.print_exc()
            return make_server_error_response(message=str(e))
        
        
class CheckUploadedFileView(View):
    def put(self,request):
        try:
            data = json.loads(request.body)
            md5_list = data.get("md5_list", [])
            # 判断是否有valid_flag为True且md5在md5_list中的Document对象
            exists = Document.objects.filter(valid_flag=True, md5__in=md5_list)
            existing_md5s = list(exists.values_list('md5', flat=True))
            return make_get_success_response(data={"existing_md5s": existing_md5s})
        except Exception as e:
            traceback.print_exc()
            return make_server_error_response(message=str(e))
        
class UploadFilesView(View):
    def post(self, request):
        try:
            files = request.FILES.getlist("files")
            md5_list = json.loads(request.POST.get("md5_list", "[]"))
            mode = request.POST.get("mode", "single")
            user_uuid = request.POST.get("user_uuid", None)
            # "overwrite" | "skip" | "ignore" | "none";
            duplicate_action = request.POST.get("duplicate_action", "none")
            created_docs = []
            
            for idx, file in enumerate(files):

                # ----------------------------
                # 1️⃣ 基础信息
                # ----------------------------
                file_uuid = uuid.uuid4()
                file_name = file.name
                file_size = file.size
                md5 = md5_list[idx] if idx < len(md5_list) else ""
                # 如果有重复的md5，根据duplicate_action处理
                if md5 and Document.objects.filter(valid_flag=True, md5=md5).exists():
                    if duplicate_action == "overwrite":
                        Document.objects.filter(valid_flag=True, md5=md5).update(valid_flag=False)
                    elif duplicate_action == "skip":
                        continue

                # ----------------------------
                # 2️⃣ 状态逻辑
                # ----------------------------
                if mode == "auto":
                    status = "Pendding"
                else:
                    status = "Stopping"

                # ----------------------------
                # 3️⃣ 存储文件（示例：本地 or OSS）
                # ----------------------------
                store_uid = file_uuid

                # 示例：本地存储
                # 创建一个文件夹，以 store_uid 命名,为root/store_uid,文件为root/store_uid/file_name
                dir_path = os.path.join(MEDIA_ROOT,str(store_uid))
                os.makedirs(dir_path, exist_ok=True)

                file_path = os.path.join(dir_path, file.name)

                with open(file_path, "wb") as f:
                    for chunk in file.chunks():
                        f.write(chunk)

                # ----------------------------
                # 4️⃣ 入库
                # ----------------------------
                doc = Document.objects.create(
                    uuid=file_uuid,
                    file_name=file_name,
                    store_uid=store_uid,
                    file_size=file_size,
                    md5=md5,
                    upload_user_id=user_uuid,
                    current_status=status
                )

                created_docs.append(str(doc.uuid))

            # ----------------------------
            # 5️⃣ auto 模式触发异步任务（预留）
            # ----------------------------
            # if mode == "auto":
            #     self.trigger_async_task(created_docs)
            # 这里返回创建的文档UUID列表，前端可以根据这些UUID去查询状态或者其他信息
            uuid_list = [str(doc_uuid) for doc_uuid in created_docs]
            return make_get_success_response(data={"created_uuids": uuid_list}, message="Files uploaded successfully")

        except Exception as e:
            traceback.print_exc()
            return make_server_error_response(message=str(e))
        
        
class DeleteUploadedFileView(View):
    def delete(self,request,uuid):
        try:
            doc = Document.objects.filter(uuid=uuid, valid_flag=True).first()
            if not doc:
                return make_custom_success_response(message="File deleted successfully")
            doc.valid_flag = False
            doc.save()
            # TODO：同时停止其他相关的异步任务（预留）
            return make_custom_success_response(message="File deleted successfully")
        except Exception as e:
            traceback.print_exc()
            return make_server_error_response(message=str(e))

class GetUploadedFilePDFView(View):
    def get(self, request, uuid):
        try:
            doc = Document.objects.filter(uuid=uuid, valid_flag=True).first()

            if not doc:
                raise Http404("File not found")

            file_path = os.path.join(
                MEDIA_ROOT,
                str(doc.store_uid),
                doc.file_name
            )

            if not os.path.exists(file_path):
                raise Http404("File not found")

            # ✅ 关键：直接返回二进制流
            response = FileResponse(
                open(file_path, "rb"),
                content_type="application/pdf"
            )

            response["Content-Disposition"] = f'inline; filename="{doc.file_name}"'

            return response

        except Exception as e:
            return make_server_error_response(message=str(e))
            
            
# 获取一个文件的信息
class GetUploadedFileInfoView(View):
    def get(self, request, uuid):
        try:
            doc = Document.objects.filter(uuid=uuid, valid_flag=True).first()
            if not doc:
                return make_get_error_response(message="File not found")

            res_data = {
                "uuid": str(doc.uuid),
                "file_name": doc.file_name,
                "file_size": doc.file_size,
                "md5": doc.md5,
                "current_status": doc.current_status,
                "upload_user_id": doc.upload_user_id,
                "upload_time": doc.upload_time,
            }

            return make_get_success_response(data=res_data)

        except Exception as e:
            return make_server_error_response(message=str(e))
        
class GetSingleFileParseStateView(View):
    def get(self, request, uuid):
        try:
            status_result = []

            doc = Document.objects.filter(uuid=uuid, valid_flag=True).first()
            if not doc:
                return make_get_error_response(message="File not found")

            latest_status = DocumentParseStatus.objects.filter(
                document=doc
            ).order_by("-update_time").first()

            if not latest_status:
                return make_get_success_response(data={"status_result": []})

            while latest_status:
                status_result.append({
                    "status": latest_status.status,
                    "update_time": latest_status.update_time,
                    "start_end_flag": latest_status.start_end_flag,
                    "uuid": str(latest_status.uuid),
                })

                latest_status = latest_status.previous_status

            return make_get_success_response(data={"status_result": status_result})

        except Exception as e:
            traceback.print_exc()
            return make_server_error_response(message=str(e))
                
            
class StartParseFileView(View):
    def post(self, request, uuid):
        try:
            doc = Document.objects.filter(uuid=uuid, valid_flag=True).first()
            if not doc:
                return make_get_error_response(message="File not found")
            rb_data = json.loads(request.body)
            stage = rb_data.get("stage", None)
            if stage not in ["doc_parse","metadata_extract","table_locate","table_reconstruct","data_filling","header_split","data_layer_split","data_alignment","data_storage"]:
                return make_get_error_response(message="Invalid stage")
            # 异步解析
            prevUuid = rb_data.get("prev", None)
            thread = Thread(target=async_parse, args=(doc, stage, prevUuid))
            thread.start()
            return make_custom_success_response(message="Parse started successfully")
        except Exception as e:
            traceback.print_exc()
            return make_server_error_response(message=str(e))
            
class GetParseResultView(View):
    def get(self, request, uuid):
        try:
            status = DocumentParseStatus.objects.filter(uuid=uuid).first()
            if not status:
                return make_get_error_response(message="Status not found")
            if status.error_message is not None and status.error_message != "":
                return make_get_error_response(message=status.error_message)
            # TODO: 根据不同的解析阶段返回不同的结果
            result_data = {}
            if status.status == "doc_parse":
                result_data = get_doc_parse_result(status)
            elif status.status == "metadata_extract":
                result_data = get_metadata_extract_result(status)
            elif status.status == "table_locate":
                result_data = get_table_locate_result(status)
            elif status.status == "table_reconstruct":
                result_data = get_table_reconstruct_result(status)
            elif status.status == "data_filling":
                result_data = get_data_filling_result(status)
            
            return make_get_success_response(data={"result": result_data})
        except Exception as e:
            traceback.print_exc()
            return make_server_error_response(message=str(e))


class GetParsedPictureView(View):
    def get(self,request,uuid):
        try:
            pic = ExperimentTablePicture.objects.filter(uuid=uuid).first()
            if not pic:
                raise Http404("Picture not found")
            # 获取图片的路径
            image_path = pic.image_path
            experimentTableResults = pic.table_result.experiment_table_results
            documentParseResult = DocumentParseResult.objects.filter(experiment_table_result=experimentTableResults).first()
            documentParseStatus = DocumentParseStatus.objects.filter(parse_result=documentParseResult).first()
            # 获取路径
            mineru_dir = get_result_path_from_state_uuid(str(documentParseStatus.uuid),"doc_parse")
            result_subdir = os.listdir(mineru_dir)[0]
            parse_result_dir = os.path.join(mineru_dir,result_subdir,"vlm")
            image_ful_path = os.path.join(parse_result_dir,image_path)
            return FileResponse(
                open(image_ful_path, "rb"),
                content_type="image/png"
            )
        except Exception as e:
            traceback.print_exc()
            return make_server_error_response(message=str(e))
 
            
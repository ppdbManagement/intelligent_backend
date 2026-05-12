from rest_framework import serializers
from ..models import *
from ..config.basic_config import parse_status_mapping,parse_state

def fmt(t):
    if not t:
        return None
    return t.strftime("%Y-%m-%d %H:%M:%S")

class ParseTotalStatusListSerializer(serializers.ModelSerializer):
    file_size = serializers.SerializerMethodField()
    parse_info = serializers.SerializerMethodField()
    parse_status = serializers.SerializerMethodField()
    class Meta:
        model = Document
        fields = ['uuid', 'file_name', 'file_size','upload_time','parse_status','parse_info']
        
    def get_file_size(self, obj):
        # 将文件大小转换为MB
        siz =  round(obj.file_size / (1024 * 1024), 2)  # 保留两位小数
        # 转化为字符串并添加单位
        return f"{siz} MB"
    
    def get_parse_info(self, obj):
        latest_status = DocumentParseStatus.objects.filter(
            document=obj
        ).order_by("-create_time").first()

        if not latest_status:
            return "暂无解析信息"

        status_result = []

        while latest_status:
            status_result.append({
                "status": latest_status.status,
                "create_time": latest_status.create_time,
                "start_end_flag": latest_status.start_end_flag,
                "uuid": str(latest_status.uuid),
                "error_message": latest_status.error_message
            })
            latest_status = latest_status.previous_status

        stage_keys = [
            "doc_parse",
            "metadata_extract",
            "table_locate",
            "table_reconstruct",
            "data_filling",
            "context_extract",
            "data_layer_split",
            "data_alignment",
            "data_storage",
        ]


        # ✅ 时间格式：精确到秒
        def fmt(t):
            if not t:
                return None
            return t.strftime("%Y-%m-%d %H:%M:%S")

        result_lines = []

        for key in stage_keys:
            start_time = None
            end_time = None
            error_message = None

            for item in status_result:
                if item["status"] != key:
                    continue

                if item["start_end_flag"] == "start":
                    start_time = fmt(item["create_time"])
                elif item["start_end_flag"] == "end":
                    end_time = fmt(item["create_time"])
                    error_message = item.get("error_message")

            name = parse_state.get(key, key)

            if start_time and end_time:
                text = f"{name}: {start_time} -> {end_time}"
            elif start_time and not end_time:
                text = f"{name}: {start_time} -> 进行中"
            else:
                text = f"{name}: 未开始"
                continue  # 如果阶段未开始，则不显示

            if error_message:
                text += f"（错误：{error_message}）"

            result_lines.append(text)

        return "\n".join(result_lines)

    
    def get_parse_status(self, obj):
        # 获取当前状态的值
        status_value = obj.current_status
        # 根据状态值获取对应的状态名称
        status_name = parse_status_mapping.get(status_value, "未知状态")
        return status_name
        
        
        
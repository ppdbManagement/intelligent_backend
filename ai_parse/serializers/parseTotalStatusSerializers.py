from rest_framework import serializers
from ..models import Document
from ..config.basic_config import parse_status_mapping


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
        return "解析信息"
    
    def get_parse_status(self, obj):
        # 获取当前状态的值
        status_value = obj.current_status
        # 根据状态值获取对应的状态名称
        status_name = parse_status_mapping.get(status_value, "未知状态")
        return status_name
        
        
        
from django.db import models
import uuid
from .parseResultModel import LiteratureInfo,ExperimentTableResults,FlatParseResults,DatasetSplitResults

class Document(models.Model):
    uuid = models.UUIDField(
        primary_key=True, auto_created=True, default=uuid.uuid4, editable=False)
    # 文件信息
    file_name = models.CharField(max_length=255)
    store_uid = models.CharField(max_length=255)
    file_size = models.BigIntegerField()
    md5 = models.CharField(max_length=32)
    
    
    upload_user_id = models.UUIDField()
    upload_time = models.DateTimeField(auto_now_add=True)
    current_status = models.CharField(max_length=20, default='pending')  # pending, processing, completed, failed
    
    valid_flag = models.BooleanField(
        verbose_name="是否有效", default=True, null=False, blank=False)
    
    class Meta:
        ordering = ['-upload_time']
            
    def __str__(self):
        return self.file_name


# 文献解析结果
class DocumentParseResult(models.Model):
    uuid = models.UUIDField(
        primary_key=True, auto_created=True, default=uuid.uuid4, editable=False)
    result_path = models.CharField(max_length=255)
    literature_info = models.ForeignKey(LiteratureInfo,on_delete=models.SET_NULL, null=True, blank=True)
    experiment_table_result = models.ForeignKey(ExperimentTableResults,on_delete=models.SET_NULL, null=True, blank=True)
    flat_parse_result = models.ForeignKey(FlatParseResults,on_delete=models.SET_NULL, null=True, blank=True)
    dataset_split_result = models.ForeignKey(DatasetSplitResults,on_delete=models.SET_NULL, null=True, blank=True)
    create_time = models.DateTimeField(auto_now_add=True)


    
# 文献的解析状态
class DocumentParseStatus(models.Model):
    uuid = models.UUIDField(
        primary_key=True, auto_created=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE)
    # 这里是几个阶段：
    status = models.CharField(max_length=30)
    start_end_flag = models.CharField(max_length=10, default='start')  # start, end
    error_message = models.TextField(blank=True, null=True)
    update_time = models.DateTimeField(auto_now=True)
    previous_status = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='next_status')
    # 当前状态的解析结果
    parse_result = models.ForeignKey(DocumentParseResult, on_delete=models.SET_NULL, null=True, blank=True)
    
    
    def __str__(self):
        return f"{self.document.file_name} - {self.status} - {self.update_time}"



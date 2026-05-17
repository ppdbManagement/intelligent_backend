from django.db import models
import uuid


# 第一阶段解析结果，文献信息
class LiteratureInfo(models.Model):
    uuid = models.UUIDField(
        primary_key=True, auto_created=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=500, null=True, blank=True)
    authors = models.CharField(max_length=500, null=True, blank=True)
    journal = models.CharField(max_length=500, null=True, blank=True)
    abstract = models.TextField(null=True, blank=True)
    doi = models.CharField(max_length=200, null=True, blank=True)
    keywords = models.CharField(max_length=500, null=True, blank=True)
    publication_date = models.CharField(max_length=100, null=True, blank=True)
    volume = models.CharField(max_length=100, null=True, blank=True)
    page = models.CharField(max_length=100, null=True, blank=True)
    
    def __str__(self):
        return self.title if self.title else str(self.uuid)
    
    
# 第二阶段解析结果，实验表格和相关语境

class ExperimentTableResults(models.Model):
    uuid = models.UUIDField(
        primary_key=True, auto_created=True, default=uuid.uuid4, editable=False)

class SingleExperimentTableResult(models.Model):
    uuid = models.UUIDField(
        primary_key=True, auto_created=True, default=uuid.uuid4, editable=False)
    caption = models.CharField(max_length=2000, null=True, blank=True)
    table_order = models.IntegerField(null=True, blank=True)
    related_segment_tags = models.CharField(max_length=500, null=True, blank=True)  # 存储相关语境标签
    related_segment_parse_result = models.TextField(null=True, blank=True)  # 存储相关语境解析结果
    store_uid = models.CharField(max_length=100, null=True, blank=True)  # 存储表格ID，便于关联图片等信息
    experiment_table_results = models.ForeignKey(ExperimentTableResults, on_delete=models.CASCADE, related_name='single_table_results')
    

class ExperimentTablePicture(models.Model):
    uuid = models.UUIDField(
        primary_key=True, auto_created=True, default=uuid.uuid4, editable=False)
    image_path = models.CharField(max_length=500, null=True, blank=True)
    image_order = models.IntegerField(null=True, blank=True)
    table_result = models.ForeignKey(SingleExperimentTableResult, on_delete=models.CASCADE, related_name='pictures')
    
# 第三阶段，扁平化结果

class FlatParseResults(models.Model):
    uuid = models.UUIDField(
        primary_key=True, auto_created=True, default=uuid.uuid4, editable=False)
    
class SingleFlatParseResult(models.Model):
    uuid = models.UUIDField(
        primary_key=True, auto_created=True, default=uuid.uuid4, editable=False)
    origin_table = models.ForeignKey(SingleExperimentTableResult, on_delete=models.SET_NULL, related_name='flat_parse_results', null=True)
    flat_parse_results = models.ForeignKey(FlatParseResults, on_delete=models.CASCADE, related_name='single_flat_results')
    store_uid = models.CharField(max_length=100, null=True, blank=True)  # 存储表格ID，便于关联图片等信息
    data_update = models.BooleanField(default=False)  # 标记是否已更新数据
    data_update_time = models.DateTimeField(null=True, blank=True)  # 数据更新时间
    
class SingleFlatParseTableHeader(models.Model):
    uuid = models.UUIDField(
        primary_key=True, auto_created=True, default=uuid.uuid4, editable=False)
    header_name = models.CharField(max_length=200, null=True, blank=True)
    header_order = models.IntegerField(null=True, blank=True)
    single_flat_parse_result = models.ForeignKey(SingleFlatParseResult, on_delete=models.CASCADE, related_name='headers')
    raw_header_name = models.CharField(max_length=200, null=True, blank=True)  # 存储原始表头名称，便于后续对比和分析
    description = models.TextField(null=True, blank=True)  # 存储表头描述信息，便于理解表头含义
    unit = models.CharField(max_length=100, null=True, blank=True)  # 存储表头单位信息，便于理解数据含义
    
# 第四阶段,数据集拆分了
class DatasetSplitResults(models.Model):
    uuid = models.UUIDField(
        primary_key=True, auto_created=True, default=uuid.uuid4, editable=False)
    
class SingleDatasetSplitResult(models.Model):
    uuid = models.UUIDField(
        primary_key=True, auto_created=True, default=uuid.uuid4, editable=False)
    origin_table = models.ForeignKey(SingleExperimentTableResult, on_delete=models.SET_NULL, related_name='dataset_split_results', null=True)
    flat_parse_result = models.ForeignKey(SingleFlatParseResult, on_delete=models.SET_NULL, related_name='dataset_split_results', null=True)
    dataset_split_results = models.ForeignKey(DatasetSplitResults, on_delete=models.CASCADE, related_name='single_dataset_split_results')
    store_uid = models.CharField(max_length=100, null=True, blank=True)  # 存储表格ID，便于关联图片等信息

class SingleDataset(models.Model):
    uuid = models.UUIDField(
        primary_key=True, auto_created=True, default=uuid.uuid4, editable=False)
    dataset_name = models.CharField(max_length=200, null=True, blank=True)
    dataset_description = models.TextField(null=True, blank=True)
    
    
class DatasetComponent(models.Model):
    uuid = models.UUIDField(
        primary_key=True, auto_created=True, default=uuid.uuid4, editable=False)
    component_name = models.CharField(max_length=200, null=True, blank=True)
    component_order = models.IntegerField(null=True, blank=True)
    matched_component_uuid = models.CharField(max_length=100, null=True, blank=True)  # 存储匹配的组分UUID，便于关联分析
    dataset = models.ForeignKey(SingleDataset, on_delete=models.CASCADE, related_name='components')
    
class DatasetVariable(models.Model):
    uuid = models.UUIDField(
        primary_key=True, auto_created=True, default=uuid.uuid4, editable=False)
    variable_name = models.CharField(max_length=200, null=True, blank=True)
    variable_description = models.TextField(null=True, blank=True)
    matched_variable_uuid = models.CharField(max_length=100, null=True, blank=True)  # 存储匹配的变量UUID，便于关联分析
    dataset = models.ForeignKey(SingleDataset, on_delete=models.CASCADE, related_name='variables')
    unit_symbol = models.CharField(max_length=100, null=True, blank=True)  # 存储变量单位符号，便于理解数据含义
    matched_unit_uuid = models.CharField(max_length=100, null=True, blank=True)  # 存储匹配的单位UUID，便于关联分析
    
class DatasetProperty(models.Model):
    uuid = models.UUIDField(
        primary_key=True, auto_created=True, default=uuid.uuid4, editable=False)
    property_name = models.CharField(max_length=200, null=True, blank=True)
    property_description = models.TextField(null=True, blank=True)
    matched_property_uuid = models.CharField(max_length=100, null=True, blank=True)  # 存储匹配的属性UUID，便于关联分析
    dataset = models.ForeignKey(SingleDataset, on_delete=models.CASCADE, related_name='properties')
    unit_symbol = models.CharField(max_length=100, null=True, blank=True)  # 存储属性单位符号，便于理解数据含义
    matched_unit_uuid = models.CharField(max_length=100, null=True, blank=True)
    
class DatasetConstraint(models.Model):
    uuid = models.UUIDField(
        primary_key=True, auto_created=True, default=uuid.uuid4, editable=False)
    constraint_name = models.CharField(max_length=200, null=True, blank=True)
    constraint_description = models.TextField(null=True, blank=True)
    matched_constraint_uuid = models.CharField(max_length=100, null=True, blank=True)  # 存储匹配的约束UUID，便于关联分析
    dataset = models.ForeignKey(SingleDataset, on_delete=models.CASCADE, related_name='constraints')
    unit_symbol = models.CharField(max_length=100, null=True, blank=True)  # 存储约束单位符号，便于理解数据含义
    matched_unit_uuid = models.CharField(max_length=100, null=True, blank=True)
    constraint_value = models.CharField(max_length=200, null=True, blank=True)  # 存储约束值信息，便于理解约束条件
    
# 变量、物性、约束需要与组分挂钩
class ComponentVariable(models.Model):
    uuid = models.UUIDField(
        primary_key=True, auto_created=True, default=uuid.uuid4, editable=False)
    component = models.ForeignKey(DatasetComponent, on_delete=models.CASCADE, related_name='component_variables')
    variable = models.ForeignKey(DatasetVariable, on_delete=models.CASCADE, related_name='variable_components')
    
class ComponentProperty(models.Model):
    uuid = models.UUIDField(
        primary_key=True, auto_created=True, default=uuid.uuid4, editable=False)
    component = models.ForeignKey(DatasetComponent, on_delete=models.CASCADE, related_name='component_properties')
    property = models.ForeignKey(DatasetProperty, on_delete=models.CASCADE, related_name='property_components')
    
class ComponentConstraint(models.Model):
    uuid = models.UUIDField(
        primary_key=True, auto_created=True, default=uuid.uuid4, editable=False)
    component = models.ForeignKey(DatasetComponent, on_delete=models.CASCADE, related_name='component_constraints')
    constraint = models.ForeignKey(DatasetConstraint, on_delete=models.CASCADE, related_name='constraint_components')
    
class DatasetPhase(models.Model):
    uuid = models.UUIDField(
        primary_key=True, auto_created=True, default=uuid.uuid4, editable=False)
    phase_name = models.CharField(max_length=200, null=True, blank=True)
    phase_description = models.TextField(null=True, blank=True)
    matched_phase_uuid = models.CharField(max_length=100, null=True, blank=True)  # 存储匹配的相UUID，便于关联分析
    dataset = models.ForeignKey(SingleDataset, on_delete=models.CASCADE, related_name='phases')
    
class DatasetPoint(models.Model):
    uuid = models.UUIDField(
        primary_key=True, auto_created=True, default=uuid.uuid4, editable=False)
    dataset = models.ForeignKey(SingleDataset, on_delete=models.CASCADE, related_name='data_points')
    point_data = models.TextField(null=True, blank=True)  # 存储数据点的原始数据，便于后续解析和分析
    

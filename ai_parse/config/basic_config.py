type_conversion_dict = {
    "CharField": "short_string",
    "TextField": "long_string",
    "FloatField": "float",
    "IntegerField": "int",
    "BooleanField": "bool",
    "DateTimeField": "datetime",
    "operate":"operate",
    "ForeignKey":"short_string",
    "UUIDField":"short_string",
    "JSONField": "json",
}

parse_status_list = [{"value": "Pendding", "label": "待解析"},
                {"value": "Parsing", "label": "解析中"},
                {"value": "Stopping", "label": "解析暂停"},
                {"value": "Success", "label": "解析成功"},
                {"value": "Failed", "label": "解析失败"},]

# 解析状态的映射关系
parse_status_mapping = {
    "Pendding": "待解析",
    "Parsing": "解析中",
    "Stopping": "解析暂停",
    "Success": "解析成功",
    "Failed": "解析失败",
}

parse_state = {
    "doc_parse": "文档解析",
    "metadata_extract": "论文元数据提取",
    "table_locate": "表格定位与语境获取",
    "table_reconstruct": "表格重构",
    "data_filling": "数据填充",
    "header_split": "表头层拆分",
    "data_layer_split": "数据层拆分",
    "data_alignment": "数据对齐",
    "data_storage": "数据入库"
}
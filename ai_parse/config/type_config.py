from enum import Enum


# 量的类型，枚举类型
class QuantityType(Enum):
    NORMAL = '标准'
    TEMPERATURE_RELATED = '热相关'
    TRANSFER_RELATED = '传递相关'
    CONCENTRATION_RELATED = '浓度相关'
    SIZE_RELATED = '尺寸相关'
    CURRENCY_RELATED = '货币相关'
    OTHER = '其他'
    

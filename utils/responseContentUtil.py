# this file contains response content

# 返回状态码的枚举
from django.http import JsonResponse


class ResponseCode:
    SUCCESS = 200
    ERROR = 500
    BAD_REQUEST = 400

# 操作成功的内容
class SuccessContent:
    GET_SUCCESS = "获取成功"
    CREATE_SUCCESS = "新增成功"
    UPDATE_SUCCESS = "编辑成功"
    DELETE_SUCCESS = "删除成功"
    VALIDATE_SUCCESS = "验证成功"
    
# 操作失败的内容
class ErrorContent:
    GET_ERROR = "获取失败"
    CREATE_ERROR = "新增失败"
    UPDATE_ERROR = "编辑失败"
    DELETE_ERROR = "删除失败"
    SERVER_ERROR = "服务器错误"
    VALIDATE_ERROR = "验证失败"
    
def make_response(code, message, data=None):
    """
    生成统一的响应格式
    :param code: 状态码
    :param message: 响应消息
    :param data: 响应数据
    :return: dict
    """
    response = {
        "code": code,
        "message": message,
        "data": data
    }
    return JsonResponse(response)

# 封装的快速返回的内容
def make_get_success_response(message="", data=None):
    # return make_response(ResponseCode.SUCCESS, SuccessContent.GET_SUCCESS, data)
    if message != "":
        message = ": " + message
    return make_response(ResponseCode.SUCCESS, SuccessContent.GET_SUCCESS + message, data)
def make_create_success_response(message="", data=None):
    # return make_response(ResponseCode.SUCCESS, SuccessContent.CREATE_SUCCESS, data)
    if message != "":
        message = ": " + message
    return make_response(ResponseCode.SUCCESS, SuccessContent.CREATE_SUCCESS + message, data)
def make_update_success_response(message="", data=None):
    # return make_response(ResponseCode.SUCCESS, SuccessContent.UPDATE_SUCCESS, data)
    if message != "":
        message = ": " + message
    return make_response(ResponseCode.SUCCESS, SuccessContent.UPDATE_SUCCESS + message, data)
def make_delete_success_response(message="", data=None):
    # return make_response(ResponseCode.SUCCESS, SuccessContent.DELETE_SUCCESS, data)
    if message != "":
        message = ": " + message
    return make_response(ResponseCode.SUCCESS, SuccessContent.DELETE_SUCCESS + message, data)
def make_validate_success_response(message="", data=None):
    # return make_response(ResponseCode.SUCCESS, SuccessContent.VALIDATE_SUCCESS, data)
    if message != "":
        message = ": " + message
    return make_response(ResponseCode.SUCCESS, SuccessContent.VALIDATE_SUCCESS + message, data)
def make_get_error_response(message="", data=None):
    return make_response(ResponseCode.BAD_REQUEST,ErrorContent.GET_ERROR+" : "+message, data)
def make_create_error_response(message="", data=None):
    return make_response(ResponseCode.BAD_REQUEST,ErrorContent.CREATE_ERROR+" : "+message, data)
def make_update_error_response(message="", data=None):
    return make_response(ResponseCode.BAD_REQUEST,ErrorContent.UPDATE_ERROR+" : "+message, data)
def make_delete_error_response(message="", data=None):
    return make_response(ResponseCode.BAD_REQUEST,ErrorContent.DELETE_ERROR+" : "+message, data)
def make_server_error_response(message="", data=None):
    return make_response(ResponseCode.ERROR, ErrorContent.SERVER_ERROR + " : " + message, data)
def make_validate_error_response(message="", data=None):
    return make_response(ResponseCode.BAD_REQUEST, ErrorContent.VALIDATE_ERROR + " : " + message, data)


# 特殊情况的返回内容
def make_custom_success_response(message="", data=None):
    return make_response(ResponseCode.SUCCESS, message, data)
def make_custom_error_response(message="", data=None):
    return make_response(ResponseCode.BAD_REQUEST, message, data)
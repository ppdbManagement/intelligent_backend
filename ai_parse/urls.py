from django.urls import path
from .views.parseTotal  import *

app_name = 'ai_parse'

urlpatterns = [
    # Define your URL patterns here
    path('get_parse_total_data',ParseTotalStatusView.as_view(), name='get_parse_total_data'),
    
    # 检查上传的文件是否有已经上传过
    path('check_uploaded_file',CheckUploadedFileView.as_view(), name='check_uploaded_file'),
    
    path('upload_files',UploadFilesView.as_view(), name='upload_files'),
    
    path('delete_uploaded_file/<str:uuid>',DeleteUploadedFileView.as_view(), name='delete_uploaded_file'),
    
    path('get_uploaded_file_pdf/<str:uuid>',GetUploadedFilePDFView.as_view(), name='get_uploaded_file_pdf'),
    
    path('get_uploaded_file_info/<str:uuid>',GetUploadedFileInfoView.as_view(), name='get_uploaded_file_info'),
    
    path('get_single_file_parse_state/<str:uuid>',GetSingleFileParseStateView.as_view(), name='get_single_file_parse_state'),
    
    path('start_parse_file/<str:uuid>',StartParseFileView.as_view(), name='start_parse_file'),
    
    path('get_parse_result/<str:uuid>',GetParseResultView.as_view(), name='get_parse_result'),
]
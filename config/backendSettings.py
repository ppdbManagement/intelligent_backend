# 文件存储和文件解析的路径
import os


MEDIA_ROOT = '/data_extend/qjk_workspace/thu_graduation_project/final_code/media/'

# 数据初始化的文件夹路径
SEED_ROOT = '/data_extend/qjk_workspace/thu_graduation_project/final_code/seed'

# PubMedBERT embedding 的 存放路径
PUBMEDBERT_EMBEDDING_PATH = "/data_extend/qjk_workspace/thu_graduation_project/vllm_deploy/pubmedbert-base-embeddings"

# Chromadb 索引文件存放路径
CHROMADB_INDEX_PATH = os.path.join(MEDIA_ROOT, "chromadb_v1")
import os
import pandas as pd
import chromadb
from ai_parse.utils.chroma_embedder import ChromaBiomedEmbeddingFunction
from config.backendSettings import CHROMADB_INDEX_PATH,SEED_ROOT

def split_names(s):
    if pd.isna(s) or not s:
        return []
    return [i.strip() for i in str(s).split("||") if i.strip()]


def build_meta(componentidentifier_uuid, name_cn_list, name_en_list):
    name_show = "{}[{}]".format(
        name_cn_list[0] if name_cn_list else "",
        name_en_list[0] if name_en_list else ""
    )
    return {
        "componentidentifier_uuid": componentidentifier_uuid,
        "name_show": name_show,
    }


def insert_compounds_embedding():
    print("Starting data embedding process...")

    # 1. 初始化 Chroma
    client = chromadb.PersistentClient(path=CHROMADB_INDEX_PATH)

    embedding_func = ChromaBiomedEmbeddingFunction()

    collection = client.get_or_create_collection(
        name="compounds",
        embedding_function=embedding_func,
        metadata={"hnsw:space": "cosine"}
    )

    # 2. 读取数据
    file_path = f"{SEED_ROOT}/processed_compound_data_with_uuid.csv"
    df = pd.read_csv(file_path, dtype=str).fillna("")

    # 3. 批量容器
    ids, documents, metadatas = [], [], []

    # 4. 遍历（用 itertuples 更快）
    for row_idx, row in enumerate(df.itertuples(index=False)):

        name_en_list = split_names(getattr(row, "processed_names_en", ""))
        name_cn_list = split_names(getattr(row, "processed_names_cn", ""))
        uuid = getattr(row, "componentidentifier_uuid", "")

        meta = build_meta(uuid, name_cn_list, name_en_list)

        # 中文
        for i, name_cn in enumerate(name_cn_list):
            if name_cn:
                ids.append(f"cn_{row_idx}_{i}")
                documents.append(name_cn)
                meta_copy = meta.copy()
                meta_copy["origin_name"] = name_cn
                metadatas.append(meta_copy)

        # 英文
        for i, name_en in enumerate(name_en_list):
            if name_en:
                ids.append(f"en_{row_idx}_{i}")
                documents.append(name_en)   
                meta_copy = meta.copy()
                meta_copy["origin_name"] = name_en
                metadatas.append(meta_copy)

    # 5. 批量写入
    batch_size = 1000
    total = len(ids)

    for i in range(0, total, batch_size):
        end = min(i + batch_size, total)

        collection.add(
            ids=ids[i:end],
            documents=documents[i:end],
            metadatas=metadatas[i:end]
        )

        print(f"Inserted batch: {i} - {end} / {total}")

    print("Data embedding process completed.")
    

def init_compound_embedding_data():
    # insert_compounds_embedding()
    print("Compound embedding data initialization completed.")

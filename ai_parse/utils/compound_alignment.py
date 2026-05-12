import json
from string import Template
from ..remote_api.remote_api import getCompoundSearchData
import chromadb
from .chroma_embedder import ChromaBiomedEmbeddingFunction
from config.backendSettings import CHROMADB_INDEX_PATH
from .ParateraQwenClient import ParateraQwenClient
from .simple_tools import safe_json_loads
# 进行组分对齐

# 判断不同类型标识
import re
import requests

class ChromaTools:
    def __init__(self, collection_name: str = "compounds",path: str = CHROMADB_INDEX_PATH):
        self.client = chromadb.PersistentClient(path)
        self.embedding_func = ChromaBiomedEmbeddingFunction()
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.embedding_func,
            metadata={"hnsw:space": "cosine"}
        )
    def semantic_search(self, query: str, n_results: int = 5) :
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            include=["documents","metadatas", "distances"]
        )
        
        output = []
        if not results["ids"] or not results["ids"][0]:
            return output
        
        for i in range(len(results["ids"][0])):
            dist = results["distances"][0][i]  # cosine distance
            output.append({
                "id": results["ids"][0][i],
                "metadata": results["metadatas"][0][i],
                "similarity": round(1.0 - dist, 4),
                "distance": round(dist, 4)
            })
        return output
        
        
chromaTools = ChromaTools()
        

def is_cas(query):
    return bool(re.fullmatch(r"\d{1,7}-\d{2}-\d", query.strip()))

def is_inchikey(query):
    return bool(re.fullmatch(r"[A-Z]{14}-[A-Z]{10}-[A-Z]", query.strip()))

def is_smiles(query):
    return any(c in query for c in "=#()[]")


def alignment_by_cas(cas):
    try:
        response = getCompoundSearchData(query=cas, query_type="cas")
        uuids = response.get("data", {}).get("uuids", [])
        if uuids:
            return uuids[0]  # 返回第一个匹配的UUID
        else:
            return None
    except Exception as e:
        print(f"Error during CAS alignment: {e}")
        return None

def alignment_by_inchikey(inchikey):
    try:
        response = getCompoundSearchData(query=inchikey, query_type="inchikey")
        uuids = response.get("data", {}).get("uuids", [])
        if uuids:
            return uuids[0]  # 返回第一个匹配的UUID
        else:
            return None
    except Exception as e:
        print(f"Error during InChIKey alignment: {e}")
        return None

# def alignment_by_smiles(smiles):
#     pass

def alignment_by_name(name):
    try:
        results = chromaTools.semantic_search(name, n_results=10)
        # 将result按照metadata里面的componentidentifier_uuid进行聚合
        uuid_map = {}
        for result in results:
            metadata = result["metadata"]
            component_uuid = metadata.get("componentidentifier_uuid")
            if component_uuid:
                if component_uuid not in uuid_map:
                    uuid_map[component_uuid] = []
                uuid_map[component_uuid].append(result)
        
        uuid_to_pend_list = []
        for uuid, items in uuid_map.items():
            pend_list = []
            for item in items:
                pend_list.append(item["metadata"]["origin_name"])
            uuid_to_pend_list.append("{} => {}".format(uuid, json.dumps(pend_list, ensure_ascii=False)))
        client = ParateraQwenClient()
        prompt_text = prompt.substitute(target_components=name, backend_components="\n".join(uuid_to_pend_list))
        response = client.simple_chat(prompt_text)
        response_json = safe_json_loads(response)
        if response_json and "uuid" in response_json:
            return response_json["uuid"]
        else:
            return None
        
    except Exception as e:
        print(f"Error during name alignment: {e}")
        return None

def enhanced_by_pubchem(name):
    def get_inchi_key_by_name(name):
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{name}/property/InChIKey/JSON"
        data = requests.get(url,timeout=20).json()
        inchi_key = data["PropertyTable"]["Properties"][0]["InChIKey"]
        return inchi_key
    try:
        retrieved_inchi_key = get_inchi_key_by_name(name)
        if is_inchikey(retrieved_inchi_key):
            search_result = alignment_by_inchikey(retrieved_inchi_key)
            if search_result:
                return {"target_uuid": search_result}
            else:
                return {
                    "target_uuid": None,
                    "recommended_inchi_key": retrieved_inchi_key
                    }
        else:
            print(f"Retrieved InChIKey is not valid: {retrieved_inchi_key}")
            return {"target_uuid": None}
    except Exception as e:
        print(f"Error during PubChem enhancement: {e}")
        return {"target_uuid": None}




def align_compound(query):
    target_uuid = None
    # 判断输入类型
    if is_cas(query):
        target_uuid = alignment_by_cas(query)
    elif is_inchikey(query):
        target_uuid = alignment_by_inchikey(query)
    # elif is_smiles(query):
    #     target_uuid = alignment_by_smiles(query)
    else:
        target_uuid = alignment_by_name(query)
    
    if target_uuid is not None:
        return {
            "target_uuid": target_uuid,
        }
    # 如果没有找到，尝试使用PubChem增强
    enhanced_result = enhanced_by_pubchem(query)
    return enhanced_result
    
    
prompt = Template("""
你是一个化学/材料组分名称标准化与匹配助手。

## 任务
我会提供两部分数据：

### 1. 需要对齐的组分（target components）
- 这是用户希望匹配的目标名称列表

### 2. 后端组分库（backend components）
- 格式为：
  uuid => [name1, name2, name3...]

这些 name 可能是同一个物质的不同叫法（同义词/别名/俗称/缩写等）。

---

## 你的任务
请在 backend components 中，找出**与 target components 中某个组分属于“同一物质但不同名称”**的那一条记录。

判断标准包括但不限于：
- 同一化学物质的不同名称（中英文、缩写、商品名、俗名）
- 结构/功能一致
- 行业常见别名

如果找到匹配项：
- 返回对应 uuid

如果没有找到：
- 返回 None

---

## 输出格式（非常重要）
你必须严格输出 JSON，不要输出任何解释：

{
  "uuid": "xxx" 或 null
}

---

## 输入数据

### target components
$target_components

### backend components
$backend_components

---

## 注意
- 只允许输出一个 uuid（最匹配的）
- 不要输出多个候选
- 不要解释
- 不要添加额外字段
""")
from tqdm import tqdm
import json
from string import Template
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from config.backendSettings import SEED_ROOT
from ai_parse.utils.ParateraQwenClient import ParateraQwenClient
from string import Template

prompt_for_unit_deal = Template("""
你是一个“通用物理与工程单位系统清洗、标准化与补全引擎”。

你的任务是对输入单位列表进行质量审核、清洗、优化、语义增强，并补充该物理量维度下的常见标准单位。

================================================
【输入格式】
================================================
输入是一个 JSON 对象，结构如下：

{
  "D_xxx": [
    {
      "unit_name_en": "",
      "unit_name_zh": "",
      "symbol": "",
      "dimension": "",
      "unit_basic_symbol": "",
      "unit_factor": 0.0,
      "unit_offset": 0.0,
      "unit_description": "",
      "unit_description_en": ""
    }
  ]
}

你只处理数组中的单位列表。

================================================
【核心任务】
================================================

你需要执行三类操作：

① 清洗已有单位
② 优化已有单位
③ 补充该维度下“常见标准单位”

================================================
【1. 单位合理性检查（清洗）】
================================================

判断每个单位是否合理：

- 是否真实存在于物理/工程体系
- 是否被实际使用（科学/工程/工业）
- 是否符号混乱或错误定义
- 是否重复或等价单位
- 是否极冷门、几乎无实际用途

👉 不合理或极少使用单位必须删除

================================================
【2. 符号优化】
================================================

检查 symbol 并优化：

- 必须使用国际通用或工程标准写法
- 去除括号、国家标识、说明文字
- 合并重复符号体系（如 US/UK 变体）
- 使用统一简洁表达（如 ton_us / ton_uk）

================================================
【3. 名称规范化】
================================================

优化：

- unit_name_en：标准英文名称
- unit_name_zh：标准中文名称

要求：
- 使用科学/工程领域通用表达
- 避免直译错误或口语化表达
- 保持同一物理量领域一致性

================================================
【4. 描述生成】
================================================

必须生成：

- unit_description（中文）
- unit_description_en（英文）

要求：
- 简洁专业
- 描述该单位的物理意义或用途
- 不要重复字段信息

================================================
【5. 数据修正】
================================================

- 修正 symbol（如有更标准写法）
- 修正明显错误 unit_factor
- unit_offset 通常为 0
- unit_basic_symbol 可根据体系合理设置（不强制 SI）

================================================
【6. 删除规则】
================================================

必须删除：

- 非标准或历史废弃单位
- 定义不明确单位
- 无法验证或极低使用率单位
- 重复或等价单位（只保留一个标准版本）
- 符号混乱无法统一单位

================================================
【7. 维度补全（新增重要能力）】
================================================

你必须基于 dimension，自动补充该物理量领域中“常见且标准”的单位。

要求：

- 必须属于该 dimension 合理范围
- 必须是科学/工程/工业常用单位
- 必须优先选择国际标准或主流单位
- 不得添加冷门或历史废弃单位
- 不得添加无法定义或歧义单位

补充原则：

✔ 优先 SI 单位
✔ 其次国际工程单位
✔ 再其次主流行业单位（如英制常用单位）
❌ 不允许冷门或学术边缘单位

================================================
【8. 合并规则】
================================================

- 如果补充单位与已有单位重复，只保留标准版本
- 如果已有单位更完整，则不重复添加
- 保证最终列表“去重 + 完整 + 标准”

================================================
【严格输出要求】
================================================

你必须只输出 JSON 数组（list），不能包含任何额外结构：

✔ 正确：
[
  { ... },
  { ... }
]

❌ 错误：
{
  "D_xxx": [...]
}

================================================
【禁止行为】
================================================

❌ 不要输出解释
❌ 不要输出分析过程
❌ 不要输出 markdown
❌ 不要输出任何额外文字
❌ 不要增加字段

================================================
【处理原则】
================================================

- 优先保留常用标准单位
- 删除混乱或低价值单位
- 补全该维度主流单位体系
- 保证符号统一规范
- 保证描述专业清晰

================================================
【输入数据】
================================================

$input
""")


import json
from concurrent.futures import ProcessPoolExecutor, as_completed


def process_dimension(args):
    dimension_name, unit_list, prompt_template = args

    try:
        client = ParateraQwenClient()

        prompt_1 = prompt_template.substitute(
            input=json.dumps(unit_list, ensure_ascii=False, indent=4)
        )

        response_1 = client.simple_chat(user_message=prompt_1)

        processed_units = json.loads(response_1)

        return dimension_name, processed_units

    except Exception as e:
        print(f"[ERROR] dimension={dimension_name}, error={e}")
        return dimension_name, []


def deal_unit():
    data_file = SEED_ROOT + "/unit_unit.json"

    with open(data_file, "r", encoding="utf-8") as f:
        unit_data = json.load(f)

    # 按 dimension 聚合
    dimension_unit_mapping = {}
    for unit_item in unit_data:
        dim = unit_item.get("dimension")
        if dim not in dimension_unit_mapping:
            dimension_unit_mapping[dim] = []
        dimension_unit_mapping[dim].append(unit_item)

    # 构造任务列表
    tasks = [
        (dim, unit_list, prompt_for_unit_deal)
        for dim, unit_list in dimension_unit_mapping.items()
    ]

    processed_mapping = {}

    # 8进程并行
    with ProcessPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(process_dimension, t) for t in tasks]

        for future in as_completed(futures):
            dim, result = future.result()
            processed_mapping[dim] = result

    # 保存最终结果
    output_file = SEED_ROOT + "/unit_unit_processed.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(processed_mapping, f, ensure_ascii=False, indent=4)

    print(f"Done. Saved to {output_file}")

from ai_parse.utils.unit_alignment import unit_alignment
def test_for_unit_alignment():
    res = unit_alignment("千米")
    print(res)




if __name__ == "__main__":
    # deal_unit()
    test_for_unit_alignment()
    pass

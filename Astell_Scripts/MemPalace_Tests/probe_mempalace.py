import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from astell_config import MEMPALACE_DB, add_runtime_paths

add_runtime_paths()
from mempalace.palace import get_collection

db_path = str(MEMPALACE_DB)
col = get_collection(db_path)

query = "CreateEngineEntityByTypeStr"
print(f"=== 正在 ChromaDB 底层直接查询: {query} ===")

# 直接调用 ChromaDB 的 query，取 10 个结果
res = col.query(
    query_texts=[query],
    n_results=10,
    where={"wing": "wing_Official_SDK"}
)

docs = res.get("documents", [[]])[0]
metas = res.get("metadatas", [[]])[0]
dists = res.get("distances", [[]])[0]

if not docs:
    print("未找到任何结果。")
else:
    for i, (doc, meta, dist) in enumerate(zip(docs, metas, dists)):
        print(f"\n--- 匹配 {i+1} ---")
        print(f"来源: {meta.get('source_file')}")
        print(f"距离 (Distance): {dist:.4f}")
        print("内容预览:")
        print(doc[:300] + "..." if len(doc) > 300 else doc)

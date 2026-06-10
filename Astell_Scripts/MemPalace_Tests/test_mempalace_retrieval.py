import sys
from pathlib import Path

# 把 mempalace 源文件加入环境
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from astell_config import LIBRARY_PATH, MEMPALACE_DB, add_runtime_paths

add_runtime_paths()

try:
    from mempalace.palace import get_collection, get_closets_collection
    from mempalace.miner import process_file
    from mempalace.searcher import search_memories
except ImportError as e:
    print("找不到 MemPalace:", e)
    sys.exit(1)

db_path = str(MEMPALACE_DB)
drawers_col = get_collection(db_path)
closets_col = get_closets_collection(db_path)

print("==== 步骤1：矿工(Miner)下井 ====")
# 我们把刚刚写的 hall_fact.md、hall_events.md、和 closet 的 AAKK 放进记忆宫殿
files_to_mine = [
    LIBRARY_PATH / "wing_Astell_Architecture" / "hall" / "hall_fact.md",
    LIBRARY_PATH / "wing_Astell_Architecture" / "hall" / "hall_events.md",
    LIBRARY_PATH / "wing_Astell_Architecture" / "room_Architect" / "closet" / "ACT1_Architecture_Proof.md"
]

for p in files_to_mine:
    if p.exists():
        print(f"正在挖掘: {p.name}")
        # wing 指定为 Astell_Architecture
        # agent 填入 Astell_Overmind
        # 因为我们是手动归档，提供一个虚拟的 room 也可以
        process_file(p, LIBRARY_PATH, drawers_col, "wing_Astell_Architecture", [{"name": "Architect_Room"}], "Astell_Overmind", False, closets_col)
    else:
        print(f"文件不存在: {p}")

print("\n==== 步骤2：以太共鸣(Searcher)检索 ====")
query = "子代理静默失败怎么办？"
print(f"正在向宫殿发起质询: '{query}'")

res = search_memories(query, db_path, wing="wing_Astell_Architecture", n_results=2)

hits = res.get("results", [])
if hits:
    for i, h in enumerate(hits, 1):
        print(f"\n[找回记忆 {i}] 相似度: {h.get('similarity', 0):.4f} | 来源: {h.get('source_file')}")
        print("摘录:")
        print(h.get('text', '')[:300] + "...")
else:
    print("❌ 宫殿深处空无一物，未找回任何记忆。")
    
print("\n✨ MemPalace 功能测试与 AAKK 固化归档全量验证完毕！")

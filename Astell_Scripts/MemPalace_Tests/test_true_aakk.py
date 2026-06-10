import sys
import os
from pathlib import Path
import json

# 把 mempalace 源文件加入环境
sys.path.insert(0, r"D:\Astell_Library\mempalace-develop")

try:
    from mempalace.palace import get_collection, get_closets_collection
    from mempalace.miner import process_file
    from mempalace.searcher import search_memories
except ImportError as e:
    print("找不到 MemPalace:", e)
    sys.exit(1)

db_path = r"D:\Astell_Library\mempalace_db"
drawers_col = get_collection(db_path)
closets_col = get_closets_collection(db_path)

print("==== 步骤1：矿工(Miner)下井提取正统 AAKK ====")
# 定位子代理刚刚拷贝过来的贪吃史莱姆文件
bio_drawer_dir = Path(r"Library\wing_mod_reference1\room_生物开发\drawer")
files_to_mine = list(bio_drawer_dir.rglob("*.json"))

if not files_to_mine:
    print(f"❌ 警告：在 {bio_drawer_dir} 未找到任何 JSON 文件，子代理可能没有成功拷贝！")
else:
    for p in files_to_mine:
        print(f"正在由 MemPalace 引擎自动提炼 AAKK 并挖掘: {p.name}")
        process_file(
            filepath=p, 
            project_path=Path("Library"), 
            collection=drawers_col, 
            wing="wing_mod_reference1", 
            rooms=[{"name": "room_生物开发"}], 
            agent="a生物开发", 
            dry_run=False, 
            closets_col=closets_col
        )
    print("✅ 正统 AAKK 提炼完成！MemPalace 已将文件摘要和实体信息压缩写入 closets 集合。")

print("\n==== 步骤2：窥视底层的 AAKK 压缩记忆 (Closets Collection) ====")
# 我们直接向 ChromaDB 查询看 closets 里生成了什么
try:
    all_closets = closets_col.get(limit=5)
    print("最新生成的 AAKK (Closet) 压缩条目样本：")
    for doc, meta in zip(all_closets['documents'], all_closets['metadatas']):
        print(f"  [压缩指引] {doc[:100]}...")
        print(f"  [关联抽屉] {meta.get('pointers', '[]')}")
except Exception as e:
    print(f"查询 closets_col 失败: {e}")

print("\n==== 步骤3：以太共鸣(Searcher) 检索验证 ====")
query = "贪吃史莱姆的寻路AI或者变种定义是什么？"
print(f"正在向宫殿发起质询: '{query}'")

# search_memories 内部会优先匹配 closets (AAKK)，然后再去 drawer 里拿原文
res = search_memories(query, db_path, wing="wing_mod_reference1", n_results=1)

hits = res.get("results", [])
if hits:
    for i, h in enumerate(hits, 1):
        match_type = h.get('matched_via', 'drawer')
        print(f"\n[找回记忆 {i}] 相似度: {h.get('similarity', 0):.4f} | 匹配路径: {match_type}")
        print(f"来源文件: {h.get('source_file')}")
        if 'closet_preview' in h:
            print(f"AAKK 预览线索: {h.get('closet_preview')}")
        print("抽屉原文摘录:")
        print(h.get('text', '')[:300] + "...\n")
else:
    print("❌ 宫殿深处空无一物，未找回任何记忆。")
    
print("✨ MemPalace 正统 AAKK 压缩与联动测试验证完毕！")
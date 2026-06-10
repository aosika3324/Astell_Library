import os
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from astell_config import ASTELL_LIBRARY_ROOT

def init_project():
    print("--- [SYSTEM] 开始建立《荒野生存》中央指挥室与基础环境 ---")
    
    # 1. 建立 Evolution 跟踪文件
    evo_dir = Path(os.environ.get("ASTELL_WILD_SURVIVAL_EVOLUTION_DIR", ASTELL_LIBRARY_ROOT / "Evolution" / "Wild_Survival"))
    evo_dir.mkdir(parents=True, exist_ok=True)
    
    files_to_create = {
        "Registry.md": "# 荒野生存 资源登记与 ID 字典\n\n记录所有创建的道具、生物、动作、粒子等 JSON 配置的 ID，供子代理调度和写入。资源应按相关性分组。\n\n## 道具分类 (Items)\n\n## 实体分类 (Entities)\n\n## 方块分类 (Blocks)\n\n## UI分类 (UI)\n",
        "Ownership.md": "# 荒野生存 模块责任划分\n\n记录文件夹里哪些文件是哪个子代理写的。核查员只会查看对应的部分。\n\n",
        "Pending_Issues.md": "# 待处理事项 (Pending Issues)\n\n如果核查员发现问题，计数达到三次则写入此处供主代理审查。\n\n",
        "Task_List.md": "# 任务进度看板 (Task List)\n\n- [ ] 阶段一：建立中央指挥室\n- [ ] 阶段二：派发 [道具与方块] 子代理\n- [ ] 阶段三：派发 [实体与视效] 子代理\n- [ ] 阶段四：派发 [UI 架构] 子代理\n- [ ] 阶段五：派发 [核心逻辑脚本] 子代理\n- [ ] 阶段六：主脑验收及核查挑刺\n",
        "Nitpicks.md": "# 挑刺员专区 (Nitpicks)\n\n挑刺员总结的潜在性能问题和代码漏洞。\n\n",
        "Public_Mailbox.md": "# 公共信箱 (Public Mailbox)\n\n子代理跨界求助信箱。\n\n"
    }
    
    for filename, content in files_to_create.items():
        filepath = evo_dir / filename
        if not filepath.exists():
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"已创建跟踪文件: {filename}")
            
    # 2. 建立 MC Studio 目录结构
    mc_dir_value = os.environ.get("ASTELL_WILD_SURVIVAL_ADDON_DIR")
    if not mc_dir_value:
        raise RuntimeError("请先设置 ASTELL_WILD_SURVIVAL_ADDON_DIR，指向目标 MC Studio AddOn 目录。")
    mc_dir = Path(mc_dir_value)
    mc_dir.mkdir(parents=True, exist_ok=True)
    
    # Behavior Pack 和 Resource Pack 基础结构
    bp_dirs = [
        "behavior_pack/items",
        "behavior_pack/blocks",
        "behavior_pack/entities",
        "behavior_pack/recipes",
        "behavior_pack/functions",
        "behavior_pack/spawn_rules",
        "behavior_pack/scripts/wild_survival",
    ]
    
    rp_dirs = [
        "resource_pack/items",
        "resource_pack/blocks",
        "resource_pack/entity",
        "resource_pack/models/entity",
        "resource_pack/textures/items",
        "resource_pack/textures/blocks",
        "resource_pack/textures/entity",
        "resource_pack/textures/ui",
        "resource_pack/ui",
        "resource_pack/animation_controllers",
        "resource_pack/animations",
        "resource_pack/particles",
        "resource_pack/texts",
    ]
    
    for d in bp_dirs + rp_dirs:
        (mc_dir / d).mkdir(parents=True, exist_ok=True)
        
    print(f"已在 {mc_dir} 初始化 AddOn 目录结构。")
    print("--- [SYSTEM] 初始化完成 ---")

if __name__ == "__main__":
    init_project()

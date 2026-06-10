"""Local ModSDK helper tools used by Astell.

This module intentionally uses Astell's local `wing_Official_SDK` documents and
small clean-room templates. It does not vendor code from MCNeteaseDevs'
`modsdk_mcp_server`, so the integration can later switch to a sidecar process
without entangling licenses or Astell's memory workflow.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from astell_config import LIBRARY_PATH


OFFICIAL_SDK_PATH = LIBRARY_PATH / "wing_Official_SDK"
SEARCH_EXTENSIONS = {".md", ".txt", ".json", ".py"}


PRACTICES: dict[str, list[str]] = {
    "general": [
        "实现前先确认服务端/客户端边界；仅把需要同步的状态跨端传递。",
        "所有自定义 identifier 保持 namespace:name 格式，避免与原版或其他 AddOn 冲突。",
        "资源包与行为包文件名、identifier、纹理短名要一致可追踪。",
        "把一次性初始化放在系统生命周期入口，避免在 tick 或事件高频路径里重复注册。",
    ],
    "event": [
        "事件监听注册应集中管理，避免同一对象重复 ListenForEvent。",
        "回调里先做快速过滤，例如实体类型、方块 ID、维度或玩家 ID。",
        "跨系统调用前检查对象是否仍有效，尤其是实体死亡、玩家退出、区块卸载之后。",
    ],
    "performance": [
        "避免在每 tick 遍历全量实体或全量玩家；优先用事件驱动和局部缓存。",
        "高频路径不要重复创建组件工厂、解析 JSON、扫描目录或做大字符串拼接。",
        "定时器和延迟任务需要有明确取消或收敛条件。",
    ],
    "python2": [
        "网易 ModSDK 运行环境常见 Python 2.7 约束，避免 f-string、类型注解、dataclass、pathlib 等 Python 3 专属语法。",
        "字符串编码要谨慎，面向中文资源名时优先保持 JSON/文件为 UTF-8。",
        "异常处理不要裸吞；至少记录模块名、实体/玩家 ID 和触发事件。",
    ],
    "resource": [
        "行为包与资源包都要补齐 identifier、description、textures、texts/lang 等链路。",
        "新增资源 ID 后要写入 Astell 信息记录，便于后续冲突审计。",
        "贴图、模型、动画控制器路径保持小写和稳定命名，减少跨平台路径问题。",
    ],
}


def _tokenize(query: str) -> list[str]:
    raw_tokens = re.findall(r"[A-Za-z0-9_:.]+|[\u4e00-\u9fff]+", query.lower())
    split_tokens: list[str] = []
    for token in raw_tokens:
        split_tokens.append(token)
        split_tokens.extend(part for part in re.split(r"[_:.]+", token) if part)
    return list(dict.fromkeys(t for t in split_tokens if len(t) >= 2))


def _iter_official_files(scope: str) -> list[Path]:
    if not OFFICIAL_SDK_PATH.exists():
        return []

    files = [
        path
        for path in OFFICIAL_SDK_PATH.rglob("*")
        if path.is_file() and path.suffix.lower() in SEARCH_EXTENSIONS
    ]
    scope_key = (scope or "docs").lower()
    if scope_key in {"api", "apis", "接口", "event", "events", "事件"}:
        hints = ("interface", "event", "接口", "事件", "api", "component", "组件")
        filtered = [path for path in files if any(h in str(path).lower() for h in hints)]
        return filtered or files
    return files


def _snippet(text: str, tokens: list[str], max_chars: int = 520) -> str:
    low = text.lower()
    positions = [low.find(token) for token in tokens if token and low.find(token) >= 0]
    start = max(0, min(positions) - 160) if positions else 0
    snippet = text[start : start + max_chars].strip()
    return re.sub(r"\s+", " ", snippet)


def search_modsdk_official(query: str, scope: str = "docs", limit: int = 5) -> dict[str, Any]:
    """Search Astell's local official SDK wing with lightweight keyword scoring."""

    tokens = _tokenize(query)
    if not tokens:
        return {"query": query, "scope": scope, "results": []}

    results: list[dict[str, Any]] = []
    for path in _iter_official_files(scope):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        text_low = text.lower()
        path_low = str(path).lower()
        score = 0
        for token in tokens:
            score += text_low.count(token) * 3
            if token in path_low:
                score += 6
        if score <= 0:
            continue

        rel_path = path.relative_to(LIBRARY_PATH).as_posix()
        results.append(
            {
                "path": rel_path,
                "score": score,
                "snippet": _snippet(text, tokens),
            }
        )

    results.sort(key=lambda item: (-item["score"], item["path"]))
    return {"query": query, "scope": scope, "results": results[: max(1, min(limit, 20))]}


def _identifier(namespace: str, name: str) -> str:
    clean_namespace = re.sub(r"[^a-z0-9_]", "_", (namespace or "astell").lower()).strip("_")
    clean_name = re.sub(r"[^a-z0-9_]", "_", name.lower()).strip("_")
    return f"{clean_namespace or 'astell'}:{clean_name or 'new_asset'}"


def _pack_entry(path: str, content: dict[str, Any]) -> dict[str, str]:
    return {
        "path": path,
        "content": json.dumps(content, ensure_ascii=False, indent=2),
    }


def _lang_entry(key: str, label: str) -> dict[str, str]:
    return {"path": "resource_pack/texts/zh_CN.lang", "content": f"{key}={label}\n"}


def _item_files(full_id: str, short_name: str, label: str, components: dict[str, Any]) -> list[dict[str, str]]:
    item_components = {
        "minecraft:max_stack_size": 64,
        "minecraft:icon": short_name,
    }
    item_components.update(components)
    return [
        _pack_entry(
            f"behavior_pack/items/{short_name}.json",
            {
                "format_version": "1.10",
                "minecraft:item": {
                    "description": {"identifier": full_id},
                    "components": item_components,
                },
            },
        ),
        _pack_entry(
            "resource_pack/textures/item_texture.json",
            {
                "resource_pack_name": "vanilla",
                "texture_name": "atlas.items",
                "texture_data": {short_name: {"textures": f"textures/items/{short_name}"}},
            },
        ),
        _lang_entry(f"item.{full_id}.name", label),
    ]


def _tool_components(short_name: str, *, damage: int, durability: int, mining_speed: int | None = None) -> dict[str, Any]:
    components: dict[str, Any] = {
        "minecraft:max_stack_size": 1,
        "minecraft:icon": short_name,
        "minecraft:damage": damage,
        "minecraft:durability": {"max_durability": durability},
        "minecraft:hand_equipped": True,
    }
    if mining_speed is not None:
        components["minecraft:digger"] = {
            "use_efficiency": True,
            "destroy_speeds": [{"block": "minecraft:stone", "speed": mining_speed}],
        }
    return components


def generate_modsdk_template(
    kind: str,
    identifier: str,
    namespace: str = "astell",
    display_name: str | None = None,
) -> dict[str, Any]:
    """Generate minimal Bedrock/NetEase-style JSON templates."""

    kind_key = (kind or "").lower()
    name = re.sub(r"^[a-z0-9_]+:", "", identifier.lower()).replace("-", "_")
    full_id = _identifier(namespace, name)
    short_name = full_id.split(":", 1)[1]
    label = display_name or short_name.replace("_", " ").title()

    if kind_key in {"item", "custom_item", "物品"}:
        files = _item_files(full_id, short_name, label, {})
    elif kind_key in {"food", "custom_food", "食物"}:
        files = _item_files(
            full_id,
            short_name,
            label,
            {
                "minecraft:food": {
                    "nutrition": 4,
                    "saturation_modifier": "normal",
                    "can_always_eat": False,
                },
                "minecraft:use_duration": 32,
            },
        )
    elif kind_key in {"sword", "剑"}:
        files = _item_files(full_id, short_name, label, _tool_components(short_name, damage=6, durability=250))
    elif kind_key in {"pickaxe", "镐"}:
        files = _item_files(full_id, short_name, label, _tool_components(short_name, damage=4, durability=250, mining_speed=6))
    elif kind_key in {"axe", "斧"}:
        files = _item_files(full_id, short_name, label, _tool_components(short_name, damage=5, durability=250, mining_speed=5))
    elif kind_key in {"shovel", "锹"}:
        files = _item_files(full_id, short_name, label, _tool_components(short_name, damage=3, durability=250, mining_speed=5))
    elif kind_key in {"hoe", "锄"}:
        files = _item_files(full_id, short_name, label, _tool_components(short_name, damage=2, durability=250, mining_speed=4))
    elif kind_key in {"bow", "弓"}:
        files = _item_files(
            full_id,
            short_name,
            label,
            {
                "minecraft:max_stack_size": 1,
                "minecraft:use_duration": 72000,
                "minecraft:shooter": {
                    "ammunition": [{"item": "minecraft:arrow", "use_offhand": True}],
                    "charge_on_draw": True,
                    "launch_power_scale": 1.0,
                },
                "minecraft:durability": {"max_durability": 384},
            },
        )
    elif kind_key in {"throwable", "projectile", "投掷物"}:
        files = _item_files(
            full_id,
            short_name,
            label,
            {
                "minecraft:max_stack_size": 16,
                "minecraft:projectile": {"projectile_entity": full_id},
                "minecraft:throwable": {"do_swing_animation": True, "launch_power_scale": 1.0},
            },
        ) + [
            _pack_entry(
                f"behavior_pack/entities/{short_name}.json",
                {
                    "format_version": "1.16.0",
                    "minecraft:entity": {
                        "description": {"identifier": full_id, "is_spawnable": False, "is_summonable": True},
                        "components": {
                            "minecraft:collision_box": {"width": 0.25, "height": 0.25},
                            "minecraft:projectile": {
                                "power": 1.5,
                                "gravity": 0.05,
                                "on_hit": {"impact_damage": {"damage": 4}},
                            },
                        },
                    },
                },
            )
        ]
    elif kind_key in {"armor", "盔甲"}:
        files = _item_files(
            full_id,
            short_name,
            label,
            {
                "minecraft:max_stack_size": 1,
                "minecraft:armor": {"protection": 3},
                "minecraft:wearable": {"slot": "slot.armor.chest"},
                "minecraft:durability": {"max_durability": 240},
            },
        )
    elif kind_key in {"block", "custom_block", "方块"}:
        files = [
            _pack_entry(
                f"behavior_pack/blocks/{short_name}.json",
                {
                    "format_version": "1.16.0",
                    "minecraft:block": {
                        "description": {"identifier": full_id},
                        "components": {
                            "minecraft:destroy_time": 1.0,
                            "minecraft:explosion_resistance": 1.0,
                            "minecraft:map_color": "#7f7f7f",
                        },
                    },
                },
            ),
            _pack_entry(
                f"resource_pack/blocks.json",
                {full_id: {"textures": short_name, "sound": "stone"}},
            ),
            _pack_entry(
                f"resource_pack/textures/terrain_texture.json",
                {
                    "resource_pack_name": "vanilla",
                    "texture_name": "atlas.terrain",
                    "texture_data": {short_name: {"textures": f"textures/blocks/{short_name}"}},
                },
            ),
            _lang_entry(f"tile.{full_id}.name", label),
        ]
    elif kind_key in {"entity", "custom_entity", "实体"}:
        files = [
            _pack_entry(
                f"behavior_pack/entities/{short_name}.json",
                {
                    "format_version": "1.16.0",
                    "minecraft:entity": {
                        "description": {
                            "identifier": full_id,
                            "is_spawnable": True,
                            "is_summonable": True,
                        },
                        "components": {
                            "minecraft:health": {"value": 20, "max": 20},
                            "minecraft:movement": {"value": 0.25},
                            "minecraft:collision_box": {"width": 0.6, "height": 1.8},
                        },
                    },
                },
            ),
            _pack_entry(
                f"resource_pack/entity/{short_name}.json",
                {
                    "format_version": "1.10.0",
                    "minecraft:client_entity": {
                        "description": {
                            "identifier": full_id,
                            "materials": {"default": "entity_alphatest"},
                            "textures": {"default": f"textures/entity/{short_name}"},
                            "geometry": {"default": f"geometry.{short_name}"},
                            "render_controllers": ["controller.render.default"],
                        }
                    },
                },
            ),
            _lang_entry(f"entity.{full_id}.name", label),
        ]
    elif kind_key in {"recipe", "合成", "配方"}:
        files = [
            _pack_entry(
                f"behavior_pack/recipes/{short_name}.json",
                {
                    "format_version": "1.12",
                    "minecraft:recipe_shaped": {
                        "description": {"identifier": full_id},
                        "tags": ["crafting_table"],
                        "pattern": [" A ", " A ", " B "],
                        "key": {
                            "A": {"item": "minecraft:stick"},
                            "B": {"item": "minecraft:planks"},
                        },
                        "result": {"item": full_id, "count": 1},
                    },
                },
            )
        ]
    elif kind_key in {"loot_table", "loot", "战利品"}:
        files = [
            _pack_entry(
                f"behavior_pack/loot_tables/{short_name}.json",
                {
                    "pools": [
                        {
                            "rolls": 1,
                            "entries": [
                                {
                                    "type": "item",
                                    "name": full_id,
                                    "weight": 1,
                                    "functions": [{"function": "set_count", "count": {"min": 1, "max": 1}}],
                                }
                            ],
                        }
                    ]
                },
            )
        ]
    elif kind_key in {"spawn_rule", "spawn_rules", "生成规则"}:
        files = [
            _pack_entry(
                f"behavior_pack/spawn_rules/{short_name}.json",
                {
                    "format_version": "1.8.0",
                    "minecraft:spawn_rules": {
                        "description": {
                            "identifier": full_id,
                            "population_control": "animal",
                        },
                        "conditions": [
                            {
                                "minecraft:spawns_on_surface": {},
                                "minecraft:brightness_filter": {"min": 7, "max": 15, "adjust_for_weather": False},
                                "minecraft:weight": {"default": 10},
                                "minecraft:herd": {"min_size": 1, "max_size": 3},
                                "minecraft:biome_filter": {"test": "has_biome_tag", "operator": "==", "value": "plains"},
                            }
                        ],
                    },
                },
            )
        ]
    else:
        raise ValueError("kind 仅支持 item/block/entity/recipe/loot_table/spawn_rule/food/sword/pickaxe/axe/shovel/hoe/armor/bow/throwable")

    return {
        "kind": kind_key,
        "identifier": full_id,
        "display_name": label,
        "files": files,
        "next_steps": [
            "把生成内容写入对应 behavior_pack/resource_pack 路径。",
            "补齐真实贴图、模型、语言文件和脚本逻辑。",
            "调用 register_resource_id 登记新增资源 ID。",
            "实现完成后调用 record_astell_trace 写开发日志。",
        ],
    }


def review_modsdk_code(code: str) -> dict[str, Any]:
    """Run a lightweight ModSDK-oriented code review."""

    findings: list[dict[str, str]] = []

    def add(severity: str, title: str, detail: str) -> None:
        findings.append({"severity": severity, "title": title, "detail": detail})

    checks = [
        (r"(^|[^A-Za-z0-9_])f['\"]", "high", "Python 2.7 不支持 f-string", "网易 ModSDK 常见运行环境不能执行 f-string，改用 % 或 .format。"),
        (r"def\s+\w+\([^)]*:\s*[^)]*\)", "high", "疑似函数类型注解", "Python 2.7 不支持参数类型注解。"),
        (r"->\s*[A-Za-z_][A-Za-z0-9_]*\s*:", "high", "疑似返回值类型注解", "Python 2.7 不支持返回值类型注解。"),
        (r"\basync\s+def\b|\bawait\b", "high", "疑似 async/await", "Python 2.7 不支持 async/await，且 ModSDK 回调一般不是 asyncio 模型。"),
        (r"\bfrom\s+pathlib\s+import\b|\bimport\s+pathlib\b", "medium", "pathlib 兼容性风险", "Python 2.7 环境中 pathlib 不一定可用，建议用 os.path。"),
        (r"\bdataclass\b|\bfrom\s+dataclasses\s+import\b", "medium", "dataclass 兼容性风险", "dataclass 是 Python 3 生态能力，不适合作为 ModSDK 默认代码。"),
        (r"except\s+Exception\s*:\s*(pass)?", "medium", "异常处理过于粗糙", "至少记录模块、事件名、实体/玩家 ID，避免静默失败。"),
    ]
    for pattern, severity, title, detail in checks:
        if re.search(pattern, code, flags=re.MULTILINE):
            add(severity, title, detail)

    if len(re.findall(r"ListenForEvent\(", code)) > 1:
        add("medium", "事件监听可能分散注册", "建议集中注册并确认不会重复执行初始化。")
    if re.search(r"OnTick|Update|tick", code, flags=re.IGNORECASE) and re.search(r"GetEntities|GetPlayerList|os\.listdir|json\.loads", code):
        add("high", "高频回调内疑似重操作", "tick/update 路径中避免全量扫描、JSON 解析或目录扫描。")
    if "CreateEngineCompFactory()" in code and len(re.findall(r"CreateEngineCompFactory\(\)", code)) > 1:
        add("low", "组件工厂重复创建", "可缓存 EngineCompFactory，减少样板和高频开销。")
    if re.search(r"identifier|minecraft:", code) and not re.search(r"[a-z0-9_]+:[a-z0-9_]+", code):
        add("low", "资源 ID 命名需要复核", "自定义 identifier 建议保持 namespace:name。")

    return {
        "summary": "未发现明显问题。" if not findings else f"发现 {len(findings)} 个需要复核的问题。",
        "findings": findings,
        "best_practices": PRACTICES["general"][:3],
    }


def get_modsdk_best_practices(topic: str = "general") -> dict[str, Any]:
    topic_key = (topic or "general").lower()
    rules = PRACTICES.get(topic_key, PRACTICES["general"])
    return {"topic": topic_key, "rules": rules, "available_topics": sorted(PRACTICES)}

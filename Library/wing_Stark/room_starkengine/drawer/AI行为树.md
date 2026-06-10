# [StarkEngine] AI 行为树系统 (AI行为树.md)

> **AI 检索元数据**  
> **项目名称**: StarkEngine (wing_Stark)  
> **核心领域**: Behavior Tree, 行为节点, 条件节点, 组合节点, 节点颜色识别  
> **主要目标**: 提供一套超越基岩版原生 JSON 配置的、高度可自定义且功能丰富的生物行为逻辑系统。

---

## 1. 概述 (Overview)

AI 行为树是 StarkEngine 中最强大的功能之一。它解决了原生 JSON 驱动行为表现力弱、逻辑难以维护的问题，引入了现代游戏引擎（如 UE/Unity）通用的行为树架构。

### 核心特性
*   **纯服务端运行**: 行为树逻辑完全运行在服务端，不增加客户端开销。
*   **高表现力**: 支持复杂的组合逻辑、随机分支、多条件判断。
*   **节点库丰富**: 内置了渲染管理、多种攻击模式、智能寻路与生成的预制节点。

---

## 2. 系统架构 (Architecture)

行为树系统由五大部分构成，共同协作决定实体的行为流向：

1.  **实体行为树组件**: 一种特殊的实体组件（`StarkBaseActorComponent`），通过 `AddNode` 挂载至生物。
2.  **黑板 (BlackBoard)**: 类似于字典的共享数据容器，用于在不同节点间传递信息（如目标坐标、血量阈值）。
3.  **行为节点 (Action Node)**: 执行具体动作（如：攻击、移动、播放动画）。
4.  **条件节点 (Condition Node)**: 输出判断结果，影响决策方向（如：检测范围内是否有目标）。
5.  **组合节点 (Composite Node)**: 行为树的“骨干”，连接并管理行为与条件节点的逻辑关系。

---

## 3. 节点颜色与逻辑手册

为了在开发中快速识别节点属性，SE 遵循以下颜色/类型标准：

| 颜色 | 节点类型 (Type) | 逻辑描述 | 常见示例 |
| :--- | :--- | :--- | :--- |
| <font color="#f7ea48">**黄色**</font> | **组合节点 (Composite)** | 逻辑分支（枝）。决定如何执行子节点。 | `Selector`, `Sequence` |
| <font color="#f86a6a">**红色**</font> | **条件节点 (Condition)** | 判断逻辑（叶）。根据环境返回真假。 | `HasTarget`, `IsTargetInRange` |
| <font color="#53d353">**绿色**</font> | **行为节点 (Action)** | 执行动作（叶）。完成具体的指令。 | `PlayAnimation`, `MoveToTarget` |

---

## 4. 实战案例：[风暴之主] 行为树逻辑拆解

以下是采用“风暴之主”AI 逻辑的代码化呈现，展示了组合节点与叶子节点的配合。

```python
# [案例] 风暴之主 AI 核心逻辑片段
Selector([ # 1. 根选择器
    Sequence([ # 2. 逻辑流：有目标时的追击与技能
        HasTarget(), # 【红】检测是否有目标
        Selector([ # 3. 逻辑分歧：根据距离选择技能
            Sequence([ # 4. 近战距离 (0-5格)
                IsTargetInRange(0, 5), # 【红】目标在近战位
                Selector([ # 5. 随机抽取近战技能
                    Sequence([ # 技能 A: 闪电
                        RandomChance(0.5), # 【红】50% 几率
                        LogAction('闪电'), # 【绿】打印日志
                        StayStatic(), # 【绿】原地停止
                        PlayAnimation('animation.travel.container.stormlord.skill2'), # 【绿】播动画
                        ThunderPower(radius=5, duration=[4, 4]) # 【绿】释放闪电
                    ]),
                    Sequence([ # 技能 B: 风刃
                        RandomChance(0.3), # 【红】30% 几率
                        LogAction('风刃'),
                        PlayAnimation('animation.travel.container.stormlord.skill1'),
                        WaitAction(1), # 【绿】强制等待 1s
                        WindKnife(damage=random.randint(2, 5), box_size=(8, 5, 8)), # 【绿】风刃攻击
                        RandomWaitAction(1, 2) # 【绿】随机后摇
                    ]),
                    Sequence([ # 兜底逻辑: 等待
                        LogAction('等待'),
                        RandomWaitAction(0.5, 1)
                    ])
                ])
            ]),
            Sequence([ # 6. 远距离行为
                Selector([
                    Sequence([ # 目标在 20格 内
                        IsTargetInRange(0, 20),
                        RandomChance(0.3),
                        LogAction('距离过远闪电'),
                        StayStatic(),
                        PlayAnimation('animation.travel.container.stormlord.skill2'),
                        ThunderPower(radius=20, duration=[4, 4])
                    ]),
                    Sequence([ # 目标过远，执行追击
                        MoveToTarget(speed=2.0) # 【绿】高速靠近目标
                    ])
                ])
            ])
        ])
    ]),
    Sequence([ # 7. 无目标时的巡航逻辑
        Selector([
            StayStatic(),
            RandomWaitAction(2, 3) # 无所事事，随机等待
        ])
    ])
])
```

### 核心节点逻辑总结
*   **Selector (选择器)**: 只要有一个子节点返回成功，就停止向下搜索，返回成功。适用于“寻找可用技能”或“优先级判断”。
*   **Sequence (顺序器)**: 只有子节点全部成功，才返回成功。适用于“先检测条件 A，再执行动作 B”的流水线逻辑。

---
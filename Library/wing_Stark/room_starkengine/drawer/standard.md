# [Stark项目] 开发规范标准 (standard.md)

> **AI 检索元数据**  
> **项目名称**: Stark (wing_Stark)  
> **核心领域**: 目录分类, 命名规范, 路径管理, Python 开发  
> **主要目标**: 提高 AI 辅助开发时的路径准确度与代码健壮性。

---

## 1. 目录分类规范 (Directory Categorization)

### 1.1 核心原则
严禁在资源目录下进行“扁平化”存储。必须按照**玩法元素**或**逻辑类型**（如载具、Boss、基础物品等）建立子文件夹进行分类管理。

### 1.2 强制执行目录清单
以下目录中的 JSON 或 资源文件必须严格分类，禁止直接堆放在根目录：

| 包体类型 | 目录路径 (Folders) |
| :--- | :--- |
| **行为包 (BP)** | `entities`, `animations`, `animation_controllers` |
| **资源包 (RP)** | `entity`, `animations`, `animation_controller`, `particles`, `sounds`, `models\entity`, `render_controllers` |

### 1.3 资源分类示例
*   **推荐结构**: `entities/vehicle/car.json`, `entities/boss/dragon.json`
*   **不推荐结构**: `entities/car.json`, `entities/dragon.json`

---

## 2. 贴图路径深度约束 (Texture Path Depth)

资源包中的 `textures` 文件夹必须遵循以下固定格式，严禁随意创建顶级目录：

**格式**:  
`资源包/textures/travel/{项目英文名}/{资源品类}/{分类}/{文件名}.png`

*   **项目示例**: `test_project`
*   **实际路径示例**:  
    `textures/travel/test_project/entities/vehicle/car.png`

---

## 3. ID 与 键名 命名规范 (Naming Convention)

所有跨文件引用的键名和 ID 必须包含项目前缀，以防止命名冲突。

### 3.1 命名格式表

| 类型 | 格式 | 示例 |
| :--- | :--- | :--- |
| **Geometry (模型标识符)** | `geometry.travel_{项目英文名}_{名称}` | `geometry.travel_stark_car` |
| **Animation (动画键名)** | `animation.travel.{项目英文名}.{分类}.{动作}` | `animation.travel.stark.human.walk` |
| **Animation Controller** | `controller.animation.travel.{项目英文名}.{名称}` | `controller.animation.travel.stark.car` |
| **Render Controller** | `controller.render.travel.{项目英文名}.{名称}` | `controller.render.travel.stark.car` |
| **Namespace (命名空间)** | `travel:{项目英文名}_{名称}` | `travel:stark_item_box` |

> **注**: 凡是使用 `namespace:xxxxx` 的地方，全部严格遵循上述命名空间格式。

---

## 4. Python 开发：字符串类路径规范 (Python Class Path)

在涉及 UI 注册（如 `RegisterUI`）或需要提供“字符串类路径”的参数时，**严禁硬编码字符串**。

### 4.1 推荐方案 (推荐使用)
通过导入类并使用反射获取路径，避免因文件移动或类名更改导致的维护灾难：

```python
# 1. 正常导入类
from myTestModScript.UI.myUI import myUIClass

# 2. 动态生成路径参数
# 效果等同于 "myTestModScript.UI.myUI.myUIClass"
class_path = myUIClass.__module__ + '.' + myUIClass.__name__

# 3. 传参
RegisterUI(class_path, ...)
```

### 4.2 禁止方案 (禁止使用)
`RegisterUI("myTestModScript.UI.myUIClass")`  
*(原因：当文件重命名或位置变动时，IDE 无法识别该字符串错误，会导致运行时崩溃且难以排查)*

---
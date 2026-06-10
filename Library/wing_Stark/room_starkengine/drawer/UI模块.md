# UI模块

## 概述
SE提供了一套完整的UI系统，包含UI动效、现代化装饰器UI事件等。SE提供两种UI基类StarkBaseUI以及StarkBaseUIProxy，前者适用于所有的自定义JSON UI，后者适用于原版代理UI。它们统一由UIManager进行管理。这两种UI基类提供了丰富的内容，封装了大部分UI API，用法基本相似，我们主要以StarkBaseUI为主讲解。

如果你不清楚什么是原版代理UI和正常的自定义UI，请查阅网易相关文档学习。

## UI Manager（UI管理器）
仅存在于客户端，全局单例，本质是一个场景组件（StarkBaseLevelComponent）
可通过GetNodeByName(StarkNodes.UI)来获取该组件实例
它的作用主要是用来管理UI界面的注册、创建、关闭。

### RegisterUI
注册一个UI界面（非原版代理UI），每个界面只需要注册一次，建议在Start中注册。
| 参数名 | 参数类型 | 描述 |
| :--- | :--- | :--- |
| uiKey | str | 唯一标识符 |
| uiCls | class | 继承于StarkBaseUI的ui类 |
| uiDef | str | [缺省] UI定义文件路径 (xxxx.main)，不填默认是uiKey.main |

### OpenUI
打开一个UI界面（非原版代理UI）
| 参数名 | 参数类型 | 描述 |
| :--- | :--- | :--- |
| uiKey | str | 唯一标识符 |
| **params | any | UI额外参数，比如isHud=False，与网易CreateUI的createParam参数相同 |

### CloseUI
关闭一个UI界面（非原版代理UI）
但是推荐还是在UI类里面自己写关闭逻辑
| 参数名 | 参数类型 | 描述 |
| :--- | :--- | :--- |
| uiKey | str | 唯一标识符 |

### GetUI
获取一个已打开的UI界面对象实例
| 参数名 | 参数类型 | 描述 |
| :--- | :--- | :--- |
| uiKey | str | 唯一标识符 |
**返回**: UI对应的python类的实例

### PushUI
以栈堆管理的方式打开一个UI界面（非原版代理UI）
注意：如果你不知道什么是栈堆管理的方式打开与OpenUI普通创建的区别，你可以查阅相关网易文档，或者自己试一下两种方式。
| 参数名 | 参数类型 | 描述 |
| :--- | :--- | :--- |
| uiKey | str | 唯一标识符 |
| **params | any | UI额外参数，比如isHud=False，与网易PushScreen的createParam参数相同 |

### PopUI
以栈堆管理的方式关闭一个UI界面（非原版代理UI）
无参数，会关闭你最后一个PushUI的界面

### PopTopUI
以栈堆管理的方式关闭最顶层的界面，包括原版UI界面也都会关闭（非原版代理UI）

---

## UI基类

### 生命周期
- **Start**: 在UI创建成功后调用
- **OnUpdate**: UI每帧调用
- **OnDestroy**: UI销毁时调用，在StarkBaseUIProxy是Destroy而不是OnDestroy请注意

### 滑动列表+网格托管代理
很多时候会用到滑动列表ScrollingView+Grid(SVG)这种UI结构，也就是滑动列表的画布内容是一个grid，这种形式从监听到特定逻辑实现整个流程极为繁琐麻烦，SE提供了一套非常方便的托管代理。

#### svg_process
托管一个SVG结构
| 参数名 | 参数类型 | 描述 |
| :--- | :--- | :--- |
| path | str | 滑动列表的路径 |
| callback | callable | 当SVG网格中一个格子单元刷新时会调用，传入参数见下方 |
| do_call | bool | [缺省] 是否立刻执行一次全网格的callback调用，默认false |

**SVG托管回调函数参数**
| 参数名 | 参数类型 | 描述 |
| :--- | :--- | :--- |
| cellName | str | 单元格的名称 |
| cellPath | callable | 单元格的路径 |

#### svg_cancel
取消托管一个SVG结构
| 参数名 | 参数类型 | 描述 |
| :--- | :--- | :--- |
| path | str | 滑动列表的路径 |

#### svg_recall
手动触发一遍SVG中所有单元格的callback回调
| 参数名 | 参数类型 | 描述 |
| :--- | :--- | :--- |
| path | str | 滑动列表的路径 |

---

## 装饰器
SE的UI系统提供一套现代化非常方便的UI常用装饰器，它们在StarkUIBind类中

### ButtonDown
绑定一个按钮按下的回调事件
| 参数名 | 参数类型 | 描述 |
| :--- | :--- | :--- |
| path | str | 按钮的路径 |
| isSwallow | bool | [缺省]是否会吞噬点击事件，isSwallow为Ture时，点击时，点击事件不会穿透到世界。如破坏方块、镜头转向不会被响应，默认True |

```python
class MyUI(StarkBaseUI):
    def __init__(self,*args):
        ...
        
    @StarkUIBind.ButtonDown('/testBtn')
    def onBtnPressed(self, args):
        ...
        # 这里写点击的业务逻辑
```

### ButtonUp
绑定一个按钮按下抬起后的回调事件
| 参数名 | 参数类型 | 描述 |
| :--- | :--- | :--- |
| path | str | 按钮的路径 |
| isSwallow | bool | [缺省]是否会吞噬点击事件，isSwallow为Ture时，点击时，点击事件不会穿透到世界。如破坏方块、镜头转向不会被响应，默认True |

### Loop
将函数循环执行，有该装饰器的函数从UI创建后会一直循环自动执行
| 参数名 | 参数类型 | 描述 |
| :--- | :--- | :--- |
| interval | float | 间隔多久触发一次 |

---

## UI动画
SE提供一套强大的不局限于json ui动画的更灵活的动画系统。

### play_animation
播放动画。start和end参数代表动画开始的位置到终点的位置。
位置的写法有多种：
- `(30,60)`: tuple类型，这种最为直接
- `"30,60"`: 等同于（30，60）
- `"R30,60"`: 字符串类型，R表示使用相对位置，如R30,60表示相对于目前控件位置的(30,60)处
- `"R20%S,60"`: %S表示相对于控件自身尺寸的比例，则R20%S表示 目前控件所在的位置+控件尺寸20%大小的位置
- `"50%P, 60"`: %P表示相对于父控件尺寸的的比例，50%P表示 父控件大小*50%
- R可与%S/%P混用

| 参数名 | 参数类型 | 描述 |
| :--- | :--- | :--- |
| path | str | 需要播放动画的控件路径 |
| prop | StarkAnimProperty | 动画类型：Position, Size, Alpha, Visible |
| start | str/tuple | 起始位置 |
| end | str/tuple | 结束位置 |
| duration | float | 动画时长 |
| easing | StarkEasing | [缺省] 缓动类型，默认为StarkEasing.Linear |
| on_complete | callable | [缺省] 播放完成时触发的回调函数 |
| delay | float | [缺省] 延迟播放，默认不延迟 |
**返回**: StarkUIAnimation，可链式调用 `.then(...)` 衔接下一段同属性动画。

### stop_animation
| 参数名 | 参数类型 | 描述 |
| :--- | :--- | :--- |
| path | str | 需要播放动画的控件路径 |
| prop | StarkAnimProperty | 动画类型 |
| jump_to_end | bool | 直接跳到结尾，如果为False的话将不会触发on_complete与接下来的链式动画 |

### then
链式播放动画。参数含义同 play_animation。
```python
self.play_animation(self.tipsPanel.GetPath(), StarkAnimProperty.Alpha, 0, 1, 1, 
                    easing=StarkEasing.OutQuad).then(0, 1, 
                    easing=StarkEasing.OutQuad, 
                    delay=max(0, duration - 0.5), start_val=1)
```

---

## 常用UI API封装 (StarkBaseUI / StarkBaseUIProxy)
*注：以下方法双基类通用。*

### 定时器
- **add_timer(time, callback, *args, **kwargs)**: 添加一次性定时器。返回 timer 句柄。
- **add_timer_repeat(time, callback, *args, **kwargs)**: 添加重复定时器。返回 timer 句柄。
- **remove_timer(timer)**: 取消定时器。

### 控件属性操控
- **get_system(systemName, namespace='')**: 获取客户端系统实例。
- **get_toggle(path)**: 获取开关选中状态 (bool)。
- **set_toggle(path, selected)**: 设置开关选中状态。
- **set_pos(path, pos)**: 设置控件位置 (x, y)。
- **get_pos(path)**: 获取控件位置 (x, y)。
- **get_golbal_pos(path)**: 获取控件全局位置。
- **get_size(path)**: 获取控件尺寸 (w, h)。
- **set_size(path, size)**: 设置控件尺寸 (w, h)。
- **set_alpha(path, alpha)**: 设置控件透明度 (0~1)。
- **rotate_image(path, angle)**: 旋转图片控件 (0~360)。

### 状态与触摸
- **enable_widget(path)**: 启用控件触摸。
- **disable_widget(path)**: 禁用控件触摸。
- **get_visible2(path)**: 获取控件是否可见。
- **set_visible2(path, visible)**: 设置控件可见性。

### 原版 HUD 控制
- **disable_vanilla_hud()**: 隐藏原版 HUD。
- **enable_vanilla_hud()**: 恢复显示原版 HUD。

### 交互组件操作
- **set_slider_value(path, value)**: 设置滑条数值。
- **get_slider_value(path)**: 获取滑条数值。
- **get_label_text(path)**: 获取标签文本。
- **set_label_text(path, text)**: 设置标签文本。
- **get_edit_box_text(path)**: 获取输入框文本。
- **set_edit_box_text(path, text)**: 设置输入框文本。
- **add_combobox_options(path, options_list)**: 向下拉框逐项添加选项。
- **set_combobox_selected(path, index)**: 按下标选中下拉框项。
- **set_combobox_selected_by_show_name(path, showName)**: 按显示名称选中下拉框项。
- **set_progress(path, progress)**: 设置进度条值 (0~1)。
- **get_progress(path)**: 从缓存读取进度。

### 图像与渲染
- **set_image(path, imagePath)**: 设置 Image 精灵贴图路径。
- **set_image_gray(path, isGray)**: 设置 Image 是否灰度。
- **set_image_color(path, color)**: 设置 Image 精灵颜色。
- **get_item_render_item(path)**: 获取物品渲染控件当前物品。
- **set_item_render_item(path, itemName, aux, isEnchanted, user_data)**: 设置物品渲染控件。
- **set_paperdoll_entityId(path, entity_id, scale=1.0, render_depth=-15, ...)**: 在 PaperDoll 上按 ID 渲染。
- **set_paperdoll_entity_identifier(path, entity_identifier, ...)**: 在 PaperDoll 上按标识符渲染。

### 按钮事件手动绑定
- **button_up_event(path, callback, isSwallow=True)**: 绑定抬起。
- **button_down_event(path, callback, isSwallow=True)**: 绑定按下。
- **button_cancel_event(path, callback, isSwallow=True)**: 绑定取消。
- **button_move_event(path, callback, isSwallow=True)**: 绑定移动。

### Grid 与 ScrollView 操控
- **get_grid_count(path)**: 获取 Grid 逻辑数量。
- **set_grid_count(path, count, x_Max=2)**: 设置 Grid 行列与可见子项。
- **get_sv_content(path)**: 获取 ScrollView 内容区路径。
- **get_sv_percent(path)**: 获取 ScrollView 滚动百分比。
- **get_sv_pos(path)**: 获取 ScrollView 内容位置。

### SVG 代理相关内部 API
- **svg_process(path, callback, do_call)**
- **svg_recall(path)**
- **svg_cancel(path)**
- **svg_distributor(args)**: 供 Grid 尺寸改变事件注册。

### 路径处理工具
- **remove_all_child(path)**: 删除某路径下全部子控件。
- **path_last(path)**: 取路径最后一段。
- **path_parent(path)**: 取父路径。
- **path_child(path, AllPath)**: 从长路径取出第一级子名。
- **relative_path(path)**: HUD 绝对路径规约为相对路径。

---

## 引擎核心接入
- **GetLoaderSystem()**: 返回 StarkLoaderClientSys 实例。
- **GetNodeByName(nodeName)**: 从 ComponentMgr 取节点。

### Proxy 类专属 API
- **GetBaseUIControl(path)**: 获取引擎原版 UI 控件。
- **GetChildrenName(path)**: 获取子控件名称列表。

---

## 详细生命周期接口说明

### 核心回调
- **OnRenderTick(args)**: 每帧渲染回调（先更新动画，再执行此回调）。
- **Start()**: 初始化逻辑入口。
- **OnUpdate(args)**: 逻辑更新入口。

### 自定义 UI (StarkBaseUI)
- **Create(args)**: 界面创建入口（处理注解、订阅事件）。
- **Update(args)**: 转发 OnUpdate。
- **Destroy()**: 注销事件、清理资源、调用 OnDestroy。
- **OnDestroy()**: 销毁时钩子。

### 代理 UI (StarkBaseUIProxy)
- **OnCreate(args)**: 注解处理与 __Start。
- **OnTick()**: 转发 OnUpdate。
- **Destroy()**: 空实现（占位）。
- **OnDestroy()**: 执行 Shutdown、注销监听、最后调用子类 Destroy()。
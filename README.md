# simple-event-system
A simple plugin, hook, and event-driven system framework.

## Install
```bash
pip install simple-event-system
```

## 介绍

在当前系统中，总共有以下几类对象：

1. 事件：当系统遇到外部输入时，事件会被送入事件队列。
2. 插件：插件是事件处理器，当激活一个插件时，插件会被送入插件队列。
3. 全局数据区：全局数据区是一个所有插件共享的存储空间，插件可以读写全局数据区的数据，从而影响其他插件的行为。
4. 钩子：钩子是全局数据区的中间件，当插件读写全局数据区时，如果设置了钩子，则会透过钩子的操作方法，间接操作全局数据。

### 插件

每当事件发生时，这个事件会被通知到已经激活的所有插件。这些插件会依据其优先级的顺序被调用。当插件处理完这个事件后，可以有以下几种选择：

1. 将这个事件继续向下传递。
2. 不再将这个事件继续向下传递。
3. 向事件队列中塞入若干个新事件（当前事件是否向下传递可选，新事件将在未来从头开始调用每个插件的处理函数）。

```python
# 对 AbstractPlugin 类派生可以得到新的插件
from simple_event_system import AbstractPlugin, AbstractEvent， EventSystem

# 自定义一个插件必须要重写以下几个函数
class MyPlugin(AbstractPlugin):

    # identifier 用于定义插件的唯一标识符
    # 具有相同 identifier 值的插件在插件列表中只能存在一个
    def identifier(self) -> str: 
        return "MyPlugin"

    # 插件优先级
    # 优先级编号越小的插件，将会被越先执行
    def priority(self) -> float:
        return 5000

    # 事件处理函数
    #   返回两个参数
    #   第一个参数表示当前事件是否会被传递给下游插件（一般来说请使用 True）
    #   第二个参数是一个列表，描述当前插件想要向事件队列尾部追加什么新事件（一般来说请使用空 list []）
    # 输入参数
    #   event 中有 identifier 和 message 两个方法，用于获取事件的类型和信息
    #   global_data_mgr 中有 get 和 put 两个方法，用于直接或者间接操作全局数据
    #   这里的 global_data_mgr 是已经被 hook 好的版本，使用它可以自动调用钩子序列
    def process_event(self, global_data_mgr:GlobalDataMgr, event:AbstractEvent) -> tuple[bool, list[AbstractEvent]]:
        return True, []

# 创建事件系统
es = EventSystem(logfile_path)

# 调用 activate 方法可以启动插件
# 在钩子 SystemStatusHook 运行的前提下
# 可以通过将 SystemStatusHook.MyPlugin.PluginActive 设置为 True 启动插件
MyPlugin().activate(es)

# 调用 deactivate 可以禁用插件
# 在钩子 SystemStatusHook 运行的前提下
# 可以通过将 SystemStatusHook.MyPlugin.PluginActive 设置为 False 关闭插件
MyPlugin().deactivate(es)

# 启动事件系统（在新线程执行，不会阻塞程序）
es.run()
```

### 钩子

在没有任何钩子的前提下，所有插件对全局数据区的读写将是直接的。如果加入了钩子，能够实现让某些指定的插件间接调用全局数据区，从而实现对插件功能的修改。

当一个插件身上安插了多个钩子时，这些钩子会按照优先级依次串联，编号最小的钩子直接操作真实数据，编号第二小的钩子操作编号最小的钩子，以此类推。插件访问的将是与这个插件相关的编号最大的钩子提供的全局数据区抽象。用户不需要手动将插件加入到插件队列中，只要插件存在， EventSystem 就能自动扫描到这个插件。

```python
# 对 AbstractGlobalDataHook 类派生可以得到新的插件
from simple_event_system import AbstractGlobalDataHook， EventSystem

# 自定义一个钩子需要重写以下函数
class MyHook(AbstractGlobalDataHook):

    # 钩子的唯一标识符 identifier
    # 具有相同 identifier 的钩子在钩子列表中至多只能出现一个
    def identifier(self) -> str:
        return "MyHook" 

    # 优先级编码
    # 优先级编码越小，距离真实全局系统数据的距离越近
    def priority(self) -> int:
        return 5000

    # 描述这个钩子是否对某个指定插件生效
    # return True 对所有插件有效
    def match_plugin(self, plugin_name:str) -> bool: 
        return True

    # 钩子对外暴露的 get 接口
    # 用于读取全局数据区
    # 返回 self.upstream_item.get(plugin_user, key) 相当于对原始功能不做任何修改
    def get(self, plugin_user:str, key:str) -> Any:
        if self.upstream_item is None:
            raise ValueError()
        return self.upstream_item.get(plugin_user, key)

    # 钩子对外暴露的 put 接口
    # 用于修改全局数据区
    # 返回 self.upstream_item.put(plugin_user, key, val) 相当于对原始功能不做任何修改
    def put(self, plugin_user:str, key:str, val:Any):
        if self.upstream_item is None:
            raise ValueError()
        return self.upstream_item.put(plugin_user, key, val)

# 创建事件系统
es = EventSystem(logfile_path)

# 调用 activate 方法可以启动钩子
# 在钩子 SystemStatusHook 运行的前提下
# 可以通过将 SystemStatusHook.MyHook.HookActive 设置为 True 启动钩子
MyHook().activate(es)

# 调用 deactivate 可以禁用钩子
# 在钩子 SystemStatusHook 运行的前提下
# 可以通过将 SystemStatusHook.MyHook.HookActive 设置为 False 关闭钩子
MyHook().deactivate(es)

# 启动事件系统（程序会在新线程运行）
es.run()
```

### 事件

事件是当前系统运行的主要驱动力，用户可以根据自己的需要自定义事件。事件中将携带一个 identifier 和 message，其中 identifier 是一个字符串，而 message 是一个把字符串映射成其他类型的字典。

```python
# 对 AbstractEvent 类派生可以得到新的插件
from simple_event_system import AbstractGlobalDataHook

# 这个对象用户可以自己写初始化函数
# 当需要将事件引入系统时
# 建议使用自定义插件的 process_event 函数返回值的第二个分量
class MyEvent(AbstractEvent):

    # 返回事件的类型（字符串）
    def identifier(self) -> str:
        return "MyEvent"
    
    # 事件所具有的信息（字典）
    def message(self) -> dict[str, Any]:
        return dict()

```

将事件引入事件队列需要借助自定义插件 process_event 函数的返回值。

## 官方接口、插件与钩子

### EventSystem

EventSystem 是管理所有插件的管理器，但是他自己也像一个插件一样，使用全局数据控制自身的运行。EventSystem 主要使用以下几个全局变量：

1. `EventSystem.Running`：描述当前事件系统是否需要继续运行，默认值是 `True`，设为 `False` 可以让系统终止。
2. `EventSystem.Timer`: 一个浮点数，默认值是 `3.0`，表示每隔三秒钟 EventSystem 会向事件队列中插入一个 `TimerEvent` 事件。这个 `TimeEvent` 事件会带有一个浮点数 `TimeNow` 信息，用于表示这个事件触发时系统已经运行了多少秒。
3. `EventSystem.Sleep`：一个浮点数，默认值是 `0.5`，表示当事件队列中没有任何事件时，EventSystem 临时睡眠的最长时间。

### EventDebuggerPlugin

EventDebuggerPlugin 是一个用于调试的插件，启用这个插件时，插件会在所有事件发生时输出这个事件的全部信息到命令行。这个插件在运行时不会默认启动，但是用户可以根据自己的需要启动这个事件调试器。

```python
from simple_event_system import EventDebuggerPlugin， EventSystem

# 创建事件系统
es = EventSystem(logfile_path)

# 启动事件调试
EventDebuggerPlugin().activate(es)

# 启动事件系统
es.run()
```

### KeyboardInterruptExitPlugin

KeyboardInterruptExitPlugin 是一个方便命令行程序退出用的插件，启用这个插件的时候，使用 `Ctrl+C` 键可以让 EventSystem 终止执行。其原理是将 `EventSystem.Running` 的值设成 `False`。如果不启用这个插件， EventSystem 将很难退出，这个插件默认是开启的。

```python
from simple_event_system import KeyboardInterruptExitPlugin， EventSystem

# 创建事件系统
es = EventSystem(logfile_path)

# 启动 Ctrl+C 退出功能
KeyboardInterruptExitPlugin().activate()

# 启动事件系统
es.run()
```

### SystemStatusHook

SystemStatusHook 是一个用于方便地查看和管理系统状态的钩子，在启用了这个钩子之后，全局空间中以下变量将可以用来查询系统状态。这个插件默认是开启的，否则用户不能方便地启动或者关停其他插件与钩子。

1. `SystemStatusHook.<插件名称>.PluginActive`：检查指定插件是否现在处于运行状态。
2. `SystemStatusHook.<钩子名称>.HookActive`：检查某个钩子是否处于运行状态。
3. `SystemStatusHook.ActivePluginList`：（只读）所有正在运行了的插件的名称，一个 list of str。
4. `SystemStatusHook.ActiveHookList`：（只读）所有正在运行了的钩子的名称，一个 list of str。

对 `SystemStatusHook.<插件名称>.PluginActive` 或者 `SystemStatusHook.<钩子名称>.HookActive` 设置为 `True` 或者 `False` 可以启用或者停用指定的钩子与插件，为我们提供了方便的操作接口。当我们想通过这两个变量启动钩子或者插件时，如果钩子或者插件未定义，程序会抛出异常。当我们想要 deactivate 插件或者钩子的时候，如果指定的钩子或者插件正在运行，程序就会将其关闭，如果指定的钩子或者插件未运行或者不存在，程序不会报错。这种方法的用途是为插件或者钩子提供方便的控制其他插件或者钩子的启停方案。

另外，由于 EventSystem 本身也可以被视为一个特殊插件，将 `SystemStatusHook.EventSystem.PluginActive` 的值设置成 False 可以用来关闭系统。将变量 `SystemStatusHook.EventDebuggerPlugin.PluginActive` 设置为 True 可以打开调试插件。

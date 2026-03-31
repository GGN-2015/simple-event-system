import traceback
import queue
import os
import datetime
import time
import threading
from typing import Optional, Any
import signal


try:
    from .AbstractEvent import AbstractEvent
    from .AbstractEvent import ExitEvent, StartupEvent, TimerEvent, KeyboardInterruptEvent
    from .AbstractPlugin import AbstractPlugin
    from .AbstractPlugin import EventDebuggerPlugin, KeyboardInterruptExitPlugin
    from .AbstractGlobalData import AbstractGlobalData, AbstractGlobalDataHook
    from .GlobalDataMgr import GlobalDataMgr
    from .GetAllConcreteSubclass import get_all_concrete_subclasses
except:
    from AbstractEvent import AbstractEvent
    from AbstractEvent import ExitEvent, StartupEvent, TimerEvent, KeyboardInterruptEvent
    from AbstractPlugin import AbstractPlugin
    from AbstractPlugin import EventDebuggerPlugin, KeyboardInterruptExitPlugin
    from AbstractGlobalData import AbstractGlobalData, AbstractGlobalDataHook
    from GlobalDataMgr import GlobalDataMgr
    from GetAllConcreteSubclass import get_all_concrete_subclasses


# 软件的事件系统
# 负责维护事件队列，调用插件处理事件
class EventSystem:

    def __init__(self, log_filepath:str) -> None:

        # 设置日志文件
        os.makedirs(os.path.dirname(log_filepath), exist_ok=True)
        self._log_filepath = log_filepath

        # 所有插件构成的序列
        self._plugin_list:list[AbstractPlugin] = []

        # 构建全局数据存储区
        # 这个程序会自动管理钩子
        self._global_data_mgr = GlobalDataMgr()
        self._global_data_mgr.set_event_system(self)

        # 创建线程安全的事件队列
        self._event_queue:queue.Queue = queue.Queue()

        # 记录上个计时器的触发时刻
        self._last_timer_release = time.time()

        # 记录当前工作线程
        self._thread_now:Optional[threading.Thread] = None
        self.thread_start_time = 0

    # 关闭一个钩子
    def hook_deactivate(self, hook_name):
        self._global_data_mgr.hook_deactivate(hook_name)

    # 打开一个钩子
    def hook_activate(self, hook_name):
        self._global_data_mgr.hook_activate(hook_name)

    # 关闭一个插件
    def plugin_deactivate(self, plugin_name:str):
        if plugin_name in self.get_plugin_name_list():
            pos = -1
            for idx, plugin_item in enumerate(self._plugin_list):
                if plugin_item.identifier() == plugin_name:
                    pos = idx
                    break
            if pos != -1:
                self._plugin_list.pop(pos)

    # 打开一个插件
    def plugin_activate(self, plugin_name:str):
        for subclass_type in get_all_concrete_subclasses(AbstractPlugin):
            subclass_obj = subclass_type()
            assert isinstance(subclass_obj, AbstractPlugin)
            if subclass_obj.identifier() == plugin_name:
                self.add_plugin_item(subclass_obj)
                return
        raise ValueError(f"EventSystem.plugin_activate: {plugin_name} is not a plugin identifier.")

    def add_plugin_item(self, subclass_obj:AbstractPlugin):
        if subclass_obj.identifier() not in self.get_plugin_name_list():
            self._plugin_list.append(subclass_obj)
            self._plugin_list.sort(
                key=lambda plugin:(plugin.priority(), plugin.identifier()))

    @classmethod
    def _get_time(cls) -> str:
        return datetime.datetime.now().strftime(r"%Y-%m-%d_%H-%M-%S")


    # 向日志中记录插件异常
    # 包括异常时间以及出错插件
    def _log_plugin_error(self, plugin_name:str, msg:str):
        with self._global_data_mgr.rlock():

            # 向文件中追加一行报错信息
            with open(self._log_filepath, "a") as fp:
                fp.write(f"{EventSystem._get_time()}: {plugin_name}: {msg.strip()}\n")


    # 获取所有插件名称构成的列表
    def get_plugin_name_list(self) -> list[str]:
        return [plg.identifier() for plg in self._plugin_list]


    # 让某个事件在插件链中传递
    def _push_event(self, event:AbstractEvent):

        # 依次枚举所有插件，尝试处理事件
        for plugin in self._plugin_list:
            # pass_down 用于描述插件是否会将事件传递下去
            # 如果命令执行失败，则认为可以传递下去
            try:
                pass_down, event_list = plugin.process_event(self._global_data_mgr, event)

                # 对插件返回值进行类型检查
                if not isinstance(pass_down, bool):
                    raise TypeError("EventSystem._push_event: type of pass_down should be bool.")
                if not isinstance(event_list, list):
                    raise TypeError("EventSystem._push_event: type of event_list should be list.")
                for i in range(len(event_list)):
                    if not isinstance(event_list[i], AbstractEvent):
                        raise TypeError(f"EventSystem._push_event: type of event_list[{i}] should be AbstractEvent.")

            except:
                pass_down, event_list = True, [] # 命令执行失败时不拦截插件
                self._log_plugin_error(plugin.identifier(), traceback.format_exc())
            
            # 检查是否需要向事件队列里增加新的事件
            if len(event_list) > 0:
                for new_event_item in event_list:
                    self._event_queue.put(new_event_item)

            # 检查是否要继续传递命令
            if not pass_down:
                break


    # 在主循环启动之前，初始化必要的全局变量
    # 全局变量可以在任何插件内得到修改
    # EventSystem 会把自己伪装成插件，但是实际上他不是插件
    def _before_main_loop(self):

        # 设置系统运行状态
        # 如果这个值变成 False，系统不再运行
        self._global_data_mgr.put("EventSystem", "Running", True)

        # EventSystem.Timer 决定基础计时器的周期
        # 基础计时器每隔若干秒，就会向队列里加入一个 TimerEvent
        # 如果这个值小于零，那么系统将不会发送周期计时器中断
        self._global_data_mgr.put("EventSystem", "Timer", 3.0)

        # 如果没有读取到任何事件
        # 暂停多久再进行下一次读取
        self._global_data_mgr.put("EventSystem", "Sleep", 0.5)


    def _process_loop(self):

        # 一直执行，直到系统退出
        # 可以在插件中修改这个值用于退出程序
        while self._global_data_mgr.get("EventSystem", "Running") is True:
            
            # 事件队列不为空，则执行一次插件表
            # EventSystem.Sleep 是无事发生时，消息队列的睡眠时间
            try:

                # 获取当前事件
                # 如果超时，则会抛出 queue.Empty
                event_now = self._event_queue.get(block=True, timeout=(
                    self._global_data_mgr.get("EventSystem", "Sleep")))
                self._push_event(event_now)

            # 队列为空时正常的，不需要当作错误处理
            except queue.Empty:
                pass
            
            # 计时器超时
            # 发送一个计时器超时事件
            if self._global_data_mgr.get("EventSystem", "Timer") >= 0:
                if (time.time() - self._last_timer_release 
                        >= self._global_data_mgr.get("EventSystem", "Timer")):
                    self._push_event(TimerEvent(time.time() - self.thread_start_time))
                    self._last_timer_release = time.time() # 下次要过一会再响


    # 执行主循环
    def _mainloop(self):

        # 初始化全局变量
        self._before_main_loop()

        # 发送启动事件
        self._push_event(StartupEvent())

        # 之所以需要套两次
        # 是怕内层被键盘中断后无法处理
        while self._global_data_mgr.get("EventSystem", "Running") is True:

            try:
                self._process_loop() # 在这里一直循环
            except KeyboardInterrupt:
                self._event_queue.put(KeyboardInterruptEvent())
        
        # 发送退出事件
        self._push_event(ExitEvent())

    # 处理 Ctrl+C 事件
    def ctrl_c_signal_handler(self, signum, frame):
        self._event_queue.put(KeyboardInterruptEvent())

    # 在新线程中启动事件系统
    def run(self):
        
        # 中断退出事件插件
        # 插件激活后会自动加入自身到事件队列
        KeyboardInterruptExitPlugin().activate(self)

        # SystemStatusHook 启动系统运行状态钩子
        # 为系统提供一些运行状态监控信息（比如有哪些钩子与插件正在工作）
        # SystemStatusHook 和 EventDebuggerPlugin 有联动
        # 如果 SystemStatusHook 在工作则 EventDebuggerPlugin 会输出他的信息
        SystemStatusHook().activate(self)

        self._thread_now = threading.Thread(target=self._mainloop, args=())
        self.thread_start_time = time.time() # 记录线程启动时刻
        signal.signal(signal.SIGINT, self.ctrl_c_signal_handler)
        self._thread_now.start()


# 用于测试
# 点击奇数次 Ctrl+C 会将 EventSystem.Timer 设置为 1.0
# 点击偶数次 Ctrl+C 会将 EventSystem.Timer 设置为 2.0
# 点击超过二十次 Ctrl+C 会触发系统退出事件
class _KeybordInterruptToggleTimerPlugin(AbstractPlugin):
    def __init__(self) -> None:
        super().__init__()
        self.ctrl_c_strike_time = 0
    def identifier(self) -> str:
        return "_KeybordInterruptToggleTimerPlugin"
    def priority(self) -> float:
        return 10000
    def process_event(self, global_data_mgr:GlobalDataMgr, event:AbstractEvent) -> tuple[bool, list[AbstractEvent]]:
        if event.identifier() == "KeyboardInterruptEvent":
            self.ctrl_c_strike_time += 1
            if self.ctrl_c_strike_time >= 20:
                global_data_mgr.put(self.identifier(), "EventSystem.Timer", 3.0)
                global_data_mgr.put(self.identifier(), "EventSystem.Running", False) # 结束系统运行
            elif self.ctrl_c_strike_time % 2 == 1:
                global_data_mgr.put(self.identifier(), "EventSystem.Timer", 1.0)
            elif self.ctrl_c_strike_time % 2 == 0:
                global_data_mgr.put(self.identifier(), "EventSystem.Timer", 2.0)
        return True, []


# 用于测试，把所有传递出的数据都减半
# 对所有插件都有效
class _HalfFloatHook(AbstractGlobalDataHook):
    def identifier(self) -> str:
        return "_HalfFloatHook" 
    def priority(self) -> int:
        return 0
    def match_plugin(self, plugin_name:str) -> bool: # return True 对所有插件有效
        return True
    def get(self, plugin_user:str, key:str) -> Any:
        assert self.upstream_item is not None
        return self.upstream_item.get(plugin_user, key)
    def put(self, plugin_user:str, key:str, val:Any):
        assert self.upstream_item is not None
        if not isinstance(val, float):
            return self.upstream_item.put(plugin_user, key, val)
        else:
            return self.upstream_item.put(plugin_user, key, val / 2)


# 用于帮助其他插件获取系统状态所使用的钩子
# 能够为用户提供一些只读对象，这些对象是不可写的
# 但是这些对象可以获取系统信息
class SystemStatusHook(AbstractGlobalDataHook):
    def identifier(self) -> str:
        return "SystemStatusHook" 
    def priority(self) -> int:
        return -10000
    def match_plugin(self, plugin_name:str) -> bool: # return True 对所有插件有效 
        return True
    def get(self, plugin_user:str, key:str) -> Any:
        assert self.upstream_item is not None
        event_system = self.get_event_system()
        assert isinstance(event_system, EventSystem)

        if key == "SystemStatusHook.EventSystem.PluginActive":
            return self.upstream_item.get(plugin_user, "EventSystem.Running")

        # 描述当前这个 Hook 是否在工作
        if key.endswith(".HookActive") and key.startswith("SystemStatusHook."): 
            middle_name = key[len("SystemStatusHook."):-len(".HookActive")]
            return middle_name in event_system._global_data_mgr.get_hook_name_list()
        
        # 描述当前这个 Plugin 是否在工作
        elif key.endswith(".PluginActive") and key.startswith("SystemStatusHook."): 
            middle_name = key[len("SystemStatusHook."):-len(".PluginActive")]
            return middle_name in event_system._global_data_mgr.get_hook_name_list()
        
        # 获取当前正在工作的全部插件
        elif key == "SystemStatusHook.ActivePluginList": 
            return event_system.get_plugin_name_list()
        
        # 获取当前正在工作的全部钩子
        elif key == "SystemStatusHook.ActiveHookList": 
            return event_system._global_data_mgr.get_hook_name_list()
        
        # 未命中
        else:
            return self.upstream_item.get(plugin_user, key)
    def put(self, plugin_user:str, key:str, val:Any):
        assert self.upstream_item is not None
        event_system = self.get_event_system()
        assert isinstance(event_system, EventSystem)

        # 修改系统运行状态
        if key == "SystemStatusHook.EventSystem.PluginActive":
            return self.upstream_item.put(plugin_user, "EventSystem.Running", val)
        
        # 将某个钩子对应的变量值设置为 False
        # 可以停用这个钩子
        if key.endswith(".HookActive") and key.startswith("SystemStatusHook."): 
            middle_name = key[len("SystemStatusHook."):-len(".HookActive")]
            if val is False:
                event_system.hook_deactivate(middle_name)
            elif val is True:
                event_system.hook_activate(middle_name)
        
        # 将某个插件对应的变量值设置为 False
        # 可以停用这个插件
        elif key.endswith(".PluginActive") and key.startswith("SystemStatusHook."): 
            middle_name = key[len("SystemStatusHook."):-len(".PluginActive")]
            if val is False:
                event_system.plugin_deactivate(middle_name)
            elif val is True:
                event_system.plugin_activate(middle_name)
        
        # 以下两个变量均为只读
        if key == "SystemStatusHook.ActivePluginList":
            return None
        elif key == "SystemStatusHook.ActiveHookList":
            return None

        # 未命中
        else:
            return self.upstream_item.put(plugin_user, key, val)


if __name__ == "__main__":
    DIRNOW = os.path.dirname(os.path.abspath(__file__))

    # 创建事件系统
    es = EventSystem(os.path.join(DIRNOW, "log.txt"))

    # 启动事件系统
    es.run()

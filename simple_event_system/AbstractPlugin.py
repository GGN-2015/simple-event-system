import threading
from abc import ABC, abstractmethod


try:
    from .AbstractEvent import AbstractEvent # 抽象事件
    from .GlobalDataMgr import GlobalDataMgr
except:
    from AbstractEvent import AbstractEvent # 抽象事件
    from GlobalDataMgr import GlobalDataMgr


# 描述一个抽象的插件
# 所有插件都应该以这个插件为基类
class AbstractPlugin(ABC):

    def __init__(self) -> None:
        super().__init__()


    # 把当前插件对象加入插件队列
    def activate(self, event_system):

        # 插件名不能与系统基础冲突
        if self.identifier() == "EventSystem":
            raise ValueError("AbstractPlugin.activate: you can not activate a plugin called EventSystem.")
        event_system.plugin_activate(self.identifier())


    # 关闭当前插件
    # 从已经注册的插件列表中删除他
    def deactivate(self, event_system):
        event_system.plugin_deactivate(self.identifier())


    # 用来描述插件的名称
    # 不同插件的名字必须不同
    @abstractmethod
    def identifier(self) -> str:
        return "AbstractPlugin"


    # 在插件系统中的优先级
    # priority 越小，优先级越高
    @abstractmethod
    def priority(self) -> float:
        return 0


    # 处理事件，并执行相关操作
    # 返回值为 True 表示不对事件进行拦截
    # 返回值为 False 表示对事件进行拦截，以后的插件不能获得其相关信息
    # 插件可以修改全局数据信息
    # 返回值中 list[AbstractEvent] 是当前插件释放到事件序列中的新事件
    @abstractmethod
    def process_event(self, global_data_mgr:GlobalDataMgr, event:AbstractEvent) -> tuple[bool, list[AbstractEvent]]:
        return True, []
    

# 事件调试器插件
# 会把所有经过这个插件的事件输出出来
class EventDebuggerPlugin(AbstractPlugin):
    def identifier(self) -> str:
        return "EventDebuggerPlugin"
    def priority(self) -> float:
        return 0
    def process_event(self, global_data_mgr:GlobalDataMgr, event:AbstractEvent) -> tuple[bool, list[AbstractEvent]]:
        print("EventDebuggerPlugin:")
        print(f"    Event Now: {event.identifier()}: {event.message()}")
        if global_data_mgr.get(self.identifier(), "SystemStatusHook.SystemStatusHook.HookActive") is True:
            plugin_list = global_data_mgr.get(self.identifier(), "SystemStatusHook.ActivePluginList")
            print("    Plugin List:", plugin_list)
            hook_list = global_data_mgr.get(self.identifier(), "SystemStatusHook.ActiveHookList")
            print("    Hook List:", hook_list)
        return True, []


# 在遇到键盘中断时退出系统
# 将 EventSystem.Running 设置为 False 可以停止系统
class KeyboardInterruptExitPlugin(AbstractPlugin):
    def identifier(self) -> str:
        return "KeyboardInterruptExitPlugin"
    def priority(self) -> float:
        return 10000
    def process_event(self, global_data_mgr:GlobalDataMgr, event:AbstractEvent) -> tuple[bool, list[AbstractEvent]]:
        if event.identifier() == "KeyboardInterruptEvent":
            global_data_mgr.put(self.identifier(), "EventSystem.Running", False)
        return True, []

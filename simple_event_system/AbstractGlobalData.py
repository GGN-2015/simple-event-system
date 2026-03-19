from typing import Any, Optional
from abc import ABC, abstractmethod
import threading


# 抽象的全局数据对象
# 所有的插件都会将数据存入 AbstractGlobalData 从而控制系统
class AbstractGlobalData(ABC):
    
    # 获取事件系统对象
    @abstractmethod
    def get_event_system(self) -> Any:
        return None

    @abstractmethod
    def get(self, plugin_user:str, key:str) -> Any:
        return None
    
    @abstractmethod
    def put(self, plugin_user:str, key:str, val:Any):
        return None


# 抽象的全局数据钩子
# 能够对全局数据操作进行包装
# 可以拦截一些操作
class AbstractGlobalDataHook(AbstractGlobalData):

    def __init__(self) -> None:
        super().__init__()
        self.upstream_item:Optional[AbstractGlobalData] = None


    # 默认获得事件系统的方法是使用上游事件系统
    def get_event_system(self) -> Any:
        if self.upstream_item is not None:
            return self.upstream_item.get_event_system()
        else:
            return None


    # 启动一个数据钩子
    # 如果自己不在数据钩子序列中，则将自己加进去
    def activate(self, event_system):
        event_system.hook_activate(self.identifier())
    

    # 删除一个指定的数据钩子
    # 把自己从钩子序列中删除
    def deactivate(self, event_system):
        event_system.hook_deactivate(self.identifier())


    # 设置上游对象
    # 由于一个装饰器可能被很多对象公用，因此 upstream 可能随时被修改
    def upstream(self, upstream_item: AbstractGlobalData):
        self.upstream_item = upstream_item


    # 用于表明数据钩子的身份
    # 将用于区分两个数据钩子是否相同
    @abstractmethod
    def identifier(self) -> str:
        return "AbstractGlobalDataHook"


    # 设置装饰器优先级
    # 编号越小优先级越高    
    @abstractmethod
    def priority(self) -> int:
        return 0
    

    # 给定插件名称
    # 返回值将决定该装饰器是否会用于这个插件的 IO
    @abstractmethod
    def match_plugin(self, plugin_name:str) -> bool:
        return False
    

    # 执行获取操作
    # 使用前应该先设置上游
    @abstractmethod
    def get(self, plugin_user:str, key:str) -> Any:
        if self.upstream_item is None:
            raise ValueError()
        return self.upstream_item.get(plugin_user, key)


    # 执行写操作
    # 使用前应该先设置上游
    @abstractmethod
    def put(self, plugin_user:str, key:str, val:Any):
        if self.upstream_item is None:
            raise ValueError()
        return self.upstream_item.put(plugin_user, key, val)


# 用于描述系统运行时的全局数据
# 全局数据所有插件都可以修改并使用，相当于一个黑板系统
class ConcreteGlobalData(AbstractGlobalData):

    # 初始化全局信息
    def __init__(self) -> None:
        self.global_dict:dict[str, Any] = dict()
        self.thread_rlock = threading.RLock()
        self.event_system = None # 记录一个指向事件系统的反向指针


    # 设置事件系统对象
    def set_event_system(self, new_event_system:Any):
        self.event_system = new_event_system


    # 获取当前事件系统对象
    def get_event_system(self) -> Any:
        if self.event_system is None:
            raise ValueError("GlobalDataMgr.get_event_system: self.event_system has not been set yet.")
        return self.event_system


    # 返回一个全局信息
    # 在命名习惯上，应该将变量名命名为 <模块名>.<变量名>
    # 从而用来表明这个变量主要是谁在读取
    def get(self, plugin_user:str, key:str) -> Any:
        content = self.global_dict.get(key)
        return content


    # 设置一个全局信息
    # 设置全局信息的时候必须加锁
    def put(self, plugin_user:str, key:str, val:Any):
        with self.thread_rlock:

            # 检查类型一致
            if (self.global_dict.get(key) is not None) and type(self.global_dict[key]) != type(val):
                    raise TypeError(f"ConcreteGlobalData.put: type of {key} should be {type(self.global_dict[key])}, not {type(val)}.")
            
            # 类型完全一致才可以设置值
            self.global_dict[key] = val



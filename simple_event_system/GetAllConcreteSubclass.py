import inspect
from abc import ABC, abstractmethod

# 第一步：定义一个抽象基类（用于测试）
class BaseAbstractClass(ABC):
    @abstractmethod
    def do_something(self):
        pass

# 定义抽象子类（仍包含抽象方法）
class AbstractSubClass(BaseAbstractClass):
    @abstractmethod
    def do_another_thing(self):
        pass

# 定义非抽象子类（实现所有抽象方法）
class ConcreteSubClass1(BaseAbstractClass):
    def do_something(self):
        print("ConcreteSubClass1 实现了抽象方法")

# 定义多层继承的非抽象子类
class ConcreteSubClass2(ConcreteSubClass1):
    def do_something(self):
        print("ConcreteSubClass2 重写了抽象方法")

# 第二步：核心函数：获取所有非抽象子类
def get_all_concrete_subclasses(base_class):
    concrete_subclasses = []
    
    # 递归遍历所有子类
    def _recursive_get_subclasses(cls):
        # 获取当前类的直接子类
        subclasses = cls.__subclasses__()
        for subclass in subclasses:
            # 判断是否为非抽象类
            if not inspect.isabstract(subclass):
                concrete_subclasses.append(subclass)
            # 递归处理子类的子类
            _recursive_get_subclasses(subclass)
    
    _recursive_get_subclasses(base_class)
    return concrete_subclasses

# 第三步：测试使用
if __name__ == "__main__":
    # 获取 BaseAbstractClass 的所有非抽象子类
    result = get_all_concrete_subclasses(BaseAbstractClass)
    
    # 打印结果
    print("所有非抽象子类：")
    for cls in result:
        print(f"- {cls.__name__}")
    
    # 输出：
    # 所有非抽象子类：
    # - ConcreteSubClass1
    # - ConcreteSubClass2
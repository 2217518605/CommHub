"""
基础序列化器类
"""
from rest_framework import serializers
from rest_framework.fields import empty
from django.db import models


class CacheAttribute:
    """缓存属性装饰器"""
    ''' 通过缓存避免重复计算 '''

    def __init__(self, func):
        self.func = func
        self.name = func.__name__

    def __get__(self, instance, owner):
        if instance is None:
            return self
        cache_name = f'_cache_{self.name}'
        if not hasattr(instance, cache_name):
            setattr(instance, cache_name, self.func(instance))
        return getattr(instance, cache_name)


class WritableSerializerReturnDict(dict):
    """可写的序列化器返回字典，支持字典访问和属性访问"""

    def __init__(self, *args, serializer=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.serializer = serializer

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{key}'")

    def __setattr__(self, key, value):
        if key == 'serializer':
            super().__setattr__(key, value)
        else:
            self[key] = value


class ParamsSerializer(serializers.Serializer):
    """参数序列化器基类"""
    _init_complete = False
    __data = None

    def __init__(self, data=empty, instance=None, valid_exception=True, *argv, **kwargs):
        if isinstance(data, models.Model):
            instance = data
            data = empty
        self.valid_exception = valid_exception
        super().__init__(instance=instance, data=data, *argv, **kwargs)
        self._init_complete = True

    @property
    def params_data(self):
        """返回验证过后的数据"""
        self.validation()
        return self.o

    def validation(self):
        """执行数据验证"""
        self.is_valid(raise_exception=True)
        self.__data = self.validated_data
        return self.o

    @property
    def o(self):
        """返回包装后的数据对象"""
        '''缓存序列化器的 data 结果，避免重复执行数据验证和转换 '''
        if self.__data is not None:
            return WritableSerializerReturnDict(self.__data, serializer=self)
        return WritableSerializerReturnDict(serializer=self)

    @CacheAttribute
    def data(self):
        """重写 data 属性"""
        if hasattr(self, 'initial_data'):
            self.is_valid(self.valid_exception)
        ret_data = self.__data or super().data
        return WritableSerializerReturnDict(ret_data, serializer=self)


DataSerializer = ParamsSerializer


class EmptySerializer(serializers.Serializer):
    """空序列化器，用于不需要响应体的接口文档定义"""
    pass


"""
通用装饰器
"""
from functools import wraps

from drf_yasg.utils import swagger_auto_schema
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken,TokenBackendError


# API 文档装饰器
api_doc = swagger_auto_schema


def api_post(func):
    """标记为 POST 方法的 API 装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    wrapper.bind_to_methods = ['post']
    wrapper.detail = False
    return wrapper


def api_get(func):
    """标记为 GET 方法的 API 装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    wrapper.bind_to_methods = ['get']
    wrapper.detail = False
    return wrapper


def api_put(func):
    """标记为 PUT 方法的 API 装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    wrapper.bind_to_methods = ['put']
    wrapper.detail = False
    return wrapper


def api_delete(func):
    """标记为 DELETE 方法的 API 装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    wrapper.bind_to_methods = ['delete']
    wrapper.detail = False
    return wrapper

# 登录验证器
def require_login(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if hasattr(args[0], 'request'):
            view_self = args[0]  # 类
            request = view_self.request
        else:
            request = args[0] # 方法

        token_header = request.META.get('HTTP_AUTHORIZATION')
        if not token_header or token_header.startswith('Bearer') is False:
            return Response({
                    'code': 401,
                    'msg': '请先登录',
                    'data': None
                })

        token_ = token_header.split(' ')[1]  # 去除 Bearer
        jwt_auth = JWTAuthentication()  # 验证令牌有效与否
        try:
            validate_token = jwt_auth.get_validated_token(token_) # 校验签名和过期时间
            user = jwt_auth.get_user(validate_token) # 获取令牌对应的用户
            request.user = user # 将用户绑定到 request，供后续使用
        except InvalidToken:
            return Response({
                'code': 401,
                'msg': '令牌无效',
                'data': None
            })
        except TokenBackendError as s:
            return Response({
                'code': 401,
                'msg': f'令牌错误，认证失败，错误原因：{str(s)}',
                'data': None
            })
        return func(*args, **kwargs)
    return wrapper




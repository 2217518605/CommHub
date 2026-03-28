import logging

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import exception_handler
from rest_framework import status
from rest_framework.exceptions import NotFound
from django.shortcuts import _get_queryset

logger = logging.getLogger(__name__)


class CommonPageNumberPagination(PageNumberPagination):
    """
    通用分页器
    """
    page_size = 10  # 每页显示的条数
    max_page_size = 100  # 最大每页显示的条数
    page_query_param = "page"  # 页码参数名
    page_size_query_param = "page_size"  # 每页显示的条数参数名

    def get_paginated_response(self, data):
        """ 返回分页数据信息 """
        return Response({
            'status': status.HTTP_200_OK,
            'message': '成功',
            'data': {
                'total': self.page.paginator.count,
                'page_size': self.get_page_size(self.request),
                'page_num': self.page.number,
                'total_page': self.page.paginator.num_pages,
                'list': data  # 分页后的数据
            }
        })


def get_client_ip(request):
    """
    获取客户端真实 IP
    """
    x_forwarded_for = request.META.get(
        'HTTP_X_FORWARDED_FOR')  # X-Forwarded-For: <client>, <proxy1>, <proxy2>, <proxy3>
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', 'unknown')
    return ip


def common_exception_handler(exc, context):
    """
    全局的 DRF 异常处理器
    """

    response = exception_handler(exc, context)

    # 获取请求上下文
    request = context.get('request')
    view = context.get('view')

    # 基础日志信息
    log_extra = {
        'user_id': getattr(request.user, 'id', None) if request else None,
        'username': getattr(request.user, 'username', 'anonymous') if request else 'anonymous',
        'ip': get_client_ip(request) if request else 'unknown',
        'method': request.method if request else 'UNKNOWN',
        'path': request.get_full_path() if request else 'UNKNOWN',
        'view_class': view.__class__.__name__ if view else 'UnknownView'
    }

    if response is None:
        logger.error(
            f"【500 服务器内部错误】{exc.__class__.__name__}: {str(exc)}",
            exc_info=True,
            extra=log_extra
        )

        return Response(
            {"detail": "服务器内部错误，请稍后再试"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    if response.status_code >= 400:
        if response.status_code == 400:
            logger.warning(f"【{response.status_code} 客户端参数格式错误】{response.data}", extra=log_extra)
        elif response.status_code == 401:
            logger.warning(f"【{response.status_code} 客户端未授权】{response.data}", extra=log_extra)
        elif response.status_code == 403:
            logger.warning(f"【{response.status_code} 客户端无权限】{response.data}", extra=log_extra)
        elif response.status_code == 404:
            logger.warning(f"【{response.status_code} 客户端资源不存在】{response.data}", extra=log_extra)
        elif response.status_code == 405:
            logger.warning(f"【{response.status_code} 客户端请求方法不支持】{response.data}", extra=log_extra)
        elif response.status_code == 406:
            logger.warning(f"【{response.status_code} 客户端请求格式不支持】{response.data}", extra=log_extra)

    return response


def common_response(status: int = status.HTTP_200_OK, message: str = "操作成功", data: dict = None):
    return Response({
        "status": status,
        "message": message,
        "data": data
    })


def get_object_or_404(klass, *args, msg=None, **kwargs):
    """ 改写Django原生的报错机制，更加人类化 """

    queryset = _get_queryset(klass)

    if not hasattr(queryset, "get"):
        klass__name = klass.__name__ if isinstance(klass, type) else klass.__class__.__name__
        raise ValueError(f"First argument must be a Model, Manager, or QuerySet, not '{klass__name}'.")

    try:
        return queryset.get(*args, **kwargs)
    except queryset.model.DoesNotExist:
        if msg:
            error_message = msg
        else:
            model_name = queryset.model._meta.verbose_name
            lookup = ", ".join(f"{k}={v}" for k, v in kwargs.items())
            error_message = f"无法找到 {model_name} (条件: {lookup})"

        logger.warning(f"Data not found: {error_message}")

        raise NotFound(error_message)
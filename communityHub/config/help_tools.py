import logging

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from ipware import get_client_ip


logger = logging.getLogger(__name__)

class CommonPageNumberPagination(PageNumberPagination):
    """
    通用分页器
    """
    page_size = 10 #  每页显示的条数
    max_page_size = 100 # 最大每页显示的条数
    page_query_param = "page" # 页码参数名
    page_size_query_param = "page_size" # 每页显示的条数参数名

    def get_paginated_response(self, data):
        """ 返回分页数据信息 """
        return Response({
            'code': 200,
            'msg': '成功',
            'data': {
                'total': self.page.paginator.count,
                'page_size': self.get_page_size(self.request),
                'page_num': self.page.number,
                'total_page': self.page.paginator.num_pages,
                'list': data  # 分页后的数据
            }
        })

def get_current_ip(request):
    """ 获取当前请求的 ip 地址 """
    client_ip, is_routable = get_client_ip(request)
    if client_ip is None:
        logger.warning("无法从请求中获取任何客户端 IP 地址")
        raise ValueError("无法获取 IP")

    if is_routable:
        # 公网 IP
        return client_ip
    else:
        # 私有 IP
        logger.debug(f"客户端使用私有 IP: {client_ip}")
        return client_ip
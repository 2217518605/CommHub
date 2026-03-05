"""
增强的请求类
"""
from django.http import HttpRequest

class EnhanceRequest(HttpRequest):
    """
    增强的 Request 类
    主要用于代码提示和 IDE 支持
    """
    rid: str
    logs: dict
    ip: str
    org_session_id: str
    app_org_session_id: str
    data: dict


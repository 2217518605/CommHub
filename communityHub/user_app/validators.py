import logging

from django.core.cache import cache
from django.conf import settings
from rest_framework import status
from rest_framework.response import Response

from config.help_tools import get_client_ip

logger = logging.getLogger(__name__)


def get_count(cache_key):
    """ 获取次数 """

    return cache.get(cache_key, 0)


def increment_count(cache_key, timeout=settings.LOCK_TIME):
    """ 增加计数 """

    current_count = get_count(cache_key)
    cache.set(cache_key, current_count + 1, timeout=timeout)
    return current_count + 1


def check_ip_lock(request):
    """ 检查 IP 是否被锁定 """

    client_ip = get_client_ip(request)

    # 登录失败计数
    ip_fail_key = f"{settings.CACHE_KEY_IP_FAIL}{client_ip}"
    ip_fail_count = get_count(ip_fail_key)

    # 注册次数计数
    register_ip_key = f"{settings.CACHE_KEY_REGISTER}{client_ip}"
    register_count = get_count(register_ip_key)

    if ip_fail_count > settings.IP_MAX_FAILS:
        logger.warning(f'用户 IP: {client_ip} 登录尝试过于频繁，请稍后 {settings.LOCK_TIME // 60} 分钟后再试')
        return Response({
            'status': status.HTTP_429_TOO_MANY_REQUESTS,
            'message': f'IP: {client_ip} 登录尝试过于频繁，请稍后 {settings.LOCK_TIME // 60} 分钟再试',
            'data': None
        })

    if register_count > settings.IP_MAX_FAILS:
        logger.info(f'用户 IP: {client_ip} 注册用户尝试过于频繁，请稍后 {settings.LOCK_TIME // 60} 分钟后再试')
        return Response({
            'status': status.HTTP_429_TOO_MANY_REQUESTS,
            'message': f'IP: {client_ip} 注册用户尝试过于频繁，请稍后 {settings.LOCK_TIME // 60} 分钟再试',
            'data': None
        })
    return None


def check_account_lock(account):
    """  检查账号是否被锁定 """

    account_fail_key = f"fail_account_{account}"
    account_fail_count = get_count(account_fail_key)

    if account_fail_count > settings.ACCOUNT_MAX_FAILS:
        logger.warning(f'用户账号：{account} 登录尝试过于频繁，请稍后 {settings.LOCK_TIME // 60} 分钟后再试')
        return Response({
            'status': status.HTTP_400_BAD_REQUEST,
            'message': f'账号：{account} 登录尝试过于频繁，请稍后 {settings.LOCK_TIME // 60} 分钟再试',
            'data': None
        })
    return None


def record_login_failure(request, account):
    """ 记录 IP 登录失败 """

    client_ip = get_client_ip(request)
    ip_fail_key = f"{settings.CACHE_KEY_IP_FAIL}{client_ip}"
    account_fail_key = f"fail_account_{account}"

    increment_count(ip_fail_key)
    increment_count(account_fail_key)

    logger.warning(f"用户账号 {account} 在 IP: {client_ip} 登录失败")


def record_ip_register(request):
    """ 记录 IP 注册频率 """

    client_ip = get_client_ip(request)
    register_ip_key = f"{settings.CACHE_KEY_REGISTER}{client_ip}"

    increment_count(register_ip_key)

    logger.warning(f"IP: {client_ip} 尝试注册用户了")


def clear_login_success_cache(account):
    """ 登录成功时清除失败缓存 """

    account_fail_key = f"fail_account_{account}"
    cache.delete(account_fail_key)

    logger.info(f"用户 {account} 登录成功，已清除失败缓存")

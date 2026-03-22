from rest_framework.permissions import BasePermission, AllowAny


class IsPublic(BasePermission):
    """ 公开的权限（未登录也可以） """

    def has_permission(self, request, view):
        return True

class IsCommonUser(BasePermission):
    """ 普通用户权限(登录的都可以) """

    def has_permission(self, request, view):
        return request.user.is_authenticated

class IsAdmin(BasePermission):
    """ 管理员权限 """

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.user_type == "admin"


class IsSuperAdmin(BasePermission):
    """ 超级管理员权限 """

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_staff == True

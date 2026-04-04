"""
URL configuration for communityHub project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path,include
from django.conf.urls.static import static
from django.conf import settings
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

schema_view = get_schema_view(
    openapi.Info(
        title="\"邻里汇\"平台 API 文档",
        default_version='v1',
        description=" \"邻里汇\" 平台，集成社区管理、购物、评论、组织等等模块于一起的一个平台。 ",
        terms_of_service="",
        contact=openapi.Contact(email="2217518605@qq.com"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)

urlpatterns = [
                  path("admin/", admin.site.urls),
                  path("swagger/",schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'), # Swagger 文档
                  path("organization/",include("organization_app.urls")),
                  path("user/",include("user_app.urls")),
                  path("goods/",include("goods_app.urls")),
                  path("order/",include("order_app.urls")),
                  path("discount/",include("discount_app.urls")),

              ] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

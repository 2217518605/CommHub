from django.urls import path

from .views import GoodsRetrieveViewSet

urlpatterns = [
    path("goods_retrieve/<int:pk>/",
         GoodsRetrieveViewSet.as_view({"get": "retrieve", "delete": "destroy", "put": "update"}),
         name="goods_retrieve"),
    path("goods_create/", GoodsRetrieveViewSet.as_view({'post': 'create'}), name="goods_create")
]

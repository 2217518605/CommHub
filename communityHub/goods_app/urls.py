from django.urls import path

from .views import GoodsRetrieveViewSet, GoodsCommentsRetrieveViewSet,GoodsCommentsListViewSet

urlpatterns = [
    path("goods_retrieve/<int:pk>/",
         GoodsRetrieveViewSet.as_view({"get": "retrieve", "delete": "destroy", "put": "update"}),
         name="goods_retrieve"),
    path("goods_create/", GoodsRetrieveViewSet.as_view({'post': 'create'}), name="goods_create"),

    path("goods_comments_create/", GoodsCommentsRetrieveViewSet.as_view({"post": "create"}),
         name="goods_comments_retrieve"),
    path("goods_comments_retrieve/<int:pk>/", GoodsCommentsRetrieveViewSet.as_view({"delete": "destroy"}),
         name="goods_comments_retrieve"),
    path("goods_comments_list/", GoodsCommentsListViewSet.as_view({"post": "list"}),)
]

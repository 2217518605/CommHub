from django.urls import path

from .views import CouponRetrieveViewSet

urlpatterns = [
    path("user_coupon/", CouponRetrieveViewSet.as_view({"post": "create", "put": "update"}), name="user_coupon")
]

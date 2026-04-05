from django.urls import path

from .views import CouponRetrieveViewSet, UserCouponViewSet

urlpatterns = [
    path("coupon_template/", CouponRetrieveViewSet.as_view({"post": "create", "put": "update"}), name="user_coupon"),
    path("user_coupon/", UserCouponViewSet.as_view({"post": "create"}), name="user_coupon")
]

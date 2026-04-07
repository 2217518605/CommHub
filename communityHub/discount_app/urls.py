from django.urls import path

from .views import CouponRetrieveViewSet, UserCouponViewSet

urlpatterns = [
    path("coupon_template/", CouponRetrieveViewSet.as_view({"post": "create"}), name="user_coupon"),
    path("coupon_template/<int:pk>/", CouponRetrieveViewSet.as_view({"put": "update"}), name="user_coupon"),
    path("user_coupon/", UserCouponViewSet.as_view({"post": "create"}), name="user_coupon")
]

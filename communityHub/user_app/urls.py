from django.urls import path

from .views import UserRetrieveView, UserLoginView

urlpatterns = [
    path("user_create/", UserRetrieveView.as_view({'post': 'create'}), name="user_create"),
    path("user_retrieve/<int:pk>/", UserRetrieveView.as_view({"get": "retrieve", 'put': 'update', "delete": "destroy"}),
         name="user_retrieve"),
    path("user_login/", UserLoginView.as_view({'post': 'user_login'}), name="user_login"),
    path("user_logout/", UserLoginView.as_view({'post': 'user_login_out'}), name="user_logout"),
]

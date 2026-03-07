from django.urls import path

from organization_app.views import OrganizationRetrieveView, OrganizationListView

urlpatterns = [
    path("organization_create/", OrganizationRetrieveView.as_view({"post": "create"}), name="organization_get"),
    path("organization_retrieve/<int:pk>/",
         OrganizationRetrieveView.as_view({"get": "retrieve", "put": "update", "delete": "destroy"}),
         name="organization_create"),
    path("organization_list/", OrganizationListView.as_view({"get": "list", "post": "list_export"}),
         name="organization_list"),
    path("organization_list_export/<str:file_name>/",
         OrganizationListView.as_view({"post": "list_download"}),
         name="organization_list_export"),

]

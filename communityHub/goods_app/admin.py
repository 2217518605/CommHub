from django.contrib import admin

from .models import GoodsImage

@admin.register(GoodsImage)
class GoodsImageAdmin(admin.ModelAdmin):
    list_display = ["id", "goods", "sort_order", "create_time"]
    search_fields = ["goods__name"]

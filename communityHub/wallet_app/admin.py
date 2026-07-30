from django.contrib import admin
from wallet_app.models import Wallet, RechargeOrder, BalanceLog


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'display_balance', 'create_time', 'update_time']
    list_filter = ['create_time']
    search_fields = ['user__username', 'user__account']
    readonly_fields = ['create_time', 'update_time']

    def display_balance(self, obj):
        return f"¥{obj.user.balance}"
    display_balance.short_description = '账户余额'


@admin.register(RechargeOrder)
class RechargeOrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'recharge_number', 'amount', 'status', 'pay_time', 'create_time']
    list_filter = ['status', 'create_time']
    search_fields = ['user__username', 'recharge_number']
    readonly_fields = ['recharge_number', 'create_time', 'update_time']
    ordering = ['-create_time']


@admin.register(BalanceLog)
class BalanceLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'change_amount', 'balance_before', 'balance_after', 'source_type', 'source_id', 'create_time']
    list_filter = ['source_type', 'create_time']
    search_fields = ['user__username', 'remark']
    readonly_fields = ['create_time', 'update_time']
    ordering = ['-create_time']

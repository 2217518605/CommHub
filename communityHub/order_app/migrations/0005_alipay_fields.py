from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("order_app", "0004_order_user_coupon"),
    ]

    operations = [
        migrations.AlterField(
            model_name="order",
            name="transaction_id",
            field=models.CharField(blank=True, db_index=True, max_length=64, null=True, verbose_name="第三方流水号"),
        ),
    ]

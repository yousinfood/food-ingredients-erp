from django.db import models


class DeliveryTrip(models.Model):
    class Status(models.TextChoices):
        PREPARING = "preparing", "準備中"
        DEPARTED = "departed", "已出車"
        COMPLETED = "completed", "已完成"
        CANCELLED = "cancelled", "已取消"

    trip_date = models.DateField("出車日期")
    trip_number = models.PositiveIntegerField("趟次")
    trip_code = models.CharField("出車代碼", max_length=30, unique=True)
    status = models.CharField(
        "狀態",
        max_length=20,
        choices=Status.choices,
        default=Status.PREPARING,
    )
    note = models.TextField("備註", blank=True)
    created_at = models.DateTimeField("建立時間", auto_now_add=True)
    started_at = models.DateTimeField("出車時間", null=True, blank=True)
    completed_at = models.DateTimeField("完成時間", null=True, blank=True)

    class Meta:
        verbose_name = "出車趟次"
        verbose_name_plural = "出車趟次"
        ordering = ["-trip_date", "-trip_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["trip_date", "trip_number"],
                name="deliveries_trip_date_number_uniq",
            ),
        ]

    def __str__(self):
        return self.trip_code


class DeliveryTripOrder(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "待配送"
        DELIVERED = "delivered", "已送達"
        FAILED = "failed", "未送達"

    delivery_trip = models.ForeignKey(
        DeliveryTrip,
        on_delete=models.CASCADE,
        related_name="trip_orders",
        verbose_name="出車趟次",
    )
    sales_order = models.OneToOneField(
        "sales.SalesOrder",
        on_delete=models.PROTECT,
        related_name="delivery_trip_order",
        verbose_name="銷售訂單",
    )
    sequence = models.PositiveIntegerField("配送順序")
    status = models.CharField(
        "狀態",
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_at = models.DateTimeField("建立時間", auto_now_add=True)

    class Meta:
        verbose_name = "出車訂單"
        verbose_name_plural = "出車訂單"
        ordering = ["sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=["delivery_trip", "sequence"],
                name="deliveries_trip_sequence_uniq",
            ),
        ]

    def __str__(self):
        return f"{self.delivery_trip.trip_code} · {self.sales_order.order_no}"

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


class Customer(models.Model):
    code = models.CharField("客戶代碼", max_length=20, unique=True)
    name = models.CharField("客戶名稱", max_length=200)
    region = models.CharField("區域", max_length=100, blank=True)
    contact_person = models.CharField("聯絡人", max_length=100, blank=True)
    phone = models.CharField("電話", max_length=30, blank=True)
    phone_2 = models.CharField("電話 2", max_length=30, blank=True)
    phone_3 = models.CharField("電話 3", max_length=30, blank=True)
    email = models.EmailField("電子郵件", blank=True)
    address = models.CharField("配送地址", max_length=300, blank=True)
    invoice_address = models.CharField("發票地址", max_length=300, blank=True)
    map_location = models.CharField("地圖", max_length=100, blank=True)
    line_id = models.CharField("Line", max_length=100, blank=True)
    payment_method = models.CharField("付款方式", max_length=100, blank=True)
    delivery_day = models.CharField("固定配送日", max_length=100, blank=True)
    delivery_sequence = models.IntegerField("配送順序", null=True, blank=True)
    credit_limit = models.DecimalField("信用額度", max_digits=14, decimal_places=2, null=True, blank=True)
    last_transaction_date = models.DateField("最後交易日", null=True, blank=True)
    tax_id = models.CharField("統一編號", max_length=20, blank=True)
    is_active = models.BooleanField("啟用", default=True)
    notes = models.TextField("備註", blank=True)
    voice_aliases = models.CharField(
        "語音別名",
        max_length=500,
        blank=True,
        help_text="平常稱呼與台語音近字，逗號分隔。例：華都, 花都, 華豆",
    )
    created_at = models.DateTimeField("建立時間", auto_now_add=True)

    class Meta:
        verbose_name = "客戶"
        verbose_name_plural = "客戶"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class SalesOrder(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "草稿"
        CREATED = "created", "已建立"
        CONFIRMED = "confirmed", "已確認"
        SHIPPED = "shipped", "已出貨"
        COMPLETED = "completed", "已完成"
        CANCELLED = "cancelled", "已作廢"

    ACTIVE_STATUSES = (
        Status.DRAFT,
        Status.CREATED,
        Status.CONFIRMED,
        Status.SHIPPED,
        Status.COMPLETED,
    )

    order_no = models.CharField("銷售單號", max_length=30, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="sales_orders", verbose_name="客戶")
    status = models.CharField("狀態", max_length=20, choices=Status.choices, default=Status.DRAFT)
    order_date = models.DateField("訂單日期")
    delivery_date = models.DateField("交貨日期", null=True, blank=True)
    shipping_address = models.CharField("送貨地址", max_length=300, blank=True)
    notes = models.TextField("備註", blank=True)
    created_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_orders_created",
        verbose_name="建立人",
    )
    cancelled_at = models.DateTimeField("作廢時間", null=True, blank=True)
    cancelled_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_orders_cancelled",
        verbose_name="作廢人",
    )
    created_at = models.DateTimeField("建立時間", auto_now_add=True)
    updated_at = models.DateTimeField("更新時間", auto_now=True)

    class Meta:
        verbose_name = "銷售訂單"
        verbose_name_plural = "銷售訂單"
        ordering = ["-order_date", "-created_at"]

    def __str__(self):
        return self.order_no

    @property
    def total_amount(self):
        return sum(item.line_total for item in self.items.all())

    @property
    def is_voided(self):
        return self.status == self.Status.CANCELLED

    @property
    def is_editable(self):
        return not self.is_voided

    @property
    def can_void(self):
        return self.status in (
            self.Status.DRAFT,
            self.Status.CREATED,
            self.Status.CONFIRMED,
        )


class SalesOrderItem(models.Model):
    sales_order = models.ForeignKey(
        SalesOrder, on_delete=models.CASCADE, related_name="items", verbose_name="銷售訂單"
    )
    product = models.ForeignKey(
        "inventory.Product", on_delete=models.PROTECT, related_name="so_items", verbose_name="原料"
    )
    quantity = models.DecimalField(
        "數量", max_digits=12, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))]
    )
    unit_price = models.DecimalField(
        "單價", max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0"))]
    )
    shipped_qty = models.DecimalField("已出貨數量", max_digits=12, decimal_places=3, default=Decimal("0"))

    class Meta:
        verbose_name = "銷售明細"
        verbose_name_plural = "銷售明細"

    def __str__(self):
        return f"{self.sales_order.order_no} - {self.product.sku}"

    @property
    def line_total(self):
        return self.quantity * self.unit_price

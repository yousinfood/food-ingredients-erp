from decimal import Decimal
from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction

from apps.inventory.pricing_validators import NON_NEGATIVE_PRICE_VALIDATORS


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


class CustomerSearchRevision(models.Model):
    """Monotonic version for live search refresh (SSE / Supabase Realtime hook)."""

    version = models.PositiveBigIntegerField("版本", default=0)

    class Meta:
        verbose_name = "客戶搜尋版本"
        verbose_name_plural = "客戶搜尋版本"

    def __str__(self):
        return f"v{self.version}"


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
    sale_price_snapshot = models.DecimalField(
        "成交售價快照",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        help_text="訂單成立當下由後端寫入，不受日後售價調整影響",
    )
    price_source = models.CharField(
        "售價來源",
        max_length=20,
        blank=True,
        default="",
        help_text="customer=客戶專屬售價，standard=標準售價",
    )
    price_version = models.PositiveIntegerField(
        "售價版本",
        null=True,
        blank=True,
        help_text="CustomerProductPrice 主鍵（客戶售價時）",
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


class CustomerProductPrice(models.Model):
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="product_prices", verbose_name="客戶"
    )
    product = models.ForeignKey(
        "inventory.Product", on_delete=models.PROTECT, related_name="customer_prices", verbose_name="產品"
    )
    price = models.DecimalField("售價", max_digits=12, decimal_places=2, validators=NON_NEGATIVE_PRICE_VALIDATORS)
    effective_from = models.DateField("生效日")
    effective_to = models.DateField("失效日", null=True, blank=True)
    is_active = models.BooleanField("啟用", default=True)
    note = models.TextField("備註", blank=True)
    created_at = models.DateTimeField("建立時間", auto_now_add=True)
    updated_at = models.DateTimeField("更新時間", auto_now=True)

    class Meta:
        verbose_name = "客戶專屬售價"
        verbose_name_plural = "客戶專屬售價"
        ordering = ["-effective_from", "-pk"]
        indexes = [
            models.Index(
                fields=["customer", "product", "is_active", "effective_from"],
                name="sales_custo_custome_6a8b0d_idx",
            ),
        ]

    def __str__(self):
        return f"{self.customer.code} · {self.product.sku} = {self.price}"

    _IMMUTABLE_FIELDS = ("customer_id", "product_id", "price", "effective_from")

    def clean(self):
        super().clean()
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValidationError({"effective_to": "失效日不得早於生效日"})

        if self.is_active:
            if not self.customer.is_active:
                raise ValidationError("停用客戶不可建立有效售價")
            if not self.product.is_active:
                raise ValidationError("停用產品不可建立有效售價")
            self._validate_no_active_overlap()

    def _validate_no_active_overlap(self):
        others = CustomerProductPrice.objects.filter(
            customer=self.customer,
            product=self.product,
            is_active=True,
        )
        if self.pk:
            others = others.exclude(pk=self.pk)

        for other in others:
            if other.effective_from == self.effective_from:
                raise ValidationError("不可有兩筆同日生效的有效售價")
            if self._periods_overlap(
                self.effective_from,
                self.effective_to,
                other.effective_from,
                other.effective_to,
            ):
                raise ValidationError("同一客戶與產品的有效售價有效期間不可重疊")

    def _auto_close_prior_active_prices(self):
        """Close any active price that would overlap the new price's start date."""
        close_date = self.effective_from - timedelta(days=1)
        priors = (
            CustomerProductPrice.objects.select_for_update()
            .filter(
                customer_id=self.customer_id,
                product_id=self.product_id,
                is_active=True,
            )
            .order_by("-effective_from", "-pk")
        )

        for prior in priors:
            prior_end = prior.effective_to or date.max
            if prior_end < self.effective_from:
                continue
            if prior.effective_from >= self.effective_from:
                raise ValidationError(
                    {"effective_from": "新售價生效日必須晚於現行有效售價生效日"}
                )
            if close_date < prior.effective_from:
                raise ValidationError(
                    {
                        "effective_from": (
                            "新售價生效日與現行售價過近，無法自動結束舊紀錄"
                        )
                    }
                )
            prior.effective_to = close_date
            super(CustomerProductPrice, prior).save(
                update_fields=["effective_to", "updated_at"]
            )

    @staticmethod
    def _periods_overlap(from_a, to_a, from_b, to_b) -> bool:
        end_a = to_a or date.max
        end_b = to_b or date.max
        return from_a <= end_b and from_b <= end_a

    def save(self, *args, **kwargs):
        if self.pk:
            previous = CustomerProductPrice.objects.filter(pk=self.pk).first()
            if previous:
                for field in self._IMMUTABLE_FIELDS:
                    if getattr(previous, field) != getattr(self, field):
                        raise ValidationError(
                            "歷史售價不可修改核心欄位，請新增紀錄"
                        )

        with transaction.atomic():
            if self._state.adding and self.is_active:
                self._auto_close_prior_active_prices()
            self.full_clean()
            super().save(*args, **kwargs)

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.inventory.packaging import format_packaging
from apps.inventory.pricing_validators import MARGIN_RATE_VALIDATORS, NON_NEGATIVE_PRICE_VALIDATORS


class Warehouse(models.Model):
    class TemperatureZone(models.TextChoices):
        AMBIENT = "ambient", "常溫"
        CHILLED = "chilled", "冷藏 (0-4°C)"
        FROZEN = "frozen", "冷凍 (-18°C)"
        CONTROLLED = "controlled", "恆溫控濕"

    code = models.CharField("倉庫代碼", max_length=20, unique=True)
    name = models.CharField("倉庫名稱", max_length=100)
    temperature_zone = models.CharField(
        "溫區", max_length=20, choices=TemperatureZone.choices, default=TemperatureZone.AMBIENT
    )
    location = models.CharField("地址", max_length=200, blank=True)
    is_active = models.BooleanField("啟用", default=True)

    class Meta:
        verbose_name = "倉庫"
        verbose_name_plural = "倉庫"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class Product(models.Model):
    class Unit(models.TextChoices):
        KG = "kg", "公斤"
        G = "g", "公克"
        L = "l", "公升"
        ML = "ml", "毫升"
        PCS = "pcs", "件"
        BOX = "box", "箱"
        PACK = "pack", "包"

    class ProductKind(models.TextChoices):
        FINISHED = "finished", "成品"
        RAW = "raw", "原料"
        DUAL = "dual", "成品/原料"

    class SalesUnit(models.TextChoices):
        PACK = "pack", "包"
        CAN = "can", "罐"
        BAG = "bag", "袋"
        BOX = "box", "箱"
        KG = "kg", "kg"

    class NetWeightUnit(models.TextChoices):
        G = "g", "g"
        KG = "kg", "kg"

    sku = models.CharField("料號", max_length=50, unique=True)
    name = models.CharField("品名", max_length=200)
    product_kind = models.CharField(
        "產品類型", max_length=20, choices=ProductKind.choices, default=ProductKind.RAW
    )
    category = models.CharField("分類", max_length=100, blank=True)
    brand = models.CharField("品牌", max_length=100, blank=True)
    series = models.CharField("系列", max_length=100, blank=True)
    spec = models.CharField("規格", max_length=200, blank=True)
    unit = models.CharField("庫存單位", max_length=10, choices=Unit.choices, default=Unit.KG)
    sales_unit = models.CharField(
        "銷售單位",
        max_length=10,
        choices=SalesUnit.choices,
        default=SalesUnit.PACK,
    )
    net_weight_value = models.DecimalField(
        "淨重", max_digits=12, decimal_places=3, null=True, blank=True
    )
    net_weight_unit = models.CharField(
        "淨重單位",
        max_length=5,
        choices=NetWeightUnit.choices,
        blank=True,
    )
    is_for_sale = models.BooleanField("可接單販售", default=False)
    is_sellable = models.BooleanField("是否販售", default=True)
    can_be_raw_material = models.BooleanField("可做原料", default=False)
    unit_cost = models.DecimalField("每公斤成本", max_digits=12, decimal_places=4, null=True, blank=True)
    standard_price = models.DecimalField(
        "標準售價",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=NON_NEGATIVE_PRICE_VALIDATORS,
        help_text="無客戶專屬價時的預設售價（銷售單位）",
    )
    target_margin_rate = models.DecimalField(
        "目標毛利率",
        max_digits=5,
        decimal_places=4,
        default=Decimal("0.2500"),
        validators=MARGIN_RATE_VALIDATORS,
        help_text="例：0.25 = 25%",
    )
    warning_margin_rate = models.DecimalField(
        "預警毛利率",
        max_digits=5,
        decimal_places=4,
        default=Decimal("0.1500"),
        validators=MARGIN_RATE_VALIDATORS,
    )
    minimum_margin_rate = models.DecimalField(
        "最低毛利率",
        max_digits=5,
        decimal_places=4,
        default=Decimal("0.0500"),
        validators=MARGIN_RATE_VALIDATORS,
    )
    shelf_life_days = models.PositiveIntegerField("標準保質期(天)", default=365)
    storage_temp_min = models.DecimalField(
        "最低儲存溫度(°C)", max_digits=5, decimal_places=1, null=True, blank=True
    )
    storage_temp_max = models.DecimalField(
        "最高儲存溫度(°C)", max_digits=5, decimal_places=1, null=True, blank=True
    )
    description = models.TextField("描述", blank=True)
    is_active = models.BooleanField("啟用", default=True)
    created_at = models.DateTimeField("建立時間", auto_now_add=True)
    updated_at = models.DateTimeField("更新時間", auto_now=True)

    class Meta:
        verbose_name = "產品"
        verbose_name_plural = "產品"
        ordering = ["sku"]

    def __str__(self):
        return f"{self.sku} - {self.name}"

    def clean(self):
        super().clean()
        if self.target_margin_rate >= Decimal("1"):
            raise ValidationError({"target_margin_rate": "目標毛利率必須小於 1"})
        if self.minimum_margin_rate > self.warning_margin_rate:
            raise ValidationError(
                {"warning_margin_rate": "預警毛利率不得低於最低毛利率"}
            )
        if self.warning_margin_rate > self.target_margin_rate:
            raise ValidationError(
                {"target_margin_rate": "目標毛利率不得低於預警毛利率"}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def packaging_display(self) -> str:
        return format_packaging(
            net_weight_value=self.net_weight_value,
            net_weight_unit=self.net_weight_unit,
            sales_unit_label=self.get_sales_unit_display(),
        )

    @property
    def sales_unit_label(self) -> str:
        return self.get_sales_unit_display()

    @property
    def total_quantity(self):
        return self.batches.aggregate(total=models.Sum("quantity"))["total"] or Decimal("0")


class ProductCostHistoryQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("成本歷史不可修改，請新增紀錄")

    def delete(self):
        raise ValidationError("成本歷史不可刪除")


class ProductCostHistoryManager(models.Manager):
    def get_queryset(self):
        return ProductCostHistoryQuerySet(self.model, using=self._db)


class ProductCostHistory(models.Model):
    class Source(models.TextChoices):
        MANUAL = "manual", "手動"
        IMPORT = "import", "匯入"
        PURCHASE = "purchase", "採購"
        SYNC = "sync", "同步"

    _COST_FACT_FIELDS = (
        "product_id",
        "unit_cost",
        "effective_at",
        "previous_cost",
        "change_amount",
        "change_percent",
        "source",
    )

    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="cost_history", verbose_name="產品"
    )
    unit_cost = models.DecimalField(
        "單位成本",
        max_digits=12,
        decimal_places=4,
        validators=NON_NEGATIVE_PRICE_VALIDATORS,
    )
    effective_at = models.DateTimeField("生效時間")
    previous_cost = models.DecimalField(
        "前次成本", max_digits=12, decimal_places=4, null=True, blank=True
    )
    change_amount = models.DecimalField(
        "成本變動", max_digits=12, decimal_places=4, null=True, blank=True
    )
    change_percent = models.DecimalField(
        "成本漲幅", max_digits=8, decimal_places=4, null=True, blank=True
    )
    source = models.CharField(
        "來源", max_length=20, choices=Source.choices, default=Source.MANUAL
    )
    note = models.TextField("備註", blank=True)
    created_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="product_cost_history_created",
        verbose_name="建立人",
    )
    created_at = models.DateTimeField("建立時間", auto_now_add=True)

    objects = ProductCostHistoryManager()

    class Meta:
        verbose_name = "產品成本歷史"
        verbose_name_plural = "產品成本歷史"
        ordering = ["-effective_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "effective_at"],
                name="inventory_unique_product_cost_effective_at",
            ),
        ]

    def __str__(self):
        return f"{self.product.sku} @ {self.unit_cost} ({self.effective_at:%Y-%m-%d})"

    def clean(self):
        super().clean()
        if self._state.adding:
            duplicate = ProductCostHistory.objects.filter(
                product=self.product,
                effective_at=self.effective_at,
            )
            if duplicate.exists():
                raise ValidationError(
                    {"effective_at": "同一產品同一生效時間不可重複"}
                )

    def _apply_cost_deltas(self):
        prior = (
            ProductCostHistory.objects.filter(
                product=self.product,
                effective_at__lt=self.effective_at,
            )
            .order_by("-effective_at", "-pk")
            .first()
        )
        if prior is None:
            self.previous_cost = None
            self.change_amount = None
            self.change_percent = None
            return
        self.previous_cost = prior.unit_cost
        self.change_amount = self.unit_cost - prior.unit_cost
        if prior.unit_cost > 0:
            self.change_percent = (self.change_amount / prior.unit_cost).quantize(
                Decimal("0.0001")
            )
        else:
            self.change_percent = None

    def save(self, *args, **kwargs):
        if not self._state.adding and self.pk:
            previous = ProductCostHistory.objects.get(pk=self.pk)
            for field in self._COST_FACT_FIELDS:
                if getattr(previous, field) != getattr(self, field):
                    raise ValidationError("成本歷史不可修改成本事實，請新增紀錄")
            self.full_clean()
            return super().save(*args, **kwargs)

        if self._state.adding:
            self._apply_cost_deltas()
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("成本歷史不可刪除")

    @classmethod
    def get_latest_for_product(cls, product, *, as_of=None):
        """Return the latest cost row effective on or before as_of."""
        as_of = as_of or timezone.now()
        return (
            cls.objects.filter(product=product, effective_at__lte=as_of)
            .order_by("-effective_at", "-pk")
            .first()
        )


class Batch(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "available", "可用"
        QUARANTINE = "quarantine", "待檢"
        EXPIRED = "expired", "已過期"
        DEPLETED = "depleted", "已耗盡"

    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="batches", verbose_name="原料")
    batch_no = models.CharField("批次號", max_length=50)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="batches", verbose_name="倉庫")
    quantity = models.DecimalField(
        "數量", max_digits=12, decimal_places=3, validators=[MinValueValidator(Decimal("0"))]
    )
    production_date = models.DateField("生產日期", null=True, blank=True)
    expiry_date = models.DateField("有效期限")
    status = models.CharField("狀態", max_length=20, choices=Status.choices, default=Status.AVAILABLE)
    supplier_batch = models.CharField("供應商批號", max_length=50, blank=True)
    notes = models.TextField("備註", blank=True)
    created_at = models.DateTimeField("建立時間", auto_now_add=True)

    class Meta:
        verbose_name = "庫存批次"
        verbose_name_plural = "庫存批次"
        unique_together = [("product", "batch_no", "warehouse")]
        ordering = ["expiry_date"]

    def __str__(self):
        return f"{self.product.sku} / {self.batch_no}"

    @property
    def days_to_expiry(self):
        return (self.expiry_date - timezone.localdate()).days

    @property
    def is_expiring_soon(self):
        return 0 <= self.days_to_expiry <= 30


class StockMovement(models.Model):
    class MovementType(models.TextChoices):
        IN_PURCHASE = "in_purchase", "採購入庫"
        IN_PRODUCTION = "in_production", "生產入庫"
        IN_ADJUST = "in_adjust", "盤盈調整"
        OUT_SALES = "out_sales", "銷售出庫"
        OUT_PRODUCTION = "out_production", "生產領料"
        OUT_ADJUST = "out_adjust", "盤虧調整"
        TRANSFER = "transfer", "調撥"

    batch = models.ForeignKey(Batch, on_delete=models.PROTECT, related_name="movements", verbose_name="批次")
    movement_type = models.CharField("類型", max_length=20, choices=MovementType.choices)
    quantity = models.DecimalField("數量", max_digits=12, decimal_places=3)
    reference = models.CharField("參考單號", max_length=50, blank=True)
    notes = models.TextField("備註", blank=True)
    created_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True, verbose_name="操作人"
    )
    created_at = models.DateTimeField("操作時間", auto_now_add=True)

    class Meta:
        verbose_name = "庫存異動"
        verbose_name_plural = "庫存異動"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_movement_type_display()} - {self.batch} ({self.quantity})"

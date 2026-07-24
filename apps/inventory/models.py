from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.inventory.packaging import format_packaging


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
    is_for_sale = models.BooleanField("是否販售", default=False)
    can_be_raw_material = models.BooleanField("可做原料", default=False)
    unit_cost = models.DecimalField("每公斤成本", max_digits=12, decimal_places=4, null=True, blank=True)
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

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


class Recipe(models.Model):
    code = models.CharField("配方代碼", max_length=30, unique=True)
    name = models.CharField("配方名稱", max_length=200)
    output_product = models.ForeignKey(
        "inventory.Product",
        on_delete=models.PROTECT,
        related_name="output_recipes",
        verbose_name="產出原料",
    )
    output_qty = models.DecimalField(
        "標準產出量", max_digits=12, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))]
    )
    version = models.CharField("版本", max_length=20, default="1.0")
    is_active = models.BooleanField("啟用", default=True)
    notes = models.TextField("備註", blank=True)
    created_at = models.DateTimeField("建立時間", auto_now_add=True)
    updated_at = models.DateTimeField("更新時間", auto_now=True)

    class Meta:
        verbose_name = "配方"
        verbose_name_plural = "配方"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.name} (v{self.version})"


class RecipeItem(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name="items", verbose_name="配方")
    ingredient = models.ForeignKey(
        "inventory.Product", on_delete=models.PROTECT, related_name="recipe_usages", verbose_name="投入原料"
    )
    quantity = models.DecimalField(
        "用量", max_digits=12, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))]
    )
    loss_rate = models.DecimalField(
        "損耗率(%)", max_digits=5, decimal_places=2, default=Decimal("0"), validators=[MinValueValidator(Decimal("0"))]
    )

    class Meta:
        verbose_name = "配方明細"
        verbose_name_plural = "配方明細"

    def __str__(self):
        return f"{self.recipe.code} - {self.ingredient.sku}"

    @property
    def actual_quantity(self):
        return self.quantity * (1 + self.loss_rate / 100)


class ProductionOrder(models.Model):
    class Status(models.TextChoices):
        PLANNED = "planned", "已排程"
        IN_PROGRESS = "in_progress", "生產中"
        COMPLETED = "completed", "已完成"
        CANCELLED = "cancelled", "已取消"

    order_no = models.CharField("工單號", max_length=30, unique=True)
    recipe = models.ForeignKey(Recipe, on_delete=models.PROTECT, related_name="production_orders", verbose_name="配方")
    planned_qty = models.DecimalField(
        "計劃產量", max_digits=12, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))]
    )
    actual_qty = models.DecimalField("實際產量", max_digits=12, decimal_places=3, default=Decimal("0"))
    status = models.CharField("狀態", max_length=20, choices=Status.choices, default=Status.PLANNED)
    planned_start = models.DateField("計劃開始日")
    planned_end = models.DateField("計劃完成日", null=True, blank=True)
    actual_start = models.DateTimeField("實際開始", null=True, blank=True)
    actual_end = models.DateTimeField("實際完成", null=True, blank=True)
    batch_no = models.CharField("產出批次號", max_length=50, blank=True)
    notes = models.TextField("備註", blank=True)
    created_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True, verbose_name="建立人"
    )
    created_at = models.DateTimeField("建立時間", auto_now_add=True)

    class Meta:
        verbose_name = "生產工單"
        verbose_name_plural = "生產工單"
        ordering = ["-planned_start", "-created_at"]

    def __str__(self):
        return self.order_no

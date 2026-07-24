from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


class Supplier(models.Model):
    code = models.CharField("供應商代碼", max_length=20, unique=True)
    name = models.CharField("供應商名稱", max_length=200)
    contact_person = models.CharField("聯絡人", max_length=100, blank=True)
    phone = models.CharField("電話", max_length=30, blank=True)
    email = models.EmailField("電子郵件", blank=True)
    address = models.CharField("地址", max_length=300, blank=True)
    certification = models.CharField("認證(如 HACCP/ISO)", max_length=200, blank=True)
    is_active = models.BooleanField("啟用", default=True)
    notes = models.TextField("備註", blank=True)
    created_at = models.DateTimeField("建立時間", auto_now_add=True)

    class Meta:
        verbose_name = "供應商"
        verbose_name_plural = "供應商"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class PurchaseOrder(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "草稿"
        PENDING = "pending", "待審核"
        APPROVED = "approved", "已核准"
        ORDERED = "ordered", "已下單"
        PARTIAL = "partial", "部分到貨"
        RECEIVED = "received", "已到貨"
        CANCELLED = "cancelled", "已取消"

    order_no = models.CharField("採購單號", max_length=30, unique=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="purchase_orders", verbose_name="供應商")
    status = models.CharField("狀態", max_length=20, choices=Status.choices, default=Status.DRAFT)
    order_date = models.DateField("下單日期")
    expected_date = models.DateField("預計到貨日", null=True, blank=True)
    notes = models.TextField("備註", blank=True)
    created_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True, verbose_name="建立人"
    )
    created_at = models.DateTimeField("建立時間", auto_now_add=True)
    updated_at = models.DateTimeField("更新時間", auto_now=True)

    class Meta:
        verbose_name = "採購單"
        verbose_name_plural = "採購單"
        ordering = ["-order_date", "-created_at"]

    def __str__(self):
        return self.order_no

    @property
    def total_amount(self):
        return sum(item.line_total for item in self.items.all())


class PurchaseOrderItem(models.Model):
    purchase_order = models.ForeignKey(
        PurchaseOrder, on_delete=models.CASCADE, related_name="items", verbose_name="採購單"
    )
    product = models.ForeignKey(
        "inventory.Product", on_delete=models.PROTECT, related_name="po_items", verbose_name="原料"
    )
    quantity = models.DecimalField(
        "採購數量", max_digits=12, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))]
    )
    unit_price = models.DecimalField(
        "單價", max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0"))]
    )
    received_qty = models.DecimalField("已到貨數量", max_digits=12, decimal_places=3, default=Decimal("0"))

    class Meta:
        verbose_name = "採購明細"
        verbose_name_plural = "採購明細"

    def __str__(self):
        return f"{self.purchase_order.order_no} - {self.product.sku}"

    @property
    def line_total(self):
        return self.quantity * self.unit_price

    @property
    def remaining_qty(self):
        return self.quantity - self.received_qty


class GoodsReceipt(models.Model):
    receipt_no = models.CharField("入庫單號", max_length=30, unique=True)
    purchase_order = models.ForeignKey(
        PurchaseOrder, on_delete=models.PROTECT, related_name="receipts", verbose_name="採購單"
    )
    received_date = models.DateField("到貨日期")
    notes = models.TextField("備註", blank=True)
    received_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True, verbose_name="驗收人"
    )
    created_at = models.DateTimeField("建立時間", auto_now_add=True)

    class Meta:
        verbose_name = "採購入庫"
        verbose_name_plural = "採購入庫"
        ordering = ["-received_date"]

    def __str__(self):
        return self.receipt_no

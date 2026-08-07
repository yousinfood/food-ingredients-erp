from django import forms
from django.forms import inlineformset_factory
from django.utils import timezone

from apps.inventory.models import Product

from .models import Customer, CustomerProductPrice, SalesOrder, SalesOrderItem


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = [
            "code",
            "name",
            "region",
            "contact_person",
            "phone",
            "phone_2",
            "phone_3",
            "email",
            "address",
            "invoice_address",
            "map_location",
            "line_id",
            "payment_method",
            "delivery_day",
            "delivery_sequence",
            "credit_limit",
            "last_transaction_date",
            "tax_id",
            "is_active",
            "notes",
        ]
        widgets = {
            "code": forms.TextInput(attrs={"placeholder": "CUS-001"}),
            "name": forms.TextInput(attrs={"placeholder": "客戶名稱"}),
            "last_transaction_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }


def _saleable_products():
    return Product.objects.filter(
        is_active=True,
        product_kind__in=[Product.ProductKind.FINISHED, Product.ProductKind.DUAL],
    ).order_by("sku")


class SalesOrderForm(forms.ModelForm):
    class Meta:
        model = SalesOrder
        fields = ["customer", "status", "order_date", "delivery_date", "shipping_address", "notes"]
        widgets = {
            "order_date": forms.DateInput(attrs={"type": "date"}),
            "delivery_date": forms.DateInput(attrs={"type": "date"}),
            "shipping_address": forms.TextInput(attrs={"placeholder": "送貨地址"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, lock_customer=False, **kwargs):
        super().__init__(*args, **kwargs)
        if lock_customer:
            self.fields["customer"].widget = forms.HiddenInput()


class SalesOrderItemForm(forms.ModelForm):
    class Meta:
        model = SalesOrderItem
        fields = ["product", "quantity", "unit_price"]
        widgets = {
            "quantity": forms.NumberInput(attrs={"step": "0.001", "min": "0.001"}),
            "unit_price": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product"].queryset = _saleable_products()


SalesOrderItemFormSet = inlineformset_factory(
    SalesOrder,
    SalesOrderItem,
    form=SalesOrderItemForm,
    extra=3,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


class CustomerProductPriceForm(forms.ModelForm):
    class Meta:
        model = CustomerProductPrice
        fields = ["customer", "product", "price", "effective_from", "note"]
        widgets = {
            "price": forms.NumberInput(attrs={"step": "0.01", "min": "0", "placeholder": "售價"}),
            "effective_from": forms.DateInput(attrs={"type": "date"}),
            "note": forms.TextInput(attrs={"placeholder": "備註（選填）"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["customer"].queryset = Customer.objects.filter(is_active=True).order_by("code")
        self.fields["product"].queryset = Product.objects.filter(
            is_active=True,
            is_for_sale=True,
            product_kind__in=[Product.ProductKind.FINISHED, Product.ProductKind.DUAL],
        ).order_by("sku")
        if not self.initial.get("effective_from") and not self.data:
            self.initial["effective_from"] = timezone.localdate()

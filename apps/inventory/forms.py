from django import forms

from .models import Product


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            "sku",
            "name",
            "category",
            "brand",
            "series",
            "sales_unit",
            "net_weight_value",
            "net_weight_unit",
            "unit",
            "shelf_life_days",
            "storage_temp_min",
            "storage_temp_max",
            "description",
            "is_active",
        ]
        widgets = {
            "sku": forms.TextInput(attrs={"placeholder": "RM-001"}),
            "name": forms.TextInput(attrs={"placeholder": "品名"}),
            "category": forms.TextInput(attrs={"placeholder": "分類"}),
            "sales_unit": forms.Select(),
            "net_weight_unit": forms.Select(),
            "net_weight_value": forms.NumberInput(attrs={"placeholder": "例如 20 或 600", "step": "any"}),
            "unit": forms.Select(),
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sales_unit"].label = "銷售單位"
        self.fields["net_weight_value"].label = "淨重數值"
        self.fields["net_weight_unit"].label = "淨重單位"
        self.fields["net_weight_unit"].required = False
        self.fields["unit"].label = "庫存單位"

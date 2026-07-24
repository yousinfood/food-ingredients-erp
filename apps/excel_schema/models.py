from django.db import models


class SheetHomepage(models.Model):
    """工作表：首頁"""

    stat_today_delivery = models.CharField("🚚 今日配送", max_length=100, blank=True, db_column="🚚 今日配送")
    stat_today_payment = models.CharField("💰 今日收款", max_length=100, blank=True, db_column="💰 今日收款")
    stat_today_purchase = models.CharField("📦 今日採購", max_length=100, blank=True, db_column="📦 今日採購")
    stat_today_reminder = models.CharField("⚠ 今日提醒", max_length=100, blank=True, db_column="⚠ 今日提醒")
    ai_suggestion_1 = models.CharField("今天沒有待收款", max_length=300, blank=True, db_column="今天沒有待收款")
    ai_suggestion_2 = models.CharField("今天共有5家配送", max_length=300, blank=True, db_column="今天共有5家配送")
    ai_suggestion_3 = models.CharField("建議先配送仁武區", max_length=300, blank=True, db_column="建議先配送仁武區")

    class Meta:
        db_table = "首頁"
        verbose_name = "首頁"
        verbose_name_plural = "首頁"


class SheetTodayDelivery(models.Model):
    """工作表：今日配送"""

    delivery_date = models.DateField("配送日期", null=True, blank=True, db_column="配送日期")
    customer = models.ForeignKey(
        "SheetCustomerData",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="today_deliveries",
        verbose_name="客戶",
        db_column="客戶",
        to_field="customer_name",
    )
    delivery_area = models.CharField("配送區", max_length=100, blank=True, db_column="配送區")
    address = models.CharField("地址", max_length=300, blank=True, db_column="地址")
    product = models.ForeignKey(
        "SheetProductData",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="today_deliveries",
        verbose_name="產品",
        db_column="產品",
        to_field="product_name",
    )
    quantity = models.DecimalField("數量", max_digits=14, decimal_places=3, null=True, blank=True, db_column="數量")
    delivery_sequence = models.IntegerField("配送順序", null=True, blank=True, db_column="配送順序")
    status = models.CharField("狀態", max_length=50, blank=True, db_column="狀態")
    completed_at = models.DateTimeField("完成時間", null=True, blank=True, db_column="完成時間")
    notes = models.TextField("備註", blank=True, db_column="備註")

    class Meta:
        db_table = "今日配送"
        verbose_name = "今日配送"
        verbose_name_plural = "今日配送"
        indexes = [
            models.Index(fields=["delivery_date"], name="idx_today_delivery_date"),
            models.Index(fields=["delivery_area"], name="idx_today_delivery_area"),
            models.Index(fields=["status"], name="idx_today_delivery_status"),
        ]


class SheetQuickSearch(models.Model):
    """工作表：快速查詢"""

    search_keyword = models.CharField("🔍 搜尋客戶", max_length=200, blank=True, db_column="🔍 搜尋客戶")
    customer = models.ForeignKey(
        "SheetCustomerData",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quick_search_rows",
        verbose_name="客戶編號",
        db_column="客戶編號",
    )
    region = models.CharField("區域", max_length=100, blank=True, db_column="區域")
    customer_name = models.CharField("客戶名稱", max_length=200, blank=True, db_column="客戶名稱")
    contact_person = models.CharField("聯絡人", max_length=100, blank=True, db_column="聯絡人")
    phone_1 = models.CharField("📞", max_length=50, blank=True, db_column="📞_1")
    phone_2 = models.CharField("📞", max_length=50, blank=True, db_column="📞_2")
    phone_3 = models.CharField("📞", max_length=50, blank=True, db_column="📞_3")
    map_address = models.CharField("📍地址", max_length=300, blank=True, db_column="📍地址")
    create_order_action = models.CharField("🛒 建立訂單", max_length=100, blank=True, db_column="🛒 建立訂單")

    class Meta:
        db_table = "快速查詢"
        verbose_name = "快速查詢"
        verbose_name_plural = "快速查詢"
        indexes = [
            models.Index(fields=["search_keyword"], name="idx_quick_search_keyword"),
            models.Index(fields=["customer_name"], name="idx_quick_search_name"),
            models.Index(fields=["region"], name="idx_quick_search_region"),
        ]


class SheetOrderCenter(models.Model):
    """工作表：接單中心"""

    search_input = models.CharField("🔍 輸入電話或客戶名稱…", max_length=200, blank=True, db_column="🔍 輸入電話或客戶名稱…")
    customer_name = models.CharField("客戶姓名", max_length=200, blank=True, db_column="客戶姓名")
    phone_1 = models.CharField("電話", max_length=50, blank=True, db_column="電話_1")
    address_1 = models.CharField("地址", max_length=300, blank=True, db_column="地址_1")
    payment_method_1 = models.CharField("付款方式", max_length=100, blank=True, db_column="付款方式_1")
    region = models.CharField("區域", max_length=100, blank=True, db_column="區域")
    order_date = models.DateField("訂單日期", null=True, blank=True, db_column="訂單日期")
    order_customer = models.CharField("客戶", max_length=200, blank=True, db_column="客戶")
    phone_2 = models.CharField("電話", max_length=50, blank=True, db_column="電話_2")
    address_2 = models.CharField("地址", max_length=300, blank=True, db_column="地址_2")
    payment_method_2 = models.CharField("付款方式", max_length=100, blank=True, db_column="付款方式_2")
    product_name = models.CharField("品名", max_length=200, blank=True, db_column="品名")
    quantity = models.DecimalField("數量", max_digits=14, decimal_places=3, null=True, blank=True, db_column="數量")
    unit = models.CharField("單位", max_length=50, blank=True, db_column="單位")

    class Meta:
        db_table = "接單中心"
        verbose_name = "接單中心"
        verbose_name_plural = "接單中心"
        indexes = [
            models.Index(fields=["search_input"], name="idx_order_center_search"),
            models.Index(fields=["customer_name"], name="idx_order_center_custname"),
            models.Index(fields=["phone_1"], name="idx_order_center_phone1"),
            models.Index(fields=["order_date"], name="idx_order_center_orderdate"),
        ]


class SheetPaymentManagement(models.Model):
    """工作表：收款管理（Excel 空白，保留資料表）"""

    class Meta:
        db_table = "收款管理"
        verbose_name = "收款管理"
        verbose_name_plural = "收款管理"


class SheetCustomerData(models.Model):
    """工作表：客戶資料"""

    customer_code = models.CharField("客戶編號", max_length=20, primary_key=True, db_column="客戶編號")
    region = models.CharField("區域", max_length=100, blank=True, db_column="區域")
    customer_name = models.CharField("客戶名稱", max_length=200, unique=True, db_column="客戶名稱")
    contact_person = models.CharField("聯絡人", max_length=100, blank=True, db_column="聯絡人")
    phone_1 = models.CharField("📞", max_length=50, blank=True, db_column="📞_1")
    phone_2 = models.CharField("📞", max_length=50, blank=True, db_column="📞_2")
    phone_3 = models.CharField("📞", max_length=50, blank=True, db_column="📞_3")
    delivery_address = models.CharField("配送地址", max_length=300, blank=True, db_column="配送地址")
    invoice_address = models.CharField("發票地址", max_length=300, blank=True, db_column="發票地址")
    map_link = models.CharField("📍", max_length=100, blank=True, db_column="📍")
    line_id = models.CharField("🟩Line", max_length=100, blank=True, db_column="🟩Line")
    payment_method = models.CharField("付款方式", max_length=100, blank=True, db_column="付款方式")
    fixed_delivery_day = models.CharField("固定配送日", max_length=100, blank=True, db_column="固定配送日")
    delivery_sequence = models.IntegerField("配送順序", null=True, blank=True, db_column="配送順序")
    credit_limit = models.DecimalField("信用額度", max_digits=14, decimal_places=2, null=True, blank=True, db_column="信用額度")
    last_transaction_date = models.DateField("最後交易日", null=True, blank=True, db_column="最後交易日")
    notes = models.TextField("備註", blank=True, db_column="備註")

    class Meta:
        db_table = "客戶資料"
        verbose_name = "客戶資料"
        verbose_name_plural = "客戶資料"
        indexes = [
            models.Index(fields=["customer_name"], name="idx_customer_name"),
            models.Index(fields=["region"], name="idx_customer_region"),
            models.Index(fields=["phone_1"], name="idx_customer_phone_1"),
            models.Index(fields=["phone_2"], name="idx_customer_phone_2"),
            models.Index(fields=["phone_3"], name="idx_customer_phone_3"),
        ]


class SheetProductData(models.Model):
    """工作表：產品資料"""

    product_code = models.CharField("產品編號", max_length=20, primary_key=True, db_column="產品編號")
    product_name = models.CharField("產品名稱", max_length=200, unique=True, db_column="產品名稱")
    product_type = models.CharField("產品類型", max_length=100, blank=True, db_column="產品類型")
    specification = models.CharField("規格", max_length=200, blank=True, db_column="規格")
    unit = models.CharField("單位", max_length=50, blank=True, db_column="單位")
    is_for_sale = models.CharField("是否販售", max_length=10, blank=True, db_column="是否販售")
    can_be_raw_material = models.CharField("可做原料", max_length=10, blank=True, db_column="可做原料")
    is_active = models.CharField("啟用", max_length=10, blank=True, db_column="啟用")
    notes = models.TextField("備註", blank=True, db_column="備註")
    cost = models.DecimalField("成本", max_digits=14, decimal_places=2, null=True, blank=True, db_column="成本")
    price = models.DecimalField("售價", max_digits=14, decimal_places=2, null=True, blank=True, db_column="售價")

    class Meta:
        db_table = "產品資料"
        verbose_name = "產品資料"
        verbose_name_plural = "產品資料"
        indexes = [
            models.Index(fields=["product_name"], name="idx_product_name"),
            models.Index(fields=["product_type"], name="idx_product_type"),
            models.Index(fields=["is_active"], name="idx_product_active"),
        ]


class SheetRawMaterialData(models.Model):
    """工作表：原料資料"""

    material_code = models.CharField("原料編號", max_length=20, primary_key=True, db_column="原料編號")
    material_name = models.CharField("原料名稱", max_length=200, db_column="原料名稱")
    category = models.CharField("分類", max_length=100, blank=True, db_column="分類")
    unit = models.CharField("單位", max_length=50, blank=True, db_column="單位")
    cost_per_kg = models.DecimalField("每公斤成本", max_digits=14, decimal_places=4, null=True, blank=True, db_column="每公斤成本")
    latest_purchase_price = models.DecimalField("最新採購價", max_digits=14, decimal_places=4, null=True, blank=True, db_column="最新採購價")
    last_purchase_date = models.DateField("最近採購日", null=True, blank=True, db_column="最近採購日")
    safety_stock = models.DecimalField("安全庫存", max_digits=14, decimal_places=3, null=True, blank=True, db_column="安全庫存")
    is_active = models.CharField("啟用", max_length=10, blank=True, db_column="啟用")
    notes = models.TextField("備註", blank=True, db_column="備註")

    class Meta:
        db_table = "原料資料"
        verbose_name = "原料資料"
        verbose_name_plural = "原料資料"
        indexes = [
            models.Index(fields=["material_name"], name="idx_material_name"),
            models.Index(fields=["category"], name="idx_material_category"),
        ]


class SheetRecipeManagement(models.Model):
    """工作表：配方管理"""

    product = models.ForeignKey(
        SheetProductData,
        on_delete=models.CASCADE,
        related_name="recipe_management_rows",
        verbose_name="產品編號",
        db_column="產品編號",
    )
    product_name = models.CharField("產品名稱", max_length=200, blank=True, db_column="產品名稱")
    version = models.CharField("版本", max_length=50, blank=True, db_column="版本")
    material = models.ForeignKey(
        SheetRawMaterialData,
        on_delete=models.CASCADE,
        related_name="recipe_management_rows",
        verbose_name="原料編號",
        db_column="原料編號",
    )
    material_name = models.CharField("原料名稱", max_length=200, blank=True, db_column="原料名稱")
    quantity = models.DecimalField("用量", max_digits=14, decimal_places=3, null=True, blank=True, db_column="用量")
    unit = models.CharField("單位", max_length=50, blank=True, db_column="單位")
    sort_order = models.IntegerField("排序", null=True, blank=True, db_column="排序")
    is_active = models.CharField("是否啟用", max_length=10, blank=True, db_column="是否啟用")
    notes = models.TextField("備註", blank=True, db_column="備註")

    class Meta:
        db_table = "配方管理"
        verbose_name = "配方管理"
        verbose_name_plural = "配方管理"
        indexes = [
            models.Index(fields=["version"], name="idx_recipe_mgmt_version"),
            models.Index(fields=["sort_order"], name="idx_recipe_mgmt_sort"),
        ]


class SheetRecipeMaster(models.Model):
    """工作表：配方主檔"""

    recipe_id = models.CharField("配方ID", max_length=20, primary_key=True, db_column="配方ID")
    product = models.ForeignKey(
        SheetProductData,
        on_delete=models.PROTECT,
        related_name="recipe_masters",
        verbose_name="產品編號",
        db_column="產品編號",
    )
    product_name = models.CharField("產品名稱", max_length=200, blank=True, db_column="產品名稱")
    product_type = models.CharField("產品類型", max_length=100, blank=True, db_column="產品類型")
    product_feature = models.CharField("產品特性", max_length=200, blank=True, db_column="產品特性")
    recipe_version = models.CharField("配方版本", max_length=50, blank=True, db_column="配方版本")
    base_batch_kg = models.DecimalField("基準批次(kg)", max_digits=14, decimal_places=3, null=True, blank=True, db_column="基準批次(kg)")
    status = models.CharField("狀態", max_length=50, blank=True, db_column="狀態")
    created_date = models.DateField("建立日期", null=True, blank=True, db_column="建立日期")
    change_reason = models.CharField("修改原因", max_length=300, blank=True, db_column="修改原因")
    notes = models.TextField("備註", blank=True, db_column="備註")
    total_cost = models.DecimalField("總成本", max_digits=14, decimal_places=4, null=True, blank=True, db_column="總成本")
    cost_per_kg = models.DecimalField("每公斤成本", max_digits=14, decimal_places=4, null=True, blank=True, db_column="每公斤成本")

    class Meta:
        db_table = "配方主檔"
        verbose_name = "配方主檔"
        verbose_name_plural = "配方主檔"
        indexes = [
            models.Index(fields=["product_name"], name="idx_recipe_master_pname"),
            models.Index(fields=["status"], name="idx_recipe_master_status"),
        ]


class SheetRecipeDetail(models.Model):
    """工作表：配方明細"""

    recipe = models.ForeignKey(
        SheetRecipeMaster,
        on_delete=models.CASCADE,
        related_name="details",
        verbose_name="配方ID",
        db_column="配方ID",
    )
    item_no = models.IntegerField("項次", db_column="項次")
    material = models.ForeignKey(
        SheetRawMaterialData,
        on_delete=models.PROTECT,
        related_name="recipe_details",
        verbose_name="原料編號",
        db_column="原料編號",
    )
    material_name = models.CharField("原料名稱", max_length=200, blank=True, db_column="原料名稱")
    selected_item = models.CharField("採用品項", max_length=200, blank=True, db_column="採用品項")
    quantity = models.DecimalField("用量", max_digits=14, decimal_places=3, null=True, blank=True, db_column="用量")
    unit = models.CharField("單位", max_length=50, blank=True, db_column="單位")
    notes = models.TextField("備註", blank=True, db_column="備註")
    cost_per_kg = models.DecimalField("每公斤成本", max_digits=14, decimal_places=4, null=True, blank=True, db_column="每公斤成本")
    cost = models.DecimalField("成本", max_digits=14, decimal_places=4, null=True, blank=True, db_column="成本")

    class Meta:
        db_table = "配方明細"
        verbose_name = "配方明細"
        verbose_name_plural = "配方明細"
        constraints = [
            models.UniqueConstraint(fields=["recipe", "item_no"], name="uniq_recipe_detail_item"),
        ]
        indexes = [
            models.Index(fields=["item_no"], name="idx_recipe_detail_itemno"),
        ]


class SheetProductionRecord(models.Model):
    """工作表：生產記錄（Excel 空白，保留資料表）"""

    class Meta:
        db_table = "生產記錄"
        verbose_name = "生產記錄"
        verbose_name_plural = "生產記錄"


class SheetPurchaseReceipt(models.Model):
    """工作表：採購進貨"""

    receipt_no = models.CharField("進貨單號", max_length=50, db_column="進貨單號")
    receipt_date = models.DateField("日期", null=True, blank=True, db_column="日期")
    material = models.ForeignKey(
        SheetRawMaterialData,
        on_delete=models.PROTECT,
        related_name="purchase_receipts",
        verbose_name="原料編號",
        db_column="原料編號",
    )
    material_name = models.CharField("原料名稱", max_length=200, blank=True, db_column="原料名稱")
    quantity = models.DecimalField("數量", max_digits=14, decimal_places=3, null=True, blank=True, db_column="數量")
    unit_price = models.DecimalField("單價", max_digits=14, decimal_places=4, null=True, blank=True, db_column="單價")
    supplier_name = models.CharField("供應商", max_length=200, blank=True, db_column="供應商")
    notes = models.TextField("備註", blank=True, db_column="備註")

    class Meta:
        db_table = "採購進貨"
        verbose_name = "採購進貨"
        verbose_name_plural = "採購進貨"
        constraints = [
            models.UniqueConstraint(fields=["receipt_no", "material"], name="uniq_purchase_receipt_line"),
        ]
        indexes = [
            models.Index(fields=["receipt_date"], name="idx_purchase_receipt_date"),
            models.Index(fields=["supplier_name"], name="idx_purchase_supplier"),
        ]


class SheetInventoryManagement(models.Model):
    """工作表：庫存管理（Excel 空白，保留資料表）"""

    class Meta:
        db_table = "庫存管理"
        verbose_name = "庫存管理"
        verbose_name_plural = "庫存管理"


class SheetSupplierData(models.Model):
    """工作表：供應商資料（Excel 空白，保留資料表）"""

    class Meta:
        db_table = "供應商資料"
        verbose_name = "供應商資料"
        verbose_name_plural = "供應商資料"


class SheetDeliveryRule(models.Model):
    """工作表：配送規則"""

    customer = models.ForeignKey(
        SheetCustomerData,
        on_delete=models.CASCADE,
        related_name="delivery_rules",
        verbose_name="客戶編號",
        db_column="客戶編號",
    )
    customer_name = models.CharField("客戶名稱", max_length=200, blank=True, db_column="客戶名稱")
    weekday = models.CharField("星期", max_length=20, blank=True, db_column="星期")
    delivery_area = models.CharField("配送區", max_length=100, blank=True, db_column="配送區")
    delivery_sequence = models.IntegerField("配送順序", null=True, blank=True, db_column="配送順序")
    fixed_product = models.ForeignKey(
        SheetProductData,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="delivery_rules",
        verbose_name="固定產品",
        db_column="固定產品",
        to_field="product_code",
    )
    fixed_quantity = models.DecimalField("固定數量", max_digits=14, decimal_places=3, null=True, blank=True, db_column="固定數量")
    is_delivery = models.CharField("是否配送", max_length=10, blank=True, db_column="是否配送")
    notes = models.TextField("備註", blank=True, db_column="備註")
    created_date = models.DateField("建立日期", null=True, blank=True, db_column="建立日期")
    updated_at = models.DateTimeField("最後更新", null=True, blank=True, db_column="最後更新")

    class Meta:
        db_table = "配送規則"
        verbose_name = "配送規則"
        verbose_name_plural = "配送規則"
        indexes = [
            models.Index(fields=["weekday"], name="idx_delivery_rule_weekday"),
            models.Index(fields=["delivery_area"], name="idx_delivery_rule_area"),
        ]


class SheetPriceManagement(models.Model):
    """工作表：價格管理（Excel 空白，保留資料表）"""

    class Meta:
        db_table = "價格管理"
        verbose_name = "價格管理"
        verbose_name_plural = "價格管理"


class SheetVendorData(models.Model):
    """工作表：廠商資料（Excel 空白，保留資料表）"""

    class Meta:
        db_table = "廠商資料"
        verbose_name = "廠商資料"
        verbose_name_plural = "廠商資料"


class SheetAiConsole(models.Model):
    """工作表：AI控制台（Excel 空白，保留資料表）"""

    class Meta:
        db_table = "AI控制台"
        verbose_name = "AI控制台"
        verbose_name_plural = "AI控制台"


class SheetSystemSettings(models.Model):
    """工作表：系統設定（Excel 空白，保留資料表）"""

    class Meta:
        db_table = "系統設定"
        verbose_name = "系統設定"
        verbose_name_plural = "系統設定"


class SheetImprovementCenter(models.Model):
    """工作表：改善中心（Excel 空白，保留資料表）"""

    class Meta:
        db_table = "改善中心"
        verbose_name = "改善中心"
        verbose_name_plural = "改善中心"

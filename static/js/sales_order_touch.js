(function () {
  "use strict";

  function init() {
    const config = window.SALES_ORDER_CONFIG || {};
    const form = document.getElementById("sales-order-form");
    if (!form) return;

    const searchInput = document.getElementById("product-search");
    const searchResults = document.getElementById("product-search-results");
    const orderLines = document.getElementById("order-lines");
    const orderLinesEmpty = document.getElementById("order-lines-empty");
    const orderLinesInputs = document.getElementById("order-lines-inputs");
    const lineCountEl = document.getElementById("line-count");
    const orderTotalEl = document.getElementById("order-total");
    const saveBtn = document.getElementById("save-order-btn");
    const copyLastBtn = document.getElementById("copy-last-order-btn");
    const copyPartialToggleBtn = document.getElementById("copy-partial-toggle-btn");
    const copySelectedBtn = document.getElementById("copy-selected-btn");
    const frequentGrid = document.getElementById("frequent-products");
    const lastOrderGrid = document.getElementById("last-order-products");
    const categoryGrid = document.getElementById("category-grid");
    const seriesChips = document.getElementById("series-chips");
    const modifiedStarchChips = document.getElementById("modified-starch-chips");
    const naturalStarchChips = document.getElementById("natural-starch-chips");
    const seriesHint = document.getElementById("category-series-hint");
    const categoryProducts = document.getElementById("category-products");
    const backLink = document.getElementById("order-back-link");
    const leaveModal = document.getElementById("leave-order-modal");
    const leaveContinueBtn = document.getElementById("leave-continue-btn");
    const leaveDraftBtn = document.getElementById("leave-draft-btn");
    const leaveDiscardBtn = document.getElementById("leave-discard-btn");
    const removeConfirmModal = document.getElementById("order-remove-confirm-modal");
    const removeConfirmText = document.getElementById("order-remove-confirm-text");
    const removeCancelBtn = document.getElementById("order-remove-cancel");
    const removeYesBtn = document.getElementById("order-remove-yes");
    const saveConfirmModal = document.getElementById("order-save-confirm-modal");
    const saveConfirmList = document.getElementById("order-save-confirm-list");
    const saveConfirmTotal = document.getElementById("order-save-confirm-total");
    const saveConfirmCancelBtn = document.getElementById("order-save-confirm-cancel");
    const saveConfirmSubmitBtn = document.getElementById("order-save-confirm-submit");

    const lines = new Map();
    const productCatalog = new Map();
    const categoryCache = new Map();
    const draftKey = config.customerId ? "sales_order_draft_" + config.customerId : null;
    let searchTimer = null;
    let toastTimer = null;
    let undoTimer = null;
    let lastTouchPickAt = 0;
    let activeCategory = null;
    let activeSeries = null;
    let activeBrandSeries = null;
    let activeNaturalStarchItem = null;
    let activeModifiedStarchSegment = "retail";
    let draftCategory = null;
    let draftSeries = null;
    let draftBrandSeries = null;
    let draftNaturalStarchItem = null;
    let draftModifiedStarchSegment = null;
    let isSubmitting = false;
    let saveConfirmPending = false;
    let pendingRemoveConfirm = null;
    let copyPartialMode = false;

    const pickToolbar = document.getElementById("order-pick-toolbar");
    const productsScroll = document.getElementById("order-products-scroll");
    const productsZone = document.querySelector(".touch-order-products-zone");

    function scrollProductsToTop() {
      if (!productsScroll) return;
      productsScroll.scrollTop = 0;
      requestAnimationFrame(function () {
        productsScroll.scrollTop = 0;
      });
    }

    function useInListFlourHint() {
      return window.matchMedia("(min-width: 1024px)").matches;
    }

    function flourSeriesPromptHtml() {
      return (
        '<p class="touch-category-hint touch-category-hint--in-list" role="status">' +
        "選系列：低筋／中筋／高筋／油條</p>"
      );
    }

    function syncPickToolbarGap() {
      if (!pickToolbar) return;
      const toolbarH = Math.ceil(pickToolbar.getBoundingClientRect().height);
      const searchSection = pickToolbar.querySelector(".touch-product-search-section--toolbar");
      const searchH = searchSection ? Math.ceil(searchSection.getBoundingClientRect().height) : 0;
      if (productsZone) {
        productsZone.style.setProperty("--touch-product-search-offset", searchH + "px");
      }
      if (productsScroll) {
        productsScroll.style.scrollMarginTop = "0px";
      }
    }
    let pendingLeaveUrl = null;
    let leaveConfirmed = false;

    function productKey(id) {
      const n = Number(id);
      return Number.isFinite(n) ? n : id;
    }

    function seedCatalog(items) {
      (items || []).forEach(function (p) {
        if (p && p.id != null) productCatalog.set(productKey(p.id), p);
      });
    }

    seedCatalog(config.initialLines);
    seedCatalog(config.frequentProducts);
    seedCatalog(config.defaultCategoryProducts);
    if (config.lastOrder && config.lastOrder.items) seedCatalog(config.lastOrder.items);

    function getToastEl() {
      let toast = document.getElementById("touch-add-toast");
      if (!toast) {
        toast = document.createElement("div");
        toast.id = "touch-add-toast";
        toast.className = "touch-add-toast";
        toast.setAttribute("role", "status");
        toast.setAttribute("aria-live", "polite");
        document.body.appendChild(toast);
      }
      return toast;
    }

    function showToast(message, options) {
      options = options || {};
      const toast = getToastEl();
      toast.innerHTML = "";
      const text = document.createElement("span");
      text.textContent = message;
      toast.appendChild(text);
      if (options.undoLabel && typeof options.onUndo === "function") {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "touch-toast-undo";
        btn.textContent = options.undoLabel;
        btn.addEventListener("click", function (e) {
          e.preventDefault();
          clearTimeout(undoTimer);
          options.onUndo();
          toast.classList.remove("touch-add-toast--visible");
        });
        toast.appendChild(btn);
      }
      toast.classList.add("touch-add-toast--visible");
      clearTimeout(toastTimer);
      toastTimer = setTimeout(function () {
        toast.classList.remove("touch-add-toast--visible");
      }, options.duration || 5000);
    }

    function formatMoney(value) {
      return "$" + Math.round(value).toLocaleString();
    }

    function parseQty(value) {
      const qty = parseFloat(value);
      return Number.isFinite(qty) && qty > 0 ? qty : 0;
    }

    function getLineQty(line) {
      return parseQty(line.qtyHidden.value);
    }

    function setLineQty(line, qty) {
      const safe = Math.max(0, qty);
      const prev = getLineQty(line);
      line.qtyHidden.value = safe > 0 ? String(safe) : "0";
      line.qtyDisplay.textContent = safe > 0 ? String(safe) : "0";
      line.minusBtn.disabled = safe <= 0;
      if (safe !== prev) flashQtyDisplay(line);
    }

    function flashQtyDisplay(line) {
      if (!line || !line.qtyDisplay) return;
      line.qtyDisplay.classList.remove("touch-qty-display--flash");
      void line.qtyDisplay.offsetWidth;
      line.qtyDisplay.classList.add("touch-qty-display--flash");
      setTimeout(function () {
        line.qtyDisplay.classList.remove("touch-qty-display--flash");
      }, 550);
    }

    function packLabelFromProduct(product) {
      const specRaw = product.spec ? String(product.spec) : "";
      const unitRaw = product.unit_label ? String(product.unit_label) : "";
      if (specRaw && unitRaw) return specRaw + "／" + unitRaw;
      if (specRaw) return specRaw;
      if (unitRaw) return unitRaw;
      return "—";
    }

    function hideRemoveConfirmModal() {
      if (!removeConfirmModal) return;
      removeConfirmModal.hidden = true;
      pendingRemoveConfirm = null;
    }

    function showRemoveConfirmModal(productName, onConfirm) {
      if (!removeConfirmModal || !removeConfirmText) {
        if (onConfirm) onConfirm();
        return;
      }
      pendingRemoveConfirm = onConfirm;
      removeConfirmText.textContent = productName;
      removeConfirmModal.hidden = false;
    }

    function hideSaveConfirmModal() {
      if (!saveConfirmModal) return;
      saveConfirmModal.hidden = true;
    }

    function showSaveConfirmModal() {
      if (!saveConfirmModal || !saveConfirmList) return;
      saveConfirmList.innerHTML = "";
      lines.forEach(function (line) {
        const qty = getLineQty(line);
        if (qty <= 0) return;
        const packEl = line.row.querySelector(".touch-order-line-pack");
        const pack = packEl ? packEl.textContent : packLabelFromProduct(line.product);
        const item = document.createElement("li");
        item.className = "touch-order-save-confirm-item";
        item.innerHTML =
          '<span class="touch-order-save-confirm-item-name">' + escapeHtml(line.product.name) + "</span>" +
          '<span class="touch-order-save-confirm-item-pack">' + escapeHtml(pack) + "</span>" +
          '<span class="touch-order-save-confirm-item-qty">數量 ' + escapeHtml(String(qty)) + "</span>";
        saveConfirmList.appendChild(item);
      });
      if (saveConfirmTotal && orderTotalEl) {
        saveConfirmTotal.textContent = orderTotalEl.textContent;
      }
      saveConfirmModal.hidden = false;
    }

    function defaultPrice(product) {
      const mapPrice = config.customerPriceMap && config.customerPriceMap[String(product.id)];
      if (mapPrice && mapPrice !== "0") return String(mapPrice);
      if (product.last_unit_price && product.last_unit_price !== "0") {
        return String(product.last_unit_price);
      }
      const frequent = (config.frequentProducts || []).find(function (fp) {
        return productKey(fp.id) === productKey(product.id);
      });
      if (frequent && frequent.last_unit_price && frequent.last_unit_price !== "0") {
        return String(frequent.last_unit_price);
      }
      return "0";
    }

    function customerQuery() {
      return config.customerId ? "&customer=" + encodeURIComponent(config.customerId) : "";
    }

    function setSaveEnabled(enabled) {
      if (!saveBtn) return;
      saveBtn.disabled = !enabled;
      if (enabled) saveBtn.removeAttribute("disabled");
    }

    function updateTotals() {
      if (!lineCountEl || !orderTotalEl) return;
      let total = 0;
      let count = 0;
      lines.forEach(function (line) {
        const qty = getLineQty(line);
        const price = parseFloat(line.priceHidden.value) || 0;
        if (qty > 0) {
          count += 1;
          total += qty * price;
        }
        line.subtotalEl.textContent = formatMoney(qty * price);
        line.minusBtn.disabled = qty <= 0;
      });
      lineCountEl.textContent = String(count);
      orderTotalEl.textContent = formatMoney(total);
      setSaveEnabled(count > 0 && !isSubmitting);
      if (orderLinesEmpty) orderLinesEmpty.hidden = true;
      saveDraft();
    }

    function syncHiddenInputs() {
      if (!orderLinesInputs) return;
      orderLinesInputs.innerHTML = "";
      lines.forEach(function (line) {
        const qty = getLineQty(line);
        if (qty <= 0) return;
        [
          ["item_product_id", String(line.product.id)],
          ["item_quantity", line.qtyHidden.value],
          ["item_unit_price", line.priceHidden.value || "0"],
        ].forEach(function (pair) {
          const input = document.createElement("input");
          input.type = "hidden";
          input.name = pair[0];
          input.value = pair[1];
          orderLinesInputs.appendChild(input);
        });
      });
    }

    function escapeHtml(text) {
      const div = document.createElement("div");
      div.textContent = text == null ? "" : String(text);
      return div.innerHTML;
    }

    function hideResults() {
      if (!searchResults) return;
      searchResults.hidden = true;
      searchResults.innerHTML = "";
    }

    function pulseLine(row) {
      row.classList.add("touch-order-line--pulse");
      setTimeout(function () { row.classList.remove("touch-order-line--pulse"); }, 400);
    }

    function cartSnapshot() {
      const items = [];
      lines.forEach(function (line) {
        const qty = getLineQty(line);
        if (qty <= 0) return;
        items.push({
          id: line.product.id,
          name: line.product.name,
          sku: line.product.sku || "",
          spec: line.product.spec || "",
          unit_label: line.product.unit_label || "",
          quantity: line.qtyHidden.value,
          unit_price: line.priceHidden.value || "0",
        });
      });
      return {
        items: items,
        order_date: document.getElementById("order_date")?.value || "",
        delivery_date: document.getElementById("delivery_date")?.value || "",
        shipping_address: document.getElementById("shipping_address")?.value || "",
        notes: document.getElementById("notes")?.value || "",
        special_instructions: document.getElementById("special_instructions")?.value || "",
        activeCategory: activeCategory,
        activeSeries: activeSeries,
        activeBrandSeries: activeBrandSeries,
        activeNaturalStarchItem: activeNaturalStarchItem,
        activeModifiedStarchSegment: activeModifiedStarchSegment,
        saved_at: Date.now(),
      };
    }

    function saveDraft() {
      if (!draftKey || typeof localStorage === "undefined") return;
      if (config.savedOrder) return;
      try {
        const data = cartSnapshot();
        if (!data.items.length) {
          localStorage.removeItem(draftKey);
          return;
        }
        localStorage.setItem(draftKey, JSON.stringify(data));
      } catch (err) {
        /* ignore quota errors */
      }
    }

    function loadDraft() {
      if (!draftKey || typeof localStorage === "undefined") return false;
      try {
        const raw = localStorage.getItem(draftKey);
        if (!raw) return false;
        const data = JSON.parse(raw);
        if (!data.items || !data.items.length) return false;
        if (data.order_date) document.getElementById("order_date").value = data.order_date;
        if (data.delivery_date) document.getElementById("delivery_date").value = data.delivery_date;
        if (data.shipping_address != null) document.getElementById("shipping_address").value = data.shipping_address;
        if (data.notes != null) document.getElementById("notes").value = data.notes;
        if (data.special_instructions != null) document.getElementById("special_instructions").value = data.special_instructions;
        draftCategory = data.activeCategory || null;
        draftSeries = data.activeSeries || null;
        draftBrandSeries = data.activeBrandSeries || null;
        draftNaturalStarchItem = data.activeNaturalStarchItem || null;
        draftModifiedStarchSegment = data.activeModifiedStarchSegment || null;
        data.items.forEach(function (item) {
          const product = {
            id: item.id,
            name: item.name,
            sku: item.sku || "",
            spec: item.spec || "",
            unit_label: item.unit_label || "",
          };
          addLine(product, {
            quantity: item.quantity,
            unit_price: item.unit_price,
            replace: true,
            silent: true,
          });
        });
        return true;
      } catch (err) {
        return false;
      }
    }

    function clearDraft() {
      if (!draftKey || typeof localStorage === "undefined") return;
      try { localStorage.removeItem(draftKey); } catch (err) { /* ignore */ }
    }

    function hasUnsavedCart() {
      if (config.savedOrder || isSubmitting || leaveConfirmed) return false;
      let count = 0;
      lines.forEach(function (line) {
        if (getLineQty(line) > 0) count += 1;
      });
      return count > 0;
    }

    function showLeaveModal(url) {
      pendingLeaveUrl = url || null;
      if (leaveModal) {
        leaveModal.hidden = false;
        leaveModal.classList.add("touch-leave-modal--visible");
      }
    }

    function hideLeaveModal() {
      pendingLeaveUrl = null;
      if (leaveModal) {
        leaveModal.hidden = true;
        leaveModal.classList.remove("touch-leave-modal--visible");
      }
    }

    function navigateAway(url) {
      leaveConfirmed = true;
      hideLeaveModal();
      if (url) window.location.href = url;
    }

    function removeLine(productId) {
      const key = productKey(productId);
      const line = lines.get(key);
      if (!line) return null;
      const snapshot = {
        product: line.product,
        qty: getLineQty(line),
        price: line.priceHidden.value,
      };
      lines.delete(key);
      line.row.remove();
      updateTotals();
      return snapshot;
    }

    function restoreLine(snapshot) {
      addLine(snapshot.product, {
        quantity: snapshot.qty,
        unit_price: snapshot.price,
        replace: true,
        silent: true,
      });
    }

    function removeLineWithUndo(productId) {
      const snapshot = removeLine(productId);
      if (!snapshot || snapshot.qty <= 0) return;
      clearTimeout(undoTimer);
      showToast("已移除 " + snapshot.product.name, {
        undoLabel: "復原",
        duration: 5000,
        onUndo: function () { restoreLine(snapshot); },
      });
    }

    function adjustQtyWithUndo(line, key, newQty, message) {
      const prevQty = getLineQty(line);
      const prevPrice = line.priceHidden.value;
      if (newQty <= 0) {
        removeLineWithUndo(key);
        return;
      }
      setLineQty(line, newQty);
      updateTotals();
      pulseLine(line.row);
      showToast(message || ("已調整 " + line.product.name), {
        undoLabel: "復原",
        duration: 5000,
        onUndo: function () {
          if (prevQty <= 0) {
            removeLine(key);
          } else {
            setLineQty(line, prevQty);
            line.priceHidden.value = prevPrice;
            updateTotals();
          }
        },
      });
    }

    function bindLineEvents(line, product) {
      const key = productKey(product.id);
      line.minusBtn.addEventListener("click", function (e) {
        e.preventDefault();
        const current = getLineQty(line);
        if (current <= 1) removeLineWithUndo(key);
        else adjustQtyWithUndo(line, key, current - 1, "已減少 " + product.name);
      });
      line.plusBtn.addEventListener("click", function (e) {
        e.preventDefault();
        adjustQtyWithUndo(line, key, getLineQty(line) + 1, product.name + " +1");
      });
      line.row.querySelectorAll(".touch-qty-quick-btn").forEach(function (btn) {
        btn.addEventListener("click", function (e) {
          e.preventDefault();
          const add = parseInt(btn.dataset.add, 10) || 0;
          adjustQtyWithUndo(line, key, getLineQty(line) + add, product.name + " +" + add);
        });
      });
      line.row.querySelector(".touch-order-line-remove").addEventListener("click", function (e) {
        e.preventDefault();
        showRemoveConfirmModal(product.name, function () {
          removeLineWithUndo(key);
        });
      });
    }

    function addLine(product, defaults) {
      defaults = defaults || {};
      const key = productKey(product.id);
      const priceDefault = defaults.unit_price != null ? String(defaults.unit_price) : defaultPrice(product);
      const qtyDefault = defaults.replace
        ? parseQty(defaults.quantity != null ? defaults.quantity : 1)
        : 1;

      productCatalog.set(key, product);

      if (lines.has(key)) {
        const existing = lines.get(key);
        const prevQty = getLineQty(existing);
        if (defaults.replace) {
          setLineQty(existing, qtyDefault);
          if (defaults.unit_price != null) existing.priceHidden.value = priceDefault;
        } else {
          setLineQty(existing, prevQty + 1);
          if (defaults.unit_price != null && defaults.unit_price !== "0") {
            existing.priceHidden.value = priceDefault;
          }
        }
        updateTotals();
        if (!defaults.silent) {
          showToast("✓ " + product.name + " +1", defaults.undo ? {
            undoLabel: "復原",
            duration: 5000,
            onUndo: defaults.undo,
          } : undefined);
          pulseLine(existing.row);
        }
        return existing;
      }

      if (!orderLines) return null;

      const row = document.createElement("div");
      row.className = "touch-order-line";
      row.dataset.productId = String(key);
      const specRaw = product.spec ? String(product.spec) : "";
      const unitRaw = product.unit_label ? String(product.unit_label) : "";
      let packText = "";
      if (specRaw && unitRaw) {
        packText = escapeHtml(specRaw) + "／" + escapeHtml(unitRaw);
      } else if (specRaw) {
        packText = escapeHtml(specRaw);
      } else if (unitRaw) {
        packText = escapeHtml(unitRaw);
      }
      row.innerHTML =
        '<strong class="touch-order-line-name">' + escapeHtml(product.name) + "</strong>" +
        (packText ? '<span class="touch-order-line-pack">' + packText + "</span>" : "") +
        '<div class="touch-order-line-qty">' +
          '<div class="touch-qty-stepper">' +
            '<button type="button" class="touch-qty-btn touch-qty-minus" aria-label="減少">−</button>' +
            '<span class="touch-qty-display">' + escapeHtml(String(qtyDefault)) + "</span>" +
            '<button type="button" class="touch-qty-btn touch-qty-plus" aria-label="增加">+</button>' +
          "</div>" +
        "</div>" +
        '<div class="touch-qty-quick">' +
          '<button type="button" class="touch-qty-quick-btn" data-add="5">+5</button>' +
          '<button type="button" class="touch-qty-quick-btn" data-add="10">+10</button>' +
          '<button type="button" class="touch-qty-quick-btn" data-add="20">+20</button>' +
        "</div>" +
        '<div class="touch-order-line-footer">' +
          '<div class="touch-order-line-subtotal-wrap">' +
            '<span class="touch-order-line-subtotal-label">小計</span>' +
            '<span class="touch-order-line-subtotal">$0</span>' +
          "</div>" +
          '<button type="button" class="touch-order-line-remove" aria-label="移除商品">移除商品</button>' +
        "</div>" +
        '<input type="hidden" class="touch-qty-hidden" value="' + escapeHtml(String(qtyDefault)) + '">' +
        '<input type="hidden" class="touch-price-hidden" value="' + escapeHtml(priceDefault) + '">';

      orderLines.appendChild(row);

      const line = {
        product: product,
        row: row,
        qtyDisplay: row.querySelector(".touch-qty-display"),
        qtyHidden: row.querySelector(".touch-qty-hidden"),
        priceHidden: row.querySelector(".touch-price-hidden"),
        subtotalEl: row.querySelector(".touch-order-line-subtotal"),
        minusBtn: row.querySelector(".touch-qty-minus"),
        plusBtn: row.querySelector(".touch-qty-plus"),
      };
      lines.set(key, line);
      bindLineEvents(line, product);

      if (searchInput) {
        searchInput.value = "";
        hideResults();
      }
      updateTotals();
      if (!defaults.silent) {
        showToast("✓ 已加入 " + product.name, defaults.undo ? {
          undoLabel: "復原",
          duration: 5000,
          onUndo: defaults.undo,
        } : undefined);
        pulseLine(row);
      }
      return line;
    }

    function productFromCard(card) {
      const id = productKey(card.dataset.product);
      let product = productCatalog.get(id);
      if (!product) {
        product = {
          id: id,
          name: card.dataset.productName || "",
          sku: card.dataset.productSku || "",
          spec: card.dataset.productSpec || "",
          unit_label: card.dataset.productUnit || "",
        };
        productCatalog.set(id, product);
      }
      return product;
    }

    function addProductQty(product, qty, price, options) {
      options = options || {};
      qty = Math.max(1, parseInt(qty, 10) || 1);
      const key = productKey(product.id);
      const resolvedPrice = price || defaultPrice(product);
      const hadLine = lines.has(key);
      const prevQty = hadLine ? getLineQty(lines.get(key)) : 0;
      const prevPrice = hadLine ? lines.get(key).priceHidden.value : resolvedPrice;

      if (hadLine) {
        setLineQty(lines.get(key), prevQty + qty);
        if (resolvedPrice && resolvedPrice !== "0") {
          lines.get(key).priceHidden.value = String(resolvedPrice);
        }
        updateTotals();
      } else {
        addLine(product, {
          quantity: qty,
          unit_price: resolvedPrice,
          replace: true,
          silent: true,
        });
      }

      if (!options.silent) {
        showToast("✓ 已加入 " + product.name + " +" + qty, {
          undoLabel: "復原",
          duration: 5000,
          onUndo: function () {
            if (hadLine) {
              if (prevQty <= 0) removeLine(key);
              else {
                setLineQty(lines.get(key), prevQty);
                lines.get(key).priceHidden.value = prevPrice;
                updateTotals();
              }
            } else {
              removeLine(key);
            }
          },
        });
        const line = lines.get(key);
        if (line) pulseLine(line.row);
      }
    }

    function pickProductFromButton(btn) {
      btn.classList.add("touch-product-pick-btn--pressed");
      setTimeout(function () { btn.classList.remove("touch-product-pick-btn--pressed"); }, 180);

      const id = productKey(btn.dataset.product || btn.dataset.productId);
      let product = productCatalog.get(id);
      if (!product) {
        product = {
          id: id,
          name: btn.dataset.productName || btn.textContent.trim(),
          sku: btn.dataset.productSku || "",
          spec: btn.dataset.productSpec || "",
          unit_label: btn.dataset.productUnit || "",
        };
        productCatalog.set(id, product);
      }

      addProductQty(product, 1, btn.dataset.price || defaultPrice(product));
    }

    function clearLines() {
      lines.forEach(function (line) { line.row.remove(); });
      lines.clear();
      updateTotals();
    }

    function copyLastOrder() {
      if (!config.lastOrder || !config.lastOrder.items || !config.lastOrder.items.length) return;
      exitCopyPartialMode();
      clearLines();
      config.lastOrder.items.forEach(function (item) {
        addLine(item, {
          quantity: item.quantity,
          unit_price: item.unit_price,
          replace: true,
          silent: true,
        });
      });
      showToast("✓ 已複製上次訂單");
    }

    function updateCopySelectedBtn() {
      if (!copySelectedBtn || !lastOrderGrid) return;
      const count = lastOrderGrid.querySelectorAll(".touch-last-order-item--selected").length;
      copySelectedBtn.hidden = count === 0;
      copySelectedBtn.textContent = "複製已選 (" + count + ")";
    }

    function exitCopyPartialMode() {
      copyPartialMode = false;
      if (copyPartialToggleBtn) copyPartialToggleBtn.classList.remove("touch-copy-partial-active");
      if (lastOrderGrid) {
        lastOrderGrid.classList.remove("touch-copy-partial-mode");
        lastOrderGrid.querySelectorAll(".touch-last-order-item--selected").forEach(function (el) {
          el.classList.remove("touch-last-order-item--selected");
        });
      }
      updateCopySelectedBtn();
    }

    function enterCopyPartialMode() {
      copyPartialMode = true;
      if (copyPartialToggleBtn) copyPartialToggleBtn.classList.add("touch-copy-partial-active");
      if (lastOrderGrid) lastOrderGrid.classList.add("touch-copy-partial-mode");
      showToast("點選要複製的商品");
      updateCopySelectedBtn();
    }

    function copySelectedLastOrder() {
      if (!lastOrderGrid) return;
      const selected = lastOrderGrid.querySelectorAll(".touch-last-order-item--selected");
      if (!selected.length) return;
      selected.forEach(function (card) {
        const qty = parseFloat(card.dataset.copyQty) || 1;
        addProductQty(
          productFromCard(card),
          qty,
          card.dataset.price,
          { silent: true }
        );
      });
      showToast("✓ 已複製 " + selected.length + " 項");
      exitCopyPartialMode();
    }

    function productCardHtml(p) {
      productCatalog.set(productKey(p.id), p);
      const price = defaultPrice(p);
      const safeName = escapeHtml(p.name);
      return (
        '<div class="touch-product-card" data-product="' + p.id + '" data-price="' + price + '" ' +
        'data-product-name="' + safeName + '" data-product-sku="' + escapeHtml(p.sku || "") + '" ' +
        'data-product-unit="' + escapeHtml(p.unit_label || "") + '" data-product-spec="' + escapeHtml(p.spec || "") + '">' +
        '<p class="touch-frequent-name">' + safeName + "</p>" +
        '<div class="touch-product-card-actions">' +
        '<button type="button" class="touch-product-quick-add" data-add="1">+1</button>' +
        '<button type="button" class="touch-product-quick-add" data-add="5">+5</button>' +
        '<button type="button" class="touch-product-quick-add" data-add="10">+10</button>' +
        "</div></div>"
      );
    }

    function showEmptyCategoryMessage() {
      if (!categoryProducts) return;
      categoryProducts.innerHTML = '<p class="touch-empty">此分類目前沒有產品</p>';
      scrollProductsToTop();
    }

    function renderCategoryProducts(products) {
      if (!categoryProducts) return;
      if (!products.length) {
        showEmptyCategoryMessage();
        scrollProductsToTop();
        return;
      }
      categoryProducts.innerHTML = products.map(productCardHtml).join("");
      scrollProductsToTop();
    }

    function isBrandFlourCategory(category) {
      const key = config.brandFlourCategory || "有信品牌粉";
      return category === key;
    }

    function brandFlourSeriesDef(seriesKey) {
      return (config.brandFlourSeries || []).find(function (s) {
        return s.key === seriesKey;
      });
    }

    function filterProductsByNameList(products, productNames) {
      if (!productNames || !productNames.length) return [];
      const list = products || [];
      const picked = [];
      productNames.forEach(function (target) {
        let found = list.find(function (p) {
          const n = (p.name || "").trim();
          return n === target;
        });
        if (!found) {
          found = list.find(function (p) {
            const n = (p.name || "").trim();
            return n.indexOf(target) === 0;
          });
        }
        if (found && !picked.some(function (p) { return p.id === found.id; })) {
          picked.push(found);
        }
      });
      return picked;
    }

    function filterBrandFlourProducts(products, seriesKey) {
      const def = brandFlourSeriesDef(seriesKey);
      if (!def || !def.productNames) return [];
      return filterProductsByNameList(products, def.productNames);
    }

    function renderBrandFlourPickerHtml() {
      const series = config.brandFlourSeries || [];
      return (
        '<div class="touch-brand-flour-picker" role="group" aria-label="有信品牌粉系列">' +
        series
          .map(function (s) {
            const tone =
              s.key === "red"
                ? "touch-brand-flour-series-btn--red"
                : "touch-brand-flour-series-btn--blue";
            return (
              '<button type="button" class="touch-brand-flour-series-btn ' +
              tone +
              '" data-brand-series="' +
              escapeHtml(s.key) +
              '"' +
              (s.ariaLabel ? ' aria-label="' + escapeHtml(s.ariaLabel) + '"' : "") +
              ">" +
              '<span class="touch-brand-flour-series-title">' +
              escapeHtml(s.label) +
              "</span></button>"
            );
          })
          .join("") +
        "</div>"
      );
    }

    function renderBrandFlourBackBarHtml() {
      return (
        '<button type="button" class="touch-brand-flour-back" data-brand-flour-back="1">' +
        "← 返回有信品牌粉</button>"
      );
    }

    function isNaturalStarchCategory(category) {
      const key = config.naturalStarchCategory || "天然澱粉";
      return category === key;
    }

    function isModifiedStarchCategory(category) {
      const key = config.modifiedStarchCategory || "變性澱粉";
      return category === key;
    }

    function filterBySellableSegment(products, segment) {
      const list = products || [];
      if (segment === "formula") {
        return list.filter(function (p) {
          return p.is_sellable === false;
        });
      }
      return list.filter(function (p) {
        return p.is_sellable !== false;
      });
    }

    function renderModifiedStarchChips() {
      if (!modifiedStarchChips) return;
      if (!isModifiedStarchCategory(activeCategory)) {
        modifiedStarchChips.hidden = true;
        modifiedStarchChips.innerHTML = "";
        activeModifiedStarchSegment = "retail";
        syncPickToolbarGap();
        return;
      }
      const tabs = [
        { key: "retail", label: "市售商品" },
        { key: "formula", label: "自用配方" },
      ];
      modifiedStarchChips.innerHTML = tabs
        .map(function (tab) {
          const selected = activeModifiedStarchSegment === tab.key ? " series-card--selected" : "";
          return (
            '<button type="button" class="series-card series-card--medium' +
            selected +
            '" data-modified-starch-segment="' +
            escapeHtml(tab.key) +
            '">' +
            '<span class="title">' +
            escapeHtml(tab.label) +
            "</span></button>"
          );
        })
        .join("");
      modifiedStarchChips.hidden = false;
      syncPickToolbarGap();
    }

    function naturalStarchItemDef(itemKey) {
      return (config.naturalStarchItems || []).find(function (item) {
        return item.key === itemKey;
      });
    }

    function filterNaturalStarchProducts(products, itemKey) {
      const def = naturalStarchItemDef(itemKey);
      if (!def) return [];
      const list = products || [];
      const picked = [];

      function addProduct(p) {
        if (!picked.some(function (x) {
          return x.id === p.id;
        })) {
          picked.push(p);
        }
      }

      const seriesByKey = {
        potato: "馬鈴薯澱粉",
        tapioca: "太白粉",
        granule: "粒粉",
        corn: "玉米澱粉",
        glutinous: "糯米粉",
      };
      const seriesKey = (def.series || seriesByKey[itemKey] || "").trim();
      if (seriesKey) {
        list.forEach(function (p) {
          if ((p.series || "").trim() === seriesKey) {
            addProduct(p);
          }
        });
      }

      (def.productNames || []).forEach(function (target) {
        const needle = (target || "").trim();
        if (!needle) return;
        list.forEach(function (p) {
          const n = (p.name || "").trim();
          if (!n || n.indexOf(needle) < 0) return;
          addProduct(p);
        });
      });

      return picked;
    }

    function renderNaturalStarchBackBarHtml() {
      return (
        '<button type="button" class="touch-brand-flour-back" data-natural-starch-back="1">' +
        "← 返回天然澱粉</button>"
      );
    }

    function renderFlourBackBarHtml() {
      return (
        '<button type="button" class="touch-brand-flour-back" data-flour-series-back="1">' +
        "← 返回麵粉</button>"
      );
    }

    function renderNaturalStarchChips() {
      if (!naturalStarchChips) return;
      if (!isNaturalStarchCategory(activeCategory) || activeNaturalStarchItem) {
        naturalStarchChips.hidden = true;
        naturalStarchChips.innerHTML = "";
        if (!isNaturalStarchCategory(activeCategory)) {
          activeNaturalStarchItem = null;
        }
        syncPickToolbarGap();
        return;
      }
      const items = config.naturalStarchItems || [];
      naturalStarchChips.innerHTML = items
        .map(function (item) {
          return (
            '<button type="button" class="natural-starch-card" data-natural-starch-item="' +
            escapeHtml(item.key) +
            '"' +
            ' style="background-color:' +
            escapeHtml(item.bg) +
            ";color:" +
            escapeHtml(item.color) +
            '">' +
            '<span class="natural-starch-card__label">' +
            escapeHtml(item.label) +
            "</span></button>"
          );
        })
        .join("");
      naturalStarchChips.hidden = false;
      syncPickToolbarGap();
    }

    function isFlourCategory(category) {
      return category === config.flourCategory;
    }

    function setActiveCategoryButton(category) {
      if (!categoryGrid) return;
      categoryGrid.querySelectorAll(".touch-category-btn").forEach(function (btn) {
        btn.classList.toggle("touch-category-btn--active", btn.dataset.category === category);
      });
    }

    function flourSeriesToneClass(seriesName) {
      const map = {
        低筋: "series-card--low",
        中筋: "series-card--medium",
        高筋: "series-card--high",
        油條: "series-card--youtiao",
      };
      return map[seriesName] || "";
    }

    function renderSeriesChips() {
      if (!seriesChips) return;
      if (
        !isFlourCategory(activeCategory) ||
        isBrandFlourCategory(activeCategory) ||
        activeSeries
      ) {
        seriesChips.hidden = true;
        seriesChips.innerHTML = "";
        if (seriesHint) seriesHint.hidden = true;
        if (!isFlourCategory(activeCategory)) {
          activeSeries = null;
        }
        syncPickToolbarGap();
        return;
      }
      const seriesList = config.flourSeries || [];
      seriesChips.innerHTML = seriesList
        .map(function (s) {
          const selected = activeSeries === s ? " series-card--selected" : "";
          const tone = flourSeriesToneClass(s);
          return (
            '<button type="button" class="series-card ' +
            tone +
            selected +
            '" data-series="' +
            escapeHtml(s) +
            '">' +
            '<span class="title">' +
            escapeHtml(s) +
            "</span>" +
            '<span class="subtitle">系列</span></button>'
          );
        })
        .join("");
      seriesChips.hidden = false;
      if (seriesHint) {
        if (useInListFlourHint()) {
          seriesHint.hidden = true;
        } else {
          seriesHint.hidden = !!activeSeries;
        }
      }
      syncPickToolbarGap();
    }

    function applyCategoryView() {
      if (!activeCategory) return;
      renderSeriesChips();
      renderModifiedStarchChips();
      renderNaturalStarchChips();
      if (isBrandFlourCategory(activeCategory)) {
        if (seriesHint) seriesHint.hidden = true;
        if (!activeBrandSeries) {
          if (categoryProducts) {
            categoryProducts.innerHTML = renderBrandFlourPickerHtml();
          }
          scrollProductsToTop();
          return;
        }
        const cached = categoryCache.get(activeCategory) || [];
        const filtered = filterBrandFlourProducts(cached, activeBrandSeries);
        if (!categoryProducts) return;
        if (!filtered.length) {
          categoryProducts.innerHTML =
            renderBrandFlourBackBarHtml() + '<p class="touch-empty">此系列目前沒有產品</p>';
          scrollProductsToTop();
          return;
        }
        categoryProducts.innerHTML =
          renderBrandFlourBackBarHtml() + filtered.map(productCardHtml).join("");
        scrollProductsToTop();
        return;
      }
      if (isNaturalStarchCategory(activeCategory)) {
        if (seriesHint) seriesHint.hidden = true;
        if (!activeNaturalStarchItem) {
          if (categoryProducts) {
            categoryProducts.innerHTML = "";
          }
          scrollProductsToTop();
          return;
        }
        const cachedStarch = categoryCache.get(activeCategory) || [];
        const starchFiltered = filterNaturalStarchProducts(cachedStarch, activeNaturalStarchItem);
        if (!categoryProducts) return;
        if (!starchFiltered.length) {
          categoryProducts.innerHTML =
            renderNaturalStarchBackBarHtml() + '<p class="touch-empty">此品項目前沒有產品</p>';
          scrollProductsToTop();
          return;
        }
        categoryProducts.innerHTML =
          renderNaturalStarchBackBarHtml() + starchFiltered.map(productCardHtml).join("");
        scrollProductsToTop();
        return;
      }
      if (isModifiedStarchCategory(activeCategory)) {
        if (seriesHint) seriesHint.hidden = true;
        const modifiedCached = categoryCache.get(activeCategory) || [];
        const sellableFiltered = filterBySellableSegment(
          modifiedCached,
          activeModifiedStarchSegment
        );
        if (!categoryProducts) return;
        if (!sellableFiltered.length) {
          categoryProducts.innerHTML = '<p class="touch-empty">此分頁目前沒有產品</p>';
        } else {
          categoryProducts.innerHTML = sellableFiltered.map(productCardHtml).join("");
        }
        scrollProductsToTop();
        return;
      }
      if (isFlourCategory(activeCategory)) {
        if (seriesHint) seriesHint.hidden = true;
        if (!activeSeries) {
          if (categoryProducts) {
            categoryProducts.innerHTML = "";
          }
          scrollProductsToTop();
          return;
        }
        const cached = categoryCache.get(activeCategory) || [];
        const flourFiltered = cached.filter(function (p) {
          return p.series === activeSeries;
        });
        if (!categoryProducts) return;
        if (!flourFiltered.length) {
          categoryProducts.innerHTML =
            renderFlourBackBarHtml() + '<p class="touch-empty">此系列目前沒有產品</p>';
          scrollProductsToTop();
          return;
        }
        categoryProducts.innerHTML =
          renderFlourBackBarHtml() + flourFiltered.map(productCardHtml).join("");
        scrollProductsToTop();
        return;
      }
      if (seriesHint) seriesHint.hidden = true;
      renderCategoryProducts(categoryCache.get(activeCategory) || []);
    }

    function selectCategory(category, options) {
      options = options || {};
      if (!category) return;
      activeCategory = category;
      if (!options.keepSeries) activeSeries = null;
      if (!options.keepBrandSeries) activeBrandSeries = null;
      if (!options.keepNaturalStarch) activeNaturalStarchItem = null;
      if (!options.keepModifiedStarchSegment) activeModifiedStarchSegment = "retail";
      setActiveCategoryButton(category);
      renderSeriesChips();
      renderModifiedStarchChips();
      renderNaturalStarchChips();

      const cached = categoryCache.get(category);
      if (cached) {
        applyCategoryView();
        scrollProductsToTop();
        return;
      }

      if (categoryProducts) {
        categoryProducts.innerHTML = '<p class="touch-empty touch-loading-hint">載入中…</p>';
      }
      scrollProductsToTop();

      fetch(config.searchUrl + "?category=" + encodeURIComponent(category) + customerQuery(), {
        headers: { Accept: "application/json" },
      })
        .then(function (r) {
          if (!r.ok) throw new Error("fetch failed");
          return r.json();
        })
        .then(function (data) {
          const products = data.results || [];
          categoryCache.set(category, products);
          seedCatalog(products);
          applyCategoryView();
        })
        .catch(function () {
          if (categoryProducts) {
            categoryProducts.innerHTML = '<p class="touch-empty">無法載入分類，請稍後再試</p>';
          }
        });
    }

    function selectSeries(series) {
      if (!isFlourCategory(activeCategory)) return;
      activeSeries = series || null;
      renderSeriesChips();
      applyCategoryView();
    }

    function selectBrandSeries(seriesKey) {
      if (!isBrandFlourCategory(activeCategory)) return;
      activeBrandSeries = seriesKey || null;
      applyCategoryView();
    }

    function selectNaturalStarchItem(itemKey) {
      if (!isNaturalStarchCategory(activeCategory)) return;
      activeNaturalStarchItem = itemKey || null;
      renderNaturalStarchChips();
      applyCategoryView();
    }

    function selectModifiedStarchSegment(segmentKey) {
      if (!isModifiedStarchCategory(activeCategory)) return;
      activeModifiedStarchSegment = segmentKey === "formula" ? "formula" : "retail";
      renderModifiedStarchChips();
      applyCategoryView();
    }

    function initSuccessPanel() {
      const panel = document.getElementById("quick-order-success");
      const nextBtn = document.getElementById("quick-next-customer");
      if (!panel) return;
      clearDraft();
      if (nextBtn) {
        setTimeout(function () { nextBtn.focus(); }, 150);
        nextBtn.addEventListener("click", clearDraft);
      }
      panel.querySelectorAll("a").forEach(function (link) {
        link.addEventListener("click", clearDraft);
      });
    }

    form.addEventListener("click", function (e) {
      const quickAdd = e.target.closest(".touch-product-quick-add");
      if (quickAdd && form.contains(quickAdd)) {
        e.preventDefault();
        e.stopPropagation();
        const card = quickAdd.closest(".touch-product-card");
        if (!card) return;
        const qty = parseInt(quickAdd.dataset.add, 10) || 1;
        addProductQty(
          productFromCard(card),
          qty,
          card.dataset.price || defaultPrice(productFromCard(card))
        );
        return;
      }

      const lastItem = e.target.closest(".touch-last-order-item");
      if (copyPartialMode && lastItem && lastOrderGrid && lastOrderGrid.contains(lastItem)) {
        if (!e.target.closest(".touch-product-quick-add")) {
          e.preventDefault();
          lastItem.classList.toggle("touch-last-order-item--selected");
          updateCopySelectedBtn();
          return;
        }
      }

      const pickMain = e.target.closest(".touch-product-pick-main");
      if (pickMain && form.contains(pickMain)) {
        e.preventDefault();
        e.stopPropagation();
        if (copyPartialMode && pickMain.closest(".touch-last-order-item")) return;
        if (Date.now() - lastTouchPickAt < 400) return;
        const card = pickMain.closest(".touch-product-card");
        if (card) {
          addProductQty(
            productFromCard(card),
            1,
            card.dataset.price || defaultPrice(productFromCard(card))
          );
        } else {
          pickProductFromButton(pickMain);
        }
        return;
      }

      const pickBtn = e.target.closest(".touch-product-result");
      if (pickBtn && form.contains(pickBtn)) {
        e.preventDefault();
        e.stopPropagation();
        pickProductFromButton(pickBtn);
        return;
      }

      const catBtn = e.target.closest(".touch-category-btn");
      if (catBtn && categoryGrid && categoryGrid.contains(catBtn)) {
        e.preventDefault();
        selectCategory(catBtn.dataset.category);
        return;
      }

      const seriesBtn = e.target.closest("#series-chips .series-card");
      if (seriesBtn && seriesBtn.dataset.series) {
        e.preventDefault();
        selectSeries(seriesBtn.dataset.series);
        return;
      }

      const brandSeriesBtn = e.target.closest("[data-brand-series]");
      if (brandSeriesBtn && form.contains(brandSeriesBtn)) {
        e.preventDefault();
        selectBrandSeries(brandSeriesBtn.dataset.brandSeries);
        return;
      }

      const brandBackBtn = e.target.closest("[data-brand-flour-back]");
      if (brandBackBtn && form.contains(brandBackBtn)) {
        e.preventDefault();
        selectBrandSeries(null);
      }

      const naturalStarchBtn = e.target.closest("[data-natural-starch-item]");
      if (naturalStarchBtn && naturalStarchChips && naturalStarchChips.contains(naturalStarchBtn)) {
        e.preventDefault();
        selectNaturalStarchItem(naturalStarchBtn.dataset.naturalStarchItem);
        return;
      }

      const naturalStarchBackBtn = e.target.closest("[data-natural-starch-back]");
      if (naturalStarchBackBtn && form.contains(naturalStarchBackBtn)) {
        e.preventDefault();
        selectNaturalStarchItem(null);
        return;
      }

      const modifiedStarchBtn = e.target.closest("[data-modified-starch-segment]");
      if (
        modifiedStarchBtn &&
        modifiedStarchChips &&
        modifiedStarchChips.contains(modifiedStarchBtn)
      ) {
        e.preventDefault();
        selectModifiedStarchSegment(modifiedStarchBtn.dataset.modifiedStarchSegment);
        return;
      }

      const flourSeriesBackBtn = e.target.closest("[data-flour-series-back]");
      if (flourSeriesBackBtn && form.contains(flourSeriesBackBtn)) {
        e.preventDefault();
        selectSeries(null);
      }
    });

    form.addEventListener("touchend", function (e) {
      const target = e.target.closest(".touch-product-pick-main, .touch-product-quick-add, .touch-product-result");
      if (!target || !form.contains(target)) return;
      if (target.closest(".touch-product-quick-add")) return;
      e.preventDefault();
      lastTouchPickAt = Date.now();
      if (target.classList.contains("touch-product-pick-main")) {
        const card = target.closest(".touch-product-card");
        if (card && !(copyPartialMode && card.classList.contains("touch-last-order-item"))) {
          addProductQty(
            productFromCard(card),
            1,
            card.dataset.price || defaultPrice(productFromCard(card))
          );
        } else if (!card) {
          pickProductFromButton(target);
        }
      } else {
        pickProductFromButton(target);
      }
    }, { passive: false });

    if (copyLastBtn) {
      copyLastBtn.addEventListener("click", function (e) {
        e.preventDefault();
        copyLastOrder();
      });
    }

    if (copyPartialToggleBtn) {
      copyPartialToggleBtn.addEventListener("click", function (e) {
        e.preventDefault();
        if (copyPartialMode) exitCopyPartialMode();
        else enterCopyPartialMode();
      });
    }

    if (copySelectedBtn) {
      copySelectedBtn.addEventListener("click", function (e) {
        e.preventDefault();
        copySelectedLastOrder();
      });
    }

    function renderResults(products) {
      if (!searchResults) return;
      if (!products.length) {
        searchResults.innerHTML = '<p class="touch-product-results-empty">找不到產品</p>';
        searchResults.hidden = false;
        return;
      }
      searchResults.innerHTML =
        '<div class="touch-frequent-grid touch-search-results-grid">' +
        products.map(productCardHtml).join("") +
        "</div>";
      searchResults.hidden = false;
      scrollProductsToTop();
      syncPickToolbarGap();
    }

    function runSearch() {
      if (!searchInput) return;
      const q = searchInput.value.trim();
      if (!q) { hideResults(); return; }
      fetch(config.searchUrl + "?q=" + encodeURIComponent(q) + customerQuery(), {
        headers: { Accept: "application/json" },
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          seedCatalog(data.results || []);
          renderResults(data.results || []);
        })
        .catch(function () { hideResults(); });
    }

    if (searchInput) {
      searchInput.addEventListener("input", function () {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(runSearch, 120);
      });
      searchInput.addEventListener("focus", syncPickToolbarGap);
      searchInput.addEventListener("blur", function () {
        window.setTimeout(syncPickToolbarGap, 80);
      });
      searchInput.addEventListener("keydown", function (e) {
        if (e.key === "Enter") {
          e.preventDefault();
          const first = searchResults && searchResults.querySelector(".touch-product-quick-add[data-add='1']");
          if (first) first.click();
        }
      });
    }

    ["order_date", "delivery_date", "shipping_address", "notes", "special_instructions"].forEach(function (id) {
      const el = document.getElementById(id);
      if (el) el.addEventListener("change", saveDraft);
      if (el && el.tagName === "TEXTAREA") el.addEventListener("input", saveDraft);
    });

    form.addEventListener("submit", function (e) {
      syncHiddenInputs();
      if (!saveBtn || saveBtn.disabled) {
        e.preventDefault();
        showToast("請至少加入一項產品");
        return;
      }
      if (!saveConfirmPending) {
        e.preventDefault();
        showSaveConfirmModal();
        return;
      }
      isSubmitting = true;
      setSaveEnabled(false);
      saveBtn.textContent = "儲存中…";
      saveBtn.setAttribute("aria-disabled", "true");
      clearDraft();
    });

    if (removeCancelBtn) {
      removeCancelBtn.addEventListener("click", function (e) {
        e.preventDefault();
        hideRemoveConfirmModal();
      });
    }

    if (removeYesBtn) {
      removeYesBtn.addEventListener("click", function (e) {
        e.preventDefault();
        const fn = pendingRemoveConfirm;
        hideRemoveConfirmModal();
        if (fn) fn();
      });
    }

    if (saveConfirmCancelBtn) {
      saveConfirmCancelBtn.addEventListener("click", function (e) {
        e.preventDefault();
        hideSaveConfirmModal();
      });
    }

    if (saveConfirmSubmitBtn) {
      saveConfirmSubmitBtn.addEventListener("click", function (e) {
        e.preventDefault();
        hideSaveConfirmModal();
        saveConfirmPending = true;
        syncHiddenInputs();
        if (typeof form.requestSubmit === "function") {
          form.requestSubmit();
        } else {
          form.submit();
        }
      });
    }

    if (saveBtn) {
      saveBtn.addEventListener("click", function () {
        syncHiddenInputs();
      });
    }

    if (backLink) {
      backLink.addEventListener("click", function (e) {
        if (!hasUnsavedCart()) return;
        e.preventDefault();
        showLeaveModal(backLink.href);
      });
    }

    if (leaveContinueBtn) {
      leaveContinueBtn.addEventListener("click", function (e) {
        e.preventDefault();
        hideLeaveModal();
      });
    }

    if (leaveDraftBtn) {
      leaveDraftBtn.addEventListener("click", function (e) {
        e.preventDefault();
        saveDraft();
        navigateAway(pendingLeaveUrl || (backLink && backLink.href));
      });
    }

    if (leaveDiscardBtn) {
      leaveDiscardBtn.addEventListener("click", function (e) {
        e.preventDefault();
        clearDraft();
        navigateAway(pendingLeaveUrl || (backLink && backLink.href));
      });
    }

    window.addEventListener("beforeunload", function (e) {
      if (!hasUnsavedCart()) return;
      e.preventDefault();
      e.returnValue = "";
    });

    const hadInitial = (config.initialLines || []).length > 0;
    let draftRestored = false;

    if (config.savedOrder) {
      clearDraft();
      initSuccessPanel();
    } else if (hadInitial) {
      config.initialLines.forEach(function (item) {
        addLine(item, { quantity: item.quantity, unit_price: item.unit_price, replace: true, silent: true });
      });
    } else {
      draftRestored = loadDraft();
    }

    const defaultCategory = config.defaultCategory || "有信品牌粉";
    const defaultProducts = config.defaultCategoryProducts || [];
    if (defaultProducts.length) {
      categoryCache.set(defaultCategory, defaultProducts);
    }

    if (draftRestored && draftCategory) {
      activeSeries = draftSeries;
      activeBrandSeries = draftBrandSeries;
      activeNaturalStarchItem = draftNaturalStarchItem;
      activeModifiedStarchSegment = draftModifiedStarchSegment || "retail";
      selectCategory(draftCategory, {
        keepSeries: true,
        keepBrandSeries: true,
        keepNaturalStarch: true,
        keepModifiedStarchSegment: true,
      });
      if (draftSeries && isFlourCategory(draftCategory)) {
        selectSeries(draftSeries);
      }
      if (draftNaturalStarchItem && isNaturalStarchCategory(draftCategory)) {
        selectNaturalStarchItem(draftNaturalStarchItem);
      }
      if (isModifiedStarchCategory(draftCategory)) {
        selectModifiedStarchSegment(activeModifiedStarchSegment);
      }
    } else {
      selectCategory(defaultCategory);
    }

    if (pickToolbar && typeof ResizeObserver !== "undefined") {
      const toolbarObserver = new ResizeObserver(syncPickToolbarGap);
      toolbarObserver.observe(pickToolbar);
    }
    window.addEventListener("resize", syncPickToolbarGap);
    syncPickToolbarGap();

    window.__SALES_ORDER_TOUCH_READY = true;
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

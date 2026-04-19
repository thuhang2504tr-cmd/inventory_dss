from django.shortcuts import render, redirect, get_object_or_404
from functools import wraps
from .models import Product, Material, SalesData, Transaction
from .services import run_dss
from .services import forecast_product
from .services import abc_classification, forecast_product
from .models import Product, BOM
from datetime import datetime, timedelta, date


def session_name_required(view_func):
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        if not request.session.get('display_name'):
            return redirect('login')
        return view_func(request, *args, **kwargs)

    return wrapped_view


def login_view(request):
    if request.session.get('display_name'):
        return redirect('dashboard')

    error_message = None

    if request.method == 'POST':
        display_name = request.POST.get('display_name', '').strip()

        if display_name:
            request.session['display_name'] = display_name
            return redirect('dashboard')

        error_message = "Vui lòng nhập tên để tiếp tục."

    return render(request, 'inventory/login.html', {
        'error_message': error_message,
    })


def logout_view(request):
    request.session.pop('display_name', None)
    return redirect('login')

# =========================
# DASHBOARD (SALES + TRANSACTION)
# =========================
@session_name_required
def dashboard(request):

    # =========================
    # POST HANDLE
    # =========================
    if request.method == 'POST':

        # ===== ADD SALES =====
        if 'add_sales' in request.POST:
            product_id = request.POST.get('product_id')
            quantity = request.POST.get('quantity')
            date_input = request.POST.get('date')

            # ép kiểu quantity
            try:
                quantity = int(quantity)
            except:
                quantity = 0

            # ép kiểu date
            try:
                date_input = datetime.strptime(date_input, "%Y-%m-%d").date()
            except:
                date_input = None

            if product_id and quantity > 0 and date_input:
                SalesData.objects.create(
                    product_id=product_id,
                    quantity=quantity,
                    date=date_input
                )

        # ===== ADD TRANSACTION =====
        elif 'add_transaction' in request.POST:
            material_id = request.POST.get('material_id')
            quantity = request.POST.get('quantity')
            t_type = request.POST.get('transaction_type')
            date_input = request.POST.get('date')

            try:
                quantity = int(quantity)
            except:
                quantity = 0

            try:
                date_input = datetime.strptime(date_input, "%Y-%m-%d").date()
            except:
                date_input = None

            if material_id and quantity > 0 and date_input:
                material = Material.objects.get(id=material_id)

                # update tồn kho
                if t_type == 'IN':
                    material.on_hand += quantity
                elif t_type == 'OUT':
                    if material.on_hand >= quantity:
                        material.on_hand -= quantity

                material.save()

                # lưu transaction
                Transaction.objects.create(
                    material=material,
                    quantity=quantity,
                    transaction_type=t_type,
                    date=date_input
                )

    # =========================
    # GET DATA
    # =========================
    products = Product.objects.all()
    materials = Material.objects.all()

    # 👉 lấy mới nhất + ổn định thứ tự
    sales_list = SalesData.objects.all().order_by('-date', '-id')[:10]
    transaction_list = Transaction.objects.all().order_by('-id')[:10]

    # 👉 Gợi ý ngày nhập gần nhất
    last_sale = SalesData.objects.order_by('-date').first()

    if last_sale:
        min_date = last_sale.date.strftime("%Y-%m-%d")
    else:
        min_date = None

    today = date.today().strftime("%Y-%m-%d")

    return render(request, 'inventory/dashboard.html', {
        'products': products,
        'materials': materials,

        'total_products': products.count(),
        'total_materials': materials.count(),

        'sales_list': sales_list,
        'transaction_list': transaction_list,

        'min_date': min_date,
        'today': today,
    })


# =========================
# DELETE SALE
# =========================
@session_name_required
def delete_sale(request, id):
    sale = get_object_or_404(SalesData, id=id)
    sale.delete()
    return redirect('dashboard')


@session_name_required
def delete_transaction(request, id):
    t = get_object_or_404(Transaction, id=id)
    t.delete()
    return redirect('dashboard')


# =========================
# PRODUCT + DSS
# =========================
@session_name_required
def product_list(request):
    products = Product.objects.all()

    results = []
    selected_product = None

    if request.method == 'POST':
        product_id = request.POST.get('product_id')

        if product_id:
            selected_product = Product.objects.get(id=product_id)
            results = run_dss(product_id)

    return render(request, 'inventory/product_list.html', {
        'products': products,
        'results': results,
        'selected_product': selected_product,
    })


# =========================
# MATERIAL LIST
# =========================
@session_name_required
def material_list(request):
    materials = Material.objects.all()

    data = []
    for m in materials:
        data.append({
            'name': m.name,
            'on_hand': m.on_hand,
            'on_order': m.on_order,
            'inventory_position': m.on_hand + m.on_order,
            'leadtime': m.leadtime,
            'holding_cost': m.holding_cost,
            'ordering_cost': m.ordering_cost,
            'price_cost': m.price_cost,
        })

    return render(request, 'inventory/material_list.html', {
        'materials': data
    })


# =========================
# OTHER PAGES
# =========================
@session_name_required
def alert(request):
    from .models import Product, BOM
    from .services import forecast_product

    alerts = []

    products = Product.objects.all()

    for p in products:
        mean, std, forecast_7,_,_,_ = forecast_product(p.id)

        boms = BOM.objects.filter(product=p)

        for bom in boms:
            material = bom.material

            # ===== Demand =====
            demand = mean * bom.quantity_per_unit

            # ===== giả sử bạn có tồn kho =====
            ip = material.on_hand + material.on_order  # ⚠️ cần field này trong model Material

            # ===== tính ROP =====
            lead_time = max(material.leadtime, 1)
            z = 1.65  # service level 95%

            material_std = std * bom.quantity_per_unit
            rop = demand * lead_time + z * material_std * (lead_time ** 0.5)

            # ===== CHECK =====
            if ip < rop:
                alerts.append({
                    "product": p.name,
                    "material": material.name,
                    "rop": round(rop, 2),
                    "ip": round(ip, 2),
                    "status": "ORDER"
                })

    return render(request, 'inventory/alert.html', {
        "alerts": alerts
    })


@session_name_required
def forecast(request):
    from .models import Product, BOM
    from .services import forecast_product
    from collections import defaultdict
    import math

    products = Product.objects.all()

    selected_product = None
    product_result = None
    material_results = []
    forecast_7 = []

    # =========================
    # PRODUCT FORECAST
    # =========================
    if request.method == 'POST':
        product_id = request.POST.get('product_id')

        if product_id:
            selected_product = Product.objects.get(id=product_id)

            mean, std, forecast_7, mae, rmse, mape = forecast_product(product_id)

            product_result = {
                "name": selected_product.name,
                "mean": round(mean, 2),
                "std": round(std, 2),
                "forecast_7": [round(x, 2) for x in forecast_7],
                "mae": round(mae, 2),
                "rmse": round(rmse, 2),
                "mape": round(mape, 2),
            }

    # =========================
    # 🔥 MATERIAL AGGREGATE (LUÔN CHẠY)
    # =========================
    material_dict = defaultdict(lambda: {
        "mean": 0,
        "variance": 0,
        "forecast_7": [0] * 7
    })

    for product in Product.objects.all():
        p_mean, p_std, p_f7, *_ = forecast_product(product.id)

        boms = BOM.objects.filter(product=product)

        for bom in boms:
            m = bom.material.name

            material_dict[m]["mean"] += p_mean * bom.quantity_per_unit
            material_dict[m]["variance"] += (p_std * bom.quantity_per_unit) ** 2

            for i in range(7):
                material_dict[m]["forecast_7"][i] += p_f7[i] * bom.quantity_per_unit

    # convert
    # 🔥 chỉ lấy material thuộc product đang chọn
    selected_materials = BOM.objects.filter(product=selected_product) \
        .values_list('material__name', flat=True)

    material_results = []

    for m, data in material_dict.items():
        if m in selected_materials:  # 👈 CHỈ HIỂN THỊ MATERIAL CỦA PRODUCT ĐANG CHỌN
            material_results.append({
                "material": m,
                "mean": round(data["mean"], 2),
                "std": round(math.sqrt(data["variance"]), 2),
                "forecast_7": [round(x, 2) for x in data["forecast_7"]]
            })

    # =========================
    # 🔥 LUÔN RETURN
    # =========================
    return render(request, 'inventory/forecast.html', {
        "products": products,
        "selected_product": selected_product,
        "product_result": product_result,
        "material_results": material_results,
        "forecast_7": forecast_7
    })
from .services import abc_classification, forecast_product
from .models import Product, BOM

@session_name_required
def abc_page(request):
    from .models import Product, Material, Transaction, BOM
    from django.db.models import Sum
    from .services import abc_classification

    products = Product.objects.all()

    product_id = request.GET.get("product_id")
    abc_filter = request.GET.get("abc")

    selected_product = None
    results = []

    # =========================
    # 🔵 1. ABC TOÀN HỆ THỐNG (THEO TRANSACTION - TỐI ƯU)
    # =========================
    material_list = []

    # 👉 gom transaction 1 lần (KHÔNG loop)
    transaction_data = (
        Transaction.objects
        .filter(transaction_type='OUT')
        .values('material')
        .annotate(total=Sum('quantity'))
    )

    # 👉 convert thành dict cho nhanh
    demand_map = {
        item['material']: item['total']
        for item in transaction_data
    }

    materials = Material.objects.all()

    for m in materials:
        demand = demand_map.get(m.id, 0)

        material_list.append({
            "material": m,
            "demand": demand  # 🔥 giữ tên mean cho abc_classification
        })

    # 👉 ABC
    abc_all = abc_classification(material_list)

    # 👉 đếm tổng
    abc_total = {"A": 0, "B": 0, "C": 0}

    for item in material_list:
        m = item["material"]
        cat = abc_all.get(m.id)

        if cat:
            abc_total[cat] += 1

    # =========================
    # 🔴 FILTER MATERIAL
    # =========================
    filtered_materials = []

    for item in material_list:
        m = item["material"]
        demand = item["demand"]
        abc = abc_all.get(m.id, "-")

        if not abc_filter or abc == abc_filter:
            filtered_materials.append({
                "material": m.name,
                "demand": demand,
                "price": m.price_cost,
                "value": demand * m.price_cost,
                "abc": abc
            })

    # =========================
    # 🟢 ABC THEO PRODUCT
    # =========================
    if product_id:
        selected_product = Product.objects.get(id=product_id)

        boms = BOM.objects.filter(product=selected_product).select_related('material')

        for bom in boms:
            m = bom.material
            demand = demand_map.get(m.id, 0)

            results.append({
                "material": m.name,
                "demand": demand,
                "price": m.price_cost,
                "value": demand * m.price_cost,
                "abc": abc_all.get(m.id, "-")
            })

    return render(request, "inventory/abc.html", {
        "products": products,
        "selected_product": selected_product,
        "results": results,
        "filtered_materials": filtered_materials,
        "abc_total": abc_total,
        "selected_abc": abc_filter
    })


@session_name_required
def system_settings(request):
    return render(request, "inventory/system_settings.html")

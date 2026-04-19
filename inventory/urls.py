from django.urls import path
from .views import (
    login_view,
    logout_view,
    dashboard,
    material_list,
    product_list,
    alert,
    forecast,
    abc_page,
    delete_sale,
    delete_transaction,
)

urlpatterns = [
    path('', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('dashboard/', dashboard, name='dashboard'),

    path('materials/', material_list, name='material-list'),
    path('products/', product_list, name='product-list'),

    path('alert/', alert, name='alert'),
    path('forecast/', forecast, name='forecast'),
    path('abc/', abc_page, name='abc'),
    path('delete-sale/<int:id>/', delete_sale, name='delete_sale'),
    path('delete-transaction/<int:id>/', delete_transaction, name='delete_transaction'),
]

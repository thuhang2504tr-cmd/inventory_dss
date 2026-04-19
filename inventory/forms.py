from django import forms
from .models import Material, Transaction

class MaterialForm(forms.ModelForm):
    class Meta:
        model = Material
        fields = ['code', 'name', 'unit_price', 'ordering_cost', 'holding_cost', 'lead_time']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control'}),
            'ordering_cost': forms.NumberInput(attrs={'class': 'form-control'}),
            'holding_cost': forms.NumberInput(attrs={'class': 'form-control'}),
            'lead_time': forms.NumberInput(attrs={'class': 'form-control'}),
        }

class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['material', 'quantity', 'transaction_type', 'date']
        widgets = {
            'quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            'transaction_type': forms.Select(attrs={'class': 'form-control'}),
            'date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
        }
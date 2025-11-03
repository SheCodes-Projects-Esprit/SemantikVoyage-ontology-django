from django.contrib import admin
from .models import Company


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "industry", "employee_count", "annual_revenue_musd")
    search_fields = ("name", "industry")


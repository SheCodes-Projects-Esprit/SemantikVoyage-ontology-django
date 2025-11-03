from django.db import models


class Company(models.Model):
    name = models.CharField(max_length=150, unique=True)
    industry = models.CharField(max_length=100, blank=True, null=True)
    employee_count = models.IntegerField(blank=True, null=True)
    annual_revenue_musd = models.FloatField(blank=True, null=True)

    def __str__(self):
        return self.name


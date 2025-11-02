from django.db import models

class ItineraryBase(models.Model):
    itinerary_id = models.CharField(max_length=50, unique=True)
    overall_status = models.CharField(max_length=50, default='Planned')
    total_cost_estimate = models.FloatField(null=True, blank=True)
    total_duration_days = models.IntegerField(null=True, blank=True)

    class Meta:
        abstract = True

    def to_rdf_triples(self):
        triples = [f'  :{self.itinerary_id} a :Itinerary ;']
        triples.append(f'    :itineraryID "{self.itinerary_id}" ;')
        if self.overall_status:
            triples.append(f'    :overallStatus "{self.overall_status}" ;')
        if self.total_cost_estimate:
            triples.append(f'    :totalCostEstimate {self.total_cost_estimate:.2f} ;')
        if self.total_duration_days:
            triples.append(f'    :totalDurationDays {self.total_duration_days} .')
        return ' ;\n'.join(triples)

class BusinessTrip(ItineraryBase):
    client_project_name = models.CharField(max_length=200)
    expense_limit = models.FloatField(null=True, blank=True)
    purpose_code = models.CharField(max_length=20)
    approval_required = models.BooleanField(default=False)

    def to_rdf_triples(self):
        base = super().to_rdf_triples()
        extras = [
            f':clientProjectName "{self.client_project_name}" ;',
            f':expenseLimit {self.expense_limit:.2f} ;' if self.expense_limit else '',
            f':purposeCode "{self.purpose_code}" ;',
            f':approvalRequired {str(self.approval_required).lower()} .'
        ]
        return base + ' ;\n' + ' ;\n'.join([e for e in extras if e])

class LeisureTrip(ItineraryBase):
    activity_type = models.CharField(max_length=100)
    accommodation = models.CharField(max_length=200, null=True, blank=True)
    budget_per_day = models.FloatField(null=True, blank=True)
    group_size = models.IntegerField(null=True, blank=True)

    def to_rdf_triples(self):
        base = super().to_rdf_triples()
        extras = [
            f':activityType "{self.activity_type}" ;',
            f':accommodation "{self.accommodation}" ;' if self.accommodation else '',
            f':budgetPerDay {self.budget_per_day:.2f} ;' if self.budget_per_day else '',
            f':groupSize {self.group_size} .'
        ]
        return base + ' ;\n' + ' ;\n'.join([e for e in extras if e])

class EducationalTrip(ItineraryBase):
    institution = models.CharField(max_length=200)
    course_reference = models.CharField(max_length=50)
    credit_hours = models.IntegerField(null=True, blank=True)
    required_documentation = models.TextField(null=True, blank=True)

    def to_rdf_triples(self):
        base = super().to_rdf_triples()
        extras = [
            f':institution "{self.institution}" ;',
            f':courseReference "{self.course_reference}" ;',
            f':creditHours {self.credit_hours} ;' if self.credit_hours else '',
            f':requiredDocumentation "{self.required_documentation}" .'
        ]
        return base + ' ;\n' + ' ;\n'.join([e for e in extras if e])
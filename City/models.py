from django.db import models

class CityBase(models.Model):
    name = models.CharField(max_length=100, unique=True)
    overall_status = models.CharField(max_length=50, default='Planned')
    population = models.IntegerField(null=True, blank=True)
    area_km2 = models.FloatField(null=True, blank=True)

    class Meta:
        abstract = True

    def to_rdf_triples(self):
        safe_name = str(self.name).replace(' ', '_')
        triples = [f' :city_{safe_name} a :City ;']
        triples.append(f' :cityName "{self.name}" ;')
        if self.overall_status:
            triples.append(f' :overallStatus "{self.overall_status}" ;')
        if self.population:
            triples.append(f' :population {self.population} ;')
        if self.area_km2:
            triples.append(f' :area {self.area_km2:.2f} .')
        return ' ;\n'.join(triples)

class CapitalCity(CityBase):
    government_seat = models.BooleanField(default=True)
    ministries = models.IntegerField(null=True, blank=True)

    def to_rdf_triples(self):
        base = super().to_rdf_triples()
        extras = [
            f':governmentSeat {str(self.government_seat).lower()} ;',
            f':numberOfMinistries {self.ministries} .' if self.ministries else ''
        ]
        return base + ' ;\n' + ' ;\n'.join([e for e in extras if e])

class MetropolitanCity(CityBase):
    districts = models.IntegerField(null=True, blank=True)
    commute_minutes = models.FloatField(null=True, blank=True)

    def to_rdf_triples(self):
        base = super().to_rdf_triples()
        extras = [
            f':numberOfDistricts {self.districts} ;' if self.districts else '',
            f':averageCommuteTime {self.commute_minutes:.1f} .' if self.commute_minutes else ''
        ]
        return base + ' ;\n' + ' ;\n'.join([e for e in extras if e])

class TouristicCity(CityBase):
    annual_visitors = models.IntegerField(null=True, blank=True)
    hotels = models.IntegerField(null=True, blank=True)

    def to_rdf_triples(self):
        base = super().to_rdf_triples()
        extras = [
            f':annualVisitors {self.annual_visitors} ;' if self.annual_visitors else '',
            f':hotelCount {self.hotels} .' if self.hotels else ''
        ]
        return base + ' ;\n' + ' ;\n'.join([e for e in extras if e])

class IndustrialCity(CityBase):
    factories = models.IntegerField(null=True, blank=True)
    pollution_index = models.FloatField(null=True, blank=True)

    def to_rdf_triples(self):
        base = super().to_rdf_triples()
        extras = [
            f':numberOfFactories {self.factories} ;' if self.factories else '',
            f':pollutionIndex {self.pollution_index:.1f} .' if self.pollution_index else ''
        ]
        return base + ' ;\n' + ' ;\n'.join([e for e in extras if e])
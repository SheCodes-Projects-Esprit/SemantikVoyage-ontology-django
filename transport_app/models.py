# transport_app/models.py
from django.db import models
from django.core.exceptions import ValidationError


# === CITY ===
class City(models.Model):
    city_name = models.CharField(max_length=255, unique=True)
    population = models.IntegerField(null=True, blank=True)
    area = models.FloatField(null=True, blank=True)
    region = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.city_name

    class Meta:
        verbose_name_plural = "Cities"


# === COMPANY ===
class Company(models.Model):
    company_name = models.CharField(max_length=255, unique=True)
    founded_year = models.IntegerField(null=True, blank=True)
    number_of_employees = models.IntegerField(null=True, blank=True)
    headquarters_location = models.CharField(max_length=255, null=True, blank=True)
    based_in = models.ForeignKey(City, on_delete=models.SET_NULL, null=True, blank=True, related_name='companies')

    @classmethod
    def get_subclass(cls, pk):
        for subclass in cls.__subclasses__():
            try:
                return subclass.objects.get(pk=pk)
            except subclass.DoesNotExist:
                continue
        raise cls.DoesNotExist(f"No {cls.__name__} with pk={pk}")

    def __str__(self):
        return self.company_name


class BusCompany(Company):
    number_of_bus_lines = models.IntegerField(null=True, blank=True)
    average_bus_age = models.FloatField(null=True, blank=True)
    ticket_price = models.FloatField(null=True, blank=True)
    eco_friendly_fleet = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Bus Company"
        verbose_name_plural = "Bus Companies"


class MetroCompany(Company):
    number_of_lines = models.IntegerField(null=True, blank=True)
    total_track_length = models.FloatField(null=True, blank=True)
    automation_level = models.CharField(max_length=255, null=True, blank=True)
    daily_passengers = models.IntegerField(null=True, blank=True)

    class Meta:
        verbose_name = "Metro Company"
        verbose_name_plural = "Metro Companies"


# === SCHEDULE ===
class Schedule(models.Model):
    schedule_id = models.CharField(max_length=50, unique=True)
    effective_date = models.DateField(null=True, blank=True)
    is_public = models.BooleanField(default=True)
    route_name = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"{self.schedule_id} - {self.route_name or 'No Route'}"

    class Meta:
        verbose_name = "Schedule"


class DailySchedule(Schedule):
    first_run_time = models.TimeField(null=True, blank=True)
    last_run_time = models.TimeField(null=True, blank=True)
    frequency_minutes = models.IntegerField(null=True, blank=True)
    day_of_week_mask = models.IntegerField(null=True, blank=True)

    class Meta:
        verbose_name = "Daily Schedule"


# === STATION ===
class Station(models.Model):
    station_name = models.CharField(max_length=255)
    station_location = models.CharField(max_length=255, null=True, blank=True)
    station_accessibility = models.BooleanField(default=False)
    located_in = models.ForeignKey(City, on_delete=models.SET_NULL, null=True, blank=True, related_name='stations')
    connected_to = models.ManyToManyField('self', symmetrical=True, blank=True)

    @classmethod
    def get_subclass(cls, pk):
        for subclass in cls.__subclasses__():
            try:
                return subclass.objects.get(pk=pk)
            except subclass.DoesNotExist:
                continue
        raise cls.DoesNotExist(f"No {cls.__name__} with pk={pk}")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['station_name', 'located_in'], name='unique_station_per_city')
        ]

    def __str__(self):
        return self.station_name

    def get_type(self):
        return self.__class__.__name__


class BusStop(Station):
    class Meta:
        proxy = False
        verbose_name = "Bus Stop"


class MetroStation(Station):
    class Meta:
        proxy = False
        verbose_name = "Metro Station"


class TrainStation(Station):
    class Meta:
        proxy = False
        verbose_name = "Train Station"


class TramStation(Station):
    class Meta:
        proxy = False
        verbose_name = "Tram Station"


# === TRANSPORT ===
class Transport(models.Model):
    transport_line_number = models.CharField(max_length=50, unique=True)
    transport_capacity = models.IntegerField(null=True, blank=True)
    transport_speed = models.FloatField(null=True, blank=True)
    transport_frequency = models.IntegerField(null=True, blank=True)

    operates_in = models.ManyToManyField(City, related_name='%(class)s_transports', blank=True)
    departs_from = models.ForeignKey(Station, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_departures')
    arrives_at = models.ForeignKey(Station, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_arrivals')
    operated_by = models.ForeignKey(Company, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_operated')
    applies_to = models.ForeignKey(Schedule, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_schedules')

    class Meta:
        abstract = False

    def __str__(self):
        return self.transport_line_number

    def get_type(self):
        return self.__class__.__name__


class Bus(Transport):
    def clean(self):
        if self.departs_from and not isinstance(self.departs_from, BusStop):
            raise ValidationError("Un Bus doit partir d'un BusStop.")
        if self.arrives_at and not isinstance(self.arrives_at, BusStop):
            raise ValidationError("Un Bus doit arriver à un BusStop.")
        if self.operated_by and not isinstance(self.operated_by, BusCompany):
            raise ValidationError("Un Bus doit être opéré par une BusCompany.")

    class Meta:
        verbose_name = "Bus"
        verbose_name_plural = "Buses"


class Metro(Transport):
    def clean(self):
        if self.departs_from and not isinstance(self.departs_from, MetroStation):
            raise ValidationError("Un Métro doit partir d'une MetroStation.")
        if self.arrives_at and not isinstance(self.arrives_at, MetroStation):
            raise ValidationError("Un Métro doit arriver à une MetroStation.")
        if self.operated_by and not isinstance(self.operated_by, MetroCompany):
            raise ValidationError("Un Métro doit être opéré par une MetroCompany.")

    class Meta:
        verbose_name = "Metro"
        verbose_name_plural = "Metros"


class Train(Transport):
    def clean(self):
        if self.departs_from and not isinstance(self.departs_from, TrainStation):
            raise ValidationError("Un Train doit partir d'une TrainStation.")
        if self.arrives_at and not isinstance(self.arrives_at, TrainStation):
            raise ValidationError("Un Train doit arriver à une TrainStation.")

    class Meta:
        verbose_name = "Train"
        verbose_name_plural = "Trains"


class Tram(Transport):
    def clean(self):
        if self.departs_from and not isinstance(self.departs_from, TramStation):
            raise ValidationError("Un Tram doit partir d'une TramStation.")
        if self.arrives_at and not isinstance(self.arrives_at, TramStation):
            raise ValidationError("Un Tram doit arriver à une TramStation.")

    class Meta:
        verbose_name = "Tram"
        verbose_name_plural = "Trams"
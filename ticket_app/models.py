# ticket_app/models.py
from django.db import models
from django.core.exceptions import ValidationError
from transport_app.models import Person, Transport


# === TICKET ===
class Ticket(models.Model):
    """Classe de base pour Ticket"""
    has_ticket_id = models.CharField(max_length=50, unique=True, help_text="Identifiant unique du ticket")
    has_price = models.FloatField(null=True, blank=True, help_text="Prix du ticket")
    has_validity_duration = models.CharField(max_length=100, null=True, blank=True, help_text="Durée de validité")
    has_purchase_date = models.DateField(null=True, blank=True, help_text="Date d'achat")
    has_expiration_date = models.DateField(null=True, blank=True, help_text="Date d'expiration")
    is_reduced_fare = models.BooleanField(default=False, help_text="Tarif réduit")
    
    # Relations
    owned_by = models.ForeignKey(Person, on_delete=models.SET_NULL, null=True, blank=True, related_name='tickets', help_text="Propriétaire du ticket")
    valid_for = models.ForeignKey(Transport, on_delete=models.SET_NULL, null=True, blank=True, related_name='valid_tickets', help_text="Transport pour lequel le ticket est valide")

    @classmethod
    def get_subclass(cls, pk):
        """Récupère l'instance de la sous-classe appropriée"""
        for subclass in cls.__subclasses__():
            try:
                return subclass.objects.get(pk=pk)
            except subclass.DoesNotExist:
                continue
        raise cls.DoesNotExist(f"No {cls.__name__} with pk={pk}")

    def __str__(self):
        return f"{self.has_ticket_id} - {self.get_type()}"

    def get_type(self):
        return self.__class__.__name__

    class Meta:
        verbose_name = "Ticket"
        verbose_name_plural = "Tickets"


class TicketSimple(Ticket):
    """Ticket Simple - Sous-classe de Ticket"""
    is_used = models.BooleanField(default=False, help_text="Ticket utilisé ou non")

    class Meta:
        verbose_name = "Ticket Simple"
        verbose_name_plural = "Tickets Simples"


class TicketSenior(Ticket):
    """Ticket Senior - Sous-classe de Ticket"""
    has_age_condition = models.IntegerField(null=True, blank=True, help_text="Condition d'âge minimum")

    class Meta:
        verbose_name = "Ticket Senior"
        verbose_name_plural = "Tickets Senior"


class TicketÉtudiant(Ticket):
    """Ticket Étudiant - Sous-classe de Ticket"""
    has_institution_name = models.CharField(max_length=255, null=True, blank=True, help_text="Nom de l'institution")
    has_student_id = models.CharField(max_length=50, null=True, blank=True, help_text="Numéro d'étudiant")

    class Meta:
        verbose_name = "Ticket Étudiant"
        verbose_name_plural = "Tickets Étudiant"


class AbonnementHebdomadaire(Ticket):
    """Abonnement Hebdomadaire - Sous-classe de Ticket"""
    has_start_date = models.DateField(null=True, blank=True, help_text="Date de début")
    has_end_date = models.DateField(null=True, blank=True, help_text="Date de fin")
    has_zone_access = models.CharField(max_length=100, null=True, blank=True, help_text="Zone d'accès")

    class Meta:
        verbose_name = "Abonnement Hebdomadaire"
        verbose_name_plural = "Abonnements Hebdomadaires"


class AbonnementMensuel(Ticket):
    """Abonnement Mensuel - Sous-classe de Ticket"""
    has_month = models.CharField(max_length=20, null=True, blank=True, help_text="Mois de l'abonnement")
    has_auto_renewal = models.BooleanField(default=False, help_text="Renouvellement automatique")
    has_payment_method = models.CharField(max_length=50, null=True, blank=True, help_text="Méthode de paiement")

    class Meta:
        verbose_name = "Abonnement Mensuel"
        verbose_name_plural = "Abonnements Mensuels"


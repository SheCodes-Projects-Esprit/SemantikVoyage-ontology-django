import rdflib
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, XSD
from django.conf import settings
import requests  # ← AJOUTEZ CET IMPORT MANQUANT
from transport_app.models import (
    Station, BusStop, MetroStation, TrainStation, TramStation,
    Transport, Bus, Metro, Train, Tram, City, Company,
    BusCompany, MetroCompany, Person, Conducteur, Contrôleur, EmployéAgence, Passager
)
try:
    from ticket_app.models import (
        Ticket, TicketSimple, TicketSenior, TicketÉtudiant,
        AbonnementHebdomadaire, AbonnementMensuel
    )
    TICKET_APP_AVAILABLE = True
except ImportError:
    TICKET_APP_AVAILABLE = False

# Namespaces
ONTOLOGY = Namespace("http://www.transport-ontology.org/travel#")

class OntologySyncService:
    def __init__(self):
        self.graph = Graph()
        self.graph.bind("", ONTOLOGY)
    
    def station_to_rdf(self, station):
        """Convert Station instance to RDF"""
        station_uri = URIRef(f"{ONTOLOGY}station_{station.id}")
        
        # Determine station type
        if isinstance(station, BusStop):
            station_type = ONTOLOGY.BusStop
        elif isinstance(station, MetroStation):
            station_type = ONTOLOGY.MetroStation
        elif isinstance(station, TrainStation):
            station_type = ONTOLOGY.TrainStation
        elif isinstance(station, TramStation):
            station_type = ONTOLOGY.TramStation
        else:
            station_type = ONTOLOGY.Station
        
        # Add triples
        self.graph.add((station_uri, RDF.type, station_type))
        self.graph.add((station_uri, ONTOLOGY.Station_hasName, Literal(station.station_name)))
        
        if station.station_location:
            self.graph.add((station_uri, ONTOLOGY.Station_hasLocation, Literal(station.station_location)))
        
        self.graph.add((station_uri, ONTOLOGY.Station_hasAccessibility, Literal(station.station_accessibility)))
        
        if station.located_in:
            city_uri = URIRef(f"{ONTOLOGY}city_{station.located_in.id}")
            self.graph.add((station_uri, ONTOLOGY.locatedIn, city_uri))
            # Also add city data
            self._add_city_to_graph(station.located_in)
        
        return station_uri
    
    def _add_city_to_graph(self, city):
        """Add city data to graph"""
        city_uri = URIRef(f"{ONTOLOGY}city_{city.id}")
        self.graph.add((city_uri, RDF.type, ONTOLOGY.City))
        self.graph.add((city_uri, ONTOLOGY.cityName, Literal(city.city_name)))
        
        if city.population:
            self.graph.add((city_uri, ONTOLOGY.population, Literal(city.population)))
        
        if city.area:
            self.graph.add((city_uri, ONTOLOGY.area, Literal(city.area)))
        
        if city.region:
            self.graph.add((city_uri, ONTOLOGY.region, Literal(city.region)))
        
        return city_uri
    
    def transport_to_rdf(self, transport):
        """Convert Transport instance to RDF"""
        transport_uri = URIRef(f"{ONTOLOGY}{transport.__class__.__name__}_{transport.transport_line_number}")
        
        # Determine transport type
        if isinstance(transport, Bus):
            transport_type = ONTOLOGY.Bus
        elif isinstance(transport, Metro):
            transport_type = ONTOLOGY.Metro
        elif isinstance(transport, Train):
            transport_type = ONTOLOGY.Train
        elif isinstance(transport, Tram):
            transport_type = ONTOLOGY.Tram
        else:
            transport_type = ONTOLOGY.Transport
        
        # Add triples
        self.graph.add((transport_uri, RDF.type, transport_type))
        self.graph.add((transport_uri, ONTOLOGY.Transport_hasLineNumber, Literal(transport.transport_line_number)))
        
        if transport.transport_capacity:
            self.graph.add((transport_uri, ONTOLOGY.Transport_hasCapacity, Literal(transport.transport_capacity)))
        
        if transport.transport_speed:
            self.graph.add((transport_uri, ONTOLOGY.Transport_hasSpeed, Literal(transport.transport_speed)))
        
        if transport.transport_frequency:
            self.graph.add((transport_uri, ONTOLOGY.Transport_hasFrequency, Literal(transport.transport_frequency)))
        
        # Departure station
        if transport.departs_from:
            dep_station_uri = self.station_to_rdf(transport.departs_from)
            self.graph.add((transport_uri, ONTOLOGY.departsFrom, dep_station_uri))
        
        # Arrival station
        if transport.arrives_at:
            arr_station_uri = self.station_to_rdf(transport.arrives_at)
            self.graph.add((transport_uri, ONTOLOGY.arrivesAt, arr_station_uri))
        
        # Operating company
        if transport.operated_by:
            company_uri = URIRef(f"{ONTOLOGY}{transport.operated_by.__class__.__name__}_{transport.operated_by.id}")
            self.graph.add((transport_uri, ONTOLOGY.operatedBy, company_uri))
            # Also add company data
            self._add_company_to_graph(transport.operated_by)
        
        # Operating cities
        for city in transport.operates_in.all():
            city_uri = URIRef(f"{ONTOLOGY}city_{city.id}")
            self.graph.add((transport_uri, ONTOLOGY.operatesIn, city_uri))
            self._add_city_to_graph(city)
        
        return transport_uri
    
    def _add_company_to_graph(self, company):
        """Add company data to graph"""
        company_uri = URIRef(f"{ONTOLOGY}{company.__class__.__name__}_{company.id}")
        
        if isinstance(company, BusCompany):
            company_type = ONTOLOGY.BusCompany
        elif isinstance(company, MetroCompany):
            company_type = ONTOLOGY.MetroCompany
        else:
            company_type = ONTOLOGY.Company
        
        self.graph.add((company_uri, RDF.type, company_type))
        self.graph.add((company_uri, ONTOLOGY.companyName, Literal(company.company_name)))
        
        if company.founded_year:
            self.graph.add((company_uri, ONTOLOGY.foundedYear, Literal(company.founded_year)))
        
        if company.number_of_employees:
            self.graph.add((company_uri, ONTOLOGY.numberOfEmployees, Literal(company.number_of_employees)))
        
        if company.headquarters_location:
            self.graph.add((company_uri, ONTOLOGY.headquartersLocation, Literal(company.headquarters_location)))
        
        if company.based_in:
            city_uri = URIRef(f"{ONTOLOGY}city_{company.based_in.id}")
            self.graph.add((company_uri, ONTOLOGY.basedIn, city_uri))
            self._add_city_to_graph(company.based_in)
        
        return company_uri
    
    def sync_station_to_ontology(self, station):
        """Sync a single station to ontology"""
        self.graph = Graph()  # Reset graph
        self.graph.bind("", ONTOLOGY)
        station_uri = self.station_to_rdf(station)
        self._upload_to_fuseki()
        return station_uri
    
    def sync_transport_to_ontology(self, transport):
        """Sync a single transport to ontology"""
        self.graph = Graph()  # Reset graph
        self.graph.bind("", ONTOLOGY)
        transport_uri = self.transport_to_rdf(transport)
        self._upload_to_fuseki()
        return transport_uri
    
    def sync_all_data(self):
        """Sync all stations and transports to ontology"""
        self.graph = Graph()  # Reset graph
        self.graph.bind("", ONTOLOGY)
        
        # Sync all stations
        for station_class in [BusStop, MetroStation, TrainStation, TramStation]:
            for station in station_class.objects.all():
                self.station_to_rdf(station)
        
        # Sync all transports
        for transport_class in [Bus, Metro, Train, Tram]:
            for transport in transport_class.objects.all():
                self.transport_to_rdf(transport)
        
        result = self._upload_to_fuseki()
        return f"Synced {len(self.graph)} triples to ontology"
    
    def _upload_to_fuseki(self):
        """Upload current graph to Fuseki"""
        try:
            if not hasattr(settings, 'FUSEKI_URL'):
                raise Exception("FUSEKI_URL not configured in settings")
            
            rdf_data = self.graph.serialize(format='turtle')
            
            # Upload to Fuseki
            upload_url = f"{settings.FUSEKI_URL}/{settings.FUSEKI_DATASET}/data"
            if hasattr(settings, 'FUSEKI_GRAPH') and settings.FUSEKI_GRAPH:
                upload_url += f"?graph={settings.FUSEKI_GRAPH}"
            
            headers = {'Content-Type': 'text/turtle'}
            response = requests.post(upload_url, data=rdf_data.encode('utf-8'), headers=headers, timeout=30)
            
            if response.status_code != 200:
                raise Exception(f"Fuseki upload failed: {response.status_code} - {response.text}")
            
            return response
            
        except Exception as e:
            raise Exception(f"Erreur lors de l'upload vers Fuseki: {e}")

    def delete_station_from_ontology(self, station):
        """Delete station from ontology"""
        station_uri = f"{ONTOLOGY}station_{station.id}"
        delete_query = f"""
        PREFIX : <{ONTOLOGY}>
        DELETE WHERE {{
            <{station_uri}> ?p ?o .
        }}
        """
        from core.utils.fuseki import sparql_update
        sparql_update(delete_query)
    
    def delete_transport_from_ontology(self, transport):
        """Delete transport from ontology"""
        transport_uri = f"{ONTOLOGY}{transport.__class__.__name__}_{transport.transport_line_number}"
        delete_query = f"""
        PREFIX : <{ONTOLOGY}>
        DELETE WHERE {{
            <{transport_uri}> ?p ?o .
        }}
        """
        from core.utils.fuseki import sparql_update
        sparql_update(delete_query)    
    def person_to_rdf(self, person):
        """Convert Person instance to RDF"""
        # Utiliser has_id pour créer un URI stable
        person_id = person.has_id.replace('-', '_').replace(' ', '_')
        person_uri = URIRef(f"{ONTOLOGY}person_{person_id}")
        
        # Déterminer le type de personne
        if isinstance(person, Conducteur):
            person_type = ONTOLOGY.Conducteur
        elif isinstance(person, Contrôleur):
            person_type = ONTOLOGY.Contrôleur
        elif isinstance(person, EmployéAgence):
            person_type = ONTOLOGY.EmployéAgence
        elif isinstance(person, Passager):
            person_type = ONTOLOGY.Passager
        else:
            person_type = ONTOLOGY.Person
        
        # Ajouter les triples de base
        self.graph.add((person_uri, RDF.type, person_type))
        self.graph.add((person_uri, ONTOLOGY.hasID, Literal(person.has_id)))
        self.graph.add((person_uri, ONTOLOGY.hasName, Literal(person.has_name)))
        
        if person.has_age:
            self.graph.add((person_uri, ONTOLOGY.hasAge, Literal(person.has_age, datatype=XSD.integer)))
        
        if person.has_email:
            self.graph.add((person_uri, ONTOLOGY.hasEmail, Literal(person.has_email)))
        
        if person.has_phone_number:
            self.graph.add((person_uri, ONTOLOGY.hasPhoneNumber, Literal(person.has_phone_number)))
        
        if person.has_role:
            self.graph.add((person_uri, ONTOLOGY.hasRole, Literal(person.has_role)))
        
        # Propriétés spécifiques Conducteur
        if isinstance(person, Conducteur):
            if person.has_license_number:
                self.graph.add((person_uri, ONTOLOGY.hasLicenseNumber, Literal(person.has_license_number)))
            if person.has_experience_years:
                self.graph.add((person_uri, ONTOLOGY.hasExperienceYears, Literal(person.has_experience_years, datatype=XSD.integer)))
            if person.drives_line:
                self.graph.add((person_uri, ONTOLOGY.drivesLine, Literal(person.drives_line)))
            if person.has_work_shift:
                self.graph.add((person_uri, ONTOLOGY.hasWorkShift, Literal(person.has_work_shift)))
            if person.works_for:
                company_uri = URIRef(f"{ONTOLOGY}{person.works_for.__class__.__name__}_{person.works_for.id}")
                self.graph.add((person_uri, ONTOLOGY.worksFor, company_uri))
                self._add_company_to_graph(person.works_for)
        
        # Propriétés spécifiques Contrôleur
        elif isinstance(person, Contrôleur):
            if person.has_badge_id:
                self.graph.add((person_uri, ONTOLOGY.hasBadgeID, Literal(person.has_badge_id)))
            if person.has_assigned_zone:
                self.graph.add((person_uri, ONTOLOGY.hasAssignedZone, Literal(person.has_assigned_zone)))
            if person.has_inspection_count is not None:
                self.graph.add((person_uri, ONTOLOGY.hasInspectionCount, Literal(person.has_inspection_count, datatype=XSD.integer)))
            if person.works_for_company:
                self.graph.add((person_uri, ONTOLOGY.worksForCompany, Literal(person.works_for_company)))
        
        # Propriétés spécifiques EmployéAgence
        elif isinstance(person, EmployéAgence):
            if person.has_employee_id:
                self.graph.add((person_uri, ONTOLOGY.hasEmployeeID, Literal(person.has_employee_id)))
            if person.has_position:
                self.graph.add((person_uri, ONTOLOGY.hasPosition, Literal(person.has_position)))
            if person.works_at:
                self.graph.add((person_uri, ONTOLOGY.worksAt, Literal(person.works_at)))
            if person.has_schedule:
                schedule_uri = URIRef(f"{ONTOLOGY}schedule_{person.has_schedule.id}")
                self.graph.add((person_uri, ONTOLOGY.hasSchedule, schedule_uri))
        
        # Propriétés spécifiques Passager
        elif isinstance(person, Passager):
            if person.has_subscription_type:
                self.graph.add((person_uri, ONTOLOGY.hasSubscriptionType, Literal(person.has_subscription_type)))
            if person.has_preferred_transport:
                self.graph.add((person_uri, ONTOLOGY.hasPreferredTransport, Literal(person.has_preferred_transport)))
        
        return person_uri
    
    def sync_person_to_ontology(self, person):
        """Sync a single person to ontology"""
        self.graph = Graph()  # Reset graph
        self.graph.bind("", ONTOLOGY)
        person_uri = self.person_to_rdf(person)
        self._upload_to_fuseki()
        return person_uri
    
    def delete_person_from_ontology(self, person):
        """Delete person from ontology"""
        person_id = person.has_id.replace('-', '_').replace(' ', '_')
        person_uri = f"{ONTOLOGY}person_{person_id}"
        delete_query = f"""
        PREFIX : <{ONTOLOGY}>
        DELETE WHERE {{
            <{person_uri}> ?p ?o .
        }}
        """
        from core.utils.fuseki import sparql_update
        sparql_update(delete_query)
    
    def ticket_to_rdf(self, ticket):
        """Convert Ticket instance to RDF"""
        if not TICKET_APP_AVAILABLE:
            raise Exception("Ticket app not available")
        
        # Utiliser has_ticket_id pour créer un URI stable
        ticket_id = ticket.has_ticket_id.replace('-', '_').replace(' ', '_')
        ticket_uri = URIRef(f"{ONTOLOGY}ticket_{ticket_id}")
        
        # Déterminer le type de ticket
        if isinstance(ticket, TicketSimple):
            ticket_type = ONTOLOGY.TicketSimple
        elif isinstance(ticket, TicketSenior):
            ticket_type = ONTOLOGY.TicketSenior
        elif isinstance(ticket, TicketÉtudiant):
            ticket_type = ONTOLOGY.TicketÉtudiant
        elif isinstance(ticket, AbonnementHebdomadaire):
            ticket_type = ONTOLOGY.AbonnementHebdomadaire
        elif isinstance(ticket, AbonnementMensuel):
            ticket_type = ONTOLOGY.AbonnementMensuel
        else:
            ticket_type = ONTOLOGY.Ticket
        
        # Ajouter les triples de base
        self.graph.add((ticket_uri, RDF.type, ticket_type))
        self.graph.add((ticket_uri, ONTOLOGY.hasTicketID, Literal(ticket.has_ticket_id)))
        
        if ticket.has_price:
            self.graph.add((ticket_uri, ONTOLOGY.hasPrice, Literal(ticket.has_price, datatype=XSD.float)))
        
        if ticket.has_validity_duration:
            self.graph.add((ticket_uri, ONTOLOGY.hasValidityDuration, Literal(ticket.has_validity_duration)))
        
        if ticket.has_purchase_date:
            self.graph.add((ticket_uri, ONTOLOGY.hasPurchaseDate, Literal(ticket.has_purchase_date, datatype=XSD.date)))
        
        if ticket.has_expiration_date:
            self.graph.add((ticket_uri, ONTOLOGY.hasExpirationDate, Literal(ticket.has_expiration_date, datatype=XSD.date)))
        
        if ticket.is_reduced_fare:
            self.graph.add((ticket_uri, ONTOLOGY.isReducedFare, Literal(ticket.is_reduced_fare, datatype=XSD.boolean)))
        
        # Relations
        if ticket.owned_by:
            person_id = ticket.owned_by.has_id.replace('-', '_').replace(' ', '_')
            person_uri = URIRef(f"{ONTOLOGY}person_{person_id}")
            self.graph.add((ticket_uri, ONTOLOGY.ownedBy, person_uri))
            # Ajouter aussi les données de la personne
            self.person_to_rdf(ticket.owned_by)
        
        if ticket.valid_for:
            transport_uri = URIRef(f"{ONTOLOGY}{ticket.valid_for.__class__.__name__}_{ticket.valid_for.transport_line_number}")
            self.graph.add((ticket_uri, ONTOLOGY.validFor, transport_uri))
            # Ajouter aussi les données du transport
            self.transport_to_rdf(ticket.valid_for)
        
        # Propriétés spécifiques TicketSimple
        if isinstance(ticket, TicketSimple):
            if ticket.is_used is not None:
                self.graph.add((ticket_uri, ONTOLOGY.isUsed, Literal(ticket.is_used, datatype=XSD.boolean)))
        
        # Propriétés spécifiques TicketSenior
        elif isinstance(ticket, TicketSenior):
            if ticket.has_age_condition:
                self.graph.add((ticket_uri, ONTOLOGY.hasAgeCondition, Literal(ticket.has_age_condition, datatype=XSD.integer)))
        
        # Propriétés spécifiques TicketÉtudiant
        elif isinstance(ticket, TicketÉtudiant):
            if ticket.has_institution_name:
                self.graph.add((ticket_uri, ONTOLOGY.hasInstitutionName, Literal(ticket.has_institution_name)))
            if ticket.has_student_id:
                self.graph.add((ticket_uri, ONTOLOGY.hasStudentID, Literal(ticket.has_student_id)))
        
        # Propriétés spécifiques AbonnementHebdomadaire
        elif isinstance(ticket, AbonnementHebdomadaire):
            if ticket.has_start_date:
                self.graph.add((ticket_uri, ONTOLOGY.hasStartDate, Literal(ticket.has_start_date, datatype=XSD.date)))
            if ticket.has_end_date:
                self.graph.add((ticket_uri, ONTOLOGY.hasEndDate, Literal(ticket.has_end_date, datatype=XSD.date)))
            if ticket.has_zone_access:
                self.graph.add((ticket_uri, ONTOLOGY.hasZoneAccess, Literal(ticket.has_zone_access)))
        
        # Propriétés spécifiques AbonnementMensuel
        elif isinstance(ticket, AbonnementMensuel):
            if ticket.has_month:
                self.graph.add((ticket_uri, ONTOLOGY.hasMonth, Literal(ticket.has_month)))
            if ticket.has_auto_renewal is not None:
                self.graph.add((ticket_uri, ONTOLOGY.hasAutoRenewal, Literal(ticket.has_auto_renewal, datatype=XSD.boolean)))
            if ticket.has_payment_method:
                self.graph.add((ticket_uri, ONTOLOGY.hasPaymentMethod, Literal(ticket.has_payment_method)))
        
        return ticket_uri
    
    def sync_ticket_to_ontology(self, ticket):
        """Sync a single ticket to ontology"""
        self.graph = Graph()  # Reset graph
        self.graph.bind("", ONTOLOGY)
        ticket_uri = self.ticket_to_rdf(ticket)
        self._upload_to_fuseki()
        return ticket_uri
    
    def delete_ticket_from_ontology(self, ticket):
        """Delete ticket from ontology"""
        ticket_id = ticket.has_ticket_id.replace('-', '_').replace(' ', '_')
        ticket_uri = f"{ONTOLOGY}ticket_{ticket_id}"
        delete_query = f"""
        PREFIX : <{ONTOLOGY}>
        DELETE WHERE {{
            <{ticket_uri}> ?p ?o .
        }}
        """
        from core.utils.fuseki import sparql_update
        sparql_update(delete_query)

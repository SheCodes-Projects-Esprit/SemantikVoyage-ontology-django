import rdflib
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, XSD
from django.conf import settings
import requests  # ← AJOUTEZ CET IMPORT MANQUANT
from transport_app.models import (
    Station, BusStop, MetroStation, TrainStation, TramStation,
    Transport, Bus, Metro, Train, Tram, City, Company,
    BusCompany, MetroCompany
)

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
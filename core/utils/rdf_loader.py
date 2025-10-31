import os
from django.conf import settings
from .fuseki import upload_rdf

def load_ontology_to_fuseki():
    ontology_path = os.path.join(settings.BASE_DIR, 'ontology', 'transport_ontology.ttl')
    if not os.path.exists(ontology_path):
        raise FileNotFoundError("Ontology file not found.")
    return upload_rdf(ontology_path, settings.FUSEKI_GRAPH)
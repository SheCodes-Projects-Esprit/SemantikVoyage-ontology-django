import requests
from django.conf import settings

FUSEKI_QUERY_URL = f"{settings.FUSEKI_URL}/{settings.FUSEKI_DATASET}/query"
FUSEKI_UPDATE_URL = f"{settings.FUSEKI_URL}/{settings.FUSEKI_DATASET}/update"
FUSEKI_UPLOAD_URL = f"{settings.FUSEKI_URL}/{settings.FUSEKI_DATASET}/data"

def sparql_query(sparql):
    headers = {'Accept': 'application/sparql-results+json'}
    payload = {'query': sparql}
    
    # Ajouter le graph URI comme paramètre si disponible
    if settings.FUSEKI_GRAPH:
        payload['default-graph-uri'] = settings.FUSEKI_GRAPH
    
    response = requests.post(FUSEKI_QUERY_URL, data=payload, headers=headers)
    response.raise_for_status()
    return response.json()

def sparql_update(sparql):
    payload = {'update': sparql}
    
    if settings.FUSEKI_GRAPH:
        payload['default-graph-uri'] = settings.FUSEKI_GRAPH
    
    response = requests.post(FUSEKI_UPDATE_URL, data=payload)
    response.raise_for_status()
    return response

def upload_rdf(file_path, graph_uri=None):
    # Lire le fichier et déterminer le Content-Type
    file_ext = file_path.split('.')[-1].lower()
    content_type_map = {
        'ttl': 'text/turtle',
        'rdf': 'application/rdf+xml',
        'n3': 'text/n3',
        'nt': 'text/plain',
        'jsonld': 'application/ld+json'
    }
    content_type = content_type_map.get(file_ext, 'text/turtle')
    
    # Construire l'URL avec le graph URI si fourni
    upload_url = FUSEKI_UPLOAD_URL
    if graph_uri:
        upload_url = f"{upload_url}?graph={graph_uri}"
    
    # Ouvrir et envoyer le fichier avec le bon Content-Type
    with open(file_path, 'rb') as f:
        headers = {'Content-Type': content_type}
        data = f.read()
        response = requests.post(upload_url, data=data, headers=headers)
        response.raise_for_status()
    return response
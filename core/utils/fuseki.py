import requests
from django.conf import settings

FUSEKI_QUERY_URL = f"{settings.FUSEKI_URL}/{settings.FUSEKI_DATASET}/query"
FUSEKI_UPDATE_URL = f"{settings.FUSEKI_URL}/{settings.FUSEKI_DATASET}/update"
FUSEKI_UPLOAD_URL = f"{settings.FUSEKI_URL}/{settings.FUSEKI_DATASET}/data"

def sparql_query(sparql):
    headers = {'Accept': 'application/sparql-results+json'}
    payload = {'query': sparql}
    response = requests.post(FUSEKI_QUERY_URL, data=payload, headers=headers)
    response.raise_for_status()
    return response.json()

def sparql_update(sparql):
    payload = {'update': sparql}
    response = requests.post(FUSEKI_UPDATE_URL, data=payload)
    response.raise_for_status()
    return response

def upload_rdf(file_path, graph_uri=None):
    with open(file_path, 'rb') as f:
        files = {'file': f}
        params = {}
        if graph_uri:
            params['graph'] = graph_uri
        response = requests.post(FUSEKI_UPLOAD_URL, files=files, params=params)
        response.raise_for_status()
    return response
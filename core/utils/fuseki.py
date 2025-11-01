import requests
from django.conf import settings
import json

def sparql_query(sparql):
    """Execute SPARQL query on Fuseki"""
    try:
        FUSEKI_QUERY_URL = f"{settings.FUSEKI_URL}/{settings.FUSEKI_DATASET}/query"
        
        headers = {
            'Accept': 'application/sparql-results+json',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        payload = {'query': sparql}
        
        # Ajouter le graph URI comme paramètre si disponible
        if hasattr(settings, 'FUSEKI_GRAPH') and settings.FUSEKI_GRAPH:
            payload['default-graph-uri'] = settings.FUSEKI_GRAPH
        
        print(f"🔍 Envoi requête à: {FUSEKI_QUERY_URL}")
        print(f"🔍 Graph: {settings.FUSEKI_GRAPH}")
        print(f"🔍 Requête SPARQL:\n{sparql}")
        
        response = requests.post(FUSEKI_QUERY_URL, data=payload, headers=headers, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ Erreur Fuseki: {response.status_code} - {response.text}")
            raise Exception(f"Fuseki query failed: {response.status_code} - {response.text}")
        
        return response.json()
    
    except requests.exceptions.ConnectionError:
        raise Exception("Impossible de se connecter à Fuseki. Vérifiez que le serveur est démarré.")
    except Exception as e:
        raise Exception(f"Erreur lors de la requête SPARQL: {e}")

def sparql_update(sparql):
    """Execute SPARQL update on Fuseki"""
    try:
        FUSEKI_UPDATE_URL = f"{settings.FUSEKI_URL}/{settings.FUSEKI_DATASET}/update"
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        payload = {'update': sparql}
        
        response = requests.post(FUSEKI_UPDATE_URL, data=payload, headers=headers, timeout=30)
        
        if response.status_code != 200:
            raise Exception(f"Fuseki update failed: {response.status_code} - {response.text}")
        
        return response
    
    except requests.exceptions.ConnectionError:
        raise Exception("Impossible de se connecter à Fuseki. Vérifiez que le serveur est démarré.")
    except Exception as e:
        raise Exception(f"Erreur lors de la mise à jour SPARQL: {e}")

def upload_rdf(file_path, graph_uri=None):
    """Upload RDF file to Fuseki"""
    try:
        FUSEKI_UPLOAD_URL = f"{settings.FUSEKI_URL}/{settings.FUSEKI_DATASET}/data"
        
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
            response = requests.post(upload_url, data=data, headers=headers, timeout=30)
            
            if response.status_code != 200:
                raise Exception(f"Fuseki upload failed: {response.status_code} - {response.text}")
            
        return response
    
    except Exception as e:
        raise Exception(f"Erreur lors du chargement RDF: {e}")

def test_fuseki_connection():
    """Test basic connection to Fuseki"""
    try:
        test_url = f"{settings.FUSEKI_URL}/{settings.FUSEKI_DATASET}/query"
        test_query = "SELECT * WHERE { ?s ?p ?o } LIMIT 1"
        
        headers = {'Accept': 'application/sparql-results+json'}
        payload = {'query': test_query}
        
        response = requests.post(test_url, data=payload, headers=headers, timeout=10)
        return response.status_code == 200
    except:
        return False
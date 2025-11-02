from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .utils.fuseki import sparql_query
from .utils.nl_to_sparql import nl_to_sparql
from .utils.rdf_loader import load_ontology_to_fuseki
import json
import requests

def home(request):
    return render(request, 'core/index.html')

def load_ontology(request):
    try:
        response = load_ontology_to_fuseki()
        return JsonResponse({"status": "success", "message": "Ontology loaded into Fuseki successfully."})
    except FileNotFoundError as e:
        return JsonResponse({"status": "error", "message": f"File not found: {str(e)}"})
    except requests.exceptions.RequestException as e:
        return JsonResponse({"status": "error", "message": f"Connection error with Fuseki: {str(e)}. Make sure Fuseki is running at {settings.FUSEKI_URL}"})
    except Exception as e:
        return JsonResponse({"status": "error", "message": f"Error loading ontology: {str(e)}"})

@csrf_exempt
def query_view(request):
    if request.method == "POST":
        question = request.POST.get("question", "").strip()
        if not question:
            return render(request, 'core/index.html', {'error': 'Please enter a question.'})

        try:
            sparql = nl_to_sparql(question)
            result = sparql_query(sparql)
            
            # Preprocess results for easier template handling
            processed_results = []
            for binding in result.get('results', {}).get('bindings', []):
                row = {}
                for var in result.get('head', {}).get('vars', []):
                    row[var] = binding.get(var, {}).get('value', 'N/A')
                processed_results.append(row)
            
            return render(request, 'core/results.html', {
                'question': question,
                'sparql': sparql,
                'results': result,
                'processed_results': processed_results,
                'vars': result.get('head', {}).get('vars', [])
            })
        except Exception as e:
            return render(request, 'core/index.html', {'error': str(e)})

    return redirect('home')

def debug_fuseki(request):
    """Vue de débogage complète pour Fuseki"""
    from django.conf import settings
    import requests
    import json
    
    tests = {}
    
    # Test 1: Configuration
    tests['configuration'] = {
        'FUSEKI_URL': getattr(settings, 'FUSEKI_URL', 'Non défini'),
        'FUSEKI_DATASET': getattr(settings, 'FUSEKI_DATASET', 'Non défini'),
        'FUSEKI_GRAPH': getattr(settings, 'FUSEKI_GRAPH', 'Non défini'),
    }
    
    # Test 2: Connexion de base
    try:
        test_url = f"{settings.FUSEKI_URL}/{settings.FUSEKI_DATASET}/query"
        test_query = "SELECT (COUNT(*) as ?count) WHERE { ?s ?p ?o }"
        
        headers = {'Accept': 'application/sparql-results+json'}
        payload = {'query': test_query}
        
        response = requests.post(test_url, data=payload, headers=headers, timeout=10)
        tests['connexion_base'] = {
            'status': response.status_code,
            'url': test_url,
            'reponse': response.text[:500] if response.status_code != 200 else "OK"
        }
    except Exception as e:
        tests['connexion_base'] = {'erreur': str(e)}
    
    # Test 3: Compter les triples dans le graphe spécifique
    try:
        graph_query = f"""
        SELECT (COUNT(*) as ?count) WHERE {{
            GRAPH <{settings.FUSEKI_GRAPH}> {{
                ?s ?p ?o
            }}
        }}
        """
        payload_graph = {'query': graph_query}
        response_graph = requests.post(test_url, data=payload_graph, headers=headers, timeout=10)
        
        if response_graph.status_code == 200:
            data = response_graph.json()
            count = data.get('results', {}).get('bindings', [{}])[0].get('count', {}).get('value', '0')
            tests['triples_dans_graphe'] = f"{count} triples dans {settings.FUSEKI_GRAPH}"
        else:
            tests['triples_dans_graphe'] = f"Erreur: {response_graph.status_code}"
    except Exception as e:
        tests['triples_dans_graphe'] = f"Erreur: {e}"
    
    # Test 4: Tester un INSERT manuel CORRECT
    try:
        # SYNTAXE CORRECTE : INSERT DATA { GRAPH <uri> { ... } }
        test_insert = f"""
        PREFIX : <http://www.transport-ontology.org/travel#>
        INSERT DATA {{
            GRAPH <{settings.FUSEKI_GRAPH}> {{
                :Test_Debug a :Bus ;
                          :Transport_hasLineNumber "DEBUG999" ;
                          :Transport_hasCapacity 1 .
            }}
        }}
        """
        
        update_url = f"{settings.FUSEKI_URL}/{settings.FUSEKI_DATASET}/update"
        headers_update = {'Content-Type': 'application/x-www-form-urlencoded'}
        payload_update = {'update': test_insert}
        
        response_update = requests.post(update_url, data=payload_update, headers=headers_update, timeout=10)
        tests['test_insert_manuel'] = {
            'status': response_update.status_code,
            'reponse': response_update.text
        }
        
        # Vérifier si l'insertion a fonctionné
        if response_update.status_code == 200:
            verify_query = f"""
            PREFIX : <http://www.transport-ontology.org/travel#>
            SELECT ?bus WHERE {{
                GRAPH <{settings.FUSEKI_GRAPH}> {{
                    ?bus a :Bus ;
                         :Transport_hasLineNumber "DEBUG999"
                }}
            }}
            """
            payload_verify = {'query': verify_query}
            response_verify = requests.post(test_url, data=payload_verify, headers=headers, timeout=10)
            if response_verify.status_code == 200:
                verify_data = response_verify.json()
                bus_count = len(verify_data.get('results', {}).get('bindings', []))
                tests['verification_insert'] = f"Bus trouvés: {bus_count}"
                
                # Compter les nouveaux triples
                response_count = requests.post(test_url, data=payload_graph, headers=headers, timeout=10)
                if response_count.status_code == 200:
                    count_data = response_count.json()
                    new_count = count_data.get('results', {}).get('bindings', [{}])[0].get('count', {}).get('value', '0')
                    tests['nouveau_nombre_triples'] = f"{new_count} triples après insertion"
            else:
                tests['verification_insert'] = f"Erreur vérification: {response_verify.status_code}"
        
    except Exception as e:
        tests['test_insert_manuel'] = f"Erreur: {e}"
    
    return JsonResponse(tests, json_dumps_params={'indent': 2})

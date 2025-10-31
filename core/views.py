from django.shortcuts import render

from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .utils.fuseki import sparql_query
from .utils.nl_to_sparql import nl_to_sparql
from .utils.rdf_loader import load_ontology_to_fuseki
import json

def home(request):
    return render(request, 'core/index.html')

def load_ontology(request):
    try:
        response = load_ontology_to_fuseki()
        return JsonResponse({"status": "success", "message": "Ontology loaded into Fuseki."})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)})

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
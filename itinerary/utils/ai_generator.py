import os
import json
from groq import Groq
from core.utils.nl_to_sparql import nl_to_sparql
from core.utils.fuseki import sparql_query
from .ontology_manager import get_itinerary, update_itinerary

MODEL = "llama-3.3-70b-versatile"

def generate_itinerary_suggestions(user_preferences):
    client = Groq(api_key=os.getenv('GROQ_API_KEY'))
    if not os.getenv('GROQ_API_KEY'):
        return {"error": "GROQ_API_KEY missing"}
    prompt = f"""
    Generate a complete {user_preferences.get('type', 'Business')}Trip itinerary based on: duration {user_preferences.get('duration', 3)} days, budget {user_preferences.get('budget', 1000)} TND.
    Use Tunis/Sfax cities, existing transports like :Bus_23 or :Metro_L1.
    Output ONLY valid JSON: {{"itinerary_id": "007", "overall_status": "Planned", "totalCostEstimate": 800.0, "totalDurationDays": 3, "clientProjectName": "Sample Project", "expenseLimit": 1000.0, "purposeCode": "MKT", "approvalRequired": false}}
    Match ontology properties exactly.
    """
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=500
    )
    try:
        return json.loads(response.choices[0].message.content.strip())
    except json.JSONDecodeError:
        return {"error": "Invalid JSON from AI"}

def optimize_route(itinerary_id):
    current = get_itinerary(itinerary_id)
    if not current:
        return {"error": "Itinerary not found"}
    client = Groq(api_key=os.getenv('GROQ_API_KEY'))
    prompt = f"Optimize this itinerary {itinerary_id}: {json.dumps(current)}. Suggest cheaper/faster route using ontology transports (e.g., switch to :Metro_L1). Output updated JSON props only."
    response = client.chat.completions.create(model=MODEL, messages=[{"role": "user", "content": prompt}], temperature=0.2)
    suggestions = json.loads(response.choices[0].message.content.strip())
    update_itinerary(itinerary_id, suggestions)
    return suggestions

def suggest_transport_options(start, end, budget):
    question = f"Find transports from {start} to {end} under {budget} TND"
    sparql = nl_to_sparql(question)
    results_raw = sparql_query(sparql)
    results = []
    for binding in results_raw.get('results', {}).get('bindings', []):
        row = {k: binding.get(k, {}).get('value', 'N/A') for k in results_raw.get('head', {}).get('vars', [])}
        results.append(row)
    
    client = Groq(api_key=os.getenv('GROQ_API_KEY'))
    prompt = f"Rank these transports {json.dumps(results)} by cost/speed/eco-friendliness. Top 3 with reasons. Output JSON: [{{\"rank\": 1, \"transport\": {{...}}, \"reason\": \"...\"}}]"
    response = client.chat.completions.create(model=MODEL, messages=[{"role": "user", "content": prompt}], temperature=0.1)
    ranked = json.loads(response.choices[0].message.content.strip())
    return ranked
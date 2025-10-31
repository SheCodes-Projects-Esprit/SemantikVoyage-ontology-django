import os
from groq import Groq
import re

# Fallback: Simple keyword → SPARQL mapping
SIMPLE_QUERIES = {
    "bus lines in Tunis": """
    PREFIX : <http://www.transport-ontology.org/travel#>
    SELECT ?line ?capacity WHERE {
        ?bus a :Bus ;
             :Transport_hasLineNumber ?line ;
             :operatesIn :city_Tunis ;
             :Transport_hasCapacity ?capacity .
    } LIMIT 10
    """,
    "metro stations in Tunis": """
    PREFIX : <http://www.transport-ontology.org/travel#>
    SELECT ?station WHERE {
        ?station a :MetroStation ;
                 :locatedIn :city_Tunis .
    }
    """,
    "companies in Tunis": """
    PREFIX : <http://www.transport-ontology.org/travel#>
    SELECT ?company ?name WHERE {
        ?company a :Company ;
                 :basedIn :city_Tunis ;
                 :companyName ?name .
    }
    """
}

# MODÈLE
MODEL = "llama3-8b-8192"

def nl_to_sparql(question: str) -> str:
    question_lower = question.lower().strip()

    # 1. Fallback simple
    for key, sparql in SIMPLE_QUERIES.items():
        if key in question_lower:
            return sparql

    # 2. Groq AI (chargement tardif)
    api_key = os.getenv('GROQ_API_KEY')
    if not api_key:
        print("GROQ_API_KEY manquante dans .env")
        return """
        PREFIX : <http://www.transport-ontology.org/travel#>
        SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 5
        """

    try:
        client = Groq(api_key=api_key)  # ← INITIALISÉ ICI, PAS EN HAUT !

        prompt = f"""
Tu es un expert SPARQL. Convertis cette question en requête SPARQL valide basée sur l'ontologie http://www.transport-ontology.org/travel#.

Classes principales : Person, Ticket, Itinerary, Company, Schedule, Transport, Station, City.
Propriétés clés : companyName, cityName, Transport_hasLineNumber, Station_hasName, operatesIn, basedIn, locatedIn, etc.
Instances : :city_Tunis, :busCompany_Tunis, :Bus_23, :station_BabElKhadhra, etc.

Question : "{question}"

Génère UNIQUEMENT une requête SPARQL SELECT valide avec :
- PREFIX : <http://www.transport-ontology.org/travel#>
- LIMIT 10
- Pas d'explications, juste le code.
"""

        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=300,
        )
        generated = response.choices[0].message.content.strip()
        sparql = extract_sparql(generated)
        return sparql if sparql else fallback_query()

    except Exception as e:
        print(f"Groq error: {e}")
        return fallback_query()

def fallback_query():
    return """
    PREFIX : <http://www.transport-ontology.org/travel#>
    SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 5
    """

def extract_sparql(text):
    match = re.search(r'(PREFIX.*?LIMIT \d+)', text, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else None
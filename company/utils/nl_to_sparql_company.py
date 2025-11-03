# company/utils/nl_to_sparql_company.py
import os
from groq import Groq

MODEL = "llama-3.3-70b-versatile"

# === QUERY FUNCTION (UNCHANGED) ===
def company_nl_to_sparql(user_text):
    lower = user_text.lower()
    prefix = """
    PREFIX : <http://www.transport-ontology.org/travel#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    """

    select = "?name ?type ?employees ?year ?hq "
    where = ""
    optional = ""

    if "bus" in lower:
        select += "?busLines ?avgAge ?ticket ?eco "
        where = "?c a/rdfs:subClassOf* :BusCompany ; :companyName ?name ."
        optional = """
        OPTIONAL { ?c :numberOfBusLines ?busLines }
        OPTIONAL { ?c :averageBusAge ?avgAge }
        OPTIONAL { ?c :ticketPrice ?ticket }
        OPTIONAL { ?c :ecoFriendlyFleet ?eco }
        """
    elif "metro" in lower:
        select += "?metroLines ?track ?auto ?daily "
        where = "?c a/rdfs:subClassOf* :MetroCompany ; :companyName ?name ."
        optional = """
        OPTIONAL { ?c :numberOfLines ?metroLines }
        OPTIONAL { ?c :totalTrackLength ?track }
        OPTIONAL { ?c :automationLevel ?auto }
        OPTIONAL { ?c :dailyPassengers ?daily }
        """
    elif "taxi" in lower:
        select += "?vehicles ?fare ?app "
        where = "?c a/rdfs:subClassOf* :TaxiCompany ; :companyName ?name ."
        optional = """
        OPTIONAL { ?c :numberOfVehicles ?vehicles }
        OPTIONAL { ?c :averageFarePerKm ?fare }
        OPTIONAL { ?c :hasBookingApp ?app }
        """
    elif "bike" in lower or "sharing" in lower:
        select += "?stations ?bikes ?price ?electric "
        where = "?c a/rdfs:subClassOf* :BikeSharingCompany ; :companyName ?name ."
        optional = """
        OPTIONAL { ?c :numberOfStations ?stations }
        OPTIONAL { ?c :bikeCount ?bikes }
        OPTIONAL { ?c :subscriptionPrice ?price }
        OPTIONAL { ?c :electricBikes ?electric }
        """
    else:
        select += "?busLines ?metroLines ?vehicles ?stations "
        where = "?c a/rdfs:subClassOf* :Company ; :companyName ?name ."
        optional = """
        OPTIONAL { ?c :numberOfBusLines ?busLines }
        OPTIONAL { ?c :numberOfLines ?metroLines }
        OPTIONAL { ?c :numberOfVehicles ?vehicles }
        OPTIONAL { ?c :numberOfStations ?stations }
        """

    sparql = f"""
    {prefix}
    SELECT {select}
    WHERE {{
      {where}
      OPTIONAL {{ ?c rdf:type ?type }}
      OPTIONAL {{ ?c :numberOfEmployees ?employees }}
      OPTIONAL {{ ?c :foundedYear ?year }}
      OPTIONAL {{ ?c :headquartersLocation ?hq }}
      {optional}
    }}
    ORDER BY ?name
    LIMIT 50
    """
    return sparql


# === UPDATE FUNCTION — SIMPLIFIED & FIXED ===
def company_nl_to_sparql_update(question: str) -> str:
    """Generate SPARQL UPDATE using LLM with strict validation."""
    api_key = os.getenv('GROQ_API_KEY')
    if not api_key:
        return ""

    client = Groq(api_key=api_key)
    
    # Check if this is a DELETE operation
    lower = question.lower()
    is_delete = any(kw in lower for kw in ['delete', 'remove', 'drop'])

    prompt = f"""
You are a SPARQL expert. Generate a valid SPARQL UPDATE for the transport ontology.

OPERATION: {'DELETE' if is_delete else 'INSERT DATA'}

ONTOLOGY NAMESPACE: http://www.transport-ontology.org/travel#
PREFIX shorthand: :

COMPANY CLASSES:
- :BusCompany (subclass of :Company)
- :MetroCompany (subclass of :Company)
- :TaxiCompany (subclass of :Company)
- :BikeSharingCompany (subclass of :Company)

PROPERTIES:
- :companyName (string) - REQUIRED
- :numberOfEmployees (integer)
- :foundedYear (string)
- :headquartersLocation (string)

BusCompany specific:
- :numberOfBusLines (integer)
- :averageBusAge (float)
- :ticketPrice (float)
- :ecoFriendlyFleet (boolean: true/false)

MetroCompany specific:
- :numberOfLines (integer)
- :totalTrackLength (float)
- :automationLevel (string)
- :dailyPassengers (integer)

TaxiCompany specific:
- :numberOfVehicles (integer)
- :hasBookingApp (boolean: true/false)
- :averageFarePerKm (float)

BikeSharingCompany specific:
- :numberOfStations (integer)
- :bikeCount (integer)
- :subscriptionPrice (float)
- :electricBikes (boolean: true/false)

RULES:
1. Subject URI format: :company_<NAME_WITH_UNDERSCORES>
2. MUST include: rdf:type :<CompanyType>
3. MUST include: :companyName "<name>"
4. Numbers: NO QUOTES (e.g., 5000 not "5000")
5. Strings: USE QUOTES (e.g., "Tunis" not Tunis)
6. Booleans: true or false (lowercase, no quotes)
7. End with period (.)
8. DO NOT include PREFIX declarations (they will be added automatically)
9. DO NOT wrap in INSERT DATA {{ }} (will be added automatically)

EXAMPLE OUTPUT (what you should generate):
:company_SOTRA a :BusCompany ;
  :companyName "SOTRA" ;
  :numberOfEmployees 5000 ;
  :headquartersLocation "" ;
  :numberOfBusLines 150 ;
  :ecoFriendlyFleet true .

USER REQUEST: {question}

Generate ONLY the triples (no INSERT DATA wrapper, no PREFIX):
"""

    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=500,
        )
        raw = resp.choices[0].message.content.strip()
        cleaned = _clean_sparql_triples(raw)
        print(f"[AI Generated Triples]\n{cleaned}")
        return cleaned
    except Exception as e:
        print(f"Groq Error: {e}")
        return ""


def _clean_sparql_triples(text: str) -> str:
    """Clean LLM output to extract just the triples."""
    lines = []
    skip_keywords = ['PREFIX', 'INSERT', 'DATA', 'GRAPH', 'WHERE', '```']
    
    for line in text.splitlines():
        line = line.strip()
        # Skip empty lines, comments, and SPARQL keywords
        if not line or line.startswith('#'):
            continue
        if any(kw in line.upper() for kw in skip_keywords):
            continue
        # Skip lines that are just braces
        if line in ['{', '}']:
            continue
        
        lines.append(line)
    
    result = '\n'.join(lines)
    
    # Ensure it ends with a period
    if result and not result.rstrip().endswith('.'):
        result = result.rstrip()
        if result.endswith(';'):
            result = result[:-1]
        result += ' .'
    
    return result
import os
from groq import Groq

MODEL = "llama-3.3-70b-versatile"


def city_nl_to_sparql(question: str) -> str:
    api_key = os.getenv('GROQ_API_KEY')
    if not api_key:
        return ""
    client = Groq(api_key=api_key)

    schema = """
PREFIX : <http://www.transport-ontology.org/travel#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

CLASSES:
- :City and subclasses :CapitalCity, :MetropolitanCity, :TouristicCity, :IndustrialCity

DATA PROPERTIES (City):
- :cityName (string)
- :population (integer)
- :area (float)
- :region (string)
- :numberOfMinistries (CapitalCity)
- :numberOfDistricts, :averageCommuteTime (MetropolitanCity)
- :annualVisitors, :hotelCount (TouristicCity)
- :numberOfFactories, :pollutionIndex (IndustrialCity)

SPARQL PATTERNS:
- Use ?c a/rdfs:subClassOf* :City to match all cities.
- Optional values with OPTIONAL { }
"""

    examples = """
EXAMPLES (SELECT only):
INPUT: "List all cities"
OUTPUT:
PREFIX : <http://www.transport-ontology.org/travel#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?name ?type
WHERE {
  ?c a/rdfs:subClassOf* :City ;
     :cityName ?name .
  OPTIONAL { ?c rdf:type ?type }
}
ORDER BY ?name
LIMIT 10

INPUT: "Show city where name = Tunis"
OUTPUT:
PREFIX : <http://www.transport-ontology.org/travel#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?name ?pop ?area
WHERE {
  ?c a/rdfs:subClassOf* :City ;
     :cityName ?name .
  FILTER(LCASE(?name) = "tunis")
  OPTIONAL { ?c :population ?pop }
  OPTIONAL { ?c :area ?area }
}
LIMIT 10
"""

    prompt = f"""You are an expert SPARQL generator for a transport ontology.
{schema}
{examples}

RULES:
1) Output ONLY a valid SPARQL SELECT query, with PREFIX : and PREFIX rdfs:.
2) Use :cityName (never City_hasName).
3) Always end with LIMIT 10. No markdown.

USER: {question}
SPARQL:"""

    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=600,
    )
    return _clean(resp.choices[0].message.content)


def city_nl_to_sparql_update(question: str) -> str:
    api_key = os.getenv('GROQ_API_KEY')
    if not api_key:
        return ""
    client = Groq(api_key=api_key)

    schema = """
GRAPH URI: <http://www.transport-ontology.org/travel>
INSERT example:
PREFIX : <http://www.transport-ontology.org/travel#>
INSERT DATA { GRAPH <http://www.transport-ontology.org/travel> {
  :city_New a :City ; :cityName "New" ; :population 0 ; :area 0.0 .
}}

DELETE example (by name):
PREFIX : <http://www.transport-ontology.org/travel#>
WITH <http://www.transport-ontology.org/travel>
DELETE WHERE { { ?s a/rdfs:subClassOf* :City ; :cityName "New" ; ?p ?o } }

MODIFY example (rename):
PREFIX : <http://www.transport-ontology.org/travel#>
WITH <http://www.transport-ontology.org/travel>
DELETE { ?s :cityName "Old" }
INSERT { ?s :cityName "New" }
WHERE  { ?s a/rdfs:subClassOf* :City ; :cityName "Old" }
"""

    prompt = f"""Generate a SPARQL UPDATE for the transport ontology.
Requirements:
- Always use GRAPH <http://www.transport-ontology.org/travel> for INSERT DATA.
- For DELETE/INSERT or DELETE WHERE, use WITH <http://www.transport-ontology.org/travel>.
- Use :cityName (never City_hasName).
- Output only the SPARQL UPDATE, no markdown.

User request: {question}
SPARQL UPDATE:"""

    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": schema + "\n" + prompt}],
        temperature=0.0,
        max_tokens=600,
    )
    return _clean(resp.choices[0].message.content)


def _clean(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip('`')
    if 'PREFIX' in text:
        text = text[text.index('PREFIX'):]
    return text



import os, json
from groq import Groq

MODEL = "llama-3.3-70b-versatile"

def generate_city_suggestions(prefs):
    client = Groq(api_key=os.getenv('GROQ_API_KEY'))
    prompt = f"""
    Generate a {prefs.get('type','Capital')}City JSON for a Tunisian city.
    Use realistic numbers (population, area, etc.).
    Output **only** JSON matching the ontology (name is the identifier):
    {{"name":"Tunis","overall_status":"Planned","population":1200000,"area_km2":212.6,
      "government_seat":true,"ministries":20}}
    """
    resp = client.chat.completions.create(model=MODEL, messages=[{"role":"user","content":prompt}],
                                          temperature=0.3, max_tokens=500)
    return json.loads(resp.choices[0].message.content.strip())
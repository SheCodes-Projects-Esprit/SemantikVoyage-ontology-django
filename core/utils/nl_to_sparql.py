import os
from groq import Groq
import re

MODEL = "llama-3.3-70b-versatile"  # Plus puissant pour meilleure génération

def nl_to_sparql(question: str) -> str:
    api_key = os.getenv('GROQ_API_KEY')
    if not api_key:
        print("[ERROR] GROQ_API_KEY missing in .env")
        return ""

    client = Groq(api_key=api_key)

    # SCHÉMA ULTRA-COMPLET avec TOUTES les relations de votre ontologie
    schema_snippet = """
TRANSPORT ONTOLOGY COMPLETE SCHEMA:
Base IRI: http://www.transport-ontology.org/travel#
Prefix: PREFIX : <http://www.transport-ontology.org/travel#>

═══════════════════════════════════════════════════════════════════
CLASSES & OBJECT PROPERTIES (RELATIONSHIPS):
═══════════════════════════════════════════════════════════════════

1. PERSON HIERARCHY:
   - Person (base class)
     ├─ Passager: buys→Ticket, follows→Itinerary, usesTransport→Transport
     ├─ Conducteur: worksFor→Company
     ├─ Contrôleur: (inspector)
     └─ EmployéAgence: (agency employee)
   
   Data Properties: hasName, hasAge, hasID, hasEmail, hasPhoneNumber, hasRole
   Passager: hasSubscriptionType, hasPreferredTransport
   Conducteur: hasLicenseNumber, hasExperienceYears, drivesLine, hasWorkShift

2. TICKET HIERARCHY:
   - Ticket (base class): ownedBy→Person, validFor→Transport
     ├─ TicketSimple: isUsed
     ├─ AbonnementMensuel: hasMonth, hasAutoRenewal, hasPaymentMethod
     ├─ AbonnementHebdomadaire: hasStartDate, hasEndDate, hasZoneAccess
     ├─ TicketÉtudiant: hasInstitutionName, hasStudentID
     └─ TicketSenior: hasAgeCondition
   
   Data Properties: hasTicketID, hasPrice, hasPurchaseDate, hasExpirationDate, isReducedFare

3. TRANSPORT HIERARCHY:
   - Transport (base class): operatedBy→Company, operatesIn→City, departsFrom→Station, arrivesAt→Station
     ├─ Bus
     ├─ Metro
     ├─ Train
     └─ Tram
   
   Data Properties: Transport_hasLineNumber, Transport_hasCapacity, Transport_hasSpeed, Transport_hasFrequency

4. STATION HIERARCHY:
   - Station (base class): locatedIn→City, connectedTo→Station (symmetric & transitive)
     ├─ BusStop
     ├─ MetroStation
     ├─ TrainStation
     └─ TramStation
   
   Data Properties: Station_hasName, Station_hasLocation, Station_hasAccessibility

5. COMPANY HIERARCHY:
   - Company (base class): basedIn→City, manages→Transport
     ├─ BusCompany: numberOfBusLines, averageBusAge, ticketPrice, ecoFriendlyFleet
     ├─ MetroCompany: numberOfLines, totalTrackLength, automationLevel, dailyPassengers
     ├─ TaxiCompany: numberOfVehicles, bookingApp, averageFarePerKm, serviceType
     └─ BikeSharingCompany: numberOfStations, bikeCount, subscriptionPrice, electricBikes
   
   Data Properties: companyName, foundedYear, numberOfEmployees, headquartersLocation

6. CITY HIERARCHY:
   - City (base class): cityName, population, area, region
     ├─ CapitalCity: governmentSeat, numberOfMinistries, internationalEmbassies, annualBudget
     ├─ MetropolitanCity: suburbanPopulation, publicTransportCoverage, numberOfDistricts, averageCommuteTime
     ├─ TouristicCity: annualVisitors, mainAttractions, hotelCount, coastalCity
     └─ IndustrialCity: numberOfFactories, mainIndustries, industrialZoneArea, pollutionIndex

7. ITINERARY HIERARCHY:
   - Itinerary (base class): uses→Transport, hasSchedule→Schedule
     ├─ BusinessTrip: clientProjectName, expenseLimit, purposeCode, approvalRequired
     ├─ LeisureTrip: activityType, accommodation, budgetPerDay, groupSize
     └─ EducationalTrip: institution, courseReference, creditHours, requiredDocumentation
   
   Data Properties: itineraryID, overallStatus, totalCostEstimate, totalDurationDays

8. SCHEDULE HIERARCHY:
   - Schedule (base class): appliesTo→Transport
     ├─ DailySchedule: firstRunTime, lastRunTime, frequencyMinutes, dayOfWeekMask
     ├─ SeasonalSchedule: season, startDate, endDate, operationalCapacityPercentage
     └─ OnDemandSchedule: bookingLeadTimeHours, serviceWindowStart, serviceWindowEnd, maxWaitTimeMinutes
   
   Data Properties: scheduleID, routeName, effectiveDate, isPublic

═══════════════════════════════════════════════════════════════════
EXISTING INSTANCES (use these exact URIs):
═══════════════════════════════════════════════════════════════════
Cities: :city_Tunis, :city_Sfax, :city_Sousse, :city_Bizerte
Companies: :busCompany_Tunis, :metroCompany_Tunis, :taxiCompany_YellowCab, :bikeSharingCompany_VeloGo
Transports: :Bus_23, :Metro_L1
Stations: :station_BabElKhadhra, :station_BenArous, :station_TunisMarine, :station_LaMarsa
Persons: :person_AhmedK (Passager), :person_SamiraJ (Conducteur)
Tickets: :ticket_0001, :subscription_Ahmed_Oct
Itineraries: :ITN001, :ITN002, :ITN003, :ITN004, :ITN005, :ITN006
Schedules: :SCH001, :SCH002, :SCH003, :SCH004, :SCH005, :SCH006

═══════════════════════════════════════════════════════════════════
SPARQL PATTERNS YOU MUST USE:
═══════════════════════════════════════════════════════════════════
1. For subclasses: ?x a/rdfs:subClassOf* :ClassName  OR  ?x a :SpecificSubclass
2. For relationships: ?subject :propertyName ?object .
3. For optional properties: OPTIONAL { ?x :property ?y }
4. For filters: FILTER(?var > value) or FILTER(CONTAINS(?var, "text"))
5. Always add: ORDER BY and LIMIT 10
"""

    examples = """
═══════════════════════════════════════════════════════════════════
PERFECT EXAMPLES - COPY THIS STRUCTURE EXACTLY:
═══════════════════════════════════════════════════════════════════

Input: "List all itineraries"
PREFIX : <http://www.transport-ontology.org/travel#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?id ?status ?cost ?duration
WHERE {
  ?it a/rdfs:subClassOf* :Itinerary ;
      :itineraryID ?id ;
      :overallStatus ?status .
  OPTIONAL { ?it :totalCostEstimate ?cost }
  OPTIONAL { ?it :totalDurationDays ?duration }
}
ORDER BY ?id
LIMIT 10

Input: "Show bus lines in Tunis"
PREFIX : <http://www.transport-ontology.org/travel#>
SELECT ?line ?capacity ?speed
WHERE {
  ?bus a :Bus ;
       :Transport_hasLineNumber ?line ;
       :operatesIn :city_Tunis ;
       :Transport_hasCapacity ?capacity ;
       :Transport_hasSpeed ?speed .
}
LIMIT 10

Input: "Show all passengers and their tickets"
PREFIX : <http://www.transport-ontology.org/travel#>
SELECT ?personName ?personAge ?ticketID ?ticketPrice
WHERE {
  ?person a :Passager ;
          :hasName ?personName ;
          :hasAge ?personAge ;
          :buys ?ticket .
  ?ticket :hasTicketID ?ticketID ;
          :hasPrice ?ticketPrice .
}
LIMIT 10

Input: "Show all drivers and their companies"
PREFIX : <http://www.transport-ontology.org/travel#>
SELECT ?driverName ?driverAge ?license ?companyName
WHERE {
  ?driver a :Conducteur ;
          :hasName ?driverName ;
          :hasAge ?driverAge ;
          :hasLicenseNumber ?license ;
          :worksFor ?company .
  ?company :companyName ?companyName .
}
LIMIT 10

Input: "Show all transports with operators stations and schedules"
PREFIX : <http://www.transport-ontology.org/travel#>
SELECT ?line ?companyName ?departStation ?arriveStation ?scheduleName
WHERE {
  ?trans :Transport_hasLineNumber ?line ;
         :operatedBy ?company ;
         :departsFrom ?depart ;
         :arrivesAt ?arrive .
  ?company :companyName ?companyName .
  ?depart :Station_hasName ?departStation .
  ?arrive :Station_hasName ?arriveStation .
  OPTIONAL {
    ?schedule :appliesTo ?trans ;
              :routeName ?scheduleName .
  }
}
LIMIT 10

Input: "Business trips under 1000"
PREFIX : <http://www.transport-ontology.org/travel#>
SELECT ?id ?project ?cost
WHERE {
  ?trip a :BusinessTrip ;
        :itineraryID ?id ;
        :clientProjectName ?project ;
        :totalCostEstimate ?cost .
  FILTER(?cost < 1000)
}
ORDER BY ?cost
LIMIT 10

Input: "Show all schedules"
PREFIX : <http://www.transport-ontology.org/travel#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?id ?route ?date
WHERE {
  ?sch a/rdfs:subClassOf* :Schedule ;
       :scheduleID ?id ;
       :routeName ?route .
  OPTIONAL { ?sch :effectiveDate ?date }
}
ORDER BY ?id
LIMIT 10

Input: "Find connected metro stations"
PREFIX : <http://www.transport-ontology.org/travel#>
SELECT ?station1Name ?station2Name
WHERE {
  ?s1 a :MetroStation ;
      :Station_hasName ?station1Name ;
      :connectedTo ?s2 .
  ?s2 :Station_hasName ?station2Name .
}
LIMIT 10

Input: "Show companies managing transports"
PREFIX : <http://www.transport-ontology.org/travel#>
SELECT ?companyName ?transportLine
WHERE {
  ?company :companyName ?companyName ;
           :manages ?trans .
  ?trans :Transport_hasLineNumber ?transportLine .
}
LIMIT 10

Input: "List educational trips with institutions"
PREFIX : <http://www.transport-ontology.org/travel#>
SELECT ?id ?institution ?course ?credits
WHERE {
  ?trip a :EducationalTrip ;
        :itineraryID ?id ;
        :institution ?institution ;
        :courseReference ?course ;
        :creditHours ?credits .
}
LIMIT 10
"""

    prompt = f"""You are an expert SPARQL query generator for a Transport Ontology.

{schema_snippet}

{examples}

═══════════════════════════════════════════════════════════════════
CRITICAL INSTRUCTIONS:
═══════════════════════════════════════════════════════════════════
1. Output ONLY the SPARQL query - NO explanations, NO markdown, NO ```
2. Use EXACT property names from the schema above
3. Always start with PREFIX lines
4. Use ?variableName patterns from examples
5. For subclasses use: a/rdfs:subClassOf* :ClassName
6. For relationships follow the arrow directions: subject :property object
7. Use OPTIONAL {{ }} for properties that might not exist
8. Always end with LIMIT 10
9. Match the exact format of the examples above

User Question: "{question}"

Generate the SPARQL query NOW (nothing else):"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=800,
    )
    
    generated = response.choices[0].message.content.strip()
    print(f"[DEBUG] AI Generated:\n{generated}\n")
    
    # Extraction minimale (juste nettoyage)
    sparql = clean_sparql(generated)
    print(f"[OK] Final SPARQL:\n{sparql}\n")
    
    return sparql

def clean_sparql(text):
    """Clean AI output - minimal processing"""
    # Remove markdown blocks
    text = re.sub(r'```sparql\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'```\s*', '', text)
    
    # Remove any explanation text before PREFIX
    if 'PREFIX' in text:
        text = text[text.index('PREFIX'):]
    
    # Remove any text after LIMIT
    if 'LIMIT' in text.upper():
        lines = text.split('\n')
        result = []
        for line in lines:
            result.append(line)
            if 'LIMIT' in line.upper():
                break
        text = '\n'.join(result)
    
    return text.strip()
def nl_to_sparql_update(question: str) -> str:
    """Convert natural language to SPARQL UPDATE queries"""
    api_key = os.getenv('GROQ_API_KEY')
    if not api_key:
        print("[ERROR] GROQ_API_KEY missing in .env")
        return ""

    client = Groq(api_key=api_key)

    update_schema = """
═══════════════════════════════════════════════════════════════════
SPARQL UPDATE OPERATIONS - INSERT, DELETE, MODIFY
═══════════════════════════════════════════════════════════════════

CRITICAL RULES FOR UPDATE QUERIES:
1. INSERT: Add new triples
2. DELETE: Remove triples  
3. DELETE/INSERT: Modify triples

EXAMPLES OF UPDATE OPERATIONS:

INSERT NEW STATION (WITH GRAPH):
PREFIX : <http://www.transport-ontology.org/travel#>
INSERT DATA {
  GRAPH <http://www.transport-ontology.org/travel> {
    :station_new_bus_stop a :BusStop ;
                        :Station_hasName "Nouvel Arrêt" ;
                        :Station_hasLocation "Rue Principale" ;
                        :Station_hasAccessibility true ;
                        :locatedIn :city_Tunis .
  }
}

INSERT NEW BUS (WITH GRAPH):
PREFIX : <http://www.transport-ontology.org/travel#>
INSERT DATA {
  GRAPH <http://www.transport-ontology.org/travel> {
    :Bus_99 a :Bus ;
            :Transport_hasLineNumber "99" ;
            :Transport_hasCapacity 50 ;
            :Transport_hasSpeed 45.0 ;
            :operatesIn :city_Tunis ;
            :operatedBy :busCompany_Tunis .
  }
}

DELETE STATION (WITH GRAPH):
PREFIX : <http://www.transport-ontology.org/travel#>
DELETE WHERE {
  GRAPH <http://www.transport-ontology.org/travel> {
    :station_soukra ?p ?o .
  }
}

MODIFY STATION NAME (WITH GRAPH):
PREFIX : <http://www.transport-ontology.org/travel#>
WITH <http://www.transport-ontology.org/travel>
DELETE { :station_soukra :Station_hasName "soukra" }
INSERT { :station_soukra :Station_hasName "Soukra Modifié" }
WHERE { :station_soukra :Station_hasName "soukra" }

ADD ACCESSIBILITY TO STATION (WITH GRAPH):
PREFIX : <http://www.transport-ontology.org/travel#>
INSERT DATA {
  GRAPH <http://www.transport-ontology.org/travel> {
    :station_soukra :Station_hasAccessibility true .
  }
}

REMOVE ACCESSIBILITY FROM STATION (WITH GRAPH):
PREFIX : <http://www.transport-ontology.org/travel#>
DELETE DATA {
  GRAPH <http://www.transport-ontology.org/travel> {
    :station_soukra :Station_hasAccessibility true .
  }
}

CREATE NEW PASSENGER (WITH GRAPH):
PREFIX : <http://www.transport-ontology.org/travel#>
INSERT DATA {
  GRAPH <http://www.transport-ontology.org/travel> {
    :person_NewPassenger a :Passager ;
                        :hasName "Nouveau Passager" ;
                        :hasAge 30 ;
                        :hasEmail "nouveau@email.com" ;
                        :hasSubscriptionType "mensuel" .
  }
}

═══════════════════════════════════════════════════════════════════
EXISTING URIs YOU CAN USE:
═══════════════════════════════════════════════════════════════════
Cities: :city_Tunis, :city_Sfax, :city_Sousse, :city_Bizerte
Companies: :busCompany_Tunis, :metroCompany_Tunis
Stations: :station_BabElKhadhra, :station_BenArous, :station_TunisMarine, :station_LaMarsa, :station_soukra
Transports: :Bus_23, :Metro_L1
Persons: :person_AhmedK, :person_SamiraJ

URI PATTERNS FOR NEW INSTANCES:
- Stations: :station_{unique_name} (e.g., :station_my_new_stop)
- Transports: :{TransportType}_{line} (e.g., :Bus_99, :Metro_L2)
- Persons: :person_{unique_name} (e.g., :person_JohnDoe)

GRAPH URI: <http://www.transport-ontology.org/travel>
═══════════════════════════════════════════════════════════════════
"""

    examples = """
═══════════════════════════════════════════════════════════════════
PERFECT UPDATE EXAMPLES (WITH GRAPH):
═══════════════════════════════════════════════════════════════════

Input: "Add a new bus stop named Central Station in Tunis"
PREFIX : <http://www.transport-ontology.org/travel#>
INSERT DATA {
  GRAPH <http://www.transport-ontology.org/travel> {
    :station_central_station a :BusStop ;
                            :Station_hasName "Central Station" ;
                            :Station_hasLocation "Tunis Centre" ;
                            :Station_hasAccessibility true ;
                            :locatedIn :city_Tunis .
  }
}

Input: "Create a new bus line 99 with capacity 60"
PREFIX : <http://www.transport-ontology.org/travel#>
INSERT DATA {
  GRAPH <http://www.transport-ontology.org/travel> {
    :Bus_99 a :Bus ;
            :Transport_hasLineNumber "99" ;
            :Transport_hasCapacity 60 ;
            :Transport_hasSpeed 50.0 ;
            :Transport_hasFrequency 15 ;
            :operatesIn :city_Tunis ;
            :operatedBy :busCompany_Tunis .
  }
}

Input: "Delete the station soukra"
PREFIX : <http://www.transport-ontology.org/travel#>
DELETE WHERE {
  GRAPH <http://www.transport-ontology.org/travel> {
    :station_soukra ?p ?o .
  }
}

Input: "Change station soukra name to New Soukra"
PREFIX : <http://www.transport-ontology.org/travel#>
WITH <http://www.transport-ontology.org/travel>
DELETE { :station_soukra :Station_hasName "soukra" }
INSERT { :station_soukra :Station_hasName "New Soukra" }
WHERE { :station_soukra :Station_hasName "soukra" }

Input: "Make station soukra accessible"
PREFIX : <http://www.transport-ontology.org/travel#>
INSERT DATA {
  GRAPH <http://www.transport-ontology.org/travel> {
    :station_soukra :Station_hasAccessibility true .
  }
}

Input: "Remove accessibility from station soukra"
PREFIX : <http://www.transport-ontology.org/travel#>
DELETE DATA {
  GRAPH <http://www.transport-ontology.org/travel> {
    :station_soukra :Station_hasAccessibility true .
  }
}

Input: "Add a new passenger named John Doe age 25"
PREFIX : <http://www.transport-ontology.org/travel#>
INSERT DATA {
  GRAPH <http://www.transport-ontology.org/travel> {
    :person_JohnDoe a :Passager ;
                   :hasName "John Doe" ;
                   :hasAge 25 ;
                   :hasEmail "john@email.com" ;
                   :hasSubscriptionType "hebdomadaire" .
  }
}

Input: "Connect station Bab El Khadhra to station Ben Arous"
PREFIX : <http://www.transport-ontology.org/travel#>
INSERT DATA {
  GRAPH <http://www.transport-ontology.org/travel> {
    :station_BabElKhadhra :connectedTo :station_BenArous .
  }
}
"""

    prompt = f"""You are an expert SPARQL UPDATE query generator for a Transport Ontology.

{update_schema}

{examples}

═══════════════════════════════════════════════════════════════════
CRITICAL UPDATE INSTRUCTIONS:
═══════════════════════════════════════════════════════════════════
1. For INSERT DATA: Always use GRAPH <http://www.transport-ontology.org/travel> {{ ... }}
2. For DELETE WHERE: Always use GRAPH <http://www.transport-ontology.org/travel> {{ ... }}
3. For DELETE/INSERT: Use WITH <http://www.transport-ontology.org/travel>
4. For DELETE DATA: Always use GRAPH <http://www.transport-ontology.org/travel> {{ ... }}
5. Generate valid URIs for new instances using patterns above
6. Use existing URIs when modifying/deleting existing data
7. Include ALL required properties for new instances
8. Output ONLY the SPARQL UPDATE query - NO explanations

User Request: "{question}"

Generate the SPARQL UPDATE query NOW (nothing else):"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=800,
    )
    
    generated = response.choices[0].message.content.strip()
    print(f"[DEBUG] AI Generated UPDATE:\n{generated}\n")
    
    # Clean the output
    sparql = clean_sparql(generated)
    print(f"[OK] Final SPARQL UPDATE:\n{sparql}\n")
    
    return sparql
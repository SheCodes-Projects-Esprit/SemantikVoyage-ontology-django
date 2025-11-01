from django.core.management.base import BaseCommand
from django.conf import settings
from core.utils.fuseki import sparql_query, test_fuseki_connection
import requests

class Command(BaseCommand):
    help = 'Debug Fuseki connection and configuration'
    
    def handle(self, *args, **options):
        self.stdout.write('🔧 Debug Fuseki Configuration')
        
        # Check settings
        self.stdout.write(f"FUSEKI_URL: {getattr(settings, 'FUSEKI_URL', 'Non défini')}")
        self.stdout.write(f"FUSEKI_DATASET: {getattr(settings, 'FUSEKI_DATASET', 'Non défini')}")
        self.stdout.write(f"FUSEKI_GRAPH: {getattr(settings, 'FUSEKI_GRAPH', 'Non défini')}")
        
        # Test connection
        self.stdout.write('\n🧪 Test de connexion...')
        if test_fuseki_connection():
            self.stdout.write(self.style.SUCCESS('✅ Connexion Fuseki OK'))
        else:
            self.stdout.write(self.style.ERROR('❌ Connexion Fuseki échouée'))
            return
        
        # Test simple query
        self.stdout.write('\n🧪 Test requête simple...')
        try:
            test_query = "SELECT * WHERE { ?s ?p ?o } LIMIT 3"
            result = sparql_query(test_query)
            count = len(result['results']['bindings'])
            self.stdout.write(self.style.SUCCESS(f'✅ Requête test OK ({count} résultats)'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Requête test échouée: {e}'))
        
        # Test ontology query
        self.stdout.write('\n🧪 Test requête ontologie...')
        try:
            ontology_query = """
            PREFIX : <http://www.transport-ontology.org/travel#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            
            SELECT ?station ?name 
            WHERE {
                ?station a/rdfs:subClassOf* :Station ;
                        :Station_hasName ?name .
            }
            LIMIT 5
            """
            result = sparql_query(ontology_query)
            count = len(result['results']['bindings'])
            self.stdout.write(self.style.SUCCESS(f'✅ Requête ontologie OK ({count} stations)'))
            
            # Show results
            for binding in result['results']['bindings']:
                self.stdout.write(f"   - {binding['name']['value']}")
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Requête ontologie échouée: {e}'))
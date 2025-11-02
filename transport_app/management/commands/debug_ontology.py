from django.core.management.base import BaseCommand
from core.utils.fuseki import sparql_query, sparql_update

class Command(BaseCommand):
    help = 'Debug ontology update issues'
    
    def handle(self, *args, **options):
        self.stdout.write('🔧 Debug des problèmes de mise à jour ontologie...')
        
        # 1. Vérifier les données existantes
        self.stdout.write('\n1. 📊 Données existantes:')
        try:
            check_query = """
            PREFIX : <http://www.transport-ontology.org/travel#>
            SELECT ?s ?p ?o WHERE {
                ?s ?p ?o
            } LIMIT 10
            """
            result = sparql_query(check_query)
            self.stdout.write(f"   Total triples: {len(result['results']['bindings'])}")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   ❌ Erreur: {e}"))
        
        # 2. Tester une insertion simple
        self.stdout.write('\n2. 🧪 Test insertion:')
        try:
            test_insert = """
            PREFIX : <http://www.transport-ontology.org/travel#>
            INSERT DATA {
                :test_bus_123 a :Bus ;
                            :Transport_hasLineNumber "123" ;
                            :Transport_hasCapacity 40 .
            }
            """
            sparql_update(test_insert)
            self.stdout.write(self.style.SUCCESS('   ✅ Insertion test réussie'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   ❌ Erreur insertion: {e}"))
        
        # 3. Vérifier l'insertion
        self.stdout.write('\n3. 🔍 Vérification insertion:')
        try:
            verify_query = """
            PREFIX : <http://www.transport-ontology.org/travel#>
            SELECT ?line ?capacity WHERE {
                ?bus a :Bus ;
                     :Transport_hasLineNumber ?line ;
                     :Transport_hasCapacity ?capacity .
                FILTER(?line = "123")
            }
            """
            result = sparql_query(verify_query)
            if result['results']['bindings']:
                self.stdout.write(self.style.SUCCESS(f'   ✅ Bus test trouvé: {result["results"]["bindings"]}'))
            else:
                self.stdout.write(self.style.WARNING('   ⚠️  Bus test non trouvé'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   ❌ Erreur vérification: {e}"))
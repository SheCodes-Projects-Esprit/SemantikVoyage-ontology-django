from django.core.management.base import BaseCommand
from transport_app.services.ontology_service import OntologySyncService
from core.utils.rdf_loader import load_ontology_to_fuseki

class Command(BaseCommand):
    help = 'Initialize ontology with base data and sync existing Django data'
    
    def handle(self, *args, **options):
        try:
            # 1. Load base ontology
            self.stdout.write('Loading base ontology...')
            result = load_ontology_to_fuseki()
            self.stdout.write(self.style.SUCCESS('Base ontology loaded successfully'))
            
            # 2. Sync existing Django data
            self.stdout.write('Syncing existing Django data...')
            sync_service = OntologySyncService()
            sync_result = sync_service.sync_all_data()
            self.stdout.write(self.style.SUCCESS(f'Data sync completed: {sync_result}'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {e}'))
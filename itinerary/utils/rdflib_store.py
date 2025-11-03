from django.conf import settings
from rdflib import ConjunctiveGraph, Namespace
from rdflib.plugins.stores.sparqlstore import SPARQLUpdateStore


def get_graph():
    """Return a connected rdflib ConjunctiveGraph backed by Fuseki SPARQL endpoints."""
    query_endpoint = None
    update_endpoint = None
    try:
        base = settings.FUSEKI_URL
        dataset = settings.FUSEKI_DATASET
        query_endpoint = f"{base}/{dataset}/query"
        update_endpoint = f"{base}/{dataset}/update"
    except Exception:
        query_endpoint = "http://localhost:3030/transport_db/query"
        update_endpoint = "http://localhost:3030/transport_db/update"

    store = SPARQLUpdateStore()
    store.open((query_endpoint, update_endpoint))

    graph = ConjunctiveGraph(store=store)
    # Bind commonly used namespaces
    tr = Namespace("http://www.transport-ontology.org/travel#")
    graph.bind("", tr)  # default
    graph.bind("tr", tr)
    return graph


def get_named_graph(graph: ConjunctiveGraph):
    """Return the named graph context if configured; otherwise the default graph."""
    graph_uri = getattr(settings, "FUSEKI_GRAPH", None)
    if graph_uri:
        return graph.get_context(graph_uri)
    return graph.default_context



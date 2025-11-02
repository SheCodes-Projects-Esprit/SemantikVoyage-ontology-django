from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Get item from dictionary by key"""
    return dictionary.get(key, {})

@register.filter
def get_value(binding, var):
    """Get value from SPARQL result binding"""
    if var in binding:
        return binding[var].get('value', 'N/A')
    return 'N/A'
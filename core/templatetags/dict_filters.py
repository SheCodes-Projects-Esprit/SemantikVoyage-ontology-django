# core/templatetags/dict_filters.py
from django import template

register = template.Library()

@register.filter(name='get_item', is_safe=True)
def get_item(dictionary, key):
    if not isinstance(dictionary, dict):
        return ''
    return dictionary.get(str(key), '')  # key might be variable name as string
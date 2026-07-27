"""
Custom Template Tags and Filters for QAID Manager.

This module provides custom Django template filters for use in templates.
"""
from django import template

register = template.Library()

@register.filter
def get_object_attr(obj, attr):
    """
    Get an attribute from an object.
    
    Usage: {{ object|get_object_attr:"attribute_name" }}
    """
    return getattr(obj, attr, None)

@register.filter
def abs_value(value):
    """
    Get the absolute value of a number.
    
    Usage: {{ value|abs_value }}
    """
    try:
        return abs(float(value))
    except (ValueError, TypeError):
        return value

@register.filter
def get_item(dictionary, key):
    """
    Get an item from a dictionary by key.
    
    Usage: {{ dictionary|get_item:key }}
    """
    if dictionary is None:
        return None
    try:
        result = dictionary.get(key, None)
        if result is None and isinstance(key, str):
            try:
                result = dictionary.get(int(key), None)
            except (ValueError, TypeError):
                pass
        return result
    except (TypeError, AttributeError):
        return None

@register.filter
def split_lines(value):
    """
    Split text by newlines and return a list.
    
    Usage: {{ text|split_lines }}
    Returns a list of non-empty lines.
    """
    if not value:
        return []
    return [line.strip() for line in str(value).split('\n') if line.strip()]

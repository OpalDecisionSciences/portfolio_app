"""
Custom template filters for restaurant app.
"""
from django import template
from django.template.defaultfilters import floatformat

register = template.Library()


@register.filter
def mul(value, arg):
    """Multiply the value by the argument."""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def rating_width(value):
    """Convert rating (1-5) to percentage width (0-100)."""
    try:
        rating = float(value)
        # Convert 5-star rating to percentage (multiply by 20)
        return min(max(rating * 20, 0), 100)
    except (ValueError, TypeError):
        return 0


@register.filter
def michelin_stars_display(stars):
    """Display Michelin stars as star emojis."""
    try:
        star_count = int(stars)
        return "⭐" * star_count
    except (ValueError, TypeError):
        return ""
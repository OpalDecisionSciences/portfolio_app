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


@register.filter
def restaurant_open_status(restaurant):
    """Get restaurant open/closed status with local time consideration."""
    try:
        status_info = restaurant.is_currently_open()
        if status_info['is_open'] is True:
            return f"🟢 {status_info['status']}"
        elif status_info['is_open'] is False:
            return f"🔴 {status_info['status']}"
        else:
            return f"⚪ {status_info['status']}"
    except Exception:
        return "⚪ Hours unknown"


@register.filter
def restaurant_local_time(restaurant):
    """Display current local time for the restaurant."""
    try:
        local_time = restaurant.get_current_local_time()
        return local_time.strftime('%H:%M %Z')
    except Exception:
        return "Time unknown"


@register.filter
def restaurant_timezone(restaurant):
    """Display restaurant's timezone in a user-friendly format."""
    try:
        return restaurant.get_timezone_display()
    except Exception:
        return "Unknown timezone"


@register.filter
def get_range(value):
    """Create a range for template iteration."""
    try:
        return range(int(value))
    except (ValueError, TypeError):
        return range(0)


@register.filter
def sum_michelin_stars(restaurants):
    """Sum up all Michelin stars from a queryset of restaurants."""
    try:
        return sum(restaurant.michelin_stars for restaurant in restaurants if restaurant.michelin_stars)
    except (ValueError, TypeError):
        return 0


@register.filter
def filter_by_stars(restaurants, stars):
    """Filter restaurants by number of Michelin stars."""
    try:
        star_count = int(stars)
        return [r for r in restaurants if r.michelin_stars == star_count]
    except (ValueError, TypeError):
        return []
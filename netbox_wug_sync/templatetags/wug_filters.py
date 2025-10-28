"""
Custom template filters for NetBox WUG Sync plugin.
"""

from django import template

register = template.Library()


@register.filter
def format_duration(seconds):
    """
    Format duration in seconds to a human-readable format.
    
    Usage in templates:
    {{ duration|format_duration }}
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted string like "2m 30s" or "45s"
    """
    try:
        seconds = float(seconds)
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            remaining_seconds = seconds % 60
            if remaining_seconds < 1:
                return f"{minutes}m"
            else:
                return f"{minutes}m {remaining_seconds:.0f}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"
    except (ValueError, TypeError):
        return "0s"


@register.filter
def percentage(value, total):
    """
    Calculate percentage of value relative to total.
    
    Usage in templates:
    {{ success_count|percentage:total_count }}
    
    Args:
        value: The value to calculate percentage for
        total: The total value to calculate percentage against
        
    Returns:
        Percentage as a float, or 0 if total is 0
    """
    try:
        return (float(value) / float(total)) * 100 if float(total) != 0 else 0
    except (ValueError, TypeError, ZeroDivisionError):
        return 0
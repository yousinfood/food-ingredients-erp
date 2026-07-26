from django import template

from apps.sales.services.customer_search import highlight_match

register = template.Library()


@register.filter(name="highlight_query")
def highlight_query(value, query):
    return highlight_match(value, query or "")

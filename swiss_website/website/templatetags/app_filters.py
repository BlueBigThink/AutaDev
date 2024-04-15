from django import template
from datetime import datetime


register = template.Library()

@register.filter(name='scc_hubraum')
def scc_hubraum(value):
    if not value:
        return value
    return str(int(float(value))) + ' cm'


@register.filter(name='scc_mfk')
def scc_mfk(value):
    if not value:
        return value
    return datetime.fromtimestamp(
        int(float(value))/1000
    ).strftime('%Y-%m-%d')



@register.filter(name='scc_leistung')
def scc_leistung(value):
    if not value:
        return value
    return str(int(float(value))) + ' KW'


@register.filter(name='scc_reparturkosten')
def scc_reparturkosten(value):
    if not value:
        return value
    return str(int(float(value))) + ' CHF'


@register.filter(name='scc_sonderausstattung')
def scc_sonderausstattung(value):
    if not value:
        return value
    return str(int(float(value))) + ' CHF'


@register.filter(name='scc_katalogpreis')
def scc_katalogpreis(value):
    if not value:
        return value
    return str(int(float(value))) + ' CHF'


@register.filter(name='scc_zahlerstand')
def scc_zahlerstand(value):
    if not value:
        return value
    return str(int(float(value))) + ' km'

@register.filter(name='vin_hide')
def vin_hide(value):
    if not value:
        return value
    return str(value)[:-5] + '*****'

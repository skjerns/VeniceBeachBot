# -*- coding: utf-8 -*-
"""
Created on Wed Dec 28 06:21:09 2022

@author: Simon
"""

TEMPLATE_HELP = """Willkommen {user} beim VeniceBeachBot. Dieser Bot sagt dir, wie viel momentan in deiner Venice Beach Location los ist.
Zur Konfiguration musst du einmalig dein Studio auswählen, klicke dafür /studios

Du kannst die folgenden Befehle verwenden:
/graph -  zeige einen Graphen der momentanen Auslastung deiner Location
/studios -  liste alle Venice Beach Locations
/support [text] -  schicke eine Nachricht an den Ersteller des Bots
/status - zeige deine Einstellungen
/help -  zeige diese Hilfe an
"""

TEMPLATE_SUPPORT = """Deine Nachricht wurde an den Botersteller weitergeleitet. Vielleicht meldet er sich bei dir, vielleicht nicht."""

TEMPLATE_NO_GROUP = """Dieser Bot kann nicht in einer Gruppe verwendet werden."""

TEMPLATE_STATUS = """Du bist {user}, dein Studio ist {studio}, du hast den Bot schon {n_access}x benutzt"""

TEMPLATE_NEW_STUDIO = "Dieses Studio ist noch nicht im Pool, ab jetzt werden die Daten für dich aufgezeichnet. Das heisst, es kann ein bisschen dauern, bis die Daten ausreichend sind."

def format_user(user):
    if hasattr(user, 'to_dict'):
        user = user.to_dict()
    user_id = user["id"]
    first_name = user["first_name"]
    last_name = user["last_name"]
    user_name = user["username"]
    string = f'<a href="tg://user?id={user_id}">{first_name}' \
             f'{last_name}</a> (@{user_name})'
    return string
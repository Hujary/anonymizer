# ner/__init__.py

###     NER-Package Public API
### __________________________________________________________________________
#
#  Ziel:
#    - Eindeutige Import-Quelle für den Rest der App
#    - Verhindert "zufällig falsche Datei" Probleme
#
#  Regel:
#    - spaCy/Model/Boost nur in ner_core.py
#    - Treffer-Postfilter nur in filters.py
#


from .ner_core import finde_ner, get_current_model, set_spacy_model
from .filters import filter_ner_strict, clean_ner_hits

__all__ = [
    "finde_ner",
    "get_current_model",
    "set_spacy_model",
    "filter_ner_strict",
    "clean_ner_hits",
]
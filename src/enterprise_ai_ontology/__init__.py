"""Enterprise AI Ontology: describe, validate and visualize business meaning."""

from .models import Ontology
from .serialization import dumps, load, loads

__version__ = "0.1.0"
__all__ = ["Ontology", "dumps", "load", "loads"]

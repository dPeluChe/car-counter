"""Entry point: python -m carcounter

Lanza la aplicacion Car Counter con interfaz grafica.
"""

import sys
import os

# Asegurar que el root del proyecto este en el path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from carcounter.app import launch

if __name__ == "__main__":
    launch()

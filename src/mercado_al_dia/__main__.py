"""Ejecuta la fase 1 completa: python -m mercado_al_dia"""
import sys

from .proceso import main

sys.exit(main(sys.argv[1:]))

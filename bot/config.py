"""Carga la configuración y las rutas del proyecto."""
import os
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "data"
REMOTION = RAIZ / "remotion"
PUBLICO = REMOTION / "public"
ESCENAS = REMOTION / "src" / "escenas"
SALIDA = RAIZ / "salida"
PROMPTS = Path(__file__).resolve().parent / "prompts"


def cargar_config() -> dict:
    with open(RAIZ / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def secreto(nombre: str, obligatorio: bool = True) -> str:
    valor = os.environ.get(nombre, "").strip()
    if obligatorio and not valor:
        raise RuntimeError(f"Falta el secreto {nombre}. Agrégalo en GitHub > Settings > Secrets.")
    return valor


def prompt(nombre: str) -> str:
    return (PROMPTS / nombre).read_text(encoding="utf-8")

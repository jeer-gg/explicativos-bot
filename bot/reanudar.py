"""Reanudar un video que se quedó a medias porque se agotó el límite de Claude.

Mientras se produce, el bot va guardando el avance (tema, guion y cada escena ya dibujada).
Si se acaba el límite, guarda ese avance en data/en_curso.json, calcula cuándo se renueva y
apunta la hora. La misma tarea espera a que se renueve y sigue (si la espera no cabe en una tarea
de GitHub, lanza otra que sigue esperando). El video sigue desde donde se quedó: no se repite lo ya
hecho. La revisión de cada 20 minutos y las tareas programadas quedan de respaldo.
"""
import json
import re
from datetime import datetime, timedelta, timezone

from .config import DATOS
from .memoria import _guardar, _leer, estado, guardar_estado

EN_CURSO = DATOS / "en_curso.json"
AVANCE: dict = {}  # se va llenando durante la producción


def empezar() -> dict:
    """Devuelve el avance guardado (si hay un video a medias) y lo deja listo para seguir."""
    AVANCE.clear()
    previo = _leer(EN_CURSO, {})
    if previo.get("tema"):
        AVANCE.update(previo)
        AVANCE["reanudado"] = True
    else:
        AVANCE.update({"inicio": datetime.now(timezone.utc).isoformat(timespec="seconds"), "escenas": {}})
    AVANCE.setdefault("escenas", {})
    e = estado()
    if e.pop("reintentar_desde", None) or e.pop("esperando", None):
        e.pop("esperando", None)
        guardar_estado(e)
    return AVANCE


def inicio() -> datetime:
    return datetime.fromisoformat(AVANCE.get("inicio") or datetime.now(timezone.utc).isoformat())


def terminar():
    """El video salió bien: se borra el avance guardado."""
    if EN_CURSO.exists():
        EN_CURSO.unlink()
    AVANCE.clear()


def hora_de_renovacion(mensaje: str) -> datetime:
    """Lee "resets 1:50pm (UTC)" del aviso de Claude. Si no se entiende, en 1 hora."""
    ahora = datetime.now(timezone.utc)
    m = re.search(r"resets?\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", mensaje, re.I)
    if not m:
        return ahora + timedelta(hours=1)
    h, mi = int(m.group(1)), int(m.group(2) or 0)
    if m.group(3):
        h = h % 12 + (12 if m.group(3).lower() == "pm" else 0)
    cuando = ahora.replace(hour=h % 24, minute=mi, second=0, microsecond=0)
    if cuando <= ahora:
        cuando += timedelta(days=1)
    return cuando + timedelta(minutes=5)


def guardar_por_limite(mensaje: str) -> datetime:
    """Guarda el avance y apunta cuándo seguir."""
    if AVANCE.get("tema"):
        _guardar(EN_CURSO, {k: v for k, v in AVANCE.items() if k != "reanudado"})
    cuando = hora_de_renovacion(mensaje)
    e = estado()
    e["reintentar_desde"] = cuando.isoformat(timespec="seconds")
    guardar_estado(e)
    return cuando


def toca_reintentar() -> bool:
    """Lo usa la revisión de cada 20 minutos: ¿ya se renovó el límite?"""
    e = estado()
    cuando = e.get("reintentar_desde")
    if not cuando or datetime.now(timezone.utc) < datetime.fromisoformat(cuando):
        return False
    # Si una tarea de producción ya está esperando la renovación, ella sigue sola
    esperando = e.get("esperando")
    if esperando and datetime.now(timezone.utc) - datetime.fromisoformat(esperando) < timedelta(hours=6):
        return False
    # Se aplaza por si el intento también falla (producir lo borra al empezar)
    e["reintentar_desde"] = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(timespec="seconds")
    guardar_estado(e)
    return True

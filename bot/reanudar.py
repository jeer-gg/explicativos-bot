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
from .memoria import _guardar, _leer, cadena, estado, guardar_cadena, guardar_estado

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
    c = cadena()
    if c.pop("reintentar_desde", None) or c.pop("esperando", None):
        c.pop("esperando", None)
        guardar_cadena(c)
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
    meses = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug",
                                                "sep", "oct", "nov", "dec"])}
    f = re.search(r"resets?\s+(?:on\s+)?([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2}),?\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?",
                  mensaje, re.I)
    if f and f.group(1).lower() in meses:  # límite semanal: "resets Nov 25, 9am"
        h, mi = int(f.group(3)), int(f.group(4) or 0)
        if f.group(5):
            h = h % 12 + (12 if f.group(5).lower() == "pm" else 0)
        cuando = ahora.replace(month=meses[f.group(1).lower()], day=int(f.group(2)), hour=h % 24,
                               minute=mi, second=0, microsecond=0)
        if cuando <= ahora:
            cuando = cuando.replace(year=cuando.year + 1)
        return cuando + timedelta(minutes=5)
    m = re.search(r"resets?\s+(?:at\s+)?(?:[A-Za-z]{3}[a-z]*\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", mensaje, re.I)
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
    c = cadena()
    c["reintentar_desde"] = cuando.isoformat(timespec="seconds")
    guardar_cadena(c)
    return cuando

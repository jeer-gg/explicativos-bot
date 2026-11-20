"""Memoria del canal: lo publicado, lo pendiente y el estado de Telegram."""
import json

from .config import DATOS

MEMORIA = DATOS / "memoria.json"
ESTADO = DATOS / "estado.json"


def _leer(ruta, defecto):
    if ruta.exists():
        return json.loads(ruta.read_text(encoding="utf-8"))
    return defecto


def _guardar(ruta, datos):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")


def memoria() -> list:
    return _leer(MEMORIA, [])


def guardar_memoria(items: list):
    _guardar(MEMORIA, items)


def estado() -> dict:
    return _leer(ESTADO, {"telegram_offset": 0, "pendientes": {}})


def guardar_estado(e: dict):
    _guardar(ESTADO, e)


def resumen_para_director(n: int = 40) -> str:
    """Texto compacto con lo publicado y cómo le fue, para el director."""
    items = memoria()[-n:]
    if not items:
        return "Todavía no se ha publicado nada."
    lineas = []
    for it in items:
        m = it.get("metricas") or {}
        rend = ", ".join(f"{k}={v}" for k, v in m.items() if isinstance(v, (int, float)))
        lineas.append(
            f"- {it.get('fecha','')}: «{it.get('titulo','')}» | subtema: {it.get('subtema','')} | "
            f"gancho: {it.get('tipo_gancho','')} ({it.get('variante','A')}) | "
            f"estructura: {it.get('estructura','')} | métricas: {rend or 'sin datos aún'}"
        )
    return "\n".join(lineas)

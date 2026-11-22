"""Memoria del canal: lo publicado, lo pendiente y el estado de Telegram."""
import json

from .config import DATOS

MEMORIA = DATOS / "memoria.json"
ESTADO = DATOS / "estado.json"
TENDENCIAS = DATOS / "tendencias.json"


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


# Estado de la cadena de trabajo: uno solo para todas las páginas (el límite de Claude, los
# turnos y el vigilante son compartidos). Vive en data/estado.json de la página principal.
CLAVES_CADENA = ("latido", "reintentar_desde", "esperando", "avisado_limite", "turno_hecho",
                 "vigilante", "telegram_offset")


def _ruta_cadena():
    from .config import DATOS_PRINCIPAL
    return DATOS_PRINCIPAL / "estado.json"


def cadena() -> dict:
    return _leer(_ruta_cadena(), {"telegram_offset": 0, "pendientes": {}})


def guardar_cadena(c: dict):
    _guardar(_ruta_cadena(), c)


def resumen_para_director(n: int = 40) -> str:
    """Texto compacto con lo publicado y cómo le fue, para el director."""
    items = memoria()[-n:]
    if not items:
        return "Todavía no se ha publicado nada."
    lineas = []

    def retencion(it):
        m = it.get("metricas") or {}
        media = m.get("post_video_avg_time_watched")
        if media and it.get("duracion"):
            return min(1.5, (media / 1000) / it["duracion"])
        return None

    def vistas(it):
        m = it.get("metricas") or {}
        return m.get("fb_reels_total_plays") or m.get("blue_reels_play_count") or 0

    for it in items:
        m = it.get("metricas") or {}
        rend = ", ".join(f"{k}={v}" for k, v in m.items() if isinstance(v, (int, float)))
        r = retencion(it)
        if r is not None:
            rend += f", visto en promedio el {round(r * 100)} % del video"
        lineas.append(
            f"- {it.get('fecha','')}: «{it.get('titulo','')}» | subtema: {it.get('subtema','')} | "
            f"gancho: {it.get('tipo_gancho','')} ({it.get('variante','A')}) | "
            f"estructura: {it.get('estructura','')} | "
            f"{'tendencia: ' + it['tendencia'] if it.get('tendencia') else 'tema clásico'} | "
            f"métricas: {rend or 'sin datos aún'}"
        )
    con_datos = [it for it in items if vistas(it)]
    if len(con_datos) >= 3:
        mejores = sorted(con_datos, key=lambda it: (vistas(it), retencion(it) or 0), reverse=True)[:3]
        lineas.append("\nLOS QUE MEJOR FUNCIONARON (repite su formato, tipo de gancho y tipo de tema; "
                      "si uno despegó mucho, haz una continuación o un tema hermano):")
        lineas += [f"* «{it.get('titulo','')}» ({vistas(it)} vistas) | {it.get('estructura','')[:40]} | "
                   f"gancho: {it.get('tipo_gancho','')}" for it in mejores]
    return "\n".join(lineas)


def recuento() -> dict:
    """Recuento de temas del día: {"fecha": "AAAA-MM-DD", "tendencias": [...], "usadas": [...]}."""
    return _leer(TENDENCIAS, {})


def guardar_recuento(datos: dict):
    _guardar(TENDENCIAS, datos)

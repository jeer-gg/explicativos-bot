"""Aprendizaje: el bot estudia cómo le fue a cada video y ajusta lo que hace.

Dos mecanismos:
1. Pesos: los tipos de gancho y formatos que más vistas y retención consiguen salen más seguido
   (sin dejar de probar los demás de vez en cuando, para descubrir cosas nuevas).
2. Lecciones: cada semana Claude analiza todos los resultados y escribe lecciones concretas
   ("los ganchos de advertencia retienen el doble") que se le dan al director, al guionista y
   al que elige el gancho en cada video.
"""
import json
import statistics
from datetime import datetime, timedelta, timezone

from .config import DATOS
from .memoria import _guardar, _leer, memoria

LECCIONES = DATOS / "aprendizajes.json"


def vistas(m: dict) -> float:
    met = m.get("metricas") or {}
    return float(met.get("fb_reels_total_plays") or met.get("blue_reels_play_count") or 0)


def retencion(m: dict):
    met = m.get("metricas") or {}
    media = met.get("post_video_avg_time_watched")
    if media and m.get("duracion"):
        return min(1.5, (media / 1000) / m["duracion"])
    return None


def puntaje(m: dict, mediana: float) -> float:
    """Combina vistas (relativas a lo normal de la página) y retención."""
    v = vistas(m) / mediana if mediana else 0
    r = retencion(m)
    return v * (0.6 + (r if r is not None else 0.4))


def con_datos(minimo_horas: int = 20) -> list:
    ahora = datetime.now(timezone.utc)
    salida = []
    for m in memoria():
        if not vistas(m) or not m.get("publicado_en") or m.get("cancelado"):
            continue
        if ahora - datetime.fromisoformat(m["publicado_en"]) >= timedelta(hours=minimo_horas):
            salida.append(m)
    return salida


def pesos(opciones: list[str], campo: str, minimo_por_opcion: int = 2) -> list[float]:
    """Peso de cada opción según su rendimiento medio. Las que tienen pocos datos quedan en 1
    (neutras) y ninguna baja de 0.35, para seguir explorando."""
    items = con_datos()
    if len(items) < 6:
        return [1.0] * len(opciones)
    mediana = statistics.median(vistas(m) for m in items) or 1
    general = statistics.mean(puntaje(m, mediana) for m in items) or 1
    resultado = []
    for o in opciones:
        clave = o.split(":")[0]
        propios = [puntaje(m, mediana) for m in items if str(m.get(campo, "")).split(":")[0] == clave]
        if len(propios) < minimo_por_opcion:
            resultado.append(1.0)
        else:
            resultado.append(max(0.35, min(3.0, statistics.mean(propios) / general)))
    return resultado


def lecciones() -> list[str]:
    return _leer(LECCIONES, {}).get("lecciones", [])


def texto_lecciones() -> str:
    ls = lecciones()
    if not ls:
        return ""
    return ("\nLECCIONES APRENDIDAS DE LOS VIDEOS DE ESTA PÁGINA (aplícalas, pesan más que las reglas generales):\n"
            + "\n".join(f"- {x}" for x in ls) + "\n")


def actualizar_lecciones(claude, cfg: dict, forzar: bool = False):
    """Una vez por semana (o cuando haya bastantes datos nuevos) saca lecciones de los resultados."""
    datos = _leer(LECCIONES, {})
    items = con_datos()
    if len(items) < 6:
        return
    ultima = datos.get("fecha")
    nuevos = len(items) - datos.get("videos_analizados", 0)
    if not forzar and ultima and nuevos < 7 and \
            datetime.now(timezone.utc) - datetime.fromisoformat(ultima) < timedelta(days=7):
        return
    mediana = statistics.median(vistas(m) for m in items) or 1
    filas = []
    for m in items[-60:]:
        r = retencion(m)
        filas.append({
            "titulo": m.get("titulo"), "tema": m.get("tema"), "subtema": m.get("subtema"),
            "formato": str(m.get("estructura", "")).split(":")[0], "gancho_tipo": m.get("tipo_gancho"),
            "gancho": m.get("gancho"), "tendencia": m.get("tendencia") or "", "serie": bool(m.get("serie")),
            "duracion_s": m.get("duracion"), "hora": m.get("publicado_en"),
            "vistas": vistas(m), "veces_lo_normal": round(vistas(m) / mediana, 2),
            "porcentaje_visto": round(r * 100) if r is not None else None,
            "nota_revisor": m.get("nota_revisor"),
        })
    from .config import rol
    system = (f"Eres analista de datos de una página de Reels de {rol()}. Sacas conclusiones "
              "concretas y accionables de los resultados reales, sin inventar ni exagerar.")
    usuario = f"""Resultados de los videos publicados (vistas, cuántas veces lo normal, % visto):
{json.dumps(filas, ensure_ascii=False)}

Lecciones anteriores (corrígelas si los datos nuevos dicen otra cosa):
{json.dumps(datos.get("lecciones", []), ensure_ascii=False)}

Escribe de 5 a 8 lecciones concretas sobre qué funciona y qué no EN ESTA PÁGINA: temas,
formatos, tipos de gancho, primeras frases, tendencias o clásicos, series, duración, horas.
Cada lección con su evidencia en pocas palabras ("los ganchos de advertencia: 2,1 veces lo
normal en 5 videos"). Si hay pocos datos para algo, dilo como hipótesis a probar. Termina con
una lección de qué PROBAR distinto la próxima semana.

Devuelve JSON: {{"lecciones": ["..."], "resumen": "2 frases para el dueño de la página"}}"""
    try:
        res = claude.json(system, usuario, max_tokens=2500)
    except Exception as e:  # noqa: BLE001
        print("No se pudieron sacar lecciones:", e)
        return
    _guardar(LECCIONES, {"fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                         "videos_analizados": len(items),
                         "lecciones": [str(x) for x in res.get("lecciones", [])][:8]})
    try:
        from . import telegram
        telegram.aviso_seguro("Lo que el bot aprendió esta semana:\n" + res.get("resumen", "") + "\n\n"
                              + "\n".join(f"- {x}" for x in res.get("lecciones", [])[:8]))
    except Exception:  # noqa: BLE001
        pass

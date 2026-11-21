"""Series: historias en varias partes con intriga al final, y continuaciones de los videos que despegan.

data/series.json guarda las partes que faltan por hacer:
{"pendientes": [{"serie": "título de la serie", "parte": 2, "total": 3, "tema": "...", "angulo": "...",
                 "subtema": "...", "estructura": "...", "tendencia": "", "anterior": "resumen de lo ya contado"}],
 "secuelas": ["video_fb de los videos a los que ya se les hizo continuación"]}
"""
import statistics

from .config import DATOS
from .memoria import _guardar, _leer, memoria

SERIES = DATOS / "series.json"


def datos() -> dict:
    d = _leer(SERIES, {})
    d.setdefault("pendientes", [])
    d.setdefault("secuelas", [])
    return d


def guardar(d: dict):
    _guardar(SERIES, d)


def siguiente() -> dict | None:
    """La próxima parte que toca hacer (tiene prioridad sobre un tema nuevo)."""
    pend = datos()["pendientes"]
    return min(pend, key=lambda p: p["parte"]) if pend else None


def quitar(parte: dict):
    d = datos()
    d["pendientes"] = [p for p in d["pendientes"] if not (p["serie"] == parte["serie"] and p["parte"] == parte["parte"])]
    guardar(d)


def registrar(guion: dict, tema: dict, estilo: dict):
    """Si el guion es la parte 1 de una historia en partes, deja apuntadas las siguientes."""
    plan = guion.get("serie") or {}
    siguientes = plan.get("siguientes") or []
    if not siguientes or tema.get("serie"):
        return
    total = int(plan.get("total") or len(siguientes) + 1)
    d = datos()
    resumen = " ".join(e["voz"] for e in guion["escenas"])[:900]
    for s in siguientes[: total - 1]:
        d["pendientes"].append({
            "serie": plan.get("titulo") or guion["titulo"], "parte": int(s.get("parte", 2)), "total": total,
            "tema": s.get("tema", ""), "angulo": s.get("angulo", ""), "subtema": tema.get("subtema", ""),
            "estructura": estilo["estructura"], "tendencia": tema.get("tendencia", ""), "anterior": resumen,
        })
    guardar(d)


def avanzar(guion: dict, tema: dict):
    """Tras hacer una parte: la quita de pendientes y actualiza el resumen para la siguiente."""
    parte = tema.get("serie")
    if not parte:
        return
    quitar(parte)
    d = datos()
    resumen = (parte.get("anterior", "") + " | Parte " + str(parte["parte"]) + ": "
               + " ".join(e["voz"] for e in guion["escenas"]))[-1500:]
    for p in d["pendientes"]:
        if p["serie"] == parte["serie"]:
            p["anterior"] = resumen
    guardar(d)


def detectar_exitos(cfg: dict) -> dict | None:
    """Si un video reciente supera con creces al resto, apunta una continuación (parte 2)."""
    s = cfg.get("series", {})
    items = [m for m in memoria() if (m.get("metricas") or {}).get("fb_reels_total_plays")]
    if len(items) < s.get("minimo_videos_para_comparar", 6):
        return None
    vistas = [m["metricas"]["fb_reels_total_plays"] for m in items[-30:]]
    mediana = statistics.median(vistas)
    d = datos()
    for m in reversed(items[-10:]):
        v = m["metricas"]["fb_reels_total_plays"]
        if v >= mediana * s.get("multiplo_exito", 2.5) and m.get("video_fb") not in d["secuelas"] and not m.get("serie"):
            d["secuelas"].append(m.get("video_fb"))
            nueva = {"serie": m["titulo"], "parte": 2, "total": 2, "secuela": True,
                     "tema": f"Continuación de «{m['titulo']}» (tema: {m.get('tema', '')}): otra pregunta o "
                             "misterio hermano que la misma gente querría ver",
                     "angulo": "lo que quedó por contar o lo más sorprendente relacionado",
                     "subtema": m.get("subtema", ""), "estructura": m.get("estructura", ""),
                     "tendencia": m.get("tendencia", ""), "anterior": m.get("tema", "")}
            d["pendientes"].append(nueva)
            guardar(d)
            return nueva
    return None

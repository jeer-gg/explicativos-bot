"""Publicación de Reels en una página de Facebook con la API de Meta.

Documentación: https://developers.facebook.com/documentation/video-api/guides/reels-publishing
Pasos: iniciar sesión de subida, subir el archivo a rupload.facebook.com y publicar.
"""
import time
from pathlib import Path

import requests

from .config import secreto

VERSION = "v25.0"
GRAPH = f"https://graph.facebook.com/{VERSION}"


def _credenciales():
    return secreto("META_PAGE_ID"), secreto("META_PAGE_TOKEN")


def publicar_reel(ruta: Path, descripcion: str, titulo: str = "") -> str:
    pagina, token = _credenciales()

    # 1) Iniciar la sesión de subida
    r = requests.post(f"{GRAPH}/{pagina}/video_reels",
                      data={"upload_phase": "start", "access_token": token}, timeout=60)
    r.raise_for_status()
    inicio = r.json()
    video_id = inicio["video_id"]
    url_subida = inicio.get("upload_url") or f"https://rupload.facebook.com/video-upload/{VERSION}/{video_id}"

    # 2) Subir el archivo
    datos = ruta.read_bytes()
    r = requests.post(url_subida,
                      headers={"Authorization": f"OAuth {token}", "offset": "0",
                               "file_size": str(len(datos))},
                      data=datos, timeout=900)
    r.raise_for_status()

    # 3) Publicar
    params = {"access_token": token, "video_id": video_id, "upload_phase": "finish",
              "video_state": "PUBLISHED", "description": descripcion}
    if titulo:
        params["title"] = titulo
    r = requests.post(f"{GRAPH}/{pagina}/video_reels", params=params, timeout=120)
    r.raise_for_status()

    # Esperar a que Meta termine de procesar (informativo)
    for _ in range(20):
        time.sleep(15)
        estado = requests.get(f"{GRAPH}/{video_id}", params={"fields": "status", "access_token": token},
                              timeout=60)
        if estado.ok:
            s = estado.json().get("status", {})
            if s.get("video_status") in ("ready", "published") or \
                    s.get("publishing_phase", {}).get("status") == "complete":
                break
            if s.get("video_status") == "error":
                raise RuntimeError(f"Meta rechazó el video: {s}")
    return video_id


METRICAS = [
    "blue_reels_play_count",
    "fb_reels_total_plays",
    "post_video_avg_time_watched",
    "post_impressions_unique",
    "post_video_followers",
    "post_video_social_actions",
]


def metricas(video_id: str) -> dict:
    """Lee las métricas disponibles del Reel. Meta cambia los nombres a veces,
    así que se piden una por una y se guardan las que respondan."""
    _, token = _credenciales()
    resultado = {}
    for m in METRICAS:
        r = requests.get(f"{GRAPH}/{video_id}/video_insights",
                         params={"metric": m, "access_token": token}, timeout=60)
        if not r.ok:
            continue
        for item in r.json().get("data", []):
            valores = item.get("values") or []
            if valores and isinstance(valores[0].get("value"), (int, float)):
                resultado[item.get("name", m)] = valores[0]["value"]
    return resultado

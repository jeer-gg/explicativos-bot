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


ULTIMA = {"programado": False}  # si la última subida quedó programada


class ErrorDeFacebook(RuntimeError):
    pass


def _revisar(r: requests.Response) -> requests.Response:
    """Convierte los errores de Meta en mensajes claros (el más común: el token venció)."""
    if r.ok:
        return r
    try:
        err = r.json().get("error", {})
    except ValueError:
        err = {}
    if err.get("code") == 190 or "access token" in str(err.get("message", "")).lower():
        raise ErrorDeFacebook("El token de la página de Facebook (META_PAGE_TOKEN) venció o no es válido. "
                              "Genera uno nuevo y cámbialo en los secretos del repo.")
    if err.get("code") in (10, 200) or r.status_code == 403:
        raise ErrorDeFacebook("Facebook no da permiso para publicar en la página: " + str(err.get("message", ""))[:200])
    r.raise_for_status()
    return r


def _pedir(metodo, url, intentos: int = 4, **kw) -> requests.Response:
    """Pide a Meta y reintenta si falla la conexión o Meta tiene un error pasajero (5xx, 429)."""
    for i in range(intentos):
        try:
            r = metodo(url, **kw)
        except (requests.ConnectionError, requests.Timeout) as e:
            if i == intentos - 1:
                raise
            print(f"Fallo de conexión con Facebook ({e}); reintento")
            time.sleep(10 * (i + 1))
            continue
        if (r.status_code >= 500 or r.status_code == 429) and i < intentos - 1:
            print(f"Facebook respondió {r.status_code}; reintento")
            time.sleep(15 * (i + 1))
            continue
        return r
    return r


def borrar(video_id: str) -> None:
    """Borra un Reel (por ejemplo, uno programado que quieres cancelar)."""
    _, token = _credenciales()
    r = requests.delete(f"{GRAPH}/{video_id}", params={"access_token": token}, timeout=60)
    r.raise_for_status()


def _credenciales():
    return secreto("META_PAGE_ID"), secreto("META_PAGE_TOKEN")


def publicar_reel(ruta: Path, descripcion: str, titulo: str = "", programar: int | None = None) -> str:
    """Sube el Reel. Con `programar` (hora UNIX) queda programado y Facebook lo publica a esa hora."""
    pagina, token = _credenciales()

    # 1) Iniciar la sesión de subida
    r = _revisar(_pedir(requests.post, f"{GRAPH}/{pagina}/video_reels",
                        data={"upload_phase": "start", "access_token": token}, timeout=60))
    inicio = r.json()
    video_id = inicio["video_id"]
    url_subida = inicio.get("upload_url") or f"https://rupload.facebook.com/video-upload/{VERSION}/{video_id}"

    # 2) Subir el archivo
    datos = ruta.read_bytes()
    r = _revisar(_pedir(requests.post, url_subida,
                        headers={"Authorization": f"OAuth {token}", "offset": "0",
                                 "file_size": str(len(datos))},
                        data=datos, timeout=900))

    # 3) Publicar o programar
    params = {"access_token": token, "video_id": video_id, "upload_phase": "finish",
              "video_state": "PUBLISHED", "description": descripcion}
    if titulo:
        params["title"] = titulo
    if programar:
        r = _pedir(requests.post, f"{GRAPH}/{pagina}/video_reels", timeout=120,
                   params={**params, "video_state": "SCHEDULED", "scheduled_publish_time": int(programar)})
        if not r.ok:  # si Facebook no acepta la programación, se publica ya
            print("No se pudo programar, publico ahora:", r.text[:300])
            programar = None
    if not programar:
        r = _pedir(requests.post, f"{GRAPH}/{pagina}/video_reels", params=params, timeout=120)
    _revisar(r)
    ULTIMA["programado"] = bool(programar)

    # Esperar a que Meta termine de procesar (informativo)
    for _ in range(20):
        time.sleep(15)
        try:
            estado = requests.get(f"{GRAPH}/{video_id}", params={"fields": "status", "access_token": token},
                                  timeout=60)
        except requests.RequestException:
            continue
        if estado.ok:
            s = estado.json().get("status", {})
            if s.get("video_status") in ("ready", "published", "scheduled") or \
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

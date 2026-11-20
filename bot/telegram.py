"""Bot de Telegram para aprobar videos y recibir avisos."""
import json

import requests

from .config import secreto

API = "https://api.telegram.org/bot{token}/{metodo}"


def _url(metodo: str) -> str:
    return API.format(token=secreto("TELEGRAM_BOT_TOKEN"), metodo=metodo)


def _chat() -> str:
    return secreto("TELEGRAM_CHAT_ID")


def mensaje(texto: str, botones: list | None = None):
    datos = {"chat_id": _chat(), "text": texto[:4000]}
    if botones:
        datos["reply_markup"] = json.dumps({"inline_keyboard": botones})
    r = requests.post(_url("sendMessage"), data=datos, timeout=60)
    r.raise_for_status()


def video(ruta, texto: str, botones: list | None = None):
    datos = {"chat_id": _chat(), "caption": texto[:1000], "supports_streaming": "true"}
    if botones:
        datos["reply_markup"] = json.dumps({"inline_keyboard": botones})
    with open(ruta, "rb") as f:
        r = requests.post(_url("sendVideo"), data=datos, files={"video": f}, timeout=600)
    if not r.ok:  # por ejemplo, si pesa más de 50 MB
        mensaje(f"No pude enviar el video por Telegram ({r.status_code}). {texto}", botones)


def actualizaciones(offset: int) -> list:
    r = requests.get(_url("getUpdates"), params={"offset": offset, "timeout": 0,
                                                 "allowed_updates": json.dumps(["callback_query"])},
                     timeout=60)
    r.raise_for_status()
    return r.json().get("result", [])


def responder_boton(id_callback: str, texto: str):
    requests.post(_url("answerCallbackQuery"), data={"callback_query_id": id_callback, "text": texto},
                  timeout=30)


def aviso_seguro(texto: str):
    """Avisa sin romper nada si Telegram no está configurado."""
    try:
        mensaje(texto)
    except Exception as e:  # noqa: BLE001
        print("No se pudo avisar por Telegram:", e)

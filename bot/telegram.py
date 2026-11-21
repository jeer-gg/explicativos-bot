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


def audio(ruta, texto: str):
    with open(ruta, "rb") as f:
        r = requests.post(_url("sendAudio"), data={"chat_id": _chat(), "caption": texto[:1000]},
                          files={"audio": f}, timeout=300)
    if not r.ok:
        mensaje(f"No pude enviar el audio ({r.status_code}). {texto}")


def actualizaciones(offset: int, espera: int = 0) -> list:
    """espera > 0: Telegram mantiene la conexión abierta hasta que toques un botón (máx. espera s)."""
    r = requests.get(_url("getUpdates"), params={"offset": offset, "timeout": espera,
                                                 "allowed_updates": json.dumps(["callback_query"])},
                     timeout=espera + 30)
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

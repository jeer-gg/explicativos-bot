"""Lee los botones que tocaste en Telegram y actúa: publicar, rehacer o descartar.

Uso: python -m bot.aprobaciones
"""
import subprocess
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import telegram
from .config import SALIDA, secreto
from .memoria import estado, guardar_estado
from .publicador import borrar_pendiente, descargar_pendiente, publicar


def caducar_pendientes(horas: int = 72):
    """Borra videos pendientes que nadie aprobó en 3 días, para no acumular archivos."""
    est = estado()
    ahora = datetime.now(timezone.utc)
    for id_video, info in list(est["pendientes"].items()):
        creado = info.get("creado")
        if creado and ahora - datetime.fromisoformat(creado) > timedelta(hours=horas):
            est["pendientes"].pop(id_video)
            guardar_estado(est)
            borrar_pendiente(id_video)
            telegram.aviso_seguro(f"Descarté «{info.get('titulo')}» porque pasaron 3 días sin aprobarlo.")


def escuchar(minutos: float):
    """Atiende los botones al instante mientras quede algún video pendiente y no se acabe el tiempo."""
    import time
    limite = time.monotonic() + minutos * 60
    while estado()["pendientes"]:
        quedan = int(limite - time.monotonic())
        if quedan < 5:
            break
        procesar(espera=min(50, quedan), caducar=False)


def procesar(espera: int = 0, caducar: bool = True):
    if caducar:
        caducar_pendientes()
    chat_autorizado = secreto("TELEGRAM_CHAT_ID")
    est = estado()
    updates = telegram.actualizaciones(est.get("telegram_offset", 0), espera)
    for up in updates:
        est["telegram_offset"] = up["update_id"] + 1
        guardar_estado(est)
        cb = up.get("callback_query")
        if not cb:
            continue
        if str(cb.get("from", {}).get("id")) != str(chat_autorizado):
            telegram.responder_boton(cb["id"], "No autorizado")
            continue
        partes = cb.get("data", "").split(":")
        accion, id_video = partes[0], partes[1] if len(partes) > 1 else ""
        if id_video not in estado()["pendientes"]:
            telegram.responder_boton(cb["id"], "Ese video ya no está pendiente")
            continue

        if accion == "pub":
            variante = partes[2]
            telegram.responder_boton(cb["id"], f"Publicando versión {variante}...")
            try:
                ruta = descargar_pendiente(id_video, variante, SALIDA / "descargas" / id_video)
                video_fb = publicar(id_video, variante, Path(ruta))
                telegram.mensaje(f"Publicado en Facebook (versión {variante}). ID: {video_fb}")
            except Exception as e:  # noqa: BLE001
                telegram.aviso_seguro(f"No pude publicar: {str(e)[-1200:]}\nEl video sigue pendiente; toca el botón otra vez para reintentar.")
                print(traceback.format_exc())
        elif accion in ("rehacer", "descartar"):
            e = estado()
            e["pendientes"].pop(id_video, None)
            guardar_estado(e)
            borrar_pendiente(id_video)
            if accion == "rehacer":
                telegram.responder_boton(cb["id"], "Haciendo otro video...")
                subprocess.run(["gh", "workflow", "run", "bot.yml", "-f", "tarea=producir"], check=False)
                telegram.mensaje("Descartado. Ya empecé otro video; te llega en unos minutos.")
            else:
                telegram.responder_boton(cb["id"], "Descartado")
        est = estado()
        est["telegram_offset"] = up["update_id"] + 1
        guardar_estado(est)


if __name__ == "__main__":
    try:
        procesar()
    except Exception:
        error = traceback.format_exc()
        print(error)
        telegram.aviso_seguro("Error al procesar tu respuesta:\n" + error[-1500:])
        raise

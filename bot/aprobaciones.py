"""Lee los botones que tocaste en Telegram y actúa: publicar, rehacer o descartar.

Uso: python -m bot.aprobaciones
"""
import subprocess
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import config, telegram
from .config import SALIDA, secreto
from .memoria import cadena, estado, guardar_cadena, guardar_estado
from .publicador import borrar_pendiente, descargar_pendiente, publicar


def caducar_pendientes(horas: int = 72):
    """Borra videos pendientes que nadie aprobó en 3 días (en todas las páginas)."""
    actual = config.CANAL
    for canal in config.canales():
        config.usar_canal(canal)
        _caducar(horas)
    config.usar_canal(actual)


def _caducar(horas: int):
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


def relanzar_si_toca():
    """Vigilante: si la cadena de producción dejó de latir (una tarea murió de golpe o nunca se
    lanzó la siguiente), la relanza. La tarea nueva decide sola qué hacer (seguir, esperar...)."""
    from datetime import datetime, timedelta, timezone
    e = cadena()
    ahora = datetime.now(timezone.utc)
    latido = e.get("latido")
    muerta = not latido or ahora - datetime.fromisoformat(latido) > timedelta(minutes=200)
    ultimo = e.get("vigilante")
    if muerta and (not ultimo or ahora - datetime.fromisoformat(ultimo) > timedelta(minutes=90)):
        e["vigilante"] = ahora.isoformat(timespec="seconds")
        guardar_cadena(e)
        print("La cadena de producción no da señales de vida: la relanzo")
        subprocess.run(["gh", "workflow", "run", "bot.yml", "-f", "tarea=producir"], check=False)


def _pagina_del_video(accion: str, id_video: str) -> str | None:
    """Los botones de todas las páginas llegan al mismo chat: busca en qué página está el video."""
    from .memoria import memoria
    for canal in config.canales():
        config.usar_canal(canal)
        if accion == "borrar":
            if any(m.get("video_fb") == id_video for m in memoria()):
                return canal
        elif id_video in estado()["pendientes"]:
            return canal
    return None


def _avanzar_offset(update_id: int):
    c = cadena()
    c["telegram_offset"] = update_id + 1
    guardar_cadena(c)


def procesar(espera: int = 0, caducar: bool = True):
    actual = config.CANAL
    try:
        _procesar(espera, caducar)
    finally:
        config.usar_canal(actual)


def _procesar(espera: int, caducar: bool):
    if caducar:
        caducar_pendientes()
        relanzar_si_toca()
    chat_autorizado = secreto("TELEGRAM_CHAT_ID")
    updates = telegram.actualizaciones(cadena().get("telegram_offset", 0), espera)
    for up in updates:
        _avanzar_offset(up["update_id"])
        cb = up.get("callback_query")
        if not cb:
            continue
        if str(cb.get("from", {}).get("id")) != str(chat_autorizado):
            telegram.responder_boton(cb["id"], "No autorizado")
            continue
        partes = cb.get("data", "").split(":")
        accion, id_video = partes[0], partes[1] if len(partes) > 1 else ""
        if accion == "voz" and len(partes) == 3:
            from . import voces
            try:
                texto = voces.elegir(partes[1], int(partes[2]))
            except (ValueError, OSError):
                texto = "No pude guardar esa voz"
            telegram.responder_boton(cb["id"], texto[:190])
            telegram.aviso_seguro(texto)
            continue
        pagina = _pagina_del_video(accion, id_video)
        if pagina is None:
            telegram.responder_boton(cb["id"], "Ese video ya no está pendiente")
            continue
        config.usar_canal(pagina)  # lo que sigue se hace en la página de ese video

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
        elif accion == "borrar":
            from . import meta
            from .memoria import guardar_memoria, memoria
            try:
                meta.borrar(id_video)
                items = memoria()
                cancelado = {}
                for m in items:
                    if m.get("video_fb") == id_video:
                        m["cancelado"] = True
                        cancelado = m
                guardar_memoria(items)
                # Se hace otro video, más exigente y de otro tema, para ocupar ese horario
                e = estado()
                e["reemplazo"] = {"tema_cancelado": cancelado.get("tema", ""),
                                  "titulo_cancelado": cancelado.get("titulo", "")}
                guardar_estado(e)
                subprocess.run(["gh", "workflow", "run", "bot.yml", "-f", "tarea=producir"], check=False)
                telegram.responder_boton(cb["id"], "Cancelado")
                telegram.aviso_seguro("Listo: ese video se borró de Facebook. Ya estoy haciendo otro, de otro "
                                      "tema y con revisión más exigente, para ese mismo horario.")
            except Exception as e:  # noqa: BLE001
                telegram.responder_boton(cb["id"], "No se pudo")
                telegram.aviso_seguro(f"No pude borrar el video: {str(e)[-500:]}")
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
        _avanzar_offset(up["update_id"])


if __name__ == "__main__":
    try:
        procesar()
    except Exception:
        error = traceback.format_exc()
        print(error)
        telegram.aviso_seguro("Error al procesar tu respuesta:\n" + error[-1500:])
        raise

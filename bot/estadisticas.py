"""Lee cómo le fue a cada Reel y lo guarda en la memoria para el director."""
from datetime import datetime, timedelta, timezone

from . import meta
from .memoria import guardar_memoria, memoria


def actualizar(dias: int = 7):
    items = memoria()
    ahora = datetime.now(timezone.utc)
    cambios = 0
    for it in items:
        if not it.get("video_fb") or not it.get("publicado_en"):
            continue
        edad = ahora - datetime.fromisoformat(it["publicado_en"])
        if timedelta(hours=20) <= edad <= timedelta(days=dias):
            try:
                datos = meta.metricas(it["video_fb"])
            except Exception as e:  # noqa: BLE001
                print("No se pudieron leer métricas:", e)
                continue
            if datos:
                it["metricas"] = datos
                cambios += 1
    if cambios:
        guardar_memoria(items)
    print(f"Métricas actualizadas: {cambios}")

"""Publica un video pendiente y lo registra en la memoria."""
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from . import meta
from .memoria import estado, guardar_estado, guardar_memoria, memoria


def etiqueta(id_video: str) -> str:
    return f"pend-{id_video}"


def subir_pendiente(id_video: str, archivos: list[Path], titulo: str):
    """Guarda los videos renderizados como 'release' del repo hasta que se aprueben."""
    subprocess.run(["gh", "release", "create", etiqueta(id_video), *map(str, archivos),
                    "--title", f"Pendiente: {titulo}", "--notes", "Video pendiente de aprobación.",
                    "--prerelease"], check=True)


def descargar_pendiente(id_video: str, variante: str, carpeta: Path) -> Path:
    carpeta.mkdir(parents=True, exist_ok=True)
    subprocess.run(["gh", "release", "download", etiqueta(id_video), "-p", f"{variante}.mp4",
                    "-D", str(carpeta), "--clobber"], check=True)
    return carpeta / f"{variante}.mp4"


def borrar_pendiente(id_video: str):
    subprocess.run(["gh", "release", "delete", etiqueta(id_video), "--cleanup-tag", "-y"], check=False)


def publicar(id_video: str, variante: str, ruta: Path) -> str:
    est = estado()
    info = est["pendientes"][id_video]
    descripcion = info["descripcion"].strip() + "\n\n" + " ".join(info.get("hashtags", []))
    video_fb = meta.publicar_reel(ruta, descripcion, titulo=info["titulo"])

    items = memoria()
    items.append({
        "id": id_video,
        "fecha": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "publicado_en": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "titulo": info["titulo"],
        "tema": info["tema"],
        "subtema": info["subtema"],
        "estructura": info["estructura"],
        "paleta": info["paleta"],
        "variante": variante,
        "tipo_gancho": info["tipo_gancho"] if variante == "A" else info.get("tipo_gancho_b", ""),
        "gancho": info["ganchos"].get(variante, ""),
        "nota_revisor": info.get("nota_media"),
        "video_fb": video_fb,
        "metricas": {},
    })
    guardar_memoria(items)
    est["pendientes"].pop(id_video, None)
    guardar_estado(est)
    borrar_pendiente(id_video)
    return video_fb

"""Efectos de sonido sintetizados con ffmpeg: originales y sin problemas de derechos."""
import subprocess

from .config import PUBLICO


def generar():
    carpeta = PUBLICO / "sfx"
    carpeta.mkdir(parents=True, exist_ok=True)
    pop = carpeta / "pop.mp3"
    if not pop.exists():
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
            "-i", "sine=f=880:d=0.12:r=48000",
            "-af", "afade=t=in:st=0:d=0.005,afade=t=out:st=0.02:d=0.1,volume=0.6",
            "-ac", "2", str(pop),
        ], check=True)
    destino = carpeta / "whoosh.mp3"
    if destino.exists():
        return
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
        "-i", "anoisesrc=d=0.55:c=pink:a=0.7:r=48000",
        "-af", ("highpass=f=350,lowpass=f=3200,"
                "afade=t=in:st=0:d=0.22,afade=t=out:st=0.25:d=0.3,volume=0.9"),
        "-ac", "2", str(destino),
    ], check=True)

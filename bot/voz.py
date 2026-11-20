"""Voz con Edge TTS (gratis) y marcas de tiempo por palabra.

La voz se genera ANTES que las animaciones: su duración decide cuánto dura
cada escena, y las marcas de tiempo permiten animar justo cuando se dice algo.
"""
import asyncio
import json
import subprocess
from pathlib import Path

import edge_tts

PAUSA = 0.25  # segundos de aire al final de cada escena


async def _tts(texto: str, voz: str, velocidad: str, destino: Path) -> list:
    try:
        com = edge_tts.Communicate(texto, voz, rate=velocidad, boundary="WordBoundary")
    except TypeError:  # versiones antiguas no tienen 'boundary'
        com = edge_tts.Communicate(texto, voz, rate=velocidad)
    palabras = []
    with open(destino, "wb") as f:
        async for trozo in com.stream():
            if trozo["type"] == "audio":
                f.write(trozo["data"])
            elif trozo["type"] == "WordBoundary":
                palabras.append({
                    "w": trozo["text"],
                    "t": round(trozo["offset"] / 1e7, 3),
                    "d": round(trozo["duration"] / 1e7, 3),
                })
    return palabras


def duracion(ruta: Path) -> float:
    salida = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(ruta)],
        capture_output=True, text=True, check=True).stdout
    return float(salida.strip())


def _ffmpeg(*args):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)


def narrar_escena(texto: str, voz: str, velocidad: str, carpeta: Path, nombre: str) -> dict:
    """Genera el audio de una escena con su pausa final y sus palabras."""
    carpeta.mkdir(parents=True, exist_ok=True)
    crudo = carpeta / f"{nombre}.mp3"
    palabras = asyncio.run(_tts(texto, voz, velocidad, crudo))
    con_pausa = carpeta / f"{nombre}.wav"
    _ffmpeg("-i", str(crudo), "-af", f"apad=pad_dur={PAUSA}", "-ar", "48000", "-ac", "2", str(con_pausa))
    return {"archivo": con_pausa, "duracion": duracion(con_pausa), "palabras": palabras}


def unir_audios(partes: list, destino: Path):
    lista = destino.with_suffix(".txt")
    lista.write_text("".join(f"file '{p.resolve()}'\n" for p in partes), encoding="utf-8")
    _ffmpeg("-f", "concat", "-safe", "0", "-i", str(lista), "-c:a", "pcm_s16le", str(destino))
    lista.unlink()


def narrar_guion(guion: dict, cfg: dict, carpeta_trabajo: Path, publico: Path) -> dict:
    """Narra todas las escenas y devuelve, por variante, audio y tiempos.

    Resultado: {"A": {"audio": "voz_A.wav", "escenas": [{inicio, duracion, palabras}]}, "B": ...}
    """
    p = cfg["produccion"]
    voz, velocidad = p["voz"], p["velocidad_voz"]
    escenas = guion["escenas"]
    narradas = [narrar_escena(e["voz"], voz, velocidad, carpeta_trabajo, f"esc{i}")
                for i, e in enumerate(escenas)]
    variantes = {"A": narradas}
    if p.get("ab_gancho") and guion.get("gancho_b", {}).get("voz"):
        gancho_b = narrar_escena(guion["gancho_b"]["voz"], voz, velocidad, carpeta_trabajo, "escB")
        variantes["B"] = [gancho_b] + narradas[1:]

    resultado = {}
    for nombre, lista in variantes.items():
        total = sum(n["duracion"] for n in lista)
        if total > 89:
            raise ValueError(f"La narración dura {total:.0f}s y Facebook acepta hasta 90s.")
        archivo = f"voz_{nombre}.wav"
        unir_audios([n["archivo"] for n in lista], publico / archivo)
        inicio, tiempos = 0.0, []
        for n in lista:
            tiempos.append({"inicio": round(inicio, 3), "duracion": round(n["duracion"], 3),
                            "palabras": n["palabras"]})
            inicio += n["duracion"]
        resultado[nombre] = {"audio": archivo, "escenas": tiempos, "total": round(total, 2)}
    (carpeta_trabajo / "tiempos.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=1))
    return resultado

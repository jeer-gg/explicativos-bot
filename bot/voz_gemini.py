"""Voz natural con Google Gemini TTS.

Se narra el guion COMPLETO de una sola vez (así la voz fluye sin cortes entre escenas).
Gemini no da tiempos por palabra, así que se escucha el audio con Whisper y se alinea
con el texto del guion para saber cuándo empieza cada escena y cada palabra.
"""
import base64
import difflib
import json
import os
import re
import time
import unicodedata
import wave
from pathlib import Path

import requests

from .voz import _ffmpeg, duracion

URL = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
_WHISPER = None


def _normal(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if c.isalnum() and unicodedata.category(c) != "Mn")


def sintetizar(texto: str, cfg: dict, destino: Path) -> Path:
    """Devuelve un WAV con la narración. Prueba varios modelos por si uno no está disponible."""
    p = cfg["produccion"]
    indicacion = p.get("estilo_voz_gemini", "").strip()
    cuerpo = {
        "contents": [{"parts": [{"text": f"{indicacion}\n\n{texto}" if indicacion else texto}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": p.get("voz_gemini", "Puck")}}},
        },
    }
    errores = []
    for modelo in p.get("modelos_voz_gemini", ["gemini-2.5-flash-preview-tts"]):
        for intento in range(3):
            try:
                r = requests.post(URL.format(modelo=modelo), json=cuerpo, timeout=300,
                                  headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]})
            except requests.RequestException as e:
                errores.append(f"{modelo}: {e}")
                time.sleep(5)
                continue
            if r.status_code in (429, 500, 503) and intento < 2:
                time.sleep(20 * (intento + 1))
                continue
            if r.status_code != 200:
                errores.append(f"{modelo}: {r.status_code} {r.text[:200]}")
                break
            partes = r.json()["candidates"][0]["content"]["parts"]
            dato = next(x["inlineData"] for x in partes if "inlineData" in x)
            tasa = int((re.search(r"rate=(\d+)", dato.get("mimeType", "")) or [0, 24000])[1])
            with wave.open(str(destino), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(tasa)
                w.writeframes(base64.b64decode(dato["data"]))
            print(f"Voz generada con {modelo}")
            return destino
    raise RuntimeError("; ".join(errores)[-800:])


def escuchar_palabras(ruta: Path, cfg: dict, pista: str) -> list:
    """Palabras que dice el audio con su inicio y fin (Whisper en la CPU)."""
    global _WHISPER
    from faster_whisper import WhisperModel
    if _WHISPER is None:
        _WHISPER = WhisperModel(cfg["produccion"].get("whisper_modelo", "base"), device="cpu", compute_type="int8")
    segmentos, _ = _WHISPER.transcribe(str(ruta), language="es", word_timestamps=True,
                                       initial_prompt=pista[:400], vad_filter=False)
    return [{"w": w.word.strip(), "ini": w.start, "fin": w.end} for s in segmentos for w in (s.words or [])]


def alinear(tokens: list[str], oidas: list[dict]) -> list[tuple[float, float]]:
    """Asigna (inicio, fin) a cada palabra del guion a partir de lo que Whisper oyó."""
    a = [_normal(t) for t in tokens]
    b = [_normal(o["w"]) for o in oidas]
    tiempos: list = [None] * len(tokens)
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op == "equal" or (op == "replace" and i2 - i1 == j2 - j1):
            for k in range(i2 - i1):
                tiempos[i1 + k] = (oidas[j1 + k]["ini"], oidas[j1 + k]["fin"])
        elif op == "replace":  # p. ej. "80%" frente a "ochenta por ciento": se reparte el tramo
            ini, fin = oidas[j1]["ini"], oidas[j2 - 1]["fin"]
            paso = (fin - ini) / (i2 - i1)
            for k in range(i2 - i1):
                tiempos[i1 + k] = (ini + k * paso, ini + (k + 1) * paso)
    # Palabras que no se oyeron: se interpolan entre las vecinas conocidas
    conocidos = [i for i, t in enumerate(tiempos) if t]
    if not conocidos:
        raise RuntimeError("Whisper no reconoció la narración")
    for i, t in enumerate(tiempos):
        if t:
            continue
        antes = max((k for k in conocidos if k < i), default=None)
        despues = min((k for k in conocidos if k > i), default=None)
        if antes is None:
            fin = tiempos[despues][0]
            tiempos[i] = (max(0.0, fin - 0.25 * (despues - i)), max(0.0, fin - 0.25 * (despues - i) + 0.22))
        elif despues is None:
            ini = tiempos[antes][1] + 0.25 * (i - antes - 1)
            tiempos[i] = (ini, ini + 0.22)
        else:
            a0, b0 = tiempos[antes][1], tiempos[despues][0]
            paso = (b0 - a0) / (despues - antes)
            tiempos[i] = (a0 + (i - antes - 1) * paso, a0 + (i - antes) * paso)
    return tiempos


def narrar_variante(textos: list[str], cfg: dict, carpeta: Path, publico: Path, nombre: str) -> dict:
    carpeta.mkdir(parents=True, exist_ok=True)
    crudo = sintetizar(" ".join(textos), cfg, carpeta / f"gemini_{nombre}.wav")
    tokens, escena_de = [], []
    for i, t in enumerate(textos):
        for w in t.split():
            tokens.append(w)
            escena_de.append(i)
    tiempos = alinear(tokens, escuchar_palabras(crudo, cfg, " ".join(textos)))

    # Recorta el silencio inicial (y cualquier cosa dicha antes del guion) y el final
    corte_ini = max(0.0, tiempos[0][0] - 0.05)
    total = tiempos[-1][1] - corte_ini + 0.3
    factor = 1.0
    if total > 88:  # Facebook acepta hasta 90 s: se acelera un poco si hace falta
        factor = min(1.25, total / 86)
    archivo = f"voz_{nombre}.wav"
    _ffmpeg("-i", str(crudo), "-ss", f"{corte_ini:.3f}", "-t", f"{total:.3f}",
            "-af", f"atempo={factor:.4f}" if factor != 1 else "anull",
            "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", str(publico / archivo))
    total = duracion(publico / archivo)
    if total > 89.5:
        raise ValueError(f"La narración dura {total:.0f}s y Facebook acepta hasta 90s.")
    t_abs = [((a - corte_ini) / factor, (b - corte_ini) / factor) for a, b in tiempos]

    inicios = []
    for i in range(len(textos)):
        primera = escena_de.index(i)
        inicios.append(0.0 if i == 0 else max(0.0, t_abs[primera][0] - 0.03))
    escenas = []
    for i, ini in enumerate(inicios):
        fin = inicios[i + 1] if i + 1 < len(inicios) else total
        palabras = [{"w": tokens[k], "t": round(max(0.0, t_abs[k][0] - ini), 3),
                     "d": round(max(0.05, t_abs[k][1] - t_abs[k][0]), 3)}
                    for k in range(len(tokens)) if escena_de[k] == i]
        escenas.append({"inicio": round(ini, 3), "duracion": round(fin - ini, 3), "palabras": palabras})
    return {"audio": archivo, "escenas": escenas, "total": round(total, 2)}


def narrar_guion_gemini(guion: dict, cfg: dict, carpeta_trabajo: Path, publico: Path) -> dict:
    textos = [e["voz"] for e in guion["escenas"]]
    resultado = {"A": narrar_variante(textos, cfg, carpeta_trabajo / "voz", publico, "A")}
    if cfg["produccion"].get("ab_gancho") and guion.get("gancho_b", {}).get("voz"):
        resultado["B"] = narrar_variante([guion["gancho_b"]["voz"]] + textos[1:], cfg,
                                         carpeta_trabajo / "voz", publico, "B")
    (carpeta_trabajo / "tiempos.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=1))
    return resultado

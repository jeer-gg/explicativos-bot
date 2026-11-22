"""Elegir la voz escuchando: el bot manda por Telegram la misma frase dicha por varias voces y
el dueño toca "Elegir" en la que más le guste. Desde ese momento todos los videos de esa página
usan esa voz (se guarda en data/voz.json con "elegida": true).

Se ofrece una vez por página (y otra vez si en config.yaml sube `produccion.voz_marca.ronda_muestras`).
Mientras no se elija, se sigue usando la voz de siempre.
"""
import base64
import json
import wave
from pathlib import Path

import requests

from . import config, telegram

FRASE = ("¿Sabías que tu pan se pone duro por culpa del agua, y no del aire? Parece raro, lo sé. "
         "Pero mira lo que pasa por dentro… y al final te vas a reír de lo simple que era.")

# Indicaciones para que suene a persona y no a locutora
_HUMANA = ("Sounds like a real person talking to a friend, not an announcer or a voice assistant: "
           "relaxed natural breathing, tiny natural pauses, slight variations in speed and pitch, "
           "a genuine smile in the voice, soft consonants, never robotic or overly polished.")

CANDIDATAS_MUJER = [
    {"nombre": "Amiga que te cuenta algo", "tipo": "diseñada",
     "descripcion": "A warm Latin American woman in her late twenties telling a close friend something "
                    "fascinating over coffee. Neutral Latin American Spanish, medium pitch, relaxed and "
                    "curious, natural conversational pace. " + _HUMANA},
    {"nombre": "Pódcast íntimo", "tipo": "diseñada",
     "descripcion": "A Latin American female podcast host in her early thirties, close to the "
                    "microphone, intimate and calm, soft but clear voice, unhurried pace, speaks as if "
                    "to one listener. Neutral Latin American Spanish. " + _HUMANA},
    {"nombre": "Curiosa y expresiva", "tipo": "diseñada",
     "descripcion": "A bright, expressive Latin American woman in her mid twenties who genuinely loves "
                    "explaining how things work, playful curiosity, lively but natural intonation, "
                    "never shouting. Neutral Latin American Spanish. " + _HUMANA},
    {"nombre": "Cálida y madura", "tipo": "diseñada",
     "descripcion": "A warm, slightly low-pitched Latin American woman in her late thirties, confident "
                    "and reassuring, velvety texture, calm natural pace, like a favorite teacher "
                    "talking to you one on one. Neutral Latin American Spanish. " + _HUMANA},
    {"nombre": "Sulafat (Gemini, cálida)", "tipo": "gemini", "voz": "Sulafat"},
    {"nombre": "Despina (Gemini, suave)", "tipo": "gemini", "voz": "Despina"},
    {"nombre": "Callirrhoe (Gemini, relajada)", "tipo": "gemini", "voz": "Callirrhoe"},
]


def _ruta_voz() -> Path:
    return config.DATOS / "voz.json"


def _ruta_candidatas() -> Path:
    return config.DATOS / "voces_candidatas.json"


def voz_elegida() -> dict | None:
    """La voz que eligió el dueño para esta página (o None si todavía no eligió)."""
    try:
        v = json.loads(_ruta_voz().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return v if v.get("elegida") else None


def _disenar(cfg: dict, c: dict) -> str | None:
    from .voz_gemini import URL_VOCES, _clave
    d = cfg["produccion"].get("voz_marca", {})
    cuerpo = {"voice": {"type": "prompted", "display_name": c["nombre"][:40],
                        "prompted": {"input": c["descripcion"], "language_code": d.get("idioma", "es-419"),
                                     "gender": "female", "pitch": "medium",
                                     "accent": d.get("acento", "Latin American neutral Spanish"),
                                     "persona": c["nombre"], "context": d.get("contexto", "")}},
              "store": True}
    r = requests.post(URL_VOCES, json=cuerpo, headers={"x-goog-api-key": _clave()}, timeout=180)
    r.raise_for_status()
    return r.json()["id"]


def _decir(cfg: dict, voz: dict, destino: Path) -> Path:
    """Dice la frase de prueba con una voz concreta y la guarda como WAV."""
    from .voz_gemini import URL, _clave
    p = cfg["produccion"]
    cuerpo = {"contents": [{"parts": [{"text": FRASE}]}],
              "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {"voiceConfig": voz}}}
    ultimo = ""
    for modelo in p.get("modelos_voz_gemini", ["gemini-2.5-flash-preview-tts"]):
        r = requests.post(URL.format(modelo=modelo), json=cuerpo, timeout=300, headers={"x-goog-api-key": _clave()})
        if r.status_code != 200:
            ultimo = r.text[:200]
            continue
        for parte in r.json()["candidates"][0]["content"]["parts"]:
            dato = parte.get("inlineData") or parte.get("inline_data")
            if dato:
                pcm = base64.b64decode(dato["data"])
                with wave.open(str(destino), "wb") as w:
                    w.setnchannels(1)
                    w.setsampwidth(2)
                    w.setframerate(24000)
                    w.writeframes(pcm)
                return destino
    raise RuntimeError(f"No se pudo generar la muestra: {ultimo}")


def ofrecer_si_toca(cfg: dict) -> bool:
    """Manda las muestras de voz a Telegram una vez por página (o al subir la ronda)."""
    d = cfg["produccion"].get("voz_marca", {})
    if not d.get("elegir_escuchando") or d.get("genero", "female") != "female":
        return False
    ronda = int(d.get("ronda_muestras", 1))
    try:
        hechas = json.loads(_ruta_candidatas().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        hechas = {}
    if hechas.get("ronda") == ronda:
        return False
    from datetime import datetime, timezone
    hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if hechas.get("intento_fallido") == hoy:  # si hoy ya falló, se vuelve a intentar mañana
        return False
    if voz_elegida() and hechas.get("ronda", 0) >= ronda:
        return False
    carpeta = config.DATOS / "muestras_voz"
    carpeta.mkdir(parents=True, exist_ok=True)
    opciones = []
    actual = None
    try:
        actual = json.loads(_ruta_voz().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    lista = ([{"nombre": "La voz actual", "tipo": "actual", "id": actual.get("id"), "voz": actual.get("prebuilt")}]
             if actual and (actual.get("id") or actual.get("prebuilt")) else []) + CANDIDATAS_MUJER
    for c in lista:
        try:
            if c["tipo"] == "diseñada":
                voz_id = _disenar(cfg, c)
                config_voz, guardar = {"voice": voz_id}, {"id": voz_id, "descripcion": c["descripcion"]}
            elif c["tipo"] == "gemini" or (c["tipo"] == "actual" and c.get("voz")):
                config_voz = {"prebuiltVoiceConfig": {"voiceName": c["voz"]}}
                guardar = {"prebuilt": c["voz"]}
            else:
                config_voz, guardar = {"voice": c["id"]}, {"id": c["id"], "descripcion": actual.get("descripcion", "")}
            n = len(opciones) + 1
            muestra = _decir(cfg, config_voz, carpeta / f"voz_{n}.wav")
            telegram.audio(muestra, f"Voz {n}: {c['nombre']}")
            opciones.append({"n": n, "nombre": c["nombre"], **guardar})
        except Exception as e:  # noqa: BLE001  (una voz que falla no impide ofrecer las demás)
            print(f"No se pudo preparar la voz «{c['nombre']}»:", e)
    if not opciones:
        _ruta_candidatas().write_text(json.dumps({"intento_fallido": hoy}), encoding="utf-8")
        return False
    _ruta_candidatas().write_text(json.dumps({"ronda": ronda, "opciones": opciones}, ensure_ascii=False, indent=1),
                                  encoding="utf-8")
    filas = [[{"text": f"Elegir {o['n']}", "callback_data": f"voz:{config.CANAL}:{o['n']}"}
              for o in opciones[i:i + 4]] for i in range(0, len(opciones), 4)]
    telegram.mensaje("Escucha las voces de arriba y toca la que te suene más humana. Desde ese momento "
                     "todos los videos de esta página la usarán. Mientras tanto sigo con la de siempre.", filas)
    return True


def elegir(canal: str, n: int) -> str:
    """Guarda la voz elegida para una página. Devuelve un texto para confirmar."""
    config.usar_canal(canal)
    try:
        hechas = json.loads(_ruta_candidatas().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "Esas voces ya no están disponibles"
    opcion = next((o for o in hechas.get("opciones", []) if o["n"] == n), None)
    if not opcion:
        return "Esa voz ya no está disponible"
    guardar = {k: v for k, v in opcion.items() if k in ("id", "descripcion", "prebuilt", "nombre")}
    guardar["elegida"] = True
    _ruta_voz().write_text(json.dumps(guardar, ensure_ascii=False, indent=1), encoding="utf-8")
    return f"Listo: los próximos videos usarán la voz {n} ({opcion['nombre']})"

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


VOZ = Path(__file__).resolve().parent.parent / "data" / "voz.json"
URL_VOCES = "https://generativelanguage.googleapis.com/v1beta/voices"


def _clave() -> str:
    return os.environ["GEMINI_API_KEY"].strip()


def voz_de_marca(cfg: dict) -> str | None:
    """La voz única del canal, diseñada una sola vez con Voice Design de Gemini y reutilizada en
    TODOS los videos (se guarda su id en data/voz.json). Si cambias la descripción en
    config.yaml, se diseña una nueva. Devuelve el id o None si no se pudo."""
    d = cfg["produccion"].get("voz_marca", {})
    if not d.get("activa"):
        return None
    descripcion = d.get("descripcion", "").strip()
    guardada = json.loads(VOZ.read_text(encoding="utf-8")) if VOZ.exists() else {}
    if guardada.get("id") and guardada.get("descripcion") == descripcion:
        return guardada["id"]
    cuerpo = {"voice": {"type": "prompted", "display_name": d.get("nombre", "Voz del canal"),
                        "prompted": {"input": descripcion, "language_code": d.get("idioma", "es-419"),
                                     "gender": d.get("genero", "female"), "pitch": d.get("tono", "medium"),
                                     "accent": d.get("acento", "Latin American neutral Spanish"),
                                     "persona": d.get("persona", ""), "context": d.get("contexto", "")}},
              "store": True}
    try:
        r = requests.post(URL_VOCES, json=cuerpo, headers={"x-goog-api-key": _clave()}, timeout=180)
        r.raise_for_status()
        voz = r.json()
        voz_id = voz["id"]
    except Exception as e:  # noqa: BLE001
        print("No se pudo diseñar la voz de marca:", e, getattr(locals().get("r"), "text", "")[:300])
        return None
    VOZ.parent.mkdir(parents=True, exist_ok=True)
    VOZ.write_text(json.dumps({"id": voz_id, "descripcion": descripcion}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    try:  # que el dueño la escuche
        muestra = (voz.get("sample_audio") or voz.get("sampleAudio") or {}).get("data")
        if muestra:
            ruta = VOZ.parent / "voz_muestra.wav"
            ruta.write_bytes(base64.b64decode(muestra))
            from . import telegram
            telegram.audio(ruta, "Esta es la voz que usarán todos los videos a partir de ahora.")
    except Exception as e:  # noqa: BLE001
        print("No se pudo enviar la muestra de voz:", e)
    return voz_id


def sintetizar(texto: str, cfg: dict, destino: Path) -> Path:
    """Devuelve un WAV con la narración, siempre con la misma voz y el mismo modelo."""
    p = cfg["produccion"]
    indicacion = p.get("estilo_voz_gemini", "").strip()
    voz_id = voz_de_marca(cfg)
    voz = ({"voice": voz_id} if voz_id
           else {"prebuiltVoiceConfig": {"voiceName": p.get("voz_gemini", "Laomedeia")}})
    # Formato recomendado para Gemini TTS: notas de dirección + transcripción. Solo se lee la
    # transcripción (antes, al ir todo junto, a veces leía las instrucciones en voz alta).
    prompt = (f"### NOTAS DEL DIRECTOR (no se leen en voz alta)\n{indicacion}\n\n"
              f"### TRANSCRIPCIÓN (lee solo esto, palabra por palabra, desde la primera)\n{texto}"
              if indicacion else texto)
    cuerpo = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": voz},
        },
    }
    errores = []
    for modelo in p.get("modelos_voz_gemini", ["gemini-2.5-flash-preview-tts"]):
        for intento in range(3):
            try:
                r = requests.post(URL.format(modelo=modelo), json=cuerpo, timeout=300,
                                  headers={"x-goog-api-key": _clave()})
            except requests.RequestException as e:
                errores.append(f"{modelo}: {e}")
                time.sleep(5)
                continue
            if r.status_code in (429, 500, 503) and intento < 2:
                time.sleep(20 * (intento + 1))
                continue
            if r.status_code != 200:
                if "API key not valid" in r.text or "API_KEY_INVALID" in r.text:
                    raise RuntimeError("Google rechazó la clave GEMINI_API_KEY (no es válida). "
                                       "Créala de nuevo en aistudio.google.com/apikey y vuelve a guardarla en GitHub.")
                errores.append(f"{modelo}: {r.status_code} {r.text[:200]}")
                if voz_id:
                    # este modelo no acepta la voz diseñada: se prueba con la voz fija de reserva
                    cuerpo["generationConfig"]["speechConfig"]["voiceConfig"] = {
                        "prebuiltVoiceConfig": {"voiceName": p.get("voz_gemini", "Laomedeia")}}
                    voz_id = None
                    continue
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
    # Se le pasa el audio ya decodificado (16 kHz mono) para no depender de PyAV, cuyas
    # versiones nuevas rompen faster-whisper ("unexpected keyword argument 'metadata_errors'").
    import subprocess
    import numpy as np
    crudo = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(ruta), "-ac", "1", "-ar", "16000",
                            "-f", "f32le", "-"], capture_output=True, check=True).stdout
    audio = np.frombuffer(crudo, dtype=np.float32).copy()
    segmentos, _ = _WHISPER.transcribe(audio, language="es", word_timestamps=True,
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


def cobertura(tokens: list[str], oidas: list[dict]) -> float:
    """Qué parte del guion se oyó tal cual (0 a 1)."""
    a = [_normal(t) for t in tokens]
    b = [_normal(o["w"]) for o in oidas]
    iguales = sum(i2 - i1 for op, i1, i2, _, _ in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes()
                  if op == "equal")
    return iguales / max(1, len(a))


def inicio_del_guion(tokens: list[str], oidas: list[dict]) -> float | None:
    """Segundo en que empieza a oírse el guion (ignora lo que se haya dicho antes).

    Busca la primera palabra del guion seguida, en orden, por las siguientes. Si Whisper no oyó
    la primera palabra pero sí la segunda, empieza un poco antes de la segunda."""
    primeras = [_normal(t) for t in tokens[:5] if _normal(t)]
    oidas_n = [_normal(o["w"]) for o in oidas]
    if len(primeras) < 2:
        return oidas[0]["ini"] if oidas else None
    candidatos = []
    for i in range(min(len(oidas), 80)):
        for desde, ajuste in ((0, 0.0), (1, -0.35)):
            if oidas_n[i] != primeras[desde]:
                continue
            aciertos = 0
            for k, w in enumerate(primeras[desde:]):
                if w in oidas_n[i + k - 1 if k else i: i + k + 2]:
                    aciertos += 1
            if aciertos >= min(3, len(primeras) - desde):
                candidatos.append((i, max(0.0, oidas[i]["ini"] + ajuste)))
    if candidatos:
        return candidatos[0][1]
    return _inicio_tolerante(tokens, oidas)


def _parecidas(a: str, b: str) -> bool:
    return bool(a and b) and (a == b or difflib.SequenceMatcher(None, a, b).ratio() >= 0.75)


def _inicio_tolerante(tokens: list[str], oidas: list[dict]) -> float | None:
    """Plan B: palabras en inglés, siglas o números («Black Friday», «SSD», «27») que Whisper
    escribe distinto. Busca, en las primeras 15 palabras del guion, el primer tramo de 2 palabras
    seguidas que se oyen parecidas, y calcula hacia atrás dónde empezó el guion."""
    guion = [_normal(t) for t in tokens[:15]]
    oidas_n = [_normal(o["w"]) for o in oidas[:120]]
    for j, w in enumerate(guion[:-1]):
        if not w:
            continue
        for i in range(len(oidas_n) - 1):
            if _parecidas(oidas_n[i], w) and _parecidas(oidas_n[i + 1], guion[j + 1]):
                # Retrocede por las palabras oídas justo antes (habla seguida, sin pausa), que son las
                # del guion que no se reconocieron; una sigla puede oírse como varias («ese ese de»).
                k, pasos = i, 0
                while k > 0 and pasos < 3 * j and oidas[k]["ini"] - oidas[k - 1]["fin"] < 0.45:
                    k -= 1
                    pasos += 1
                return max(0.0, oidas[k]["ini"])
    return None


AIRE_INICIAL = 0.18  # silencio limpio antes de la primera palabra (que no se coma la primera sílaba)


def narrar_variante(textos: list[str], cfg: dict, carpeta: Path, publico: Path, nombre: str) -> dict:
    carpeta.mkdir(parents=True, exist_ok=True)
    tokens, escena_de = [], []
    for i, t in enumerate(textos):
        for w in t.split():
            tokens.append(w)
            escena_de.append(i)
    texto = " ".join(textos)

    # Se intenta hasta 3 veces conseguir una narración que diga el guion completo desde el principio
    mejor = None
    for intento in range(3):
        crudo = sintetizar(texto, cfg, carpeta / f"gemini_{nombre}_{intento}.wav")
        oidas = escuchar_palabras(crudo, cfg, texto)
        inicio = inicio_del_guion(tokens, oidas)
        if inicio is None:
            # Último recurso: si el audio sí dice casi todo el guion, se usa desde la primera palabra
            if oidas and cobertura(tokens, oidas) >= 0.6:
                inicio = oidas[0]["ini"]
                print("No se reconoció el comienzo exacto, pero el audio dice el guion; se usa.")
            else:
                print("No se encontró el comienzo del guion en el audio; se repite la voz.")
                continue
        # Recorta lo que haya antes del guion (instrucciones leídas, silencio) con margen
        limpio = carpeta / f"limpio_{nombre}_{intento}.wav"
        corte = max(0.0, inicio - 0.12)
        _ffmpeg("-i", str(crudo), "-ss", f"{corte:.3f}", "-af",
                f"adelay={int(AIRE_INICIAL * 1000)}:all=1", "-ar", "24000", "-ac", "1", str(limpio))
        oidas = escuchar_palabras(limpio, cfg, texto)  # se vuelve a escuchar el audio ya recortado
        cob = cobertura(tokens, oidas)
        print(f"Voz intento {intento + 1}: se oye el {round(cob * 100)} % del guion")
        if mejor is None or cob > mejor[0]:
            mejor = (cob, limpio, oidas)
        if cob >= 0.8:
            break
    if mejor is None:
        raise RuntimeError("La voz no dijo el guion en ninguno de los intentos")
    cob_final, limpio, oidas = mejor
    from .autocontrol import ESTADO_VIDEO
    ESTADO_VIDEO["cobertura_voz"] = cob_final
    tiempos = alinear(tokens, oidas)
    # La primera palabra nunca empieza después de lo que de verdad se oyó
    tiempos[0] = (min(tiempos[0][0], AIRE_INICIAL + 0.05), tiempos[0][1])

    total = tiempos[-1][1] + 0.3
    factor = 1.0
    if total > 88:  # Facebook acepta hasta 90 s: se acelera un poco si hace falta
        factor = min(1.25, total / 86)
    archivo = f"voz_{nombre}.wav"
    _ffmpeg("-i", str(limpio), "-t", f"{total:.3f}",
            "-af", f"atempo={factor:.4f}" if factor != 1 else "anull",
            "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", str(publico / archivo))
    total = duracion(publico / archivo)
    if total > 89.5:
        raise ValueError(f"La narración dura {total:.0f}s y Facebook acepta hasta 90s.")
    t_abs = [(a / factor, b / factor) for a, b in tiempos]
    if t_abs[-1][1] > total - 0.05:  # por seguridad: ninguna palabra fuera del audio
        k = (total - 0.1) / t_abs[-1][1]
        t_abs = [(a * k, b * k) for a, b in t_abs]

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

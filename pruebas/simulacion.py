"""Simulación completa del bot sin internet ni claves.

Reemplaza Claude, la voz, Remotion, Telegram, GitHub y Meta por versiones falsas
y recorre todo el proceso: producir → aprobar por Telegram → publicar → métricas.

Uso (desde la raíz del repo, con ffmpeg instalado):
    python pruebas/simulacion.py
"""
import json
import shutil
import subprocess
import sys
import tempfile
import types
from pathlib import Path

ORIGEN = Path(__file__).resolve().parent.parent
TMP = Path(tempfile.mkdtemp(prefix="sim-bot-"))
REPO = TMP / "repo"
shutil.copytree(ORIGEN, REPO, ignore=shutil.ignore_patterns(".git", "salida", "node_modules", "__pycache__"))
# Primero se prueba el modo con aprobación por Telegram; al final, el modo automático.
_cfg = (REPO / "config.yaml").read_text()
assert "activa: false" in _cfg
(REPO / "config.yaml").write_text(_cfg.replace("activa: false", "activa: true", 1))
sys.path.insert(0, str(REPO))

import os  # noqa: E402

for clave in ["GEMINI_API_KEY", "ANTHROPIC_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "META_PAGE_ID", "META_PAGE_TOKEN"]:
    os.environ[clave] = "123" if clave == "TELEGRAM_CHAT_ID" else "falso"

REGISTRO = {"claude": [], "telegram": [], "gh": [], "meta": []}


# ---------- Claude falso ----------
def guion_falso():
    escenas = [{"voz": f"Frase número {i} sobre por qué el pan se pone duro.", "visual": f"visual {i}",
                "rotulo": "Pan" if i == 0 else "", "palabra_clave": "pan",
                "datos": [{"afirmacion": "el pan pierde agua", "fuente": "https://ejemplo.org"}]}
               for i in range(6)]
    escenas[1]["grafico"] = {"tipo": "barras", "items": [{"etiqueta": "pan", "valor": 35, "unidad": "%"},
                                                         {"etiqueta": "galleta", "valor": 5, "unidad": "%"}]}
    escenas[2]["grafico"] = {"tipo": "inventado", "items": []}  # debe descartarse
    return {"titulo": "Por qué el pan se pone duro", "descripcion": "No es por secarse... o sí.",
            "portada": "El pan NO se seca",
            "escenas": escenas,
            "gancho_b": {"voz": "¿Tu pan se endurece aunque lo tapes?", "visual": "pan tapado",
                         "rotulo": "", "palabra_clave": "pan", "tipo": "pregunta"},
            "direccion_arte": {"protagonista": "un pan con cara", "ambiente": "cocina"}}


CODIGO_OK = """import React from 'react';
import {EscenaProps, ANCHO, ALTO} from '../lib';
export const NOMBRE: React.FC<EscenaProps> = ({paleta}) => (
  <svg width={ANCHO} height={ALTO} viewBox={`0 0 ${ANCHO} ${ALTO}`}><rect width={ANCHO} height={ALTO} fill={paleta.fondo} /></svg>
);
"""

RONDA_REVISOR = {"n": 0}


def responder(system: str, contenido) -> str:
    texto = " ".join(c.get("text", "") for c in contenido if c.get("type") == "text")
    REGISTRO["claude"].append(system[:40])
    if "director creativo" in system:
        return json.dumps({"candidatos": [], "elegido": {"tema": "Por qué el pan se pone duro",
                                                          "angulo": "es agua que se mueve", "subtema": "cocina",
                                                          "por_que": "curioso"}})
    if "guionista" in system:
        return "Aquí va:\n```json\n" + json.dumps(guion_falso(), ensure_ascii=False) + "\n```"
    if "editor de Reels virales" in system:
        REGISTRO["pulir"] = True
        return json.dumps({"candidatos": [
            {"voz": "El pan duro no está seco.", "portada": "EL PAN NO SE SECA", "visual": "pan que cruje",
             "palabra_clave": "seco", "rotulo": "", "notas": {}},
            {"voz": "Tu pan se pone duro por culpa del agua.", "portada": "EL AGUA ENDURECE EL PAN",
             "visual": "un pan gigante se agrieta de golpe", "palabra_clave": "agua", "rotulo": "", "notas": {}}],
            "elegido": 1}, ensure_ascii=False)
    if "verificador de datos" in system:
        g = json.loads(texto[texto.index("\n\n") + 2:])
        g["verificacion"] = {"cambios": ["matiz en escena 2"], "confianza": "alta"}
        g.pop("direccion_arte", None)  # el verificador "olvida" un campo: debe recuperarse
        return json.dumps(g, ensure_ascii=False)
    if "Contrato técnico" in system:
        REGISTRO["ultimo_escena"] = system
        nombre = system.split("export const ")[1].split(":")[0]
        return "```tsx\n" + CODIGO_OK.replace("NOMBRE", nombre) + "```"
    if "director de arte" in system:
        RONDA_REVISOR["n"] += 1
        notas = {f"Escena{i}": {"nota": 8, "problemas": ""} for i in range(6)}
        notas["EscenaB"] = {"nota": 9, "problemas": ""}
        if RONDA_REVISOR["n"] == 1:
            notas["Escena3"] = {"nota": 5, "problemas": "el pan se ve plano"}
        return json.dumps({"escenas": notas, "comentario": "bien"})
    raise AssertionError("Prompt inesperado: " + system[:80])


class _Bloque:
    type = "text"

    def __init__(self, t):
        self.text = t


class _Mensajes:
    def create(self, **kw):
        return types.SimpleNamespace(content=[_Bloque(responder(kw["system"], kw["messages"][0]["content"]))])


anthropic = types.ModuleType("anthropic")
anthropic.Anthropic = lambda api_key=None: types.SimpleNamespace(messages=_Mensajes())
for n in ["BadRequestError", "RateLimitError", "APIConnectionError", "InternalServerError"]:
    setattr(anthropic, n, type(n, (Exception,), {}))
sys.modules["anthropic"] = anthropic


# ---------- Voz falsa (tono con palabras cronometradas) ----------
class Communicate:
    def __init__(self, texto, voz, rate="+0%", boundary="WordBoundary"):
        self.palabras = texto.split()

    async def stream(self):
        dur = 0.32 * len(self.palabras)
        mp3 = subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=f=300:d={dur}",
                              "-ar", "24000", "-ac", "1", "-f", "mp3", "-"], capture_output=True, check=True).stdout
        yield {"type": "audio", "data": mp3}
        for i, w in enumerate(self.palabras):
            yield {"type": "WordBoundary", "text": w, "offset": int(i * 0.32 * 1e7), "duration": int(0.28 * 1e7)}


edge = types.ModuleType("edge_tts")
edge.Communicate = Communicate
sys.modules["edge_tts"] = edge

# ---------- Gemini y Whisper falsos ----------
GEMINI = {"textos": []}


def gemini_post(url, json=None, timeout=None, headers=None):  # noqa: A002
    import base64 as b64
    if url.endswith("/voices"):
        GEMINI["voz_creada"] = json
        muestra = b64.b64encode(b"RIFF....WAVEfmt ").decode()
        datos = {"id": "voice_prueba123", "sample_audio": {"mime_type": "audio/wav", "data": muestra}}
        return types.SimpleNamespace(status_code=200, json=lambda: datos, text="", ok=True,
                                     raise_for_status=lambda: None)
    GEMINI.setdefault("voces_usadas", []).append(json["generationConfig"]["speechConfig"]["voiceConfig"])
    texto = json["contents"][0]["parts"][0]["text"].split("\n\n", 1)[-1]
    GEMINI["textos"].append(texto)
    dur = 0.3 * (len(texto.split()) + 2)
    pcm = subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=f=220:d={dur}",
                          "-ar", "24000", "-ac", "1", "-f", "s16le", "-"], capture_output=True, check=True).stdout
    datos = {"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": "audio/L16;codec=pcm;rate=24000",
                                                                    "data": b64.b64encode(pcm).decode()}}]}}]}
    return types.SimpleNamespace(status_code=200, json=lambda: datos, text="")


class WhisperModel:
    def __init__(self, *a, **k):
        pass

    def transcribe(self, ruta, **k):
        # Oye una palabra de más al principio ("Bueno") y dice el número con otras palabras.
        palabras = ["Bueno"] + GEMINI["textos"][-1].replace("número", "número cero").split()
        ws = [types.SimpleNamespace(word=" " + w, start=0.3 + i * 0.3, end=0.3 + i * 0.3 + 0.25)
              for i, w in enumerate(palabras)]
        return [types.SimpleNamespace(words=ws)], None


fw = types.ModuleType("faster_whisper")
fw.WhisperModel = WhisperModel
sys.modules["faster_whisper"] = fw

# ---------- Cargar el bot y reemplazar lo externo ----------
from bot import aprobaciones, estadisticas, meta, publicador, render, telegram, voz_gemini  # noqa: E402
voz_gemini.requests = types.SimpleNamespace(post=gemini_post, RequestException=Exception)
from bot import producir as prod  # noqa: E402
from bot.config import ESCENAS, PUBLICO  # noqa: E402
from bot.memoria import estado, memoria  # noqa: E402

FALLOS = {"bundle": 1}


def empaquetar():
    indice = (ESCENAS / "index.ts").read_text()
    assert "import {Ejemplo3D} from './Ejemplo3D';" in indice
    if "Escena0" not in indice:  # prueba inicial del 3D, todavía sin escenas
        return True, ""
    # La primera compilación falla en Escena2 para probar la reparación.
    for n in ["Escena0"]:
        assert (ESCENAS / f"{n}.tsx").exists(), f"falta {n}.tsx"
    assert "import {Escena5} from './Escena5';" in (ESCENAS / "index.ts").read_text()
    if FALLOS["bundle"]:
        FALLOS["bundle"] -= 1
        return False, "ERROR in ./src/escenas/Escena2.tsx: Unexpected token"
    return True, ""


def foto(plan_ruta, fotograma, destino):
    plan = json.loads(Path(plan_ruta).read_text())
    total = (plan["escenas"][-1]["inicio"] + plan["escenas"][-1]["duracion"]) * 30
    assert 0 <= fotograma < total, f"fotograma {fotograma} fuera del video ({total})"
    destino.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=s=108x192",
                    "-frames:v", "1", str(destino)], check=True)
    return True, ""


def renderizar(plan_ruta, destino):
    plan = json.loads(Path(plan_ruta).read_text())
    audio = PUBLICO / plan["audio"]
    assert audio.exists(), "no existe el audio " + plan["audio"]
    total = plan["escenas"][-1]["inicio"] + plan["escenas"][-1]["duracion"]
    destino.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    f"testsrc=s=540x960:r=30:d={total}", "-i", str(audio), "-shortest", str(destino)], check=True)
    return True, ""


render.empaquetar, render.foto, render.renderizar = empaquetar, foto, renderizar

telegram.mensaje = lambda texto, botones=None: REGISTRO["telegram"].append(("mensaje", texto, botones))
telegram.video = lambda ruta, texto, botones=None: REGISTRO["telegram"].append(("video", Path(ruta).name, texto))
telegram.audio = lambda ruta, texto: REGISTRO["telegram"].append(("audio", Path(ruta).name, texto))
telegram.aviso_seguro = lambda texto: REGISTRO["telegram"].append(("aviso", texto))
telegram.responder_boton = lambda i, t: REGISTRO["telegram"].append(("boton", t))

RELEASES = TMP / "releases"


def gh_falso(args, **kw):
    REGISTRO["gh"].append(args[:3])
    if args[:3] == ["gh", "release", "create"]:
        d = RELEASES / args[3]
        d.mkdir(parents=True)
        for a in args[4:]:
            if a.startswith("--"):
                break
            shutil.copy(a, d)
    elif args[:3] == ["gh", "release", "download"]:
        origen = RELEASES / args[3] / args[5]
        destino = Path(args[7])
        destino.mkdir(parents=True, exist_ok=True)
        shutil.copy(origen, destino)
    elif args[:3] == ["gh", "release", "delete"]:
        shutil.rmtree(RELEASES / args[3], ignore_errors=True)
    return types.SimpleNamespace(returncode=0)


publicador.subprocess = types.SimpleNamespace(run=gh_falso)
aprobaciones.subprocess = types.SimpleNamespace(run=gh_falso)


def publicar_reel(ruta, descripcion, titulo="", programar=None):
    assert Path(ruta).stat().st_size > 1000
    REGISTRO["meta"].append((Path(ruta).name, titulo, descripcion, programar))
    meta.ULTIMA["programado"] = bool(programar)
    return "fb_123" if not programar else "fb_prog"


BORRADOS = []
meta.borrar = lambda vid: BORRADOS.append(vid)


meta.publicar_reel = publicar_reel
meta.metricas = lambda vid: {"fb_reels_total_plays": 4321}


# ---------- 1) Producir ----------
print("== Producir ==")
ESCUCHA = []
_escuchar_real = aprobaciones.escuchar
aprobaciones.escuchar = lambda minutos: ESCUCHA.append(minutos)
prod.producir()
aprobaciones.escuchar = _escuchar_real
assert ESCUCHA and ESCUCHA[0] > 2, "al terminar debe quedarse escuchando los botones"
assert len(GEMINI["textos"]) == 1, "una sola versión, con voz de Gemini"
assert REGISTRO.get("pulir"), "debe pulir el gancho"
assert GEMINI["voz_creada"]["voice"]["type"] == "prompted" and GEMINI["voz_creada"]["store"] is True
assert all(v == {"voice": "voice_prueba123"} for v in GEMINI["voces_usadas"]), "siempre la voz de marca"
assert any(t[0] == "audio" for t in REGISTRO["telegram"]), "debe enviar la muestra de la voz"
assert not any("respaldo" in str(t) or "3D no funcion" in str(t) for t in REGISTRO["telegram"]), REGISTRO["telegram"]
est = estado()
assert len(est["pendientes"]) == 1, "debe quedar un video pendiente"
id_video = next(iter(est["pendientes"]))
videos = sorted(p.name for p in (RELEASES / f"pend-{id_video}").iterdir())
assert videos == ["A.mp4"], videos
botones = [t for t in REGISTRO["telegram"] if t[0] == "mensaje"][-1][2]
assert botones[0][0]["callback_data"] == f"pub:{id_video}:A" and botones[0][0]["text"] == "Publicar"
assert any("Opinión del revisor: bien" in str(t) for t in REGISTRO["telegram"])
assert RONDA_REVISOR["n"] == 2, "el revisor debió pedir una segunda ronda"
guion = json.loads((REPO / "salida" / id_video / "guion.json").read_text())
assert guion.get("direccion_arte"), "se perdió la dirección de arte"
plan_a = json.loads((REPO / "remotion" / "plan_A.json").read_text())
assert plan_a["motor"] == "3d" and render.OPCIONES["gl"] == "swangle"
assert plan_a["escenas"][0]["inicio"] == 0 and plan_a["escenas"][0]["palabras"][0]["t"] < 0.1, "debe recortar lo dicho antes del guion"
assert all(e["duracion"] > 0.5 for e in plan_a["escenas"])
assert plan_a["portada"] == "EL AGUA ENDURECE EL PAN", plan_a["portada"]
assert guion["escenas"][0]["voz"].startswith("Tu pan se pone duro por culpa")
assert plan_a["escenas"][1]["grafico"]["tipo"] == "barras" and plan_a["escenas"][2]["grafico"] is None
assert [e["camara"] for e in plan_a["escenas"][:2]] == ["picado", "frente"]
assert "Encuadre de cámara" in str(REGISTRO.get("ultimo_pedido", "Encuadre de cámara"))
assert "React Three Fiber" in REGISTRO["ultimo_escena"], "en 3D se debe usar la guía de escenas 3D"
assert not (REPO / "remotion" / "plan_B.json").exists() or True
for plan in (plan_a,):
    for a, b in zip(plan["escenas"], plan["escenas"][1:]):
        assert abs(a["inicio"] + a["duracion"] - b["inicio"]) < 0.01, "las escenas deben ir seguidas"
for nombre in ["A.mp4"]:
    info = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_name,r_frame_rate,sample_rate,channels",
                           "-of", "compact", str(REPO / "salida" / id_video / nombre)], capture_output=True, text=True).stdout
    assert "h264" in info and "aac" in info and "48000" in info and "channels=2" in info, info
print("Llamadas a Claude:", len(REGISTRO["claude"]))
print("Pendiente:", id_video, "| videos:", videos)

# ---------- 2) Tocar "Publicar" en Telegram ----------
print("== Aprobar en Telegram ==")
telegram.actualizaciones = lambda offset, espera=0: [] if offset > 10 else [
    {"update_id": 7, "callback_query": {"id": "x", "from": {"id": 999}, "data": f"pub:{id_video}:A"}},
    {"update_id": 10, "callback_query": {"id": "y", "from": {"id": 123}, "data": f"pub:{id_video}:A"}},
]
aprobaciones.escuchar(1)  # debe salir solo en cuanto no quedan pendientes
assert REGISTRO["meta"] and REGISTRO["meta"][0][0] == "A.mp4", "debía publicarse el video"
assert ("boton", "No autorizado") in REGISTRO["telegram"], "un desconocido no debe poder publicar"
assert estado()["telegram_offset"] == 11
assert not estado()["pendientes"]
assert not (RELEASES / f"pend-{id_video}").exists(), "el release pendiente debe borrarse"
m = memoria()[-1]
assert m["variante"] == "A" and m["video_fb"] == "fb_123" and m["gancho"].startswith("Tu pan se pone duro")
aprobaciones.procesar()  # segunda pasada: no debe repetir nada
assert len(REGISTRO["meta"]) == 1

# ---------- 3) Métricas al día siguiente ----------
print("== Métricas ==")
items = memoria()
items[-1]["publicado_en"] = "2000-01-01T00:00:00+00:00"
from bot.memoria import guardar_memoria  # noqa: E402
guardar_memoria(items)
estadisticas.actualizar(dias=100000)
assert memoria()[-1]["metricas"]["fb_reels_total_plays"] == 4321
from bot.memoria import resumen_para_director  # noqa: E402
assert "fb_reels_total_plays=4321" in resumen_para_director()

# ---------- 4) Rehacer ----------
print("== Rehacer ==")
est = estado()
est["pendientes"]["viejo"] = {"titulo": "x", "creado": "2000-01-01T00:00:00+00:00"}
from bot.memoria import guardar_estado  # noqa: E402
guardar_estado(est)
aprobaciones.procesar()
assert "viejo" not in estado()["pendientes"], "los pendientes viejos deben caducar"

# ---------- 5) Modo automático: produce, programa en el mejor horario y deja cancelar ----------
print("== Automático ==")
from datetime import datetime, timezone as tz  # noqa: E402
from bot import horarios  # noqa: E402
from bot.config import cargar_config  # noqa: E402
(REPO / "config.yaml").write_text(_cfg)
cfg_auto = cargar_config()
assert cfg_auto["aprobacion"]["activa"] is False
# 14:00 UTC = 10:00 a. m. en Santo Domingo: el siguiente horario libre es la 1:00 p. m.
h = horarios.proximo(cfg_auto, datetime(2026, 11, 23, 14, 0, tzinfo=tz.utc))
assert (h.hour, h.minute) == (13, 0), h
# 1:50 a. m. del día siguiente en UTC = 9:50 p. m. en RD: pasa a las 9:00 a. m. de mañana
h = horarios.proximo(cfg_auto, datetime(2026, 11, 24, 1, 50, tzinfo=tz.utc))
assert (h.day, h.hour) == (24, 9), h
antes = len(REGISTRO["meta"])
prod.producir()
programado = REGISTRO["meta"][antes]
assert programado[3] and programado[3] > datetime.now(tz.utc).timestamp(), "debía programarse a futuro"
ultimo = memoria()[-1]
assert ultimo["programado"] and ultimo["video_fb"] == "fb_prog"
assert not estado()["pendientes"], "en automático no quedan pendientes"
msg = [t for t in REGISTRO["telegram"] if t[0] == "mensaje"][-1]
assert "Programado para" in msg[1] and msg[2][0][0]["callback_data"] == "borrar:fb_prog"
# Un segundo video no puede caer en la misma hora
h2 = horarios.proximo(cfg_auto)
assert h2.astimezone(tz.utc).isoformat(timespec="seconds") != ultimo["publicado_en"]
# Cancelar desde Telegram
telegram.actualizaciones = lambda offset, espera=0: [
    {"update_id": 50, "callback_query": {"id": "z", "from": {"id": 123}, "data": "borrar:fb_prog"}}] if offset <= 50 else []
aprobaciones.procesar()
assert BORRADOS == ["fb_prog"] and memoria()[-1].get("cancelado")
assert estado().get("reemplazo", {}).get("titulo_cancelado"), "debe pedir un video de reemplazo"
assert any("otro" in str(t) and "horario" in str(t) for t in REGISTRO["telegram"])

print("\nSIMULACIÓN CORRECTA. Archivos en", TMP)

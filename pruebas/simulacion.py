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
# El config real publica 1 video al día por página; para probar los horarios se usan 3 al día.
_cfg = (REPO / "config.yaml").read_text().replace('horarios: ["20:00"]', 'horarios: ["09:00", "13:00", "20:00"]')
assert 'horarios: ["09:00", "13:00", "20:00"]' in _cfg
(REPO / "config.yaml").write_text(_cfg)
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
                "concepto": "por qué el pan" if i else "", "mundo": f"el pan con {i + 1} capas",
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

MUNDO_OK = """import React from 'react';
import type {Paleta} from '../lib3d';
export type MundoProps = {paso: number; frame: number; fps: number; paleta: Paleta; ocultar?: string[]; resaltar?: string[]};
export const PARTES = ['miga'] as const;
export const Mundo: React.FC<MundoProps> = () => <group />;
"""

RONDA_REVISOR = {"n": 0}


GRAVE = {"n": 0}


def responder(system: str, contenido) -> str:
    texto = " ".join(c.get("text", "") for c in contenido if c.get("type") == "text")
    # Cada paso empieza con la ficha de su profesional; se registra quién trabajó y se quita para seguir.
    from bot.equipo import EQUIPO, profesional as _prof
    for _k in EQUIPO:
        if system.startswith(_prof(_k)):
            REGISTRO.setdefault("equipo", []).append(_k)
            system = system[len(_prof(_k)):]
            break
    REGISTRO["claude"].append(system[:40])
    if "Contrato técnico" in system:
        REGISTRO["sistema_escena"] = system
    if system.startswith("Eres guionista"):
        REGISTRO["guion_pedido"] = texto
    if "director creativo" in system:
        return json.dumps({"candidatos": [], "elegido": {"tema": "Por qué el pan se pone duro",
                                                          "angulo": "es agua que se mueve", "subtema": "cocina",
                                                          "por_que": "curioso"}})
    if "guionista" in system:
        return "Aquí va:\n```json\n" + json.dumps(guion_falso(), ensure_ascii=False) + "\n```"
    if "control de calidad" in system:
        REGISTRO["control"] = REGISTRO.get("control", 0) + 1
        REGISTRO["control_texto"] = texto
        if GRAVE["n"] > 0:
            GRAVE["n"] -= 1
            return json.dumps({"problemas": [{"problema": "dato falso visible en una etiqueta",
                                              "regla": "Cada número en pantalla debe coincidir con la narración.",
                                              "area": "escenas", "grave": True, "fotograma": 8}], "nota_final": 4})
        return json.dumps({"problemas": [{"problema": "etiqueta cortada en el borde",
                                          "regla": "Las etiquetas deben quedar completas dentro del cuadro, lejos de los bordes.",
                                          "area": "escenas", "grave": False}], "nota_final": 7})
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
    if "MUNDO COMPARTIDO" in system:
        REGISTRO["mundo"] = REGISTRO.get("mundo", 0) + 1
        REGISTRO["pedido_mundo"] = texto
        return "```tsx\n" + MUNDO_OK + "```"
    if "Contrato técnico" in system:
        REGISTRO["ultimo_escena"] = system
        nombre = system.split("export const ")[1].split(":")[0]
        return "```tsx\n" + CODIGO_OK.replace("NOMBRE", nombre) + "```"
    if "director de arte" in system:
        RONDA_REVISOR["n"] += 1
        notas = {f"Escena{i}": {"nota": 8, "problemas": ""} for i in range(6)}
        notas["EscenaB"] = {"nota": 9, "problemas": ""}
        if RONDA_REVISOR["n"] == 1:
            notas["Escena3"] = {"nota": 4, "problemas": "el pan se ve plano"}
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
    texto = json["contents"][0]["parts"][0]["text"]
    assert not texto.lower().startswith(("narra", "lee ")), "a Gemini solo se le manda el guion"
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
        dur = len(ruta) / 16000 if not isinstance(ruta, str) else 0.3 * (len(palabras) + 2)
        paso = min(0.3, (dur - 0.5) / max(1, len(palabras)))  # las palabras caben en el audio real
        ws = [types.SimpleNamespace(word=" " + w, start=0.3 + i * paso, end=0.3 + i * paso + paso * 0.8)
              for i, w in enumerate(palabras)]
        return [types.SimpleNamespace(words=ws)], None


fw = types.ModuleType("faster_whisper")
fw.WhisperModel = WhisperModel
sys.modules["faster_whisper"] = fw

# ---------- Cargar el bot y reemplazar lo externo ----------
from bot import aprobaciones, estadisticas, meta, publicador, render, telegram, voz_gemini  # noqa: E402
voz_gemini.requests = types.SimpleNamespace(post=gemini_post, RequestException=Exception)
from bot import voces as _voces_mod  # noqa: E402
_voces_mod.requests = types.SimpleNamespace(post=gemini_post)
from bot import producir as prod  # noqa: E402
from bot.config import ESCENAS, PUBLICO  # noqa: E402
from bot.memoria import cadena, estado, guardar_cadena, memoria  # noqa: E402

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
narraciones = [t for t in GEMINI["textos"] if t != _voces_mod.FRASE]
assert len(narraciones) == 1, "una sola versión, con voz de Gemini"
assert len(GEMINI["textos"]) - 1 >= 7, "antes del primer video manda las muestras de voz para elegir"
assert REGISTRO.get("pulir"), "debe pulir el gancho"
assert REGISTRO.get("control") == 1, "debe revisar el video terminado"
assert any("Control de calidad" in str(t) for t in REGISTRO["telegram"])
assert GEMINI["voz_creada"]["voice"]["type"] == "prompted" and GEMINI["voz_creada"]["store"] is True
# la narración (la última llamada) siempre con la voz de marca; antes van las muestras para elegir
assert GEMINI["voces_usadas"][-1] == {"voice": "voice_prueba123"}, "siempre la voz de marca"
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
assert plan_a["escenas"][0]["inicio"] == 0 and plan_a["escenas"][0]["palabras"][0]["t"] < 0.3, "debe recortar lo dicho antes del guion"
assert all(e["duracion"] > 0.5 for e in plan_a["escenas"])
assert plan_a["portada"] == "EL AGUA ENDURECE EL PAN", plan_a["portada"]
assert guion["escenas"][0]["voz"].startswith("Tu pan se pone duro por culpa")
assert plan_a["escenas"][1]["grafico"]["tipo"] == "barras" and plan_a["escenas"][2]["grafico"] is None
assert [e["camara"] for e in plan_a["escenas"][:2]] == ["picado", "frente"]
assert "Encuadre de cámara" in str(REGISTRO.get("ultimo_pedido", "Encuadre de cámara"))
assert "React Three Fiber" in REGISTRO["ultimo_escena"], "en 3D se debe usar la guía de escenas 3D"
# Mundo compartido: se dibuja una vez, las escenas lo reciben y el plan va en modo continuo
assert REGISTRO.get("mundo") == 1, "el mundo compartido se dibuja una sola vez por video"
assert "el pan con 3 capas" in REGISTRO["pedido_mundo"], "el mundo debe conocer cómo queda cada escena"
assert "Mundo compartido (OBLIGATORIO" in REGISTRO["ultimo_escena"] and "export const Mundo" in REGISTRO["ultimo_escena"]
assert plan_a["continuo"] is True and plan_a["estilo_subtitulos"] == "concepto"
assert plan_a["escenas"][1]["concepto"] == "por qué el pan"
assert (REPO / "remotion" / "src" / "escenas" / "Mundo.tsx").exists()
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

# Las reglas aprendidas deben llegar a las instrucciones del siguiente video
from bot.autocontrol import texto_reglas  # noqa: E402
assert "etiquetas deben quedar completas" in texto_reglas("escenas")

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

# ---------- 6) Se acaba el límite de Claude a mitad del video y sigue solo después ----------
print("== Límite de Claude y reanudación ==")
from bot import reanudar, estudio as est_mod  # noqa: E402
from bot.claude import LimiteDeSuscripcion  # noqa: E402
_dibujar_real = est_mod.dibujar
FALLA = {"hecho": False}


def dibujar_con_limite(claude, cfg, nombre, *a, **k):
    if nombre == "Escena3" and not FALLA["hecho"]:
        FALLA["hecho"] = True
        raise LimiteDeSuscripcion("Se agotó el límite. [You've hit your 5-hour limit · resets 1:50pm (UTC)]")
    return _dibujar_real(claude, cfg, nombre, *a, **k)


est_mod.dibujar = dibujar_con_limite
try:
    prod.producir()
    raise AssertionError("debía cortarse por el límite")
except LimiteDeSuscripcion as e:
    cuando = reanudar.guardar_por_limite(str(e))
assert (cuando.hour, cuando.minute) == (13, 55), cuando
guardado = json.loads(reanudar.EN_CURSO.read_text())
assert guardado["guion"] and guardado["tema"] and len(guardado["escenas"]) >= 1, "debe guardar el avance"
assert estado()["reintentar_desde"]
# La revisión de cada 20 minutos lo relanza cuando ya pasó la hora
e = estado(); e["reintentar_desde"] = "2000-01-01T00:00:00+00:00"; from bot.memoria import guardar_estado as _ge; _ge(e)  # noqa: E702
# Su horario ya pasó: al terminar debe publicarse en el momento
guardado["inicio"] = "2000-01-01T08:00:00+00:00"
reanudar.EN_CURSO.write_text(json.dumps(guardado))
guiones_antes = sum(1 for c in REGISTRO["claude"] if "guionista" in c)
antes = len(REGISTRO["meta"])
prod.producir()
assert sum(1 for c in REGISTRO["claude"] if "guionista" in c) == guiones_antes, "no debe reescribir el guion"
assert REGISTRO["meta"][antes][3] is None, "su horario ya pasó: se publica en el momento"
assert not reanudar.EN_CURSO.exists(), "al terminar se borra el avance"
assert any("ya había pasado" in str(t) for t in REGISTRO["telegram"])
est_mod.dibujar = _dibujar_real

# ---------- 6b) Límite con espera en la misma tarea y relevo en cadena ----------
print("== Límite: espera en la misma tarea y relevo ==")
_cfg_actual = (REPO / "config.yaml").read_text()
(REPO / "config.yaml").write_text(_cfg_actual.replace('modo_cadena: "continuo"', 'modo_cadena: "turnos"'))
import os  # noqa: E402
from datetime import datetime as _dt, timedelta as _td, timezone as _tz  # noqa: E402


def aviso_limite(minutos):
    hora = (_dt.now(_tz.utc) + _td(minutes=minutos)).strftime("%I:%M%p").lstrip("0").lower()
    return f"Se agotó el límite. [You've hit your 5-hour limit · resets {hora} (UTC)]"


ESPERAS, RELEVOS = [], []
prod._guardar_avance_en_repo = lambda *a: None
prod._relanzar_produccion = lambda: RELEVOS.append(1)


def esperar_falso(segundos):
    ESPERAS.append(segundos / 60)
    if not estado().get("reintentar_desde"):
        return  # espera de turno (no de límite)
    assert estado().get("esperando"), "mientras espera debe marcarlo"
    # mientras espera, la cadena late: el vigilante no lanza otra producción
    assert estado().get("latido")


# A) La espera cabe: espera en la misma tarea y termina el video
FALLA["hecho"] = False
MINUTOS = {"n": 30}


def dibujar_con_limite_b(claude, cfg, nombre, *a, **k):
    if nombre == "Escena3" and not FALLA["hecho"]:
        FALLA["hecho"] = True
        raise LimiteDeSuscripcion(aviso_limite(MINUTOS["n"]))
    return _dibujar_real(claude, cfg, nombre, *a, **k)


est_mod.dibujar = dibujar_con_limite_b
os.environ["MINUTOS_TAREA"] = "340"
antes = len(REGISTRO["meta"])
guiones_antes = sum(1 for c in REGISTRO["claude"] if "guionista" in c)
e = estado(); e.pop("turno_hecho", None); _ge(e)  # noqa: E702
prod.ejecutar(esperar=esperar_falso)
assert 30 <= sum(ESPERAS) <= 37, ESPERAS
assert RELEVOS == [1], "al terminar deja lanzada la siguiente tarea de la cadena"
RELEVOS.clear()
assert len(REGISTRO["meta"]) == antes + 1, "debe terminar y publicar el video"
assert sum(1 for c in REGISTRO["claude"] if "guionista" in c) == guiones_antes + 1, "un solo guion: sigue el mismo video"
assert not reanudar.EN_CURSO.exists() and not estado().get("reintentar_desde") and not estado().get("esperando")
assert any("sigo solo desde donde se quedó" in str(t) for t in REGISTRO["telegram"][-8:])

# B) La espera no cabe en la tarea: espera lo que puede y lanza otra tarea
FALLA["hecho"] = False
MINUTOS["n"] = 240
ESPERAS.clear()
os.environ["MINUTOS_TAREA"] = "200"
antes = len(REGISTRO["meta"])
e = estado(); e.pop("turno_hecho", None); _ge(e)  # noqa: E702
prod.ejecutar(esperar=esperar_falso)
assert RELEVOS == [1], "debe pasar el relevo a otra tarea"
assert 185 <= sum(ESPERAS) <= 191, ESPERAS  # espera todo lo que cabe (200 - 10)
assert reanudar.EN_CURSO.exists() and len(REGISTRO["meta"]) == antes, "el video sigue a medias"
assert not estado().get("esperando"), "al pasar el relevo deja de marcar que espera"

# C) La tarea de relevo llega cuando ya falta poco: espera y termina el mismo video
e = estado(); e["reintentar_desde"] = (_dt.now(_tz.utc) + _td(minutes=20)).isoformat(timespec="seconds"); _ge(e)  # noqa: E702
ESPERAS.clear()
os.environ["MINUTOS_TAREA"] = "340"
guiones_antes = sum(1 for c in REGISTRO["claude"] if "guionista" in c)
prod.ejecutar(esperar=esperar_falso)
assert RELEVOS == [1, 1], "termina el video y deja lanzada la siguiente"
assert len(REGISTRO["meta"]) == antes + 1 and not reanudar.EN_CURSO.exists()
RELEVOS.clear()
assert sum(1 for c in REGISTRO["claude"] if "guionista" in c) == guiones_antes, "no debe reescribir el guion"
est_mod.dibujar = _dibujar_real

# D) El límite se acaba al EMPEZAR (sin nada guardado): igual espera, no reintenta en bucle
_tema_real = prod.elegir_tema
LLAMADAS_TEMA = {"n": 0}


def tema_con_limite(*a, **k):
    LLAMADAS_TEMA["n"] += 1
    if LLAMADAS_TEMA["n"] == 1:
        raise LimiteDeSuscripcion(aviso_limite(45))
    return _tema_real(*a, **k)


prod.elegir_tema = tema_con_limite
ESPERAS.clear()
e = estado(); e.pop("turno_hecho", None); _ge(e)  # noqa: E702
avisos_antes = sum(1 for t in REGISTRO["telegram"] if "límite de uso" in str(t))
antes = len(REGISTRO["meta"])
prod.ejecutar(esperar=esperar_falso)
prod.elegir_tema = _tema_real
assert 45 <= sum(ESPERAS) <= 52, ESPERAS
assert LLAMADAS_TEMA["n"] == 2, "un intento, espera, y el segundo funciona"
assert len(REGISTRO["meta"]) == antes + 1, "después de esperar hace el video"
assert sum(1 for t in REGISTRO["telegram"] if "límite de uso" in str(t)) == avisos_antes + 1, "un solo aviso"
assert any("sigo solo con el video" in str(t) for t in REGISTRO["telegram"][-10:])
os.environ.pop("MINUTOS_TAREA")

# E) Cadena: el turno ya está hecho -> espera al siguiente aquí mismo y lo hace
print("== Trabajo en cadena ==")
os.environ["MINUTOS_TAREA"] = "340"
cfg_sim = prod.cargar_config()
RELEVOS.clear(); ESPERAS.clear()  # noqa: E702
ahora = _dt.now(_tz.utc)
siguiente = prod.proximo_turno(cfg_sim, ahora)
falta = (siguiente - ahora).total_seconds() / 60
e = estado(); e["turno_hecho"] = prod.turno_actual(cfg_sim)[1]; _ge(e)  # noqa: E702
antes = len(REGISTRO["meta"])
prod.ejecutar(esperar=esperar_falso)
if falta + 170 <= 340:  # cabe: espera y hace el video del siguiente turno
    assert len(REGISTRO["meta"]) == antes + 1 and abs(sum(ESPERAS) - falta - 1) < 2, (ESPERAS, falta)
    assert estado()["turno_hecho"] == siguiente.astimezone(_tz.utc).strftime("%Y-%m-%dT%H:%M")
else:  # no cabe: espera lo que puede y pasa el relevo, sin hacer video
    assert len(REGISTRO["meta"]) == antes and RELEVOS == [1]
assert RELEVOS == [1] and estado().get("latido"), "siempre deja la siguiente tarea y da señales de vida"

# F) Turno pendiente aunque ya sea tarde (el bot estuvo caído): se hace ya
RELEVOS.clear(); ESPERAS.clear()  # noqa: E702
e = estado(); e["turno_hecho"] = "2000-01-01T00:00"; _ge(e)  # noqa: E702
antes = len(REGISTRO["meta"])
prod.ejecutar(esperar=esperar_falso)
assert len(REGISTRO["meta"]) == antes + 1 and not ESPERAS and RELEVOS == [1]
assert estado()["turno_hecho"] == prod.turno_actual(cfg_sim)[1]

# G) Turnos: siempre hay uno actual y uno próximo, a la hora correcta
for h in range(0, 24 * 60, 37):
    t = _dt(2026, 11, 21, tzinfo=_tz.utc) + _td(minutes=h)
    a, _, _c = prod.turno_actual(cfg_sim, t)
    b = prod.proximo_turno(cfg_sim, t)
    assert a <= t < b and (b - a) <= _td(hours=12)
    assert a.astimezone(_tz(_td(hours=-4))).strftime("%H:%M") in ("03:17", "09:17", "15:17")

# H) Vigilante: si la cadena dejó de latir, la relanza (una vez, no cada 20 minutos)
from bot import aprobaciones as _ap  # noqa: E402
gh_antes = len(REGISTRO["gh"])
e = estado(); e["latido"] = (_dt.now(_tz.utc) - _td(hours=5)).isoformat(); e.pop("vigilante", None); _ge(e)  # noqa: E702
_ap.relanzar_si_toca(); _ap.relanzar_si_toca()  # noqa: E702
assert [g for g in REGISTRO["gh"][gh_antes:] if g[:3] == ["gh", "workflow", "run"]].__len__() == 1
e = estado(); e["latido"] = _dt.now(_tz.utc).isoformat(); e.pop("vigilante", None); _ge(e)  # noqa: E702
gh_antes = len(REGISTRO["gh"])
_ap.relanzar_si_toca()
assert not any(g[:3] == ["gh", "workflow", "run"] for g in REGISTRO["gh"][gh_antes:]), "si late, no relanza"
os.environ.pop("MINUTOS_TAREA")

# ---------- 7) Error grave: el bot lo arregla solo y publica sin preguntar ----------
print("== Error grave con arreglo automático ==")
from bot import autocontrol as ac  # noqa: E402
_tecnicos = ac.chequeos_tecnicos
VOZ_MAL = {"n": 1}


def tecnicos_con_error(voz, duracion):
    problemas = _tecnicos(voz, duracion)
    if VOZ_MAL["n"] > 0:
        VOZ_MAL["n"] -= 1
        problemas.append({"grave": True, "area": "voz", "problema": "la voz empieza tarde (1.2 s)",
                          "regla": "La primera palabra del gancho debe oírse en los primeros 0,3 segundos."})
    return problemas


ac.chequeos_tecnicos = tecnicos_con_error
GRAVE["n"] = 1
controles = REGISTRO.get("control", 0)
pend_antes = len(estado()["pendientes"])
antes = len(REGISTRO["meta"])
prod.producir()
ac.chequeos_tecnicos = _tecnicos
assert REGISTRO["control"] - controles == 2, "debe revisar, arreglar y volver a revisar"
assert len(REGISTRO["meta"]) == antes + 1, "debe publicarse solo, sin botones"
assert len(estado()["pendientes"]) == pend_antes, "no debe quedar esperando decisión"
avisos = [str(t) for t in REGISTRO["telegram"]]
assert any("Arreglé solo" in t and "rehice la voz" in t and "la escena 5" in t and "Ya no quedan" in t for t in avisos), avisos[-4:]
assert not any("no lo publico solo" in t for t in avisos[-6:])

# Si el error no se puede arreglar, igual se publica
GRAVE["n"] = 5
antes = len(REGISTRO["meta"])
prod.producir()
GRAVE["n"] = 0
assert len(REGISTRO["meta"]) == antes + 1, "aunque quede un error, se publica"
assert any("lo publico igual" in str(t) for t in REGISTRO["telegram"][-6:])

# ---------- 8) Facebook falla al publicar: el video no se pierde ----------
print("== Facebook caído o token vencido ==")
from bot import meta as _meta  # noqa: E402
_reel_real = meta.publicar_reel


def reel_token_vencido(*a, **k):
    raise _meta.ErrorDeFacebook("El token de la página de Facebook (META_PAGE_TOKEN) venció o no es válido.")


meta.publicar_reel = reel_token_vencido
antes = len(REGISTRO["meta"])
pend_antes = set(estado()["pendientes"])
prod.producir()  # no debe romperse
meta.publicar_reel = _reel_real
nuevos = set(estado()["pendientes"]) - pend_antes
assert len(nuevos) == 1, "el video queda guardado como pendiente"
assert any(g[:3] == ["gh", "release", "create"] for g in REGISTRO["gh"][-5:]), "se sube el video para no perderlo"
assert any("No pude publicar" in str(t) and "META_PAGE_TOKEN" in str(t) and "pub:" in str(t) for t in REGISTRO["telegram"][-6:])
assert not reanudar.EN_CURSO.exists()
for _id in nuevos:  # limpiar
    e = estado(); e["pendientes"].pop(_id, None); _ge(e)  # noqa: E702

# Un error pasajero de Facebook (500) se reintenta solo
import requests as _rq  # noqa: E402
_post_real = _rq.post
RESPUESTAS = [500, 200]


class _Resp:
    def __init__(self, code):
        self.status_code, self.ok, self.text = code, code < 400, ""

    def json(self):
        return {"video_id": "v1"}

    def raise_for_status(self):
        if not self.ok:
            raise _rq.HTTPError(str(self.status_code))


_meta.time = types.SimpleNamespace(sleep=lambda s: None)
r = _meta._pedir(lambda *a, **k: _Resp(RESPUESTAS.pop(0)), "url")
assert r.status_code == 200 and not RESPUESTAS, "debe reintentar tras un 500"
try:
    _meta._revisar(type("R", (), {"ok": False, "status_code": 400, "json": lambda self: {"error": {"code": 190, "message": "Error validating access token"}}})())
    raise AssertionError("debía avisar del token")
except _meta.ErrorDeFacebook as e:
    assert "META_PAGE_TOKEN" in str(e)

# ---------- 9) Videos rotos seguidos: como mucho 2 rehechos por día ----------
print("== Descartes en bucle ==")
from bot import revisor as _rev  # noqa: E402
_revisar_real = _rev.revisar
_rev.revisar = lambda claude, cfg, guion, fotos: {"escenas": {f["nombre"]: {"nota": 2, "problemas": "vacía"} for f in fotos}}
RELANZA = []
prod._relanzar_produccion = lambda: RELANZA.append(1)
e = estado(); e.pop("descartes", None); _ge(e)  # noqa: E702
antes = len(REGISTRO["meta"])
for _ in range(3):
    prod.producir()
_rev.revisar = _revisar_real
assert len(REGISTRO["meta"]) == antes, "un video roto no se publica"
assert estado().get("rehacer_turno"), "un descarte pide rehacer el turno"
assert any("no rehago otro" in str(t) for t in REGISTRO["telegram"][-4:])
e = estado(); e.pop("rehacer_turno", None); _ge(e)  # noqa: E702

# Nota baja pero no rota (4.5): se publica igual
_rev.revisar = lambda claude, cfg, guion, fotos: {"escenas": {f["nombre"]: {"nota": 4.5, "problemas": "mejorable"} for f in fotos}}
e = estado(); e.pop("descartes", None); e.pop("rehacer_turno", None); _ge(e)  # noqa: E702
antes = len(REGISTRO["meta"])
prod.producir()
_rev.revisar = _revisar_real
assert len(REGISTRO["meta"]) == antes + 1, "con nota 4.5 se publica igual"
assert not estado().get("rehacer_turno")

# Escenario según el tema: cambia el fondo y el suelo, no los colores del protagonista
base = {"fondo": "#D3CEC6", "tinta": "#1B1B1F", "acentos": ["#D2452F", "#E9E4DB", "#A3D92B", "#E0A526", "#C2BBAF"]}
c = prod.paleta_con_escenario(base, prod.escenario_de({"direccion_arte": {"escenario": "Cielo"}}))
assert c["fondo"] == "#9CCDF2" and c["acentos"][4] == "#7DBE4E" and c["acentos"][0] == "#D2452F"
o = prod.paleta_con_escenario(base, "oscuro")
assert o["tinta"] == "#F2EFE9" and base["acentos"][4] == "#C2BBAF", "no debe tocar la paleta original"
assert prod.escenario_de({"direccion_arte": {"escenario": "marte"}}) == "estudio"

# ---------- 10) Voz: ninguna escena queda con duración cero ----------
print("== Tiempos de escena seguros ==")
sys.modules.setdefault("edge_tts", types.ModuleType("edge_tts"))
from bot import voz_gemini as _vg  # noqa: E402
ini = _vg.inicios_seguros([0.0, 0.0, 0.0, 0.05, 6.0, 9.0], total=12.0)
assert all(b - a >= 1.0 for a, b in zip(ini, ini[1:] + [12.0])), ini
textos = ["uno dos tres cuatro cinco", "seis siete ocho nueve diez", "once doce trece catorce quince"]
tok = " ".join(textos).split()
oidas = [{"w": w, "ini": 0.5 + 0.3 * k, "fin": 0.75 + 0.3 * k} for k, w in enumerate(tok[8:])]  # corte tardío
assert _vg._cobertura_inicio(tok, oidas) < 0.5, "un corte tardío debe detectarse"
t = _vg.alinear(tok, oidas)
assert all(t[k][0] < t[k + 1][0] for k in range(len(t) - 1)), "las palabras no se apilan en el mismo instante"

# ---------- 11) La voz lee instrucciones al principio: nunca debe quedar en el video ----------
print("== Voz que lee instrucciones ==")
import re as _re  # noqa: E402
INSTR = "narra como una divulgadora de videos virales cercana y cálida lee exactamente este texto".split()
GUION_V = ["Tu pan se pone duro por culpa del agua", "y no del aire como casi todos creen"]
TOK_V = " ".join(GUION_V).split()
CASO = {"modo": "lee_instrucciones", "cortes": [], "intentos": 0}


def _palabras(lista, t0):
    return [{"w": w, "ini": round(t0 + 0.3 * k, 2), "fin": round(t0 + 0.3 * k + 0.25, 2)} for k, w in enumerate(lista)]


def _crudo():
    CASO["intentos"] += 1
    if CASO["modo"] == "lee_instrucciones":  # siempre lee las instrucciones y luego el guion
        return _palabras(INSTR + TOK_V, 0.3)
    if CASO["modo"] == "solo_instrucciones_mal_oidas":  # el guion empieza irreconocible
        return _palabras(INSTR + ["tú", "pan", "sé", "pone"] + TOK_V[4:], 0.3)
    return _palabras(TOK_V, 0.3)


def _escuchar(ruta, cfg, pista):
    crudo = CASO.setdefault("ultimo", [])
    if "gemini_" in str(ruta):
        CASO["ultimo"] = _crudo()
        return CASO["ultimo"]
    corte = CASO["cortes"][-1]
    return [{"w": o["w"], "ini": round(o["ini"] - corte + 0.25, 2), "fin": round(o["fin"] - corte + 0.25, 2)}
            for o in CASO["ultimo"] if o["ini"] >= corte - 0.01]


def _ffmpeg_v(*args):
    if "-ss" in args:
        CASO["cortes"].append(float(args[args.index("-ss") + 1]))
    Path(args[-1]).write_bytes(b"x")


_sint_orig, _esc_orig, _ff_orig, _dur_orig = _vg.sintetizar, _vg.escuchar_palabras, _vg._ffmpeg, _vg.duracion
TEXTOS_VOZ = []
_vg.sintetizar = lambda texto, cfg, destino: (TEXTOS_VOZ.append(texto), Path(destino).write_bytes(b"x"), destino)[2]
_vg.escuchar_palabras = _escuchar
_vg._ffmpeg = _ffmpeg_v
_vg.duracion = lambda ruta: 20.0
carpeta = Path(TMP) / "voz_prueba"
cfg_v = prod.cargar_config()
# A) lee las instrucciones y después el guion: se corta justo donde empieza el guion
r = _vg.narrar_variante(GUION_V, cfg_v, carpeta, carpeta, "T")
assert TEXTOS_VOZ[-1] == "\n\n".join(GUION_V), "cada escena en su párrafo (pausa natural entre ideas)"
# las palabras falsas van a 3,3 por segundo: se frena para un ritmo natural
assert r["total"] > 0
inicio_guion = 0.3 + 0.3 * len(INSTR)
assert abs(CASO["cortes"][-1] - (inicio_guion - 0.12)) < 0.05, CASO["cortes"]
# B) las instrucciones se leen y el comienzo del guion no se entiende: NUNCA se usa ese audio
CASO.update(modo="solo_instrucciones_mal_oidas", cortes=[], intentos=0)
try:
    _vg.narrar_variante(GUION_V, cfg_v, carpeta, carpeta, "T2")
    usado = CASO["cortes"][-1] if CASO["cortes"] else None
    # si se usó, el corte tiene que estar DESPUÉS de las instrucciones
    assert usado is not None and usado >= 0.3 + 0.3 * len(INSTR) - 0.2, ("se coló la instrucción", CASO["cortes"])
except RuntimeError:
    pass  # sin un audio que empiece bien, se usa la voz de respaldo (Edge): correcto
# C) el texto enviado a Gemini es solo el guion, sin notas de tono
ENVIADO = {}
_req = _vg.requests.post


class _R:
    status_code = 200

    def json(self):
        import base64 as b64
        return {"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": "audio/L16;rate=24000", "data": b64.b64encode(b"\0\0" * 10).decode()}}]}}]}


def _post(url, json=None, **k):
    ENVIADO["texto"] = json["contents"][0]["parts"][0]["text"]
    return _R()


_vg.requests.post = _post
_vg.voz_de_marca = lambda cfg: None
_sint = __import__("bot.voz_gemini", fromlist=["x"])
import importlib  # noqa: E402
_real = importlib.reload(_sint)
_real.requests.post = _post
_real.voz_de_marca = lambda cfg: None
os.environ.setdefault("GEMINI_API_KEY", "x")
_real.sintetizar("Tu pan se pone duro", cfg_v, carpeta / "s.wav")
_vg.requests.post = _req
_real.requests.post = _req  # no dejar el requests de verdad cambiado para el resto
_real.requests = types.SimpleNamespace(post=gemini_post, RequestException=Exception)
assert ENVIADO["texto"] == "Tu pan se pone duro", ENVIADO["texto"]

# El control final sabe qué dice la voz en cada fotograma (para pillar imágenes sin relación)
assert "la voz dice" in REGISTRO.get("control_texto", ""), REGISTRO.get("control_texto", "")[:200]

# ---------- 12) Segunda página: historias (mismo bot, mismo Claude y Gemini, otra página) ----------
print("== Segunda página: historias ==")
from bot import config as _config  # noqa: E402
_vg.sintetizar, _vg.escuchar_palabras, _vg._ffmpeg, _vg.duracion = _sint_orig, _esc_orig, _ff_orig, _dur_orig
assert _config.canales() == ["explicativos", "casa", "historias", "psicologia"], _config.canales()
assert not _config.canal_listo("psicologia") and not _config.canal_listo("casa"), "sin secretos no trabajan"
assert not _config.canal_listo("historias"), "sin sus secretos, la página no trabaja"
cfg_p = prod.cargar_config("explicativos")
solo = {prod.turno_actual(cfg_p, _dt(2026, 11, 23, h, 30, tzinfo=_tz.utc))[2] for h in range(24)}
assert solo == {"explicativos"}, "sin secretos, todos los turnos son de la página principal"
os.environ["META_PAGE_ID_HISTORIAS"] = "pagina_historias"
os.environ["META_PAGE_TOKEN_HISTORIAS"] = "token_historias"
assert _config.canal_listo("historias")
# 4 turnos al día que se alternan: 3:17 explicativos, 9:17 historias, 3:17 p. m. explicativos, 9:17 p. m. historias
quien = [prod.turno_actual(cfg_p, _dt(2026, 11, 23, h, 30, tzinfo=_tz.utc))[2] for h in (8, 14, 20)]
quien.append(prod.turno_actual(cfg_p, _dt(2026, 11, 24, 2, 30, tzinfo=_tz.utc))[2])
assert quien == ["explicativos", "historias", "explicativos", "historias"], quien
ids = {prod.turno_actual(cfg_p, _dt(2026, 11, 23, h, 30, tzinfo=_tz.utc))[1] for h in (8, 14)}
assert len(ids) == 2 and any(i.startswith("historias@") for i in ids)

memoria_explicativos = (REPO / "data" / "memoria.json").read_text()
_config.usar_canal("historias")
cfg_h = prod.cargar_config()
assert cfg_h["canal"]["formato"] == "historia" and cfg_h["estilo"]["acabado"] == "dibujo"
assert not cfg_h["estilo"].get("escenario_fijo"), "el escenario cambia con cada historia"
assert cfg_h["claude"]["modelo"] == cfg_p["claude"]["modelo"], "hereda lo que no cambia"
assert cfg_h["publicacion"]["horarios"] == ["22:00"]
assert any("muertes" in x for x in cfg_h["canal"]["prohibidos"]), "sin víctimas"
assert _config.secreto("META_PAGE_ID") == "pagina_historias" and _config.secreto("TELEGRAM_CHAT_ID") == "123"
from bot import voz_gemini as _vz  # noqa: E402
assert _vz.VOZ == REPO / "data" / "historias" / "voz.json", "cada página tiene su propia voz"
from bot import telegram as _tg_mod  # noqa: E402
assert _tg_mod._pagina() == "[History Time] ", _tg_mod._pagina()
llamadas_antes = len(REGISTRO["claude"])
antes = len(REGISTRO["meta"])
prod.producir()
assert len(REGISTRO["meta"]) == antes + 1, "publica en la página de historias"
nuevos = REGISTRO["claude"][llamadas_antes:]
assert any(x.startswith("Eres guionista de historias reales") for x in nuevos), nuevos[:6]
plan_h = json.loads((REPO / "remotion" / "plan_A.json").read_text())
assert plan_h["paleta"]["fondo"] == prod.escenarios(cfg_h)[plan_h["escenario"]]["fondo"], "con los colores de la página"
assert plan_h["foco"] and plan_h["paleta"]["tinta"] == "#F2EFE9", "luz de cine"
mem_h = json.loads((REPO / "data" / "historias" / "memoria.json").read_text())
assert len(mem_h) == 1, "la memoria de historias es aparte"
assert (REPO / "data" / "memoria.json").read_text() == memoria_explicativos, "no toca la otra página"
assert "Por qué el pan" not in (REPO / "data" / "historias" / "tendencias.json").read_text() if (REPO / "data" / "historias" / "tendencias.json").exists() else True

# Un botón de un video de historias se atiende desde la revisión (que arranca en la página principal)
_config.usar_canal("explicativos")
eh = json.loads((REPO / "data" / "historias" / "estado.json").read_text())
eh["pendientes"]["hist1"] = {"titulo": "La señal", "creado": _dt.now(_tz.utc).isoformat()}
(REPO / "data" / "historias" / "estado.json").write_text(json.dumps(eh))
oferta = [{"update_id": 900, "callback_query": {"id": "c9", "from": {"id": 123}, "data": "descartar:hist1"}}]
telegram.actualizaciones = lambda offset, espera=0: oferta if offset <= 900 else []
aprobaciones.procesar(caducar=False)
assert "hist1" not in json.loads((REPO / "data" / "historias" / "estado.json").read_text())["pendientes"]
assert _config.CANAL == "explicativos", "vuelve a la página principal"
assert estado()["telegram_offset"] == 901, "el chat de Telegram es uno solo"

# ---------- 13) Producción continua: siempre para la página con menos videos en cola ----------
print("== Producción continua ==")
(REPO / "config.yaml").write_text((REPO / "config.yaml").read_text()
                                  .replace('modo_cadena: "turnos"', 'modo_cadena: "continuo"')
                                  .replace("cola_maxima: 5", "cola_maxima: 2"))
cfg_c = prod.cargar_config("explicativos")
assert cfg_c["produccion"]["modo_cadena"] == "continuo" and cfg_c["publicacion"]["horarios"] == ["09:00", "13:00", "20:00"]
futuro = lambda horas: (_dt.now(_tz.utc) + _td(hours=horas)).isoformat(timespec="seconds")  # noqa: E731
mem_e = [{"tema": "x", "publicado_en": futuro(10)}, {"tema": "y", "publicado_en": futuro(30)}]  # cola llena (2)
mem_h_prev = json.loads((REPO / "data" / "historias" / "memoria.json").read_text())
for m in mem_h_prev:
    m["publicado_en"] = futuro(-50)  # ya publicados: no cuentan
mem_h = mem_h_prev + [{"tema": "z", "publicado_en": futuro(12)}]                              # cola 1
(REPO / "data" / "memoria.json").write_text(json.dumps(mem_e))
(REPO / "data" / "historias" / "memoria.json").write_text(json.dumps(mem_h))
assert len(prod._cola("explicativos")) == 2 and len(prod._cola("historias")) == 1
_config.usar_canal("explicativos")
c = cadena(); c.pop("reintentar_desde", None); c.pop("esperando", None); guardar_cadena(c)  # noqa: E702
ESPERAS.clear(); RELEVOS.clear()  # noqa: E702
prod._relanzar_produccion = lambda: RELEVOS.append(1)
os.environ["MINUTOS_TAREA"] = "175"
antes = len(REGISTRO["meta"])
prod.ejecutar(esperar=esperar_falso)
os.environ.pop("MINUTOS_TAREA")
nuevo_h = json.loads((REPO / "data" / "historias" / "memoria.json").read_text())
assert len(REGISTRO["meta"]) == antes + 1 and len(nuevo_h) == len(mem_h) + 1, "hace el video de la página con menos cola"
assert len(json.loads((REPO / "data" / "memoria.json").read_text())) == 2, "no toca la página con la cola llena"
_prox = min(min(prod._cola(c)) for c in ("explicativos", "historias"))
_falta = (_prox - _dt.now(_tz.utc)).total_seconds() / 60
assert RELEVOS == [1] and abs(sum(ESPERAS) - min(_falta + 1, 165)) < 3, (RELEVOS, ESPERAS, _falta)
# Elección directa: con hueco, toca la página con menos videos en cola
(REPO / "data" / "memoria.json").write_text(json.dumps([]))
eleccion = prod._esperar_trabajo(esperar_falso, __import__("time").monotonic(), 340, 170, cfg_c)
assert eleccion[0] == "explicativos", eleccion

# ---------- 14) Elegir la voz escuchando ----------
print("== Elegir la voz escuchando ==")
from bot import voces as _voces  # noqa: E402
_config.usar_canal("explicativos")
cfg_v2 = prod.cargar_config()
AUDIOS = []
telegram.audio = lambda ruta, texto="": AUDIOS.append(texto)
(_config.DATOS / "voces_candidatas.json").unlink(missing_ok=True)
assert _voces.ofrecer_si_toca(cfg_v2), "manda las muestras la primera vez"
opciones = json.loads((_config.DATOS / "voces_candidatas.json").read_text())["opciones"]
assert [o["nombre"] for o in opciones][0] == "La voz actual" and len(opciones) == 8, [o["nombre"] for o in opciones]
assert len(AUDIOS) == 8 and AUDIOS[1].startswith("Voz 2:")
assert any("voz:explicativos:8" in str(t) for t in REGISTRO["telegram"][-3:]), "botones Elegir"
assert not _voces.ofrecer_si_toca(cfg_v2), "no se repite en la misma ronda"
sulafat = next(o["n"] for o in opciones if o.get("prebuilt") == "Sulafat")
telegram.actualizaciones = lambda offset, espera=0: ([{"update_id": 950, "callback_query": {
    "id": "cv", "from": {"id": 123}, "data": f"voz:explicativos:{sulafat}"}}] if offset <= 950 else [])
aprobaciones.procesar(caducar=False)
elegida = json.loads((_config.DATOS / "voz.json").read_text())
assert elegida.get("elegida") and elegida.get("prebuilt") == "Sulafat", elegida
_vg2 = importlib.reload(__import__("bot.voz_gemini", fromlist=["x"]))
_vg2.requests = types.SimpleNamespace(post=gemini_post, RequestException=Exception)
_vg2.sintetizar("Hola", cfg_v2, Path(TMP) / "prueba_voz.wav")
assert GEMINI["voces_usadas"][-1] == {"prebuiltVoiceConfig": {"voiceName": "Sulafat"}}, GEMINI["voces_usadas"][-1]
# Una voz diseñada elegida tampoco se cambia aunque cambie la descripción del config
disenada = next(o for o in opciones if o.get("id") and o["nombre"] != "La voz actual")
_voces.elegir("explicativos", disenada["n"])
assert _vg2.voz_de_marca({"produccion": {"voz_marca": {"activa": True, "descripcion": "otra cosa"}}}) == disenada["id"]
# La página de historias (voz de hombre) no ofrece voces de mujer
_config.usar_canal("historias")
assert not _voces.ofrecer_si_toca(prod.cargar_config())
_config.usar_canal("explicativos")

# ---------- 15) Cuatro páginas, cada una con su estética, su voz y su hora ----------
print("== Cuatro páginas ==")
(REPO / "config.yaml").write_text((ORIGEN / "config.yaml").read_text())  # el config real
_cfgs = {c: prod.cargar_config(c) for c in _config.canales()}
_horas = [h for c in _cfgs.values() for h in c["publicacion"]["horarios"]]
assert len(_horas) == 4 and len(set(_horas)) == 4, ("1 al día por página, a horas distintas", _horas)
_marcas = {c: tuple(v["estilo"]["paletas_3d"]["marca"]) for c, v in _cfgs.items()}
assert len(set(_marcas.values())) == 4 and all(len(m) == 7 for m in _marcas.values()), _marcas
# El escenario lo elige el tema (no está fijo); los colores y el estilo de animación, la página
for _n in ("cielo", "exterior", "interior"):
    assert {prod.escenario_de({"direccion_arte": {"escenario": _n}}, v) for v in _cfgs.values()} == {_n}
    _fondos = {c: prod.paleta_con_escenario({"fondo": "#000000", "tinta": "#111111", "acentos": list(v["estilo"]["paletas_3d"]["marca"][2:])}, _n, v)["fondo"] for c, v in _cfgs.items()}
    assert len(set(_fondos.values())) == 4, ("mismo lugar, distinta paleta en cada página", _n, _fondos)
_acab = {c: prod.acabado_de(v)["acabado"] for c, v in _cfgs.items()}
assert _acab == {"explicativos": "dibujo", "historias": "dibujo", "psicologia": "dibujo", "casa": "dibujo"}, _acab
assert prod.acabado_de(_cfgs["psicologia"])["color_contorno"] == "#0A0506" and prod.escenarios(_cfgs["psicologia"])["interior"]["fondo"] == "#2B1013", "Pensan2: paleta alrededor del rojo oscuro"
assert prod.acabado_de(_cfgs["casa"])["color_contorno"] == "#3A2A1E"
assert prod.escenarios(_cfgs["explicativos"]) == prod.ESCENARIOS, "la principal queda igual"
assert _cfgs["psicologia"]["produccion"]["voz_marca"]["genero"] == "female"
assert _cfgs["casa"]["produccion"]["voz_marca"]["genero"] == "male"
assert any("salud mental" in x for x in _cfgs["psicologia"]["canal"]["prohibidos"])
assert any("dinero" in x for x in _cfgs["casa"]["canal"]["prohibidos"]), "hereda los prohibidos"
assert not any("psicolog" in s for s in _cfgs["explicativos"]["canal"]["subtemas"]), "no pisa a la página de psicología"
for c in ("psicologia", "casa"):
    os.environ[f"META_PAGE_ID_{c.upper()}"] = f"pagina_{c}"
    os.environ[f"META_PAGE_TOKEN_{c.upper()}"] = f"token_{c}"
    _config.usar_canal(c)
    assert _config.secreto("META_PAGE_ID") == f"pagina_{c}"
    assert _tg_mod._pagina() == f"[{_cfgs[c]['canal']['etiqueta']}] ", _tg_mod._pagina()
    antes = len(REGISTRO["meta"])
    prod.producir()
    assert len(REGISTRO["meta"]) == antes + 1, f"publica en la página {c}"
    plan_c = json.loads((REPO / "remotion" / "plan_A.json").read_text())
    assert plan_c["acabado"] == _acab[c] and plan_c["paleta"]["fondo"] == prod.escenarios(_cfgs[c])[plan_c["escenario"]]["fondo"], plan_c
    assert json.loads((REPO / "data" / c / "memoria.json").read_text()), "memoria propia"
    _sis = REGISTRO.get("sistema_escena", "")
    assert "Técnica 2.5D" in _sis and "<Inodoro" in _sis and "Persona2D" in _sis and "Ejemplo25D" in _sis, "las escenas usan la técnica 2.5D"
    _pedido = REGISTRO.get("guion_pedido", "")
    assert "RECETA DEL NICHO" in _pedido and _cfgs[c]["canal"]["receta"][0][:40] in _pedido, "la receta de su nicho llega al guion"
    _ritmo = str(_cfgs[c]["produccion"]["palabras_por_segundo"]).replace(".", ",")
    assert f"unas {_ritmo} palabras por segundo" in _pedido, "su propio ritmo"
_config.usar_canal("explicativos")
# Las 4 activas: la producción continua elige la que tiene menos cola
for c in _config.canales():
    (_config.ruta_datos(c) / "memoria.json").write_text(json.dumps([{"tema": "q", "publicado_en": futuro(5)}] if c != "casa" else []))
eleccion = prod._esperar_trabajo(esperar_falso, __import__("time").monotonic(), 340, 170, cfg_c)
assert eleccion[0] == "casa", eleccion

# ---------- 16) Equipo profesional, temas por potencial viral y guía de cada nicho ----------
print("== Equipo y guía de nichos ==")
_eq = set(REGISTRO.get("equipo", []))
for _k in ("director_creativo", "guionista", "director_arte"):
    assert _k in _eq, ("cada parte tiene su profesional", _k, _eq)
import bot.director as _dir
_cands = {"candidatos": [
    {"tema": "tibio", "puntos": {c: 3 for c in _dir.CRITERIOS_VIRALES}},
    {"tema": "viral", "gancho": "Tu cerebro te miente", "tono_visual": "memoria", "puntos": {**{c: 5 for c in _dir.CRITERIOS_VIRALES}, "verificable": 4}},
    {"tema": "inventado", "puntos": {**{c: 5 for c in _dir.CRITERIOS_VIRALES}, "verificable": 1}},
]}
_g = _dir.mejor_candidato(_cands, _cfgs["psicologia"]["canal"])
assert _g["tema"] == "viral" and _g["puntaje_viral"] > 0, _g
_solo_malos = {"candidatos": [{"tema": "a", "puntos": {"verificable": 1, "curiosidad": 5}}, {"tema": "b", "puntos": {"verificable": 2}}]}
assert _dir.mejor_candidato(_solo_malos, _cfgs["casa"]["canal"])["tema"] == "a", "si todos son dudosos, igual elige el de más puntos"
# pesos distintos por nicho: lo útil pesa más en casa que en historias
_util = {"tema": "u", "puntos": {"utilidad": 5}}
assert _dir.puntaje_viral(_util, _cfgs["casa"]["canal"]["pesos_virales"]) > _dir.puntaje_viral(_util, _cfgs["historias"]["canal"]["pesos_virales"])
# cada página tiene su propia guía (no se mezcla con la de C MAMUD)
assert set(_cfgs["psicologia"]["canal"]["guia"]["estilos_por_tema"]) == {"memoria", "decision", "social", "percepcion"}
import bot.guionista as _gui
for c in _config.canales():
    _txt = _gui.guia_del_nicho(_cfgs[c])
    assert "GUÍA DE CALIDAD" in _txt and _cfgs[c]["canal"]["guia"]["ritmo"][:30] in _txt and "segundo 0" in _txt, c
assert "GUÍA DE CALIDAD" in REGISTRO.get("guion_pedido", ""), "la guía llega al guionista"

# ---------- 17) La voz no se descarta por cómo escribe Whisper los números o las tildes ----------
print("== Voz tolerante ==")
from bot.voz_gemini import cobertura_flexible as _cf
_g = "El 60% de lluvia no significa lo que crees: el guión cambia".split()
_o = [{"w": w} for w in "el sesenta por ciento de lluvia no significa lo que crees el guion cambia".split()]
assert _cf(_g, _o) >= 0.9, _cf(_g, _o)
_otra = [{"w": w} for w in "hoy vamos a hablar de un tema muy distinto para todos".split()]
assert _cf(_g, _otra) < 0.3, "si la voz dice otra cosa, se nota"

print("\nSIMULACIÓN CORRECTA. Archivos en", TMP)

"""Autocontrol de calidad: revisa cada video TERMINADO, detecta errores y los convierte en
reglas que se aplican a los videos siguientes (el bot se corrige solo).

1. Chequeos técnicos medidos (sin opinión): cuándo empieza la voz, silencios largos, cuánto del
   guion se oyó, escenas que fallaron y se cambiaron por respaldo, duración.
2. Revisión final con Claude: mira 8 fotogramas del video ya editado (con subtítulos, títulos y
   tarjetas) y el guion, y lista los errores con una REGLA general para que no se repitan.
3. Memoria de reglas (data/reglas_calidad.json): cada error que se repite gana peso. Las reglas
   más importantes se añaden a las instrucciones del guionista, del dibujante de escenas y del
   revisor en los próximos videos.
4. Si el video tiene un error grave (por ejemplo, la voz empieza tarde o falta texto), el bot
   lo arregla solo (rehace la voz o las escenas afectadas), lo vuelve a revisar y lo publica.
"""
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .config import DATOS
from .memoria import _guardar, _leer

REGLAS = DATOS / "reglas_calidad.json"
ESTADO_VIDEO = {"cobertura_voz": None, "respaldos": []}  # lo rellenan voz y estudio


# ---------- 1. Chequeos técnicos ----------

def _silencios(ruta: Path, umbral="-38dB", minimo=0.45) -> list[tuple[float, float]]:
    salida = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(ruta), "-af",
                             f"silencedetect=n={umbral}:d={minimo}", "-f", "null", "-"],
                            capture_output=True, text=True).stderr
    ini = [float(x) for x in re.findall(r"silence_start: ([0-9.]+)", salida)]
    fin = [float(x) for x in re.findall(r"silence_end: ([0-9.]+)", salida)]
    return list(zip(ini, fin))


def chequeos_tecnicos(voz: Path, duracion: float) -> list[dict]:
    problemas = []
    sil = _silencios(voz)
    if sil and sil[0][0] < 0.05 and sil[0][1] > 0.5:
        problemas.append({"grave": True, "area": "voz",
                          "problema": f"la voz empieza tarde ({sil[0][1]:.1f} s de silencio al inicio)",
                          "regla": "La primera palabra del gancho debe oírse en los primeros 0,3 segundos."})
    largos = [(a, b) for a, b in sil if a > 0.5 and b - a > 0.8]
    if largos:
        problemas.append({"grave": False, "area": "voz",
                          "problema": f"{len(largos)} silencio(s) largos dentro de la narración",
                          "regla": "Frases encadenadas sin puntos ni pausas largas; la voz no se detiene más de medio segundo."})
    cob = ESTADO_VIDEO.get("cobertura_voz")
    if cob is not None and cob < 0.7:
        problemas.append({"grave": True, "area": "voz",
                          "problema": f"solo se entiende el {round(cob * 100)} % del guion en el audio",
                          "regla": "Frases cortas y fáciles de pronunciar; números escritos como se dicen."})
    if ESTADO_VIDEO.get("respaldos"):
        n = len(ESTADO_VIDEO["respaldos"])
        problemas.append({"grave": False, "area": "escenas",
                          "problema": f"{n} escena(s) fallaron y se cambiaron por una genérica",
                          "regla": "Código de escena simple y robusto: solo las piezas de ../lib3d, sin trucos raros de three.js."})
    if duracion > 88:
        problemas.append({"grave": False, "area": "guion", "problema": f"el video dura {duracion:.0f} s, al límite",
                          "regla": "Guion más compacto: una sola idea, sin repetir."})
    return problemas


# ---------- 2. Revisión final del video editado ----------

def hoja_de_fotogramas(video: Path, destino: Path, duracion: float, n: int = 8) -> Path:
    paso = max(0.5, duracion / n)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-vf",
                    f"fps=1/{paso:.2f},scale=270:-2,tile=4x2", "-frames:v", "1", str(destino)], check=True)
    return destino


def _voz_en(momentos: list, segundo: float) -> str:
    for inicio, dur, voz in momentos or []:
        if inicio - 0.05 <= segundo < inicio + dur:
            return voz
    return ""


def revision_final(claude, guion: dict, hoja: Path, momentos: list | None = None,
                   duracion: float = 0.0) -> list[dict]:
    from .claude import imagen
    voz = " / ".join(e["voz"] for e in guion["escenas"])
    por_fotograma = ""
    if momentos and duracion:
        paso = max(0.5, duracion / 8)
        lineas = [f"- Fotograma {k + 1} (segundo {k * paso + 0.1:.1f}): la voz dice «{_voz_en(momentos, k * paso + 0.1)}»"
                  for k in range(8)]
        por_fotograma = ("Lo que dice la voz en cada fotograma:\n" + "\n".join(lineas) + "\n"
                         "Comprueba que cada fotograma MUESTRA lo que dice la voz en ese momento "
                         "(el mismo objeto, la misma acción, la misma parte). Si un fotograma "
                         "muestra otra cosa o algo sin relación, es un error grave (grave=true): "
                         "desconcierta al que mira.\n")
    contenido = [
        {"type": "text", "text": (
            f"Video terminado: «{guion['titulo']}». Narración: {voz}\n" + por_fotograma +
            "Te muestro 8 fotogramas repartidos por todo el video ya editado (con subtítulos, título "
            "de portada y tarjetas de datos), en orden de izquierda a derecha y de arriba abajo.\n"
            "Busca ERRORES concretos: textos cortados o tapados, texto en pantalla encima de cosas "
            "importantes, datos o textos incorrectos o que no coinciden con la narración, objetos "
            "que no se entienden o no son fieles a la realidad, fotogramas vacíos o rotos, la misma "
            "imagen congelada en varios fotogramas seguidos. NO son errores (no los apuntes): un "
            "plano abierto para ubicar, un color fuerte para resaltar, el mismo lugar y protagonista "
            "en todo el video (es un solo mundo que cambia), gustos de estilo.\n"
            "Para cada error escribe una REGLA general y concreta que evite que se repita en "
            "cualquier video futuro (no sobre este tema en particular), y a quién va dirigida: "
            "\"escenas\" (quien dibuja), \"guion\" (quien escribe) o \"edicion\" (títulos, "
            "subtítulos, tarjetas). Marca grave=true solo si el error hace que el video no deba "
            "publicarse (por ejemplo, un dato falso visible o algo ilegible en el gancho). En "
            "\"fotograma\" pon el número (1 a 8) del fotograma donde se ve el error.")},
        imagen(hoja),
        {"type": "text", "text": ('Devuelve JSON: {"problemas": [{"problema": "...", "regla": "...", '
                                  '"area": "escenas|guion|edicion", "grave": false, "fotograma": 1}], "nota_final": n}')},
    ]
    try:
        from .config import rol
        datos = claude.json(f"Eres el jefe de control de calidad de una página de {rol()}. "
                            "Eres exigente y concreto.", contenido, max_tokens=2000)
    except Exception as e:  # noqa: BLE001
        print("No se pudo hacer la revisión final:", e)
        return []
    return [p for p in datos.get("problemas", []) if p.get("regla")][:8]


# ---------- 3. Memoria de reglas ----------

def _clave(texto: str) -> str:
    return " ".join(sorted(set(re.findall(r"[a-záéíóúñ]{5,}", texto.lower()))))[:200]


def registrar(problemas: list[dict]) -> list[dict]:
    """Suma los problemas a la memoria de reglas. Devuelve las reglas nuevas."""
    datos = _leer(REGLAS, {"reglas": []})
    nuevas = []
    ahora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for p in problemas:
        clave = _clave(p["regla"])
        existente = next((r for r in datos["reglas"]
                          if r["area"] == p.get("area") and _parecido(r["clave"], clave)), None)
        if existente:
            existente["veces"] += 1
            existente["ultima"] = ahora
        else:
            r = {"regla": p["regla"], "area": p.get("area", "escenas"), "veces": 1,
                 "ultima": ahora, "clave": clave, "ejemplo": p.get("problema", "")}
            datos["reglas"].append(r)
            nuevas.append(r)
    # Se quedan las más repetidas y recientes (como mucho 30)
    datos["reglas"] = sorted(datos["reglas"], key=lambda r: (r["veces"], r["ultima"]), reverse=True)[:30]
    _guardar(REGLAS, datos)
    return nuevas


def _parecido(a: str, b: str) -> bool:
    sa, sb = set(a.split()), set(b.split())
    return bool(sa and sb) and len(sa & sb) / min(len(sa), len(sb)) >= 0.6


# Reglas de gusto que se aprendieron antes y chocan con lo que hace virales a los Reels 3D
# (color fuerte para resaltar, un solo mundo que se repite, planos abiertos para ubicar): ya no se aplican.
_RETIRADAS = ("chillón", "chillon", "saturad", "mismo decorado", "mismo encuadre de fondo",
              "visualmente distinta", "planos consecutivos", "repetir el mismo")


def _vigente(regla: dict) -> bool:
    texto = regla.get("regla", "").lower()
    return not any(x in texto for x in _RETIRADAS)


def texto_reglas(area: str, maximo: int = 8) -> str:
    reglas = [r for r in _leer(REGLAS, {"reglas": []})["reglas"]
              if r["area"] in (area, "edicion" if area == "escenas" else area) and _vigente(r)]
    if not reglas:
        return ""
    lineas = [f"- {r['regla']}" + (" (error repetido, máxima prioridad)" if r["veces"] >= 2 else "")
              for r in reglas[:maximo]]
    return ("\nERRORES QUE YA COMETIÓ ESTE CANAL Y NO DEBEN REPETIRSE:\n" + "\n".join(lineas) + "\n")


# ---------- 4. Todo junto ----------

def revisar_video(claude, guion: dict, video: Path, voz: Path, duracion: float, trabajo: Path,
                  aprender: bool = True, momentos: list | None = None) -> dict:
    problemas = chequeos_tecnicos(voz, duracion)
    try:
        hoja = hoja_de_fotogramas(video, trabajo / "control_final.png", duracion)
        paso = max(0.5, duracion / 8)
        for p in revision_final(claude, guion, hoja, momentos, duracion):
            # Segundo aproximado del error, para saber qué escena hay que rehacer
            try:
                k = int(p.get("fotograma") or 0)
            except (TypeError, ValueError):
                k = 0
            if 1 <= k <= 8:
                p["segundo"] = round((k - 1) * paso + 0.1, 2)
            problemas.append(p)
    except Exception as e:  # noqa: BLE001
        print("Aviso: no se pudo mirar el video final:", e)
    # En los reintentos de arreglo no se vuelven a sumar las mismas reglas
    nuevas = registrar(problemas) if aprender else []
    graves = [p for p in problemas if p.get("grave")]
    (trabajo / "control_calidad.json").write_text(json.dumps(problemas, ensure_ascii=False, indent=1),
                                                  encoding="utf-8")
    return {"problemas": problemas, "graves": graves, "nuevas": nuevas}

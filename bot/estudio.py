"""El estudio: Claude dibuja cada escena como código de Remotion."""
import json
from pathlib import Path

from .claude import Claude, extraer_codigo
from .config import ESCENAS, REMOTION, prompt
from . import render

RESPALDO_3D = """import React from 'react';
import {EscenaProps, EscenaRespaldo3D} from '../lib3d';

export const {nombre}: React.FC<EscenaProps> = (props) => <EscenaRespaldo3D {...props} />;
"""

ENCUADRES = ["picado", "frente", "picado_izq", "cerca"]


def encuadre(indice: int) -> str:
    """Encuadre de cámara de cada escena (va rotando para dar dinamismo)."""
    return ENCUADRES[indice % len(ENCUADRES)]


MOTOR = {"actual": "2d"}  # lo fija producir al empezar ("3d" o "2d")

RESPALDO = """import React from 'react';
import {EscenaProps, EscenaRespaldo} from '../lib';

export const {nombre}: React.FC<EscenaProps> = (props) => <EscenaRespaldo {...props} />;
"""


def _system(cfg: dict, nombre: str) -> str:
    tres = MOTOR["actual"] == "3d"
    lib = (REMOTION / "src" / ("lib3d.tsx" if tres else "lib.tsx")).read_text(encoding="utf-8")
    ejemplo = (ESCENAS / ("Ejemplo3D.tsx" if tres else "Ejemplo.tsx")).read_text(encoding="utf-8")
    estilo = cfg["estilo"]["descripcion_3d" if tres else "descripcion"].strip()
    return (prompt("escena3d.md" if tres else "escena.md")
            .replace("{estilo}", estilo)
            .replace("{lib}", lib)
            .replace("{ejemplo}", ejemplo)
            .replace("{nombre}", nombre))


GANCHO = """
ESTA ES LA ESCENA DEL GANCHO: decide si la gente deja de hacer scroll. Desde el fotograma 0
(que es también la miniatura) debe verse algo llamativo, grande y en el centro, ya en plena
acción o a punto de pasar (algo que cae, se rompe, se tacha, sale volando, o un objeto
gigante con ojos sorprendidos). Nada de presentar el lugar con calma: el golpe principal
ocurre en el primer segundo y hay al menos 4 golpes visuales."""


FINAL = """
ESTA ES LA ÚLTIMA ESCENA (el remate): la Mascota del canal aparece feliz o guiñando, señalando
el resultado, y la imagen final debe invitar a ver el video otra vez o comentar."""


def _pedido(escena: dict, tiempos: dict, guion: dict, indice: int, estilo: dict) -> str:
    palabras = " ".join(f"{p['w']}@{p['t']:.2f}s" for p in tiempos["palabras"])
    resumen = " / ".join(e["voz"] for e in guion["escenas"])
    arte = guion.get("direccion_arte") or {}
    direccion = "\n".join(f"- {k}: {v}" for k, v in arte.items()) or "- libre, coherente con el guion"
    return f"""Video: «{guion['titulo']}»
Dirección de arte común a TODAS las escenas (respétala al pie de la letra para que el
protagonista y el mundo se vean iguales en cada escena):
{direccion}

Guion completo (para contexto): {resumen}

Escena número {indice + 1} de {len(guion['escenas'])}. Dura {tiempos['duracion']:.2f} segundos.{GANCHO if indice == 0 else ''}{FINAL if indice == len(guion['escenas']) - 1 and MOTOR['actual'] == '3d' else ''}
Voz de esta escena: «{escena['voz']}»
Palabras con su tiempo dentro de la escena: {palabras}
Palabra clave (momento visual principal): {escena.get('palabra_clave', '')}
Rótulo: «{escena.get('rotulo', '')}»{(chr(10) + "Encuadre de cámara de esta escena: " + encuadre(indice)) if MOTOR['actual'] == '3d' else ''}{(chr(10) + "Tarjeta de datos que el video pone encima (no la dibujes tú): " + str(escena.get('grafico'))) if escena.get('grafico') else ''}
Lo que debe mostrar: {escena['visual']}
Paleta sorteada: fondo {estilo['colores']['fondo']}, tinta {estilo['colores']['tinta']}, acentos {', '.join(estilo['colores']['acentos'])}{' (acentos: objeto principal, secundario, resalte, extra, suelo)' if MOTOR['actual'] == '3d' else ''}

{"Todas las escenas están en el mismo mundo: el cielo, el suelo, el sol y las sombras ya los pone el video. Tú construyes solo lo de tu escenario." if MOTOR["actual"] == "3d" else "Las escenas vecinas comparten el mismo tablero y la cámara viaja entre ellas: mantén un fondo coherente con la paleta para que el paso sea fluido."}"""


def dibujar(claude: Claude, cfg: dict, nombre: str, escena: dict, tiempos: dict, guion: dict,
            indice: int, estilo: dict, comentarios: str = "", codigo_previo: str = "", foto=None) -> str:
    pedido = _pedido(escena, tiempos, guion, indice, estilo)
    if comentarios:
        pedido += (f"\n\nEsta es una versión anterior de la escena:\n```tsx\n{codigo_previo}\n```\n"
                   f"Problemas detectados que debes corregir: {comentarios}\n"
                   "Rehaz la escena corrigiéndolos y subiendo la calidad de la ilustración.")
    if foto:
        from .claude import imagen
        pedido = [{"type": "text", "text": pedido + "\n\nAsí se veía la versión anterior "
                   "(izquierda: inicio de la escena; derecha: más adelante):"}, imagen(foto)]
    texto = claude.texto(_system(cfg, nombre), pedido, modelo=claude.modelo_escenas, max_tokens=12000)
    codigo = extraer_codigo(texto)
    (ESCENAS / f"{nombre}.tsx").write_text(codigo, encoding="utf-8")
    return codigo


def reparar(claude: Claude, cfg: dict, nombre: str, error: str) -> None:
    ruta = ESCENAS / f"{nombre}.tsx"
    codigo = ruta.read_text(encoding="utf-8")
    texto = claude.texto(
        _system(cfg, nombre),
        f"Este archivo falla al compilar o renderizar.\n```tsx\n{codigo}\n```\nError:\n{error[-3000:]}\n"
        "Corrige el error sin bajar la calidad de la ilustración. Devuelve el archivo completo.",
        modelo=claude.modelo_escenas, max_tokens=12000)
    ruta.write_text(extraer_codigo(texto), encoding="utf-8")


def usar_respaldo(nombre: str):
    plantilla = RESPALDO_3D if MOTOR["actual"] == "3d" else RESPALDO
    (ESCENAS / f"{nombre}.tsx").write_text(plantilla.replace("{nombre}", nombre), encoding="utf-8")


def escribir_indice(nombres: list[str]):
    lineas = ["// Generado por el bot. No editar a mano.",
              "import type React from 'react';",
              "import type {EscenaProps} from '../lib';",
              "import {Ejemplo} from './Ejemplo';",
              "import {Ejemplo3D} from './Ejemplo3D';"]
    lineas += [f"import {{{n}}} from './{n}';" for n in nombres]
    lineas.append("")
    lineas.append("export const ESCENAS: Record<string, React.FC<EscenaProps>> = {")
    lineas.append("  Ejemplo,")
    lineas.append("  Ejemplo3D,")
    lineas += [f"  {n}," for n in nombres]
    lineas.append("};")
    (ESCENAS / "index.ts").write_text("\n".join(lineas) + "\n", encoding="utf-8")


_REPAROS: dict = {}


def limpiar_escenas_viejas():
    _REPAROS.clear()
    for f in ESCENAS.glob("*.tsx"):
        if f.name not in ("Ejemplo.tsx", "Ejemplo3D.tsx"):
            f.unlink()


def compilar(claude: Claude, cfg: dict, nombres: list[str], intentos: int = 3) -> None:
    """Empaqueta el proyecto; si una escena rompe la compilación, la repara o la reemplaza."""
    for _ in range(intentos * len(nombres) + 1):
        ok, salida = render.empaquetar()
        if ok:
            return
        culpable = render.escena_con_error(salida, nombres)
        print("Error de compilación:", salida[-1500:])
        if not culpable:
            raise RuntimeError("Error de compilación fuera de las escenas:\n" + salida[-2000:])
        _REPAROS[culpable] = _REPAROS.get(culpable, 0) + 1
        if _REPAROS[culpable] <= intentos:
            reparar(claude, cfg, culpable, salida)
        else:
            print(f"La escena {culpable} no compila; uso la escena de respaldo.")
            usar_respaldo(culpable)
    raise RuntimeError("No se pudo compilar el proyecto.")

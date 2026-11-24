"""El estudio: Claude dibuja cada escena como código de Remotion."""
import json
from pathlib import Path

from .claude import Claude, extraer_codigo
from .config import ESCENAS, REMOTION, prompt
from . import render
from .equipo import profesional

RESPALDO_3D = """import React from 'react';
import {EscenaProps, EscenaRespaldo3D} from '../lib3d';

export const {nombre}: React.FC<EscenaProps> = (props) => <EscenaRespaldo3D {...props} />;
"""

ENCUADRES = ["picado", "frente", "picado_izq", "cerca"]


def encuadre(indice: int) -> str:
    """Encuadre de cámara de cada escena (va rotando para dar dinamismo)."""
    return ENCUADRES[indice % len(ENCUADRES)]


MOTOR = {"actual": "2d"}  # lo fija producir al empezar ("3d" o "2d")
# Mundo compartido (3D): un solo lugar y un solo protagonista que evoluciona en todas las escenas.
MUNDO = {"activo": False, "codigo": ""}


def con_mundo(nombres: list[str]) -> list[str]:
    """Archivos que se compilan: las escenas y, si está activo, el mundo compartido."""
    return nombres + (["Mundo"] if MUNDO["activo"] and "Mundo" not in nombres else [])



def _lib3d() -> str:
    """lib3d completa más la API de la técnica 2.5D (piezas 3D listas y recortes 2D)."""
    lib = (REMOTION / "src" / "lib3d.tsx").read_text(encoding="utf-8")
    l25 = (REMOTION / "src" / "lib25d.tsx").read_text(encoding="utf-8")
    api = l25[l25.find("<<API2.5D") + 9: l25.find("API2.5D>>")] if "<<API2.5D" in l25 else ""
    return lib + "\n\n// ===== ../lib25d: técnica 2.5D (importa de '../lib25d') =====" + api

BLOQUE_MUNDO = """
## Mundo compartido (OBLIGATORIO en este video)
Todas las escenas pasan en el MISMO lugar y con el MISMO protagonista, que va cambiando escena a
escena (como los Reels 3D más virales). Ese mundo ya está hecho en el archivo `./Mundo`:
```tsx
{codigo}
```
- Además de los imports permitidos, importa lo que necesites de `./Mundo`
  (`import {Mundo, Ala} from './Mundo';`).
- Tu escena dibuja la base con `<Mundo paso={PASO} frame={frame} fps={fps} paleta={paleta} />`
  (PASO es el número de tu escena, te lo doy en el pedido). NO vuelvas a construir el
  protagonista ni el lugar: ya los dibuja Mundo. No lo muevas ni lo cambies de escala.
- Lo NUEVO de tu escena (la pieza que se agrega, lo que se llena, lo que se abre) lo animas tú:
  quítalo de Mundo con `ocultar={['nombre']}` y dibuja la parte exportada (`<Ala paleta={paleta} />`)
  dentro de un `<group>` animado (caer, aparecer, mover) hasta quedar en su sitio.
- Al TERMINAR tu escena el mundo debe verse EXACTAMENTE como `<Mundo paso={PASO + 1} />`: así el
  paso a la escena siguiente es invisible y parece un solo plano.
- Cuando la voz nombra una parte, resáltala justo en ese momento: añádela a `resaltar` (o pasa
  `resaltado` a su componente) durante 1 a 1,5 segundos y vuelve a su color.
- Si la escena muestra qué pasa SIN una pieza o cuando algo falla, exagéralo con física de
  dibujo animado (se ladea y se cae, se desborda, se rompe, sale volando) y, si la siguiente
  escena lo necesita, termina con el mundo de nuevo en su estado correcto.
- Si alguna regla aprendida dice "no repetir decorado" o "cada escena distinta", en este video
  significa: cambia el ENCUADRE, el momento y lo que pasa, pero el mundo y el protagonista son
  siempre los mismos.
- Lo tuyo encima del mundo: flechas de fuerza o de flujo, líneas punteadas de trayectoria,
  etiquetas cortas, medidas, partículas (agua, aire, chispas, tornillos que llueven).
"""

RESPALDO = """import React from 'react';
import {EscenaProps, EscenaRespaldo} from '../lib';

export const {nombre}: React.FC<EscenaProps> = (props) => <EscenaRespaldo {...props} />;
"""


def _system(cfg: dict, nombre: str) -> str:
    tres = MOTOR["actual"] == "3d"
    lib = _lib3d() if tres else (REMOTION / "src" / "lib.tsx").read_text(encoding="utf-8")
    ejemplo = (ESCENAS / ("Ejemplo25D.tsx" if tres else "Ejemplo.tsx")).read_text(encoding="utf-8")
    estilo = cfg["estilo"]["descripcion_3d" if tres else "descripcion"].strip()
    from .autocontrol import texto_reglas
    extra = texto_reglas("escenas")
    guia = (cfg.get("estilo") or {}).get("guia_escenas", "").strip()
    if guia:
        extra = "\n## Guía de esta página\n" + guia + "\n" + extra
    if tres and MUNDO["activo"] and MUNDO["codigo"] and nombre != "Mundo":
        extra = BLOQUE_MUNDO.replace("{codigo}", MUNDO["codigo"]) + extra
    return profesional("director_arte") + (prompt("escena3d.md" if tres else "escena.md").replace("Responde SOLO con", extra + "\nResponde SOLO con")
            .replace("{estilo}", estilo)
            .replace("{lib}", lib)
            .replace("{ejemplo}", ejemplo)
            .replace("{nombre}", nombre))


GANCHO = """
ESTA ES LA ESCENA DEL GANCHO: decide si la gente deja de hacer scroll. Desde el fotograma 0
(que es también la miniatura) debe verse algo llamativo, grande y en el centro, ya en plena
acción o a punto de pasar (algo que cae, se rompe, se tacha, sale volando, o un objeto
gigante en pleno movimiento). Nada de presentar el lugar con calma: el golpe principal
ocurre en el primer segundo y hay al menos 4 golpes visuales."""


FINAL = """
ESTA ES LA ÚLTIMA ESCENA (el remate): muestra el resultado o la respuesta de forma clara y
satisfactoria, y que la imagen final conecte con la del inicio (el video se repite en bucle)."""


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

Escena número {indice + 1} de {len(guion['escenas'])}. Dura {tiempos['duracion']:.2f} segundos.{_paso_mundo(guion, indice)}{GANCHO if indice == 0 else ''}{FINAL if indice == len(guion['escenas']) - 1 and MOTOR['actual'] == '3d' else ''}
Voz de esta escena: «{escena['voz']}»
Palabras con su tiempo dentro de la escena: {palabras}
Palabra clave (momento visual principal): {escena.get('palabra_clave', '')}
Rótulo: «{escena.get('rotulo', '')}»{(chr(10) + "Encuadre de cámara de esta escena: " + encuadre(indice)) if MOTOR['actual'] == '3d' else ''}{(chr(10) + "Tarjeta de datos que el video pone encima (no la dibujes tú): " + str(escena.get('grafico'))) if escena.get('grafico') else ''}
Lo que debe mostrar: {escena['visual']}{_vecinas(guion, indice)}
Paleta sorteada: fondo {estilo['colores']['fondo']}, tinta {estilo['colores']['tinta']}, acentos {', '.join(estilo['colores']['acentos'])}{' (acentos: objeto principal, secundario, resalte, extra, suelo)' if MOTOR['actual'] == '3d' else ''}

{"Todas las escenas están en el mismo mundo: el cielo, el suelo, el sol y las sombras ya los pone el video. Tú construyes solo lo de tu escenario." if MOTOR["actual"] == "3d" else "Las escenas vecinas comparten el mismo tablero y la cámara viaja entre ellas: mantén un fondo coherente con la paleta para que el paso sea fluido."}"""


def _vecinas(guion: dict, indice: int) -> str:
    """Lo de antes y lo de después, para que la escena continúe la anterior y prepare la siguiente."""
    escenas = guion["escenas"]
    texto = ""
    if indice > 0:
        texto += f"\nJusto antes se vio: {escenas[indice - 1].get('visual', '')} (continúa desde ahí: mismos objetos, mismo lugar)."
    if indice < len(escenas) - 1:
        texto += f"\nJusto después se verá: {escenas[indice + 1].get('visual', '')} (deja todo listo para eso)."
    return texto


def _paso_mundo(guion: dict, indice: int) -> str:
    if not (MUNDO["activo"] and MUNDO["codigo"] and MOTOR["actual"] == "3d"):
        return ""
    escenas = guion["escenas"]
    antes = escenas[indice - 1].get("mundo", "") if indice > 0 else "el estado inicial del mundo"
    despues = escenas[indice].get("mundo", "")
    return (f"\nPASO = {indice} (usa <Mundo paso={{{indice}}} ... />)."
            f"\nAl empezar, el mundo está así: {antes}"
            f"\nAl terminar tu escena debe quedar así (igual que <Mundo paso={{{indice + 1}}} />): {despues}")


def _pedido_mundo(guion: dict, estilo: dict) -> str:
    arte = guion.get("direccion_arte") or {}
    direccion = "\n".join(f"- {k}: {v}" for k, v in arte.items()) or "- libre, coherente con el guion"
    pasos = "\n".join(
        f"- Escena {i} (paso {i}). Voz: «{e['voz']}». Se ve: {e.get('visual', '')}. "
        f"Al terminar, el mundo queda así: {e.get('mundo', '(igual que antes)')}"
        for i, e in enumerate(guion["escenas"]))
    c = estilo["colores"]
    return f"""Video: «{guion['titulo']}»
Dirección de arte:
{direccion}

Escenas (cada una cambia algo del mismo mundo):
{pasos}

Paleta: fondo {c['fondo']}, tinta {c['tinta']}, acentos {', '.join(c['acentos'])} (objeto principal, secundario, resalte, extra, suelo).
Construye el archivo Mundo.tsx con PARTES, un componente por parte, y Mundo."""


def dibujar_mundo(claude: Claude, cfg: dict, guion: dict, estilo: dict) -> str:
    """Dibuja el mundo compartido (Mundo.tsx) una sola vez por video."""
    lib = _lib3d()
    ejemplo = (ESCENAS / "Ejemplo25D.tsx").read_text(encoding="utf-8")
    guia = (cfg.get("estilo") or {}).get("guia_escenas", "").strip()
    estilo_txt = cfg["estilo"]["descripcion_3d"].strip() + (("\n\nGuía de esta página:\n" + guia) if guia else "")
    system = profesional("director_arte") + (prompt("mundo3d.md").replace("{estilo}", estilo_txt)
              .replace("{lib}", lib).replace("{ejemplo}", ejemplo))
    texto = claude.texto(system, _pedido_mundo(guion, estilo), modelo=claude.modelo_escenas, max_tokens=14000)
    codigo = extraer_codigo(texto)
    guardar_mundo(codigo)
    return codigo


def guardar_mundo(codigo: str) -> None:
    (ESCENAS / "Mundo.tsx").write_text(codigo, encoding="utf-8")
    MUNDO.update(activo=True, codigo=codigo)


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
    if nombre == "Mundo":
        lib = _lib3d()
        sistema = profesional("director_arte") + (prompt("mundo3d.md").replace("{estilo}", cfg["estilo"]["descripcion_3d"].strip())
                   .replace("{lib}", lib).replace("{ejemplo}", "(no hace falta)"))
    else:
        sistema = _system(cfg, nombre)
    texto = claude.texto(
        sistema,
        f"Este archivo falla al compilar o renderizar.\n```tsx\n{codigo}\n```\nError:\n{error[-3000:]}\n"
        "Corrige el error sin bajar la calidad de la ilustración. Devuelve el archivo completo.",
        modelo=claude.modelo_escenas, max_tokens=14000)
    nuevo = extraer_codigo(texto)
    ruta.write_text(nuevo, encoding="utf-8")
    if nombre == "Mundo":
        MUNDO["codigo"] = nuevo


RESPALDO_MUNDO = """import React from 'react';
import type {Paleta} from '../lib3d';

export type ParteProps = {paleta: Paleta; resaltado?: boolean; frame?: number};
export type MundoProps = {paso: number; frame: number; fps: number; paleta: Paleta; ocultar?: string[]; resaltar?: string[]};
export const PARTES = [] as const;
export const Mundo: React.FC<MundoProps> = () => <group />;
"""


def usar_respaldo(nombre: str):
    from .autocontrol import ESTADO_VIDEO
    ESTADO_VIDEO["respaldos"].append(nombre)
    if nombre == "Mundo":
        # Las escenas importan partes de Mundo: con el mundo vacío, las que fallen se repararán
        # (o pasarán a respaldo) en la compilación.
        (ESCENAS / "Mundo.tsx").write_text(RESPALDO_MUNDO, encoding="utf-8")
        MUNDO["codigo"] = RESPALDO_MUNDO
        return
    plantilla = RESPALDO_3D if MOTOR["actual"] == "3d" else RESPALDO
    (ESCENAS / f"{nombre}.tsx").write_text(plantilla.replace("{nombre}", nombre), encoding="utf-8")


def escribir_indice(nombres: list[str]):
    lineas = ["// Generado por el bot. No editar a mano.",
              "import type React from 'react';",
              "import type {EscenaProps} from '../lib';",
              "import {Ejemplo} from './Ejemplo';",
              "import {Ejemplo3D} from './Ejemplo3D';",
              "import {Ejemplo25D} from './Ejemplo25D';"]
    lineas += [f"import {{{n}}} from './{n}';" for n in nombres]
    lineas.append("")
    lineas.append("export const ESCENAS: Record<string, React.FC<EscenaProps>> = {")
    lineas.append("  Ejemplo,")
    lineas.append("  Ejemplo3D,")
    lineas.append("  Ejemplo25D,")
    lineas += [f"  {n}," for n in nombres]
    lineas.append("};")
    (ESCENAS / "index.ts").write_text("\n".join(lineas) + "\n", encoding="utf-8")


_REPAROS: dict = {}


def limpiar_escenas_viejas():
    _REPAROS.clear()
    MUNDO.update(activo=False, codigo="")
    for f in ESCENAS.glob("*.tsx"):
        if f.name not in ("Ejemplo.tsx", "Ejemplo3D.tsx", "Ejemplo25D.tsx"):
            f.unlink()


def compilar(claude: Claude, cfg: dict, nombres: list[str], intentos: int = 3) -> None:
    """Empaqueta el proyecto; si una escena rompe la compilación, la repara o la reemplaza."""
    nombres = con_mundo(nombres)
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

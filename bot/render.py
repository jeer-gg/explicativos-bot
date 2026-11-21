"""Llamadas a Remotion y ffmpeg."""
import json
import re
import subprocess
from pathlib import Path

from .config import REMOTION

# Opciones que fija producir según el motor: en 3D hace falta WebGL por software (sin GPU).
OPCIONES = {"gl": None, "concurrencia": "100%"}


def _gl():
    return [f"--gl={OPCIONES['gl']}"] if OPCIONES["gl"] else []


def _npx(*args, timeout=1800):
    proc = subprocess.run(["npx", "--no-install", "remotion", *args], cwd=REMOTION,
                          capture_output=True, text=True, timeout=timeout)
    return proc.returncode == 0, (proc.stdout + "\n" + proc.stderr)[-6000:]


def empaquetar() -> tuple[bool, str]:
    """Compila el proyecto. Devuelve (ok, salida)."""
    return _npx("bundle", "src/index.ts", "--out-dir=build", timeout=600)


def guardar_plan(plan: dict, nombre: str) -> Path:
    ruta = REMOTION / f"plan_{nombre}.json"
    ruta.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    return ruta


def foto(plan_ruta: Path, fotograma: int, destino: Path) -> tuple[bool, str]:
    destino.parent.mkdir(parents=True, exist_ok=True)
    return _npx("still", "build", "Video", str(destino.resolve()),
                f"--frame={fotograma}", f"--props={plan_ruta.resolve()}", *_gl(), timeout=600)


def renderizar(plan_ruta: Path, destino: Path) -> tuple[bool, str]:
    destino.parent.mkdir(parents=True, exist_ok=True)
    return _npx("render", "build", "Video", str(destino.resolve()),
                f"--props={plan_ruta.resolve()}", "--codec=h264", "--crf=18",
                f"--concurrency={OPCIONES['concurrencia']}", *_gl(), timeout=5400)


def preparar_para_facebook(origen: Path, destino: Path, musica: Path | None = None, volumen_musica: float = 0.16):
    """Codificación final según las especificaciones de Reels de Meta:
    H.264, 30 fps fijos, GOP cerrado de 2 s, yuv420p, AAC estéreo 48 kHz.

    Audio: si hay música, va de fondo y baja sola cuando habla la voz (ducking). Al final se
    iguala el volumen a -14 LUFS, el nivel habitual de las redes, para que suene como los videos
    profesionales: ni bajito ni saturado.
    """
    iguala = "loudnorm=I=-14:TP=-1.5:LRA=9"
    # Etalonaje de marca: un poco menos de saturación y un grano muy fino (textura de cine).
    imagen = ["-vf", "eq=saturation=0.92:contrast=0.98,noise=alls=3:allf=t"]
    if musica and musica.exists():
        entradas = ["-i", str(origen), "-stream_loop", "-1", "-i", str(musica)]
        filtro = ("[0:a]asplit=2[voz][llave];"
                  f"[1:a]volume={volumen_musica},afade=t=in:d=0.8[mus];"
                  "[mus][llave]sidechaincompress=threshold=0.02:ratio=10:attack=15:release=350[fondo];"
                  f"[voz][fondo]amix=inputs=2:duration=first:normalize=0,{iguala}[a]")
        filtro = "[0:v]eq=saturation=0.92:contrast=0.98,noise=alls=3:allf=t[v];" + filtro
        mapa = ["-filter_complex", filtro, "-map", "[v]", "-map", "[a]", "-shortest"]
    else:
        entradas = ["-i", str(origen)]
        mapa = [*imagen, "-af", iguala]
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error", *entradas, *mapa,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
        "-r", "30", "-g", "60", "-keyint_min", "60", "-sc_threshold", "0", "-flags", "+cgop",
        "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart", str(destino),
    ], check=True)


def elegir_musica(carpeta: Path, turno: int) -> Path | None:
    """Rota entre las pistas que haya en la carpeta de música (mp3, m4a o wav)."""
    pistas = sorted(p for p in carpeta.glob("*") if p.suffix.lower() in (".mp3", ".m4a", ".wav"))
    return pistas[turno % len(pistas)] if pistas else None


def escena_con_error(salida: str, nombres: list[str]) -> str | None:
    """Intenta averiguar qué escena causó un error de compilación o render."""
    for m in re.finditer(r"escenas/(\w+)\.tsx", salida):
        if m.group(1) in nombres:
            return m.group(1)
    for nombre in nombres:
        if re.search(rf"\b{nombre}\b", salida):
            return nombre
    return None


def imagen_vacia(ruta: Path) -> bool:
    """True si la imagen no tiene dibujo (solo un color o un degradado de cielo: el 3D no se dibujó)."""
    datos = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(ruta), "-vf", "scale=48:48,format=gray",
                            "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    if len(datos) < 48 * 48:
        return True
    saltos = [abs(datos[f * 48 + c + 1] - datos[f * 48 + c]) for f in range(48) for c in range(47)]
    return sum(saltos) / len(saltos) < 1.5

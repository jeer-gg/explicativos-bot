"""Biblioteca de efectos de sonido sintetizados con ffmpeg (originales, sin derechos de autor).

Hay varias versiones de cada efecto para que no suenen repetidos. Todos son cortos, con
graves recortados y a volumen moderado para no tapar la voz.
"""
import subprocess

from .config import PUBLICO

R = 48000

# nombre: (entradas lavfi, filtro final)  — el filtro recibe [0] (y [1] si hay dos entradas)
RECETAS = {
    # Barridos de transición (aire que pasa), de distinta duración y color
    "whoosh1": (["anoisesrc=d=0.5:c=pink:a=0.8"], "highpass=f=500,lowpass=f=5000,afade=t=in:d=0.2,afade=t=out:st=0.22:d=0.28"),
    "whoosh2": (["anoisesrc=d=0.42:c=white:a=0.5"], "highpass=f=900,lowpass=f=7000,afade=t=in:d=0.12,afade=t=out:st=0.15:d=0.27"),
    "whoosh3": (["anoisesrc=d=0.6:c=pink:a=0.8", "aevalsrc=0.25*sin(2*PI*(300*t+900*t*t)):d=0.6"],
                "[0][1]amix=inputs=2:normalize=0,highpass=f=400,lowpass=f=4500,afade=t=in:d=0.3,afade=t=out:st=0.3:d=0.3"),
    "whoosh4": (["anoisesrc=d=0.38:c=brown:a=0.9"], "highpass=f=300,lowpass=f=3500,afade=t=in:d=0.06,afade=t=out:st=0.08:d=0.3"),
    # Golpecitos para el momento clave (pop, madera, clic)
    "pop1": (["aevalsrc=sin(2*PI*(900-1500*t)*t)*exp(-28*t):d=0.18"], "highpass=f=250"),
    "pop2": (["aevalsrc=sin(2*PI*(650-900*t)*t)*exp(-24*t):d=0.2"], "highpass=f=200"),
    "pop3": (["aevalsrc=sin(2*PI*(1200-2200*t)*t)*exp(-34*t):d=0.15"], "highpass=f=300"),
    "toc1": (["aevalsrc=(0.7*sin(2*PI*320*t)+0.4*sin(2*PI*780*t))*exp(-55*t):d=0.16"], "highpass=f=180"),
    "toc2": (["aevalsrc=(0.7*sin(2*PI*410*t)+0.3*sin(2*PI*1050*t))*exp(-60*t):d=0.14"], "highpass=f=200"),
    "clic": (["anoisesrc=d=0.04:c=white:a=0.6"], "highpass=f=2000,afade=t=out:d=0.04"),
    # Datos y tarjetas
    "ding1": (["aevalsrc=(0.5*sin(2*PI*1318*t)+0.35*sin(2*PI*1975*t))*exp(-6*t):d=0.6"], "anull"),
    "ding2": (["aevalsrc=(0.5*sin(2*PI*1568*t)+0.3*sin(2*PI*2349*t))*exp(-7*t):d=0.55"], "anull"),
    # Arranque: golpe grave y corto
    "impacto": (["aevalsrc=sin(2*PI*(90-60*t)*t)*exp(-5*t):d=0.8", "anoisesrc=d=0.25:c=brown:a=0.9"],
                "[0]volume=1.4[a];[1]lowpass=f=900,afade=t=out:st=0.02:d=0.2[b];[a][b]amix=inputs=2:normalize=0"),
    # Subida de tensión antes de la revelación final
    "riser": (["anoisesrc=d=1.3:c=pink:a=0.6", "aevalsrc=0.2*sin(2*PI*(200*t+300*t*t)):d=1.3"],
              "[0][1]amix=inputs=2:normalize=0,highpass=f=500,afade=t=in:d=1.2:curve=exp,afade=t=out:st=1.22:d=0.08"),
    # Salida del título de portada
    "swish": (["anoisesrc=d=0.3:c=white:a=0.45"], "highpass=f=1500,lowpass=f=9000,afade=t=in:d=0.08,afade=t=out:st=0.1:d=0.2"),
}


def _igualar(ruta, pico=-4.0):
    """Deja todos los efectos con el mismo pico, para controlar el volumen solo desde el video."""
    import re
    salida = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(ruta), "-af", "volumedetect", "-f", "null", "-"],
                            capture_output=True, text=True).stderr
    m = re.search(r"max_volume: (-?[0-9.]+) dB", salida)
    if not m:
        return
    ganancia = pico - float(m.group(1))
    tmp = ruta.with_suffix(".tmp.mp3")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(ruta), "-af", f"volume={ganancia:.2f}dB",
                    str(tmp)], check=True)
    tmp.replace(ruta)


def generar():
    carpeta = PUBLICO / "sfx"
    carpeta.mkdir(parents=True, exist_ok=True)
    for nombre, (entradas, filtro) in RECETAS.items():
        destino = carpeta / f"{nombre}.mp3"
        if destino.exists():
            continue
        args = ["ffmpeg", "-y", "-loglevel", "error"]
        for e in entradas:
            args += ["-f", "lavfi", "-i", f"{e}:r={R}" if "aevalsrc" not in e else e.replace(":d=", f":s={R}:d=")]
        cadena = filtro if filtro.startswith("[") else f"[0]{filtro}"
        args += ["-filter_complex", f"{cadena},aformat=sample_rates={R}", "-ac", "2", str(destino)]
        subprocess.run(args, check=True)
        _igualar(destino)
    # Nombres antiguos (compatibilidad con videos 2D)
    for viejo, nuevo in (("whoosh", "whoosh1"), ("pop", "pop1"), ("ding", "ding1")):
        v = carpeta / f"{viejo}.mp3"
        if not v.exists():
            v.write_bytes((carpeta / f"{nuevo}.mp3").read_bytes())

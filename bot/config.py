"""Carga la configuración y las rutas del proyecto.

El bot maneja varias páginas ("canales"). La principal usa config.yaml y data/. Cada página
extra tiene su archivo en canales/<nombre>.yaml (solo lo que cambia respecto a config.yaml), sus
datos en data/<nombre>/ y sus secretos de Facebook con el nombre de la página al final
(META_PAGE_ID_HISTORIAS, META_PAGE_TOKEN_HISTORIAS). Claude, Gemini y Telegram son los mismos.
"""
import os
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
REMOTION = RAIZ / "remotion"
PUBLICO = REMOTION / "public"
ESCENAS = REMOTION / "src" / "escenas"
SALIDA = RAIZ / "salida"
PROMPTS = Path(__file__).resolve().parent / "prompts"
CANALES = RAIZ / "canales"
PRINCIPAL = "explicativos"
DATOS_PRINCIPAL = RAIZ / "data"

# Secretos que cambian según la página
_SECRETOS_DE_PAGINA = ("META_PAGE_ID", "META_PAGE_TOKEN")


def ruta_datos(canal: str) -> Path:
    return DATOS_PRINCIPAL if canal == PRINCIPAL else DATOS_PRINCIPAL / canal


CANAL = os.environ.get("CANAL", PRINCIPAL).strip() or PRINCIPAL
DATOS = ruta_datos(CANAL)


def canales() -> list[str]:
    """Páginas configuradas: la principal y cada canales/<nombre>.yaml."""
    extra = sorted(p.stem for p in CANALES.glob("*.yaml")) if CANALES.exists() else []
    return [PRINCIPAL] + [c for c in extra if c != PRINCIPAL]


def canal_listo(canal: str) -> bool:
    """Una página extra solo trabaja si tiene sus secretos de Facebook."""
    if canal == PRINCIPAL:
        return True
    sufijo = canal.upper()
    return all(os.environ.get(f"{s}_{sufijo}", "").strip() for s in _SECRETOS_DE_PAGINA)


# Diccionarios que cada página reemplaza enteros (no se mezclan con los de la principal).
_ENTEROS = {"guia", "escenarios"}


def _mezclar(base: dict, cambios: dict) -> dict:
    r = dict(base)
    for k, v in (cambios or {}).items():
        if k in _ENTEROS:
            r[k] = v
        else:
            r[k] = _mezclar(r[k], v) if isinstance(v, dict) and isinstance(r.get(k), dict) else v
    return r


def cargar_config(canal: str | None = None) -> dict:
    canal = canal or CANAL
    with open(RAIZ / "config.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if canal != PRINCIPAL:
        with open(CANALES / f"{canal}.yaml", encoding="utf-8") as f:
            cfg = _mezclar(cfg, yaml.safe_load(f) or {})
    cfg.setdefault("canal", {})["id"] = canal
    return cfg


def usar_canal(canal: str) -> None:
    """Cambia la página con la que trabaja el bot (datos, secretos y configuración)."""
    global CANAL, DATOS
    CANAL, DATOS = canal, ruta_datos(canal)
    DATOS.mkdir(parents=True, exist_ok=True)
    import importlib
    for nombre, attrs in {
        "memoria": {"MEMORIA": "memoria.json", "ESTADO": "estado.json", "TENDENCIAS": "tendencias.json"},
        "reanudar": {"EN_CURSO": "en_curso.json"},
        "autocontrol": {"REGLAS": "reglas_calidad.json"},
        "aprendizaje": {"LECCIONES": "aprendizajes.json"},
        "series": {"SERIES": "series.json"},
        "voz_gemini": {"VOZ": "voz.json"},
    }.items():
        try:
            m = importlib.import_module(f"{__package__}.{nombre}")
        except Exception:  # noqa: BLE001
            continue
        for attr, archivo in attrs.items():
            setattr(m, attr, DATOS / archivo)


def rol() -> str:
    """Qué hace la página actual, en pocas palabras (para los textos de Claude)."""
    try:
        return cargar_config()["canal"].get("rol") or "videos explicativos de la vida cotidiana"
    except Exception:  # noqa: BLE001
        return "videos explicativos de la vida cotidiana"


def secreto(nombre: str, obligatorio: bool = True) -> str:
    clave = f"{nombre}_{CANAL.upper()}" if CANAL != PRINCIPAL and nombre in _SECRETOS_DE_PAGINA else nombre
    valor = os.environ.get(clave, "").strip()
    if obligatorio and not valor:
        raise RuntimeError(f"Falta el secreto {clave}. Agrégalo en GitHub > Settings > Secrets.")
    return valor


def prompt(nombre: str) -> str:
    return (PROMPTS / nombre).read_text(encoding="utf-8")

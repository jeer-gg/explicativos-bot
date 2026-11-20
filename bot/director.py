"""El director: sortea el estilo y elige un tema nuevo con ayuda de los datos."""
import random

from .claude import Claude
from .memoria import memoria, resumen_para_director


def sortear_estilo(cfg: dict) -> dict:
    """Elige paleta, gancho y estructura sin repetir combinaciones recientes."""
    recientes = {
        (m.get("paleta"), m.get("tipo_gancho"), m.get("estructura")) for m in memoria()[-12:]
    }
    paletas = list(cfg["estilo"]["paletas"].keys())
    for _ in range(50):
        combo = (
            random.choice(paletas),
            random.choice(cfg["ganchos"]["tipos"]),
            random.choice(cfg["ganchos"]["estructuras"]),
        )
        if combo not in recientes:
            break
    nombre, gancho, estructura = combo
    colores = cfg["estilo"]["paletas"][nombre]
    return {
        "paleta": nombre,
        "colores": {"fondo": colores[0], "tinta": colores[1], "acentos": colores[2:]},
        "tipo_gancho": gancho,
        "estructura": estructura,
    }


def elegir_tema(claude: Claude, cfg: dict, estilo: dict) -> dict:
    canal = cfg["canal"]
    usados = [m.get("tema", "") for m in memoria()]
    system = (
        "Eres el director creativo de una página de Facebook de videos explicativos animados "
        f"en {canal['idioma']}. Público: {canal['publico']}. Tu trabajo es elegir el próximo "
        "tema con más potencial de retención y de compartirse, que sea verificable y nuevo."
    )
    usuario = f"""Canal: {canal['nombre']}
Subtemas posibles: {", ".join(canal['subtemas'])}
Temas prohibidos: {", ".join(canal['prohibidos'])}

Videos publicados y su rendimiento (usa esto para aprender qué funciona):
{resumen_para_director()}

Temas ya usados (no los repitas ni hagas variantes cercanas):
{"; ".join(usados[-150:]) or "ninguno"}

Para este video ya se sorteó:
- Tipo de gancho: {estilo['tipo_gancho']}
- Estructura: {estilo['estructura']}

Propón 3 temas candidatos concretos (no genéricos: "por qué el pan se pone duro y no blando
como las galletas" en vez de "la ciencia del pan"), cada uno con su ángulo sorprendente, y elige
el mejor según: curiosidad inmediata, que se pueda explicar visualmente en menos de 80 segundos,
que los datos sean verificables, y lo aprendido de las métricas.

Devuelve JSON:
{{"candidatos": [{{"tema": "...", "angulo": "...", "subtema": "..."}}],
  "elegido": {{"tema": "...", "angulo": "...", "subtema": "...", "por_que": "..."}}}}"""
    datos = claude.json(system, usuario, max_tokens=2000, web=True)
    return datos["elegido"]

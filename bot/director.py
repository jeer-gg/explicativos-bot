"""El director: sortea el estilo y elige un tema nuevo con ayuda de los datos."""
import random
from datetime import datetime, timedelta, timezone

from .claude import Claude
from . import aprendizaje
from .memoria import guardar_recuento, memoria, recuento, resumen_para_director


def sortear_estilo(cfg: dict) -> dict:
    """Elige paleta, gancho y estructura sin repetir combinaciones recientes."""
    recientes = {
        (m.get("paleta"), m.get("tipo_gancho"), m.get("estructura")) for m in memoria()[-12:]
    }
    grupo = "paletas_3d" if cfg["produccion"].get("motor") == "3d" else "paletas"
    paletas = list(cfg["estilo"][grupo].keys())
    tipos = cfg["ganchos"]["tipos"]
    estructuras = [e for e in cfg["ganchos"]["estructuras"] if permitir_estructura(cfg, e)]
    # Lo que mejor ha funcionado en esta página sale más seguido (sin dejar de probar lo demás).
    peso_tipos = aprendizaje.pesos(tipos, "tipo_gancho")
    peso_estr = aprendizaje.pesos(estructuras, "estructura")
    for _ in range(50):
        combo = (
            random.choice(paletas),
            random.choices(tipos, weights=peso_tipos)[0],
            random.choices(estructuras, weights=peso_estr)[0],
        )
        if combo not in recientes:
            break
    nombre, gancho, estructura = combo
    colores = cfg["estilo"][grupo][nombre]
    return {
        "tendencia": toca_tendencia(cfg),
        "paleta": nombre,
        "colores": {"fondo": colores[0], "tinta": colores[1], "acentos": colores[2:]},
        "tipo_gancho": gancho,
        "estructura": estructura,
    }


REGLAS_TENDENCIAS = """Nunca: tragedias con víctimas, muertes, crímenes, política, religión, salud o dosis,
rumores sin confirmar ni nada que se aproveche del dolor ajeno.
Facebook NO recomienda a gente nueva contenido con afirmaciones de salud o de dinero: nada de lo que es bueno o malo para el cuerpo, comida y bacterias, dietas, enfermedades, riesgos para la salud, precios, ofertas, compras, inflación, inversiones, bolsa ni criptomonedas. Si una tendencia es de eso (por ejemplo, el Black Friday o una empresa que sale a bolsa),
úsala solo si hay detrás un porqué cotidiano que NO hable de salud ni de dinero (cómo funciona
la máquina, el objeto o el fenómeno); si no, descártala."""


def _hoy(cfg: dict) -> str:
    from .horarios import _zona
    from datetime import datetime
    return datetime.now(_zona(cfg)).strftime("%Y-%m-%d")


def permitir_estructura(cfg: dict, estructura: str) -> bool:
    """Las historias en partes no deben dominar: como mucho una serie nueva cada pocos días y
    nunca mientras haya otra a medias."""
    if "HISTORIA EN PARTES" not in estructura:
        return True
    from . import series
    if series.datos()["pendientes"]:
        return False
    dias = cfg.get("series", {}).get("dias_entre_series", 4)
    limite = datetime.now(timezone.utc) - timedelta(days=dias)
    for m in memoria():
        if (m.get("serie") or {}).get("parte") == 1 and m.get("publicado_en") and \
                datetime.fromisoformat(m["publicado_en"]) > limite:
            return False
    return True


def toca_tendencia(cfg: dict) -> bool:
    """Reparto fijo por día: N de actualidad por cada clásico (por defecto 2 y 1).
    Con 3 videos al día: actualidad, actualidad, clásico."""
    t = cfg["canal"].get("tendencias", {})
    if not t.get("activo"):
        return False
    datos = recuento()
    if datos.get("fecha") != _hoy(cfg):
        return True
    actualidad = len(datos.get("usadas", []))
    clasicos = datos.get("clasicos", 0)
    return actualidad < t.get("por_cada_clasico", 2) * (clasicos + 1)


def _contar_clasico(cfg: dict):
    hoy = _hoy(cfg)
    datos = recuento()
    if datos.get("fecha") != hoy:
        datos = {"fecha": hoy, "tendencias": [], "usadas": [], "clasicos": 0}
    datos["clasicos"] = datos.get("clasicos", 0) + 1
    guardar_recuento(datos)


def recuento_del_dia(claude: Claude, cfg: dict) -> dict:
    """Una vez al día: investiga los temas del momento y saca las preguntas que la gente se hace.

    Los videos del día salen de esa lista (no del tema en sí, sino de cosas relacionadas que
    la gente se pregunta). Se guarda en data/tendencias.json para no repetir la investigación.
    """
    hoy = _hoy(cfg)
    datos = recuento()
    if datos.get("fecha") == hoy and datos.get("tendencias"):
        return datos
    t = cfg["canal"]["tendencias"]
    system = ("Eres investigador de tendencias para una página de videos explicativos de la vida "
              f"cotidiana en {cfg['canal']['idioma']}. Encuentras de qué habla la gente HOY y lo "
              "conviertes en preguntas curiosas que se pueden explicar con ciencia y datos.")
    usuario = f"""Fecha de hoy: {hoy}.
1) INVESTIGA con la búsqueda web lo que está pasando y lo que la gente busca y comenta hoy o en
los últimos 3 días en {", ".join(t.get("paises", []))}: tendencias de Google, noticias más
leídas, lo viral en TikTok, Facebook e Instagram, deportes, lanzamientos, clima y fenómenos
naturales, fiestas y fechas de la temporada.
2) Elige las 6 tendencias con más conversación que encajen con las reglas. Prefiere lo que
interesa a todo el mundo o a toda Latinoamérica (ciencia, tecnología, clima, fenómenos
naturales, lanzamientos, eventos mundiales, fechas y temporadas compartidas). Evita lo que
solo importa en un país (trámites, instituciones, precios o noticias locales): un video tiene
que poder interesarle igual a alguien de México, Argentina, República Dominicana o España.
3) Para cada una, escribe 4 preguntas RELACIONADAS que la gente se hace o se haría al ver esa
noticia, que no son la noticia en sí sino lo cotidiano que hay detrás. Ejemplo: tendencia «ola
de calor en el Caribe» → «¿por qué el ventilador no enfría el aire?», «¿por qué el asfalto
quema más que la arena?», «¿por qué sudamos más con humedad?». Deben poder explicarse con
datos verificables y verse bien en animación (objetos, cortes, comparaciones).
NICHO: todas las preguntas tienen que ser del nicho del canal ("cómo funcionan y por qué son
así las cosas de la vida cotidiana") y caer en uno de estos subtemas: {"; ".join(cfg["canal"]["subtemas"])}.
La tendencia es solo la excusa: el video nunca es sobre el famoso, el partido o la noticia,
sino sobre el objeto, el fenómeno o el porqué cotidiano que hay detrás. Si una tendencia no
da para eso, descártala.
{REGLAS_TENDENCIAS}

Devuelve JSON:
{{"tendencias": [{{"tendencia": "qué está pasando, en una frase", "fuente": "url o medio",
   "preguntas": [{{"pregunta": "...", "angulo": "lo sorprendente de la respuesta", "subtema": "..."}}]}}]}}"""
    try:
        nuevos = claude.json(system, usuario, max_tokens=5000, web=True)
        tendencias = [x for x in nuevos.get("tendencias", []) if x.get("preguntas")]
    except Exception as e:  # noqa: BLE001
        print("No se pudo hacer el recuento de tendencias:", e)
        return {}
    previo = datos if datos.get("fecha") == hoy else {}
    datos = {"fecha": hoy, "tendencias": tendencias, "usadas": previo.get("usadas", []),
             "clasicos": previo.get("clasicos", 0)}
    guardar_recuento(datos)
    try:
        from . import telegram
        lineas = [f"- {x['tendencia']}" for x in tendencias]
        telegram.aviso_seguro("Recuento de temas de hoy:\n" + "\n".join(lineas))
    except Exception:  # noqa: BLE001
        pass
    return datos


def _bloque_tendencias(datos: dict) -> str:
    usadas = set(datos.get("usadas", []))
    opciones = [f"- [{x['tendencia']}] {q['pregunta']} (ángulo: {q.get('angulo', '')}; subtema: {q.get('subtema', '')})"
                for x in datos.get("tendencias", []) for q in x.get("preguntas", [])
                if q.get("pregunta") not in usadas]
    if not opciones:
        return ""
    return f"""MODO ACTUALIDAD (este video): elige el tema de esta lista de preguntas que la gente se
hace por lo que está pasando hoy (entre corchetes, la tendencia que la inspira). Puedes
afinar la pregunta, pero el video debe salir de una de ellas. En "pregunta_origen" copia
la pregunta exacta de la lista y en "tendencia" la tendencia entre corchetes.
{chr(10).join(opciones)}
"""


def elegir_tema(claude: Claude, cfg: dict, estilo: dict) -> dict:
    canal = cfg["canal"]
    datos_tendencias = recuento_del_dia(claude, cfg) if estilo.get("tendencia") else {}
    bloque = _bloque_tendencias(datos_tendencias) if datos_tendencias else ""
    usados = [m.get("tema", "") for m in memoria()]
    system = (
        f"Eres el director creativo de una página de Facebook de {canal.get('rol', 'videos explicativos animados')} "
        f"en {canal['idioma']}. Público: {canal['publico']}. Tu trabajo es elegir el próximo "
        "tema con más potencial de retención y de compartirse, que sea verificable y nuevo."
    )
    usuario = f"""Canal: {canal['nombre']}
Subtemas posibles: {", ".join(canal['subtemas'])}
Temas prohibidos: {", ".join(canal['prohibidos'])}
Facebook NO recomienda a gente nueva contenido con afirmaciones de salud o de dinero: nada de lo que es bueno o malo para el cuerpo, comida y bacterias, dietas, enfermedades, riesgos para la salud, precios, ofertas, compras, inflación, inversiones, bolsa ni criptomonedas. Esos temas se quedan sin alcance aunque el video sea bueno.

Videos publicados y su rendimiento (usa esto para aprender qué funciona):
{resumen_para_director()}
{aprendizaje.texto_lecciones()}

Temas ya usados (no los repitas ni hagas variantes cercanas):
{"; ".join(usados[-150:]) or "ninguno"}

{bloque}
Para este video ya se sorteó:
- Tipo de gancho: {estilo['tipo_gancho']}
- Formato ganador (el tema DEBE encajar en él): {estilo['estructura']}

Propón 3 temas candidatos concretos (no genéricos: {canal.get('ejemplo_tema', '"por qué el pan se pone duro y no blando como las galletas" en vez de "la ciencia del pan"')}), cada uno con su ángulo sorprendente, y elige
el mejor según: ganas de enviárselo a alguien (lo que más reparte Facebook), curiosidad inmediata, que se pueda explicar visualmente en menos de 80 segundos,
que los datos sean verificables, y lo aprendido de las métricas.

Devuelve JSON:
{{"candidatos": [{{"tema": "...", "angulo": "...", "subtema": "...", "tendencia": "de qué se está hablando o vacío"}}],
  "elegido": {{"tema": "...", "angulo": "...", "subtema": "...", "tendencia": "...", "pregunta_origen": "...", "por_que": "..."}}}}"""
    # Con lista de tendencias no hace falta buscar en internet otra vez (ahorra uso de Claude).
    datos = claude.json(system, usuario, max_tokens=2000, web=not bloque)
    elegido = datos["elegido"]
    if bloque and elegido.get("pregunta_origen"):
        datos_tendencias.setdefault("usadas", []).append(elegido["pregunta_origen"])
        guardar_recuento(datos_tendencias)
    if not bloque:
        elegido["tendencia"] = ""
        _contar_clasico(cfg)
    return elegido

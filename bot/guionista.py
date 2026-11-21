"""Guion con investigación y verificación de datos."""
import json

from . import aprendizaje
from .claude import Claude


def _reglas_guion() -> str:
    from .autocontrol import texto_reglas
    return texto_reglas("guion")


def _bloque_serie(tema: dict, estilo: dict) -> str:
    """Instrucciones extra para historias en partes y continuaciones."""
    parte = tema.get("serie")
    if parte:
        ultima = parte["parte"] >= parte["total"]
        return f"""
SERIE: este video es la PARTE {parte['parte']} de {parte['total']} de «{parte['serie']}».
Lo que ya se contó antes: {parte.get('anterior', '')}
- La primera frase engancha por sí sola a quien no vio lo anterior, y en una frase corta recuerda
  lo esencial ("en la parte anterior viste que..."), sin repetir la explicación.
- Este video responde por completo SU propia pregunta (nadie debe sentirse engañado).
- {"Es la ÚLTIMA parte: cierra la historia con un remate satisfactorio." if ultima else
   "NO es la última: la última frase deja una intriga concreta y verdadera sobre lo que viene en la parte " + str(parte['parte'] + 1) + " (por ejemplo «pero lo más raro pasó después... en la parte " + str(parte['parte'] + 1) + "»). En vez de final en bucle, final con intriga."}
- "portada" empieza con "PARTE {parte['parte']}:".
"""
    if "HISTORIA EN PARTES" in estilo.get("estructura", ""):
        return """
SERIE NUEVA: este video es la PARTE 1 de una historia en 2 o 3 partes.
- Responde por completo su propia pregunta (nadie debe sentirse engañado), pero la historia
  continúa: la última frase deja una intriga concreta y verdadera sobre la parte 2 («y lo que
  pasó después es aún más raro... en la parte 2»). En vez de final en bucle, final con intriga.
- "portada" empieza con "PARTE 1:".
- Añade al JSON el plan de las siguientes partes:
  "serie": {"titulo": "nombre corto de la serie", "total": 2 o 3,
            "siguientes": [{"parte": 2, "tema": "qué cuenta", "angulo": "lo sorprendente"}]}
"""
    return ""


def escribir_guion(claude: Claude, cfg: dict, tema: dict, estilo: dict) -> dict:
    p = cfg["produccion"]
    canal = cfg["canal"]
    system = (
        "Eres guionista de videos explicativos animados cortos para Facebook Reels en "
        f"{canal['idioma']}. Escribes como se habla, con frases cortas, ritmo rápido y humor ligero. "
        "Cada dato que afirmas debe ser cierto y tener fuente confiable. Investiga antes de escribir."
    )
    palabras_max = int(p["duracion_max"] * 2.6)
    palabras_min = int(p["duracion_min"] * 2.4)
    usuario = f"""Tema: {tema['tema']}
Ángulo: {tema['angulo']}{(chr(10) + "Tendencia del momento que lo inspira: " + tema['tendencia'] + " (menciónala en la primera frase para enganchar, sin inventar detalles: verifica con la búsqueda web)") if tema.get('tendencia') else ""}
Tipo de gancho: {estilo['tipo_gancho']}
Formato ganador: {estilo['estructura']}
{_bloque_serie(tema, estilo)}{aprendizaje.texto_lecciones()}{_reglas_guion()}
Reglas:
- La voz arranca en el segundo 0: la primera frase ES el gancho, de 6 a 12 palabras.
- Entre {palabras_min} y {palabras_max} palabras en total, en {p['escenas_min']} a {p['escenas_max']} escenas.
- Cada escena dura entre 3 y 5 segundos de voz y muestra UNA idea visual clara (en los videos
  ganadores cambia algo cada 3 a 4 segundos). Muchas escenas
  cortas mantienen la atención mejor que pocas largas.
- Habla corrida, como un narrador entusiasta que no se detiene: frases que se encadenan con
  "y", "pero", "porque", "así que". Evita puntos y comas innecesarios, porque cada signo crea
  una pausa en la voz. Nada de frases de relleno.
- Retención: en los primeros 5 segundos promete algo concreto que se revela al final ("y lo
  más raro es lo que pasa al final"), mete una vuelta de tuerca o dato inesperado cada 2 o 3
  escenas, y termina con un remate que haga querer verlo otra vez o comentar.
- Lo que más premia Facebook es que lo vean COMPLETO, lo vuelvan a ver y lo ENVÍEN a alguien:
  · Una sola idea, bien contada. Nada de listas de cinco cosas.
  · Dura lo que la explicación necesita: sin relleno ni frases de más para alargar, y sin
    cortar información importante para acortar. El rango de palabras es orientativo.
  · El gancho promete algo que solo se cobra viendo: nunca da la respuesta en la primera frase.
  · Háblale al espectador de "tú" (lo que TÚ haces, lo que te pasa a TI), no "yo".
  · La respuesta prometida SIEMPRE se entrega antes del final: un gancho que no cumple hace
    que la gente oculte el video, y eso castiga a la página.
  · Pon al menos un dato o consejo que den ganas de enviárselo a alguien ("tengo que
    decirle esto a mi mamá").
  · Final en bucle: la última frase se encadena con la primera, para que al repetirse el
    video suene continuo y mucha gente lo vea dos veces.
- Nada de "hola", "en este video" ni "suscríbete". Termina con un remate curioso o una
  pregunta que invite a comentar.
- La descripción visual de cada escena debe ser concreta y dibujable: qué personajes u objetos
  hay, qué hacen, qué se mueve, qué metáfora visual explica la idea. Sin texto largo en pantalla
  (máximo 3 palabras de rótulo por escena).
- UN SOLO MUNDO QUE EVOLUCIONA (así son los Reels 3D con millones de vistas): todo el video pasa
  en el mismo lugar con el mismo protagonista (un objeto, una máquina, un sistema), y cada
  escena le cambia UNA cosa: se agrega una pieza, se llena, se abre, falla, se arregla. Nada de
  saltar a otro lugar u otro objeto. En cada escena escribe en "mundo" cómo queda al terminarla.
  · Empieza muchas veces por la versión más simple o rota del objeto («ya tienes un avión: una
    tabla y un palo») y cada frase le agrega la pieza que resuelve el siguiente problema.
  · Muestra qué pasa SIN la pieza (se cae, se desborda, no sube, se rompe) justo antes de
    ponerla: el fallo exagerado es lo que más retiene.
  · Nombra cada parte con su nombre real («el flotador», «el estabilizador horizontal»): la
    gente se queda para aprender cómo se llama.
- "concepto" en cada escena: de 1 a 4 palabras que se DICEN TAL CUAL en la voz de esa escena y
  resumen el momento («LA BOLA SUBE», «EL FLOTADOR», «NO SUBE SOLA», «POCA FUERZA»). Es el texto
  grande que aparece arriba de la pantalla; si hay negación, que empiece por ella.
- Escribe números como se pronuncian si pueden leerse mal ("dos mil" en vez de "2.000").
- Formato: sigue al pie de la letra la estructura sorteada; es un formato probado con cientos
  de miles de vistas.
- Lo visual es protagonista: casi siempre un OBJETO o lugar cotidiano grande y detallado que se
  arma, se abre en corte, se compara o se transforma (no gente hablando). Cada escena dice
  qué pieza aparece, qué parte se señala con una etiqueta corta, qué se mide o qué flecha se ve.
- "portada": el título grande que aparece al inicio y en la miniatura, de 3 a 6 palabras en
  mayúsculas, que dé ganas de ver (como «ESTE TRIÁNGULO NO ES DE ADORNO» o «SI TE QUEMAS
  COCINANDO...»). Debe decir lo mismo que la primera frase, no otra cosa.
- "grafico" (opcional, en 2 o 3 escenas como máximo): una tarjeta con datos que aparece en
  pantalla. Tipos: {{"tipo": "barras", "items": [{{"etiqueta": "un panel", "valor": 450, "unidad": "W"}}, ...]}}
  (2 a 4 barras), {{"tipo": "mitos", "items": ["hielo", "pasta", "mantequilla"]}} (se tachan con
  una X roja), {{"tipo": "contador", "valor": 1839, "etiqueta": "año"}}. Usa solo datos verificados.
{"- Incluye la versión B del gancho: otra primera escena con un tipo de gancho distinto." if p.get("ab_gancho") else ""}
- Define una dirección de arte común: el mismo protagonista y el mismo mundo visual en todas
  las escenas, para que el video se sienta como un solo plano continuo.

Devuelve JSON:
{{
 "titulo": "título corto para Facebook (máx. 60 caracteres)",
 "descripcion": "descripción de 1 a 2 frases que invite a ver",
 "portada": "TÍTULO DE 3 A 6 PALABRAS",
 "pregunta_comentarios": "pregunta corta para el texto de la publicación que invite a comentar (por ejemplo, ¿tú también lo hacías?)",
 "hashtags": ["3 a 5 hashtags específicos del tema, en español, sin genéricos"],
 "escenas": [
   {{"voz": "texto narrado", "visual": "descripción detallada de la ilustración y su animación",
     "rotulo": "0 a 3 palabras o vacío", "palabra_clave": "palabra de la voz donde ocurre el momento visual principal",
     "concepto": "1 a 4 palabras dichas tal cual en la voz", "mundo": "cómo queda el mundo al terminar esta escena (qué piezas hay, en qué estado)",
     "grafico": null,
     "datos": [{{"afirmacion": "...", "fuente": "url o referencia"}}]}}
 ],
{' "gancho_b": {"voz": "...", "visual": "...", "rotulo": "...", "palabra_clave": "...", "tipo": "..."},' if p.get("ab_gancho") else ""}
 "direccion_arte": {{
   "protagonista": "aspecto exacto del personaje o objeto que guía el video (forma, colores, ropa, rasgos) para dibujarlo igual en todas las escenas",
   "secundarios": "otros personajes u objetos que se repiten, con su aspecto",
   "ambiente": "el único lugar donde pasa todo el video (si es grande, como maqueta en corte)",
   "partes": "las piezas del protagonista que se agregan, cambian o se señalan, con su aspecto",
   "metafora": "la metáfora visual central que explica el tema"
 }}
}}"""
    return claude.json(system, usuario, max_tokens=6000, web=True)


def pulir_gancho(claude: Claude, cfg: dict, guion: dict) -> dict:
    """Escribe varios arranques posibles, los puntúa y se queda con el más fuerte.

    El primer segundo decide si la gente se detiene: se juzga la imagen inicial (que también
    es la miniatura), el título de portada y la primera frase que se oye.
    """
    system = ("Eres editor de Reels virales en español. Sabes que el 70 % de la gente decide en el "
              "primer segundo si se queda. Juzgas ganchos con frialdad, por lo que hace detenerse "
              "a alguien que está haciendo scroll con el sonido apagado o encendido.")
    usuario = f"""Guion actual (JSON):
{json.dumps(guion, ensure_ascii=False)}

{aprendizaje.texto_lecciones()}
Escribe 6 arranques alternativos para la PRIMERA escena (distintos entre sí: negación de lo
obvio, advertencia directa, número imposible, pregunta que duele, imagen absurda, error común).
Cada uno con: "voz" (primera frase, 6 a 12 palabras, que encaje con la escena 2 del guion),
"portada" (3 a 6 palabras en mayúsculas, dice lo mismo que la voz), "visual" (qué se VE en el
fotograma 0 y qué pasa en el primer segundo: algo grande, raro o a punto de romperse; nunca una
pantalla tranquila, y en el mismo mundo del resto del guion), "palabra_clave" (palabra de la voz
del golpe visual), "rotulo" y "concepto" (1 a 4 palabras dichas tal cual en la voz).

Reglas que separan un gancho que retiene de uno que se salta (datos de 2026):
- No da la respuesta: promete algo que solo se cobra viendo hasta el final.
- Habla de "tú", no de "yo". Empieza por la acción o el error, sin introducción.
- La imagen arranca en plena acción, con lo que es parte de la historia (el objeto, o la persona
  que vive la situación).

Puntúa cada uno de 1 a 10 en: imagen que detiene el scroll en silencio, curiosidad que solo se
cierra viendo hasta el final, claridad en menos de un segundo, emoción (sorpresa, miedo a
equivocarse, risa) y ganas de enviárselo a alguien. Elige el de mejor suma. Si el arranque
actual es mejor, elígelo.

Devuelve JSON: {{"candidatos": [{{"voz": "...", "portada": "...", "visual": "...", "palabra_clave": "...",
"rotulo": "...", "concepto": "...", "notas": {{"imagen": n, "curiosidad": n, "claridad": n, "emocion": n, "compartir": n}}}}],
"elegido": 0}}"""
    try:
        datos = claude.json(system, usuario, max_tokens=4000)
        mejor = datos["candidatos"][int(datos.get("elegido", 0))]
    except Exception as e:  # noqa: BLE001  (si falla, se queda el gancho original)
        print("No se pudo pulir el gancho:", e)
        return guion
    primera = guion["escenas"][0]
    for clave in ("voz", "visual", "palabra_clave", "rotulo", "concepto"):
        if mejor.get(clave):
            primera[clave] = mejor[clave]
    if mejor.get("portada"):
        guion["portada"] = mejor["portada"]
    print("Gancho elegido:", primera["voz"])
    return guion


def verificar_guion(claude: Claude, guion: dict) -> dict:
    """Revisa cada afirmación. Corrige o elimina lo que no se pueda sostener."""
    system = (
        "Eres verificador de datos. Revisas guiones de divulgación antes de publicarse. "
        "Compruebas cada afirmación con fuentes confiables y corriges lo exagerado o falso, "
        "manteniendo el mismo tono, ritmo y longitud aproximada."
    )
    usuario = (
        "Revisa este guion. Si una afirmación es falsa, dudosa o exagerada, reescribe esa parte "
        "de la voz para que sea correcta. No cambies lo que ya es correcto. Devuelve el guion "
        "completo con la misma estructura JSON, añadiendo el campo \"verificacion\": "
        "{\"cambios\": [\"...\"], \"confianza\": \"alta|media|baja\"}.\n\n"
        + json.dumps(guion, ensure_ascii=False, indent=1)
    )
    revisado = claude.json(system, usuario, max_tokens=7000, web=True)
    if not revisado.get("escenas") or len(revisado["escenas"]) != len(guion["escenas"]):
        return guion
    # Conserva lo que el verificador no debía tocar.
    for clave in ("titulo", "descripcion", "portada", "pregunta_comentarios", "hashtags", "serie", "gancho_b", "direccion_arte"):
        if not revisado.get(clave) and guion.get(clave):
            revisado[clave] = guion[clave]
    for nueva, vieja in zip(revisado["escenas"], guion["escenas"]):
        for clave in ("grafico", "concepto", "mundo"):
            if vieja.get(clave) and not nueva.get(clave):
                nueva[clave] = vieja[clave]
    return revisado

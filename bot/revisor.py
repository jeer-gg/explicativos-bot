"""El revisor: Claude mira fotogramas reales del video y puntúa cada escena."""
from .claude import Claude, imagen
from .equipo import profesional


ULTIMO_COMENTARIO = ""


def revisar(claude: Claude, cfg: dict, guion: dict, fotos: list[dict]) -> dict:
    """fotos: [{"nombre": "Escena0", "ruta": Path, "voz": "...", "visual": "..."}]

    Devuelve {"escenas": {"Escena0": {"nota": 8, "problemas": "..."}}, "comentario": "..."}
    """
    contenido = [{"type": "text", "text": (
        f"Video: «{guion['titulo']}». Estilo buscado: "
        f"{cfg['estilo']['descripcion_3d' if cfg['produccion'].get('motor') == '3d' else 'descripcion'].strip()}\n"
        "De cada escena te muestro dos fotogramas lado a lado (izquierda: al empezar; derecha: más "
        "adelante), tal como se verán con el texto en pantalla.\n"
        "LO QUE MÁS PESA ES LA ESTÉTICA: cómo se ve. Referencia de un 9 (Reels 3D con millones de "
        "vistas): un avión rojo con contornos de dibujo en un cielo azul con nubes, que gana una "
        "pieza por frase y la pieza nombrada se pinta de verde lima; un corte de una casa con "
        "tuberías y agua azul intensa sobre fondo oscuro, que se llena y se vacía; paneles "
        "solares 3D detallados en una azotea soleada, con cables y medidores; figuras grises en "
        "un escenario oscuro con un foco cálido sobre la figura roja protagonista, con tarjetas "
        "de datos grandes. Todos: fotograma lleno y bonito, protagonista que contrasta con el "
        "fondo, buena luz, colores limpios, un solo mundo que va cambiando. Esas son referencias "
        "de calidad, no de estilo: juzga con la paleta y el estilo de animación de ESTA página "
        "(descritos arriba); por ejemplo, si la página es de plastilina, que no haya contornos "
        "está bien. Técnica 2.5D: manos, personas, agua, humo y plantas van dibujados en 2D con "
        "curvas; si alguno de esos está armado con cajas y esferas 3D, es un error real. "
        "Retención: en la escena del gancho algo llamativo pasa desde el primer fotograma y la imagen "
        "cambia antes del segundo 3; en las demás, nada se queda quieto más de 3 segundos.\n"
        "Puntúa así: 1) estética (riqueza, luz, color, contraste del protagonista, cuadro lleno, "
        "aspecto profesional): es lo que más cuenta; 2) que se entienda la idea de la voz y sea "
        "fiel a la realidad; 3) que haya movimiento o cambio entre los dos fotogramas; 4) que la "
        "parte de la que habla la voz se vea resaltada o señalada.\n"
        "Baja mucho la nota solo por ERRORES REALES: escena vacía o casi vacía, texto cortado, "
        "tapado o ilegible, elementos que se atraviesan por error, emojis, algo que no se entiende, "
        "un dato visible que contradice la voz. NO son errores (no bajes por eso): un plano abierto "
        "para ubicar si el protagonista se distingue, un color fuerte para resaltar, repetir el "
        "mismo lugar y protagonista entre escenas (es un solo mundo que cambia). Lo importante "
        "debe quedar en el centro (se recorta al 4:5 del feed). No te fijes en detalles pequeños: "
        "si falta un objeto secundario de lo que pedía el guion pero la idea se entiende y se ve "
        "bien, no bajes la nota. En «problemas» escribe como mucho los 2 cambios que más "
        "mejorarían la escena. En la PRIMERA escena exige además "
        "un gancho visual hermoso que detenga el scroll desde el fotograma 0 (es la miniatura)."
    )}]
    from .autocontrol import texto_reglas
    reglas = texto_reglas("escenas", 12)
    if reglas:
        contenido.append({"type": "text", "text": "Comprueba también estos errores que ya se "
                          "cometieron antes y baja la nota si se repiten (si alguna regla choca con la "
                          "referencia de estética de arriba, manda la referencia):" + reglas})
    for f in fotos:
        contenido.append({"type": "text", "text": f"\n{f['nombre']}. Voz: «{f['voz']}». Debía mostrar: {f['visual']}"})
        contenido.append(imagen(f["ruta"]))
    contenido.append({"type": "text", "text": (
        "\nPuntúa cada escena de 1 a 10 (10 = nivel de un canal profesional). Sé exigente. "
        'Devuelve JSON: {"escenas": {"<nombre>": {"nota": n, "problemas": "qué corregir, concreto"}}, '
        '"comentario": "resumen en una frase"}'
    )})
    global ULTIMO_COMENTARIO
    from .config import rol
    resultado = claude.json(
        profesional("supervisor_animacion") + f"Eres director de arte de videos 3D virales de {rol()}. Lo que más te importa es que el "
        "video se vea hermoso y profesional. Eres exigente con la estética y justo: no castigas los "
        "recursos que usan los Reels ganadores.",
        contenido, max_tokens=3000)
    ULTIMO_COMENTARIO = str(resultado.get("comentario", ""))[:300]
    return resultado

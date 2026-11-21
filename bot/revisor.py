"""El revisor: Claude mira fotogramas reales del video y puntúa cada escena."""
from .claude import Claude, imagen


ULTIMO_COMENTARIO = ""


def revisar(claude: Claude, cfg: dict, guion: dict, fotos: list[dict]) -> dict:
    """fotos: [{"nombre": "Escena0", "ruta": Path, "voz": "...", "visual": "..."}]

    Devuelve {"escenas": {"Escena0": {"nota": 8, "problemas": "..."}}, "comentario": "..."}
    """
    contenido = [{"type": "text", "text": (
        f"Video: «{guion['titulo']}». Estilo buscado: "
        f"{cfg['estilo']['descripcion_3d' if cfg['produccion'].get('motor') == '3d' else 'descripcion'].strip()}\n"
        "De cada escena te muestro dos fotogramas lado a lado (izquierda: al empezar; derecha: más "
        "adelante), tal como se verán con subtítulos. "
        "Para cada escena revisa: que la ilustración sea elaborada y atractiva (no simple), "
        "que se entienda la idea de la voz, que sea fiel a la realidad, que nada importante "
        "quede tapado por los subtítulos o cortado en los bordes, que no haya texto roto ni "
        "elementos superpuestos por error, que no haya emojis, que la ilustración llene todo el "
        "cuadro vertical sin franjas vacías, y que lo importante esté en el centro (se debe "
        "entender aunque se recorte arriba y abajo al formato 4:5 del feed), que el plano sea cercano "
        "(el protagonista grande, no un cuarto vacío visto de lejos), que desde el inicio de la "
        "escena ya se vea una ilustración completa y rica, y que entre los dos fotogramas haya "
        "un cambio visible (movimiento, acción). En la PRIMERA escena exige además un gancho visual "
        "que detenga el scroll desde el fotograma 0 (es la miniatura)."
    )}]
    from .autocontrol import texto_reglas
    reglas = texto_reglas("escenas", 12)
    if reglas:
        contenido.append({"type": "text", "text": "Comprueba especialmente estos errores que ya se "
                          "cometieron antes y baja mucho la nota si se repiten:" + reglas})
    for f in fotos:
        contenido.append({"type": "text", "text": f"\n{f['nombre']}. Voz: «{f['voz']}». Debía mostrar: {f['visual']}"})
        contenido.append(imagen(f["ruta"]))
    contenido.append({"type": "text", "text": (
        "\nPuntúa cada escena de 1 a 10 (10 = nivel de un canal profesional). Sé exigente. "
        'Devuelve JSON: {"escenas": {"<nombre>": {"nota": n, "problemas": "qué corregir, concreto"}}, '
        '"comentario": "resumen en una frase"}'
    )})
    global ULTIMO_COMENTARIO
    resultado = claude.json(
        "Eres director de arte y editor de videos explicativos animados virales. Revisas con ojo crítico "
        "y comparas con los mejores Reels de explicativos 3D (objetos detallados que se arman, contornos "
        "de dibujo, etiquetas, cámara cercana, ritmo rápido).",
        contenido, max_tokens=3000)
    ULTIMO_COMENTARIO = str(resultado.get("comentario", ""))[:300]
    return resultado

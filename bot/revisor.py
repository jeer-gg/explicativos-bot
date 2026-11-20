"""El revisor: Claude mira fotogramas reales del video y puntúa cada escena."""
from .claude import Claude, imagen


def revisar(claude: Claude, cfg: dict, guion: dict, fotos: list[dict]) -> dict:
    """fotos: [{"nombre": "Escena0", "ruta": Path, "voz": "...", "visual": "..."}]

    Devuelve {"escenas": {"Escena0": {"nota": 8, "problemas": "..."}}, "comentario": "..."}
    """
    contenido = [{"type": "text", "text": (
        f"Video: «{guion['titulo']}». Estilo buscado: {cfg['estilo']['descripcion'].strip()}\n"
        "Te muestro un fotograma de cada escena tal como se verá (incluye subtítulos). "
        "Para cada escena revisa: que la ilustración sea elaborada y atractiva (no simple), "
        "que se entienda la idea de la voz, que sea fiel a la realidad, que nada importante "
        "quede tapado por los subtítulos o cortado en los bordes, que no haya texto roto ni "
        "elementos superpuestos por error, y que no haya emojis."
    )}]
    for f in fotos:
        contenido.append({"type": "text", "text": f"\n{f['nombre']}. Voz: «{f['voz']}». Debía mostrar: {f['visual']}"})
        contenido.append(imagen(f["ruta"]))
    contenido.append({"type": "text", "text": (
        "\nPuntúa cada escena de 1 a 10 (10 = nivel de un canal profesional). Sé exigente. "
        'Devuelve JSON: {"escenas": {"<nombre>": {"nota": n, "problemas": "qué corregir, concreto"}}, '
        '"comentario": "resumen en una frase"}'
    )})
    return claude.json(
        "Eres director de arte y editor de videos explicativos animados. Revisas con ojo crítico.",
        contenido, max_tokens=3000)

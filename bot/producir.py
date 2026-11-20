"""Produce un video completo: tema, guion, voz, escenas, revisión, render y aprobación.

Uso: python -m bot.producir
"""
import json
import shutil
import subprocess
import time
import traceback
from concurrent.futures import ThreadPoolExecutor

INICIO = time.monotonic()
from datetime import datetime, timezone

from . import estadisticas, estudio, render, revisor, sfx, telegram
from .claude import Claude
from .config import PUBLICO, SALIDA, cargar_config
from .director import elegir_tema, sortear_estilo
from .guionista import escribir_guion, verificar_guion
from .memoria import estado, guardar_estado
from .publicador import publicar, subir_pendiente
from .voz import narrar_guion


def _normal(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if c.isalnum() and unicodedata.category(c) != "Mn")


def momento_clave(palabras: list, clave: str):
    """Segundo (dentro de la escena) en que se dice la palabra clave."""
    objetivo = _normal(clave or "")
    if not objetivo:
        return None
    for p in palabras:
        w = _normal(p["w"])
        if w and (w == objetivo or (len(w) > 3 and (w in objetivo or objetivo in w))):
            return p["t"]
    return None


def armar_plan(cfg, tiempos_variante, nombres, guion, estilo, variante):
    fuentes = list(guion["escenas"])
    if variante == "B":
        fuentes[0] = guion["gancho_b"]
    escenas = []
    for nombre, t, fuente in zip(nombres, tiempos_variante["escenas"], fuentes):
        escenas.append({"componente": nombre, "inicio": t["inicio"], "duracion": t["duracion"],
                        "palabras": t["palabras"], "rotulo": fuente.get("rotulo", "") or "",
                        "clave": momento_clave(t["palabras"], fuente.get("palabra_clave", "")),
                        "clave_palabra": fuente.get("palabra_clave", "") or "",
                        "camara": estudio.encuadre(len(escenas)),
                        "grafico": grafico_valido(fuente.get("grafico"))})
    return {
        "motor": cfg["produccion"].get("motor", "2d"),
        "audio": tiempos_variante["audio"],
        "musica": cfg["produccion"].get("musica", "") or "",
        "subtitulos": cfg["produccion"].get("subtitulos", True),
        "paleta": estilo["colores"],
        "portada": (guion.get("portada") or "").upper()[:60],
        "escenas": escenas,
    }


def grafico_valido(g):
    """Solo deja pasar gráficos con la forma que el video sabe dibujar."""
    if not isinstance(g, dict):
        return None
    tipo, items = g.get("tipo"), g.get("items")
    try:
        if tipo == "barras" and isinstance(items, list) and 2 <= len(items) <= 4:
            return {"tipo": "barras", "items": [{"etiqueta": str(i.get("etiqueta", ""))[:18],
                                                  "valor": float(i["valor"]),
                                                  "unidad": str(i.get("unidad", ""))[:6]} for i in items]}
        if tipo == "mitos" and isinstance(items, list) and 1 <= len(items) <= 4:
            return {"tipo": "mitos", "items": [str(i)[:14] for i in items]}
        if tipo == "contador":
            return {"tipo": "contador", "valor": float(g["valor"]), "etiqueta": str(g.get("etiqueta", ""))[:20]}
    except (KeyError, TypeError, ValueError, AttributeError):
        return None
    return None


def preparar_motor(cfg: dict, trabajo) -> None:
    """Comprueba que el 3D se dibuja en esta máquina; si no, sigue en 2D y avisa."""
    p = cfg["produccion"]
    if p.get("motor", "2d") == "3d":
        estudio.MOTOR["actual"] = "3d"
        estudio.limpiar_escenas_viejas()
        estudio.escribir_indice([])
        colores = next(iter(cfg["estilo"]["paletas_3d"].values()))
        plan = {"motor": "3d", "audio": "sfx/whoosh.mp3", "musica": "", "subtitulos": False,
                "paleta": {"fondo": colores[0], "tinta": colores[1], "acentos": colores[2:]},
                "escenas": [{"componente": "Ejemplo3D", "inicio": 0, "duracion": 3, "palabras": [],
                             "rotulo": "", "clave": None}]}
        ok, salida = render.empaquetar()
        if ok:
            ruta = render.guardar_plan(plan, "prueba")
            destino = trabajo / "fotos" / "prueba3d.png"
            for gl in ("swangle", "swiftshader", "angle"):
                render.OPCIONES.update(gl=gl, concurrencia=p.get("concurrencia_3d", "50%"))
                ok, salida = render.foto(ruta, 45, destino)
                if ok and render.imagen_vacia(destino):
                    ok, salida = False, "La imagen 3D salió vacía."
                if ok:
                    print("3D funcionando con", gl)
                    return
        print("El 3D no funcionó:", salida[-1500:])
        telegram.aviso_seguro("El 3D no funcionó en esta ejecución; hago el video en 2D.\n" + salida[-600:])
        p["motor"] = "2d"
    render.OPCIONES.update(gl=None, concurrencia="100%")
    estudio.MOTOR["actual"] = "2d"


def tomar_fotos(planes, rutas_plan, trabajo, guion, nombres_por_variante):
    """Un fotograma a mitad de cada escena. Devuelve (fotos, errores)."""
    fotos, errores, vistas = [], {}, set()
    for variante, plan in planes.items():
        for i, esc in enumerate(plan["escenas"]):
            nombre = esc["componente"]
            if nombre in vistas:
                continue
            vistas.add(nombre)
            # Dos momentos de la escena (inicio y avance) unidos lado a lado en una sola imagen
            destino = trabajo / "fotos" / f"{nombre}.png"
            momentos = []
            ok, salida = True, ""
            for j, frac in enumerate((0.12, 0.68)):
                fotograma = int((esc["inicio"] + esc["duracion"] * frac) * 30)
                parte = trabajo / "fotos" / f"{nombre}_{j}.png"
                ok, salida = render.foto(rutas_plan[variante], fotograma, parte)
                if not ok:
                    break
                momentos.append(parte)
            if ok:
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(momentos[0]), "-i", str(momentos[1]),
                                "-filter_complex", "[0][1]hstack=inputs=2,scale=1080:-2", str(destino)], check=True)
            fuente = guion["gancho_b"] if (variante == "B" and i == 0) else guion["escenas"][i]
            if ok:
                fotos.append({"nombre": nombre, "ruta": destino, "voz": fuente["voz"], "visual": fuente["visual"]})
            else:
                errores[nombre] = salida
    return fotos, errores


def producir():
    cfg = cargar_config()
    claude = Claude()
    id_video = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    trabajo = SALIDA / id_video
    trabajo.mkdir(parents=True, exist_ok=True)
    sfx.generar()
    preparar_motor(cfg, trabajo)

    try:
        estadisticas.actualizar()
    except Exception as e:  # noqa: BLE001
        print("Aviso: no se actualizaron métricas:", e)

    # 1. Director
    estilo = sortear_estilo(cfg)
    tema = elegir_tema(claude, cfg, estilo)
    print("Tema:", tema)

    # 2. Guion verificado
    guion = verificar_guion(claude, escribir_guion(claude, cfg, tema, estilo))
    guion["escenas"] = guion["escenas"][: cfg["produccion"]["escenas_max"]]
    (trabajo / "guion.json").write_text(json.dumps(guion, ensure_ascii=False, indent=1), encoding="utf-8")

    # 3. Voz (marca el tiempo de todo)
    try:
        tiempos = narrar_guion(guion, cfg, trabajo / "voz", PUBLICO)
    except ValueError:
        cfg["produccion"]["velocidad_voz"] = "+18%"
        tiempos = narrar_guion(guion, cfg, trabajo / "voz", PUBLICO)
    from .voz import AVISOS
    for aviso in AVISOS:
        telegram.aviso_seguro(aviso)

    # 4. Estudio: una escena por llamada
    n = len(guion["escenas"])
    nombres_a = [f"Escena{i}" for i in range(n)]
    hay_b = "B" in tiempos
    nombres_b = ["EscenaB"] + nombres_a[1:] if hay_b else []
    todos = nombres_a + (["EscenaB"] if hay_b else [])

    def datos_escena(nombre):
        if nombre == "EscenaB":
            return guion["gancho_b"], tiempos["B"]["escenas"][0], 0
        i = int(nombre.replace("Escena", ""))
        return guion["escenas"][i], tiempos["A"]["escenas"][i], i

    estudio.limpiar_escenas_viejas()

    def dibujar_una(nombre, comentarios="", previo="", foto=None):
        esc, t, i = datos_escena(nombre)
        print("Dibujando", nombre)
        return nombre, estudio.dibujar(claude, cfg, nombre, esc, t, guion, i, estilo,
                                       comentarios=comentarios, codigo_previo=previo, foto=foto)

    # Se dibujan varias escenas a la vez para ahorrar tiempo.
    with ThreadPoolExecutor(max_workers=4) as hilos:
        codigos = dict(hilos.map(dibujar_una, todos))
    estudio.escribir_indice(todos)
    estudio.compilar(claude, cfg, todos)

    planes = {"A": armar_plan(cfg, tiempos["A"], nombres_a, guion, estilo, "A")}
    if hay_b:
        planes["B"] = armar_plan(cfg, tiempos["B"], nombres_b, guion, estilo, "B")
    rutas_plan = {v: render.guardar_plan(p, v) for v, p in planes.items()}

    # 5. Revisor: mira fotogramas reales y pide rehacer lo flojo
    nota_min = cfg["claude"]["nota_minima"]
    notas = {}
    for ronda in range(cfg["claude"]["rondas_revision"] + 1):
        fotos, errores = tomar_fotos(planes, rutas_plan, trabajo, guion, None)
        for nombre, salida in errores.items():
            print(f"{nombre} falla al renderizar; la reparo.")
            estudio.reparar(claude, cfg, nombre, salida)
        if errores:
            estudio.compilar(claude, cfg, todos)
            fotos, errores = tomar_fotos(planes, rutas_plan, trabajo, guion, None)
            for nombre in errores:
                estudio.usar_respaldo(nombre)
            if errores:
                estudio.compilar(claude, cfg, todos)
        if not fotos:
            break
        resultado = revisor.revisar(claude, cfg, guion, fotos)
        notas = {k: v for k, v in resultado.get("escenas", {}).items() if k in todos}
        print(f"Ronda {ronda}: notas", {k: v.get("nota") for k, v in notas.items()})
        flojas = {k: v for k, v in notas.items() if float(v.get("nota", 10)) < nota_min}
        if not flojas or ronda == cfg["claude"]["rondas_revision"]:
            break
        with ThreadPoolExecutor(max_workers=4) as hilos:
            fotos_por_nombre = {f["nombre"]: f["ruta"] for f in fotos}
            rehechas = hilos.map(lambda kv: dibujar_una(kv[0], kv[1].get("problemas", ""),
                                                        codigos.get(kv[0], ""), fotos_por_nombre.get(kv[0])),
                                 flojas.items())
            codigos.update(dict(rehechas))
        estudio.compilar(claude, cfg, todos)

    # 6. Render final
    videos = []
    for variante, ruta_plan in rutas_plan.items():
        crudo = trabajo / f"{variante}_crudo.mp4"
        ok, salida = render.renderizar(ruta_plan, crudo)
        if not ok:
            culpable = render.escena_con_error(salida, todos)
            if not culpable:
                raise RuntimeError("Falló el render:\n" + salida[-2000:])
            estudio.usar_respaldo(culpable)
            estudio.compilar(claude, cfg, todos)
            ok, salida = render.renderizar(ruta_plan, crudo)
            if not ok:
                raise RuntimeError("Falló el render:\n" + salida[-2000:])
        final = trabajo / f"{variante}.mp4"
        render.preparar_para_facebook(crudo, final)
        videos.append(final)

    # 7. Guardar como pendiente y pedir aprobación
    notas_num = [float(v.get("nota", 0)) for v in notas.values() if v.get("nota") is not None]
    nota_media = round(sum(notas_num) / len(notas_num), 1) if notas_num else None
    est = estado()
    est["pendientes"][id_video] = {
        "titulo": guion["titulo"],
        "descripcion": guion.get("descripcion", ""),
        "hashtags": cfg["publicacion"].get("hashtags", []),
        "tema": tema["tema"],
        "subtema": tema.get("subtema", ""),
        "estructura": estilo["estructura"],
        "paleta": estilo["paleta"],
        "tipo_gancho": estilo["tipo_gancho"],
        "tipo_gancho_b": guion.get("gancho_b", {}).get("tipo", ""),
        "ganchos": {"A": guion["escenas"][0]["voz"], "B": guion.get("gancho_b", {}).get("voz", "")},
        "nota_media": nota_media,
        "creado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    guardar_estado(est)

    if not cfg["aprobacion"]["activa"]:
        publicar(id_video, "A", videos[0])
        telegram.aviso_seguro(f"Publicado solo: «{guion['titulo']}»")
        return

    subir_pendiente(id_video, videos, guion["titulo"])
    cambios = guion.get("verificacion", {}).get("cambios", [])
    resumen = (f"Nuevo video: «{guion['titulo']}»\nTema: {tema['tema']}\n"
               f"Nota del revisor: {nota_media}\n"
               f"Verificación de datos: {guion.get('verificacion', {}).get('confianza', 'sin dato')}"
               + (f" ({len(cambios)} correcciones)" if cambios else ""))
    for video_ruta in videos:
        v = video_ruta.stem
        telegram.video(video_ruta, f"Versión {v}. Gancho: «{est['pendientes'][id_video]['ganchos'][v]}»")
    botones = [[{"text": f"Publicar {v.stem}", "callback_data": f"pub:{id_video}:{v.stem}"} for v in videos],
               [{"text": "Rehacer otro", "callback_data": f"rehacer:{id_video}"},
                {"text": "Descartar", "callback_data": f"descartar:{id_video}"}]]
    telegram.mensaje(resumen, botones)

    # Liberar espacio: los videos ya están guardados como release
    shutil.rmtree(trabajo / "voz", ignore_errors=True)

    # Quedarse escuchando los botones para publicar al instante (sin esperar al reloj de GitHub)
    limite = cfg["produccion"].get("tiempo_maximo_min", 90) - 6
    minutos = min(cfg["aprobacion"].get("escuchar_minutos", 30), limite - (time.monotonic() - INICIO) / 60)
    if minutos > 2:
        telegram.aviso_seguro(f"Toca un botón en los próximos {int(minutos)} minutos y lo hago al momento. "
                              "Después también funciona, pero puede tardar hasta una hora.")
        from .aprobaciones import escuchar
        escuchar(minutos)


if __name__ == "__main__":
    from .claude import LimiteDeSuscripcion
    try:
        producir()
    except LimiteDeSuscripcion as e:
        telegram.aviso_seguro(f"No se hizo el video de hoy: {e}")
        raise
    except Exception:
        error = traceback.format_exc()
        print(error)
        telegram.aviso_seguro("El bot falló al producir el video:\n" + error[-1500:])
        raise

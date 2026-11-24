"""Produce un video completo: tema, guion, voz, escenas, revisión, render y aprobación.

Uso: python -m bot.producir
"""
import json
import os
import shutil
import subprocess
import time
import traceback
from concurrent.futures import ThreadPoolExecutor

INICIO = time.monotonic()
from datetime import datetime, timedelta, timezone

from . import estadisticas, estudio, render, revisor, sfx, telegram
from .claude import Claude
from . import config
from .config import DATOS, PUBLICO, SALIDA, cargar_config
from .director import elegir_tema, sortear_estilo
from .guionista import escribir_guion, pulir_gancho, verificar_guion
from .memoria import estado, guardar_estado, memoria
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


# Escenarios según el tema (los Reels ganadores llenan la pantalla con un lugar que va con el tema).
# El escenario cambia con cada video; los COLORES de cada escenario los pone la página
# (estilo.escenarios en su archivo), para que todos sus videos tengan la misma paleta.
ESCENARIOS = {
    "cielo": {"fondo": "#9CCDF2", "suelo": "#7DBE4E",
              "degradado": "linear-gradient(180deg, #3C8DDE 0%, #6FB2EC 38%, #B9DDF7 72%, #D9EEFB 100%)"},
    "exterior": {"fondo": "#D7E6EF", "suelo": "#D3CDC1",
                 "degradado": "linear-gradient(180deg, #8FC0E6 0%, #C4DEEF 45%, #EAF1F2 80%, #F1EEE6 100%)"},
    "interior": {"fondo": "#EFE6D8", "suelo": "#C9A27A",
                 "degradado": "radial-gradient(ellipse 70% 55% at 30% 25%, #FFF8EC 0%, #EFE6D8 50%, #D9CBB5 100%)",
                 "foco": "#FFE9C4"},
    "oscuro": {"fondo": "#121318", "suelo": "#1C1D25", "tinta": "#F2EFE9", "foco": "#FFE0B0"},
    "estudio": {},
}
_CLAVES_ESCENARIO = ("fondo", "suelo", "tinta", "degradado", "foco")


def escenarios(cfg: dict | None = None) -> dict:
    """Los escenarios con los colores de la página (lo que no ponga la página queda igual)."""
    propios = ((cfg or {}).get("estilo") or {}).get("escenarios") or {}
    return {n: {**base, **{k: v for k, v in (propios.get(n) or {}).items() if k in _CLAVES_ESCENARIO and v}}
            for n, base in ESCENARIOS.items()}


def escenario_de(guion: dict, cfg: dict | None = None) -> str:
    fijo = ((cfg or {}).get("estilo") or {}).get("escenario_fijo")
    if fijo in ESCENARIOS:
        return fijo
    e = str((guion.get("direccion_arte") or {}).get("escenario", "")).strip().lower()
    return e if e in ESCENARIOS else "estudio"


def paleta_con_escenario(colores: dict, escenario: str, cfg: dict | None = None) -> dict:
    cambio = escenarios(cfg).get(escenario, {})
    paleta = {**colores, "acentos": list(colores["acentos"])}
    if cambio.get("fondo"):
        paleta["fondo"] = cambio["fondo"]
    if cambio.get("tinta"):
        paleta["tinta"] = cambio["tinta"]
    if cambio.get("suelo"):
        while len(paleta["acentos"]) < 5:
            paleta["acentos"].append(paleta["acentos"][-1])
        paleta["acentos"][4] = cambio["suelo"]
    return paleta


def acabado_de(cfg: dict | None = None) -> dict:
    """Estilo de animación de la página: dibujo (contorno y sombreado de caricatura) o plastilina."""
    estilo = (cfg or {}).get("estilo") or {}
    acabado = str(estilo.get("acabado", "dibujo")).strip().lower()
    return {"acabado": acabado if acabado in ("dibujo", "plastilina") else "dibujo",
            "color_contorno": estilo.get("color_contorno") or "#1B1B1F"}


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
                        "grafico": grafico_valido(fuente.get("grafico")),
                        "concepto": (fuente.get("concepto") or "").strip()[:40]})
    return {
        "motor": cfg["produccion"].get("motor", "2d"),
        "audio": tiempos_variante["audio"],
        "musica": cfg["produccion"].get("musica", "") or "",
        "subtitulos": cfg["produccion"].get("subtitulos", True),
        "paleta": paleta_con_escenario(estilo["colores"], escenario_de(guion, cfg), cfg),
        "escenario": escenario_de(guion, cfg),
        "fondo_css": escenarios(cfg)[escenario_de(guion, cfg)].get("degradado", ""),
        "foco": escenarios(cfg)[escenario_de(guion, cfg)].get("foco", ""),
        **acabado_de(cfg),
        "portada": (guion.get("portada") or "").upper()[:60],
        "escenas": escenas,
        # Un solo mundo que evoluciona (si se pudo dibujar el mundo compartido)
        "continuo": bool(estudio.MUNDO["activo"]) and cfg["produccion"].get("motor") == "3d",
        "estilo_subtitulos": cfg["produccion"].get("subtitulos_estilo", "concepto"),
    }


def _hashtags(guion: dict, cfg: dict) -> list:
    """3 a 5 hashtags específicos del tema (mejor que genéricos); si faltan, los del canal."""
    propios = [("#" + str(h).lstrip("#").replace(" ", "")) for h in guion.get("hashtags", []) if str(h).strip()]
    return (propios[:5] if len(propios) >= 3 else propios + cfg["publicacion"].get("hashtags", []))[:5]


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


def _revisar(cfg, claude, planes, rutas_plan, trabajo, guion, todos, codigos, dibujar_una, nota_min, notas):
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
        notas.clear()
        notas.update({k: v for k, v in resultado.get("escenas", {}).items() if k in todos})
        print(f"Ronda {ronda}: notas", {k: v.get("nota") for k, v in notas.items()})
        flojas = {k: v for k, v in notas.items() if float(v.get("nota", 10)) < nota_min}
        # Para no gastar de más: como mucho las 4 peores por ronda
        flojas = dict(sorted(flojas.items(), key=lambda kv: float(kv[1].get("nota", 10)))[:4])
        if not flojas or ronda == cfg["claude"]["rondas_revision"]:
            break
        with ThreadPoolExecutor(max_workers=4) as hilos:
            fotos_por_nombre = {f["nombre"]: f["ruta"] for f in fotos}
            rehechas = hilos.map(lambda kv: dibujar_una(kv[0], kv[1].get("problemas", ""),
                                                        codigos.get(kv[0], ""), fotos_por_nombre.get(kv[0])),
                                 flojas.items())
            codigos.update(dict(rehechas))
        estudio.compilar(claude, cfg, todos)


def producir():
    cfg = cargar_config()
    try:  # elegir la voz escuchando (una vez por página; no frena el video si falla)
        from . import voces
        voces.ofrecer_si_toca(cfg)
    except Exception as e:  # noqa: BLE001
        print("No se pudieron ofrecer las voces:", e)
    claude = Claude()
    id_video = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    trabajo = SALIDA / id_video
    trabajo.mkdir(parents=True, exist_ok=True)
    sfx.generar()
    from .autocontrol import ESTADO_VIDEO
    ESTADO_VIDEO.update(cobertura_voz=None, respaldos=[])
    preparar_motor(cfg, trabajo)
    from . import reanudar
    avance = reanudar.empezar()
    if avance.get("reanudado"):
        telegram.aviso_seguro("Se renovó el límite de Claude: sigo con el video que quedó a medias"
                              + (f" («{avance['guion']['titulo']}»)." if avance.get("guion") else "."))

    try:
        estadisticas.actualizar()
    except Exception as e:  # noqa: BLE001
        print("Aviso: no se actualizaron métricas:", e)
    try:
        from .aprobaciones import caducar_pendientes
        caducar_pendientes()
    except Exception as e:  # noqa: BLE001
        print("Aviso: no se revisaron los pendientes viejos:", e)

    # 1. Director: primero, si hay una parte de serie pendiente o un video que despegó, va eso
    from . import series
    try:
        exito = series.detectar_exitos(cfg)
        if exito:
            telegram.aviso_seguro(f"«{exito['serie']}» despegó: el próximo video será su parte 2.")
    except Exception as e:  # noqa: BLE001
        print("Aviso: no se pudo revisar si algún video despegó:", e)
    from . import aprendizaje
    from .director import _hoy
    if not avance.get("reanudado"):
        aprendizaje.actualizar_lecciones(claude, cfg)
    # Si este video reemplaza a uno cancelado: más exigente y con otro tema
    reemplazo = None if avance.get("reanudado") else estado().get("reemplazo")
    if reemplazo:
        cfg["claude"]["rondas_revision"] = cfg["claude"]["rondas_revision"] + 1
        cfg["claude"]["nota_minima"] = cfg["claude"]["nota_minima"] + 0.5
        if cfg["claude"].get("nota_para_publicar"):
            cfg["claude"]["nota_para_publicar"] += 0.5
        cfg["canal"]["prohibidos"] = cfg["canal"]["prohibidos"] + [
            f"el tema del video que se canceló: «{reemplazo.get('titulo_cancelado', '')}» ({reemplazo.get('tema_cancelado', '')}) ni nada parecido"]
        e = estado()
        e.pop("reemplazo", None)
        guardar_estado(e)
    estilo = avance.get("estilo") or sortear_estilo(cfg)
    parte = None if (reemplazo or avance.get("tema")) else series.siguiente(cfg)
    if parte:
        parte["_hoy"] = _hoy(cfg)
    if parte:
        estilo["estructura"] = parte.get("estructura") or estilo["estructura"]
        tema = {"tema": parte["tema"], "angulo": parte.get("angulo", ""), "subtema": parte.get("subtema", ""),
                "tendencia": parte.get("tendencia", ""), "serie": parte}
    elif avance.get("tema"):
        tema = avance["tema"]
    else:
        tema = elegir_tema(claude, cfg, estilo)
    avance.update(tema=tema, estilo=estilo)
    print("Tema:", tema)

    # 2. Guion verificado
    if avance.get("guion"):
        guion = avance["guion"]
    else:
        guion = verificar_guion(claude, pulir_gancho(claude, cfg, escribir_guion(claude, cfg, tema, estilo)))
        guion["escenas"] = guion["escenas"][: cfg["produccion"]["escenas_max"]]
        if tema.get("serie"):
            n, total = tema["serie"]["parte"], tema["serie"]["total"]
            if f"parte {n}" not in guion["titulo"].lower():
                guion["titulo"] = f"{guion['titulo']} (Parte {n})"[:80]
        series.registrar(guion, tema, estilo)
        series.avanzar(guion, tema)
        avance["guion"] = guion
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

    # 4a. Mundo compartido: el lugar y el protagonista que evolucionan en todas las escenas
    if cfg["produccion"].get("motor") == "3d" and cfg["produccion"].get("mundo_continuo", True):
        from .claude import LimiteDeSuscripcion as _Limite
        if avance["escenas"].get("Mundo"):
            estudio.guardar_mundo(avance["escenas"]["Mundo"])
        else:
            for intento_mundo in range(2):
                try:
                    print("Dibujando el mundo compartido")
                    avance["escenas"]["Mundo"] = estudio.dibujar_mundo(claude, cfg, guion, estilo)
                    break
                except _Limite:
                    raise
                except Exception as e:  # noqa: BLE001  (sin mundo, cada escena va por su cuenta)
                    print(f"No se pudo dibujar el mundo compartido (intento {intento_mundo + 1}):", e)
                    estudio.MUNDO.update(activo=False, codigo="")
                    avance["escenas"].pop("Mundo", None)

    def dibujar_una(nombre, comentarios="", previo="", foto=None):
        esc, t, i = datos_escena(nombre)
        guardado = avance["escenas"].get(nombre)
        if guardado and not comentarios:  # ya se dibujó antes de que se acabara el límite
            (estudio.ESCENAS / f"{nombre}.tsx").write_text(guardado, encoding="utf-8")
            return nombre, guardado
        print("Dibujando", nombre)
        codigo = estudio.dibujar(claude, cfg, nombre, esc, t, guion, i, estilo,
                                 comentarios=comentarios, codigo_previo=previo, foto=foto)
        avance["escenas"][nombre] = codigo
        return nombre, codigo

    # Se dibujan varias escenas a la vez para ahorrar tiempo.
    with ThreadPoolExecutor(max_workers=4) as hilos:
        codigos = dict(hilos.map(dibujar_una, todos))
    estudio.escribir_indice(todos)
    estudio.compilar(claude, cfg, todos)

    def armar_planes():
        pl = {"A": armar_plan(cfg, tiempos["A"], nombres_a, guion, estilo, "A")}
        if hay_b and "B" in tiempos:
            pl["B"] = armar_plan(cfg, tiempos["B"], nombres_b, guion, estilo, "B")
        return pl, {v: render.guardar_plan(p, v) for v, p in pl.items()}

    planes, rutas_plan = armar_planes()

    from .claude import LimiteDeSuscripcion

    def compilar_seguro():
        """Compila; si ya no queda uso de Claude, cambia por respaldo las escenas que fallen."""
        try:
            estudio.compilar(claude, cfg, todos)
        except LimiteDeSuscripcion:
            for _ in range(len(todos)):
                ok, salida = render.empaquetar()
                culpable = None if ok else render.escena_con_error(salida, estudio.con_mundo(todos))
                if ok or not culpable:
                    return
                estudio.usar_respaldo(culpable)

    # 5. Revisor: mira fotogramas reales y pide rehacer lo flojo
    nota_min = cfg["claude"]["nota_minima"]
    notas = {}
    try:
        _revisar(cfg, claude, planes, rutas_plan, trabajo, guion, todos, codigos, dibujar_una, nota_min, notas)
    except LimiteDeSuscripcion:
        telegram.aviso_seguro("Se acabó el límite de uso de Claude a mitad de la revisión; "
                              "termino el video con las escenas que ya están hechas.")
        compilar_seguro()

    # 6. Render final
    def renderizar_todo():
      videos = []
      for variante, ruta_plan in rutas_plan.items():
          crudo = trabajo / f"{variante}_crudo.mp4"
          ok, salida = render.renderizar(ruta_plan, crudo)
          if not ok:
              culpable = render.escena_con_error(salida, estudio.con_mundo(todos))
              if not culpable:
                  raise RuntimeError("Falló el render:\n" + salida[-2000:])
              estudio.usar_respaldo(culpable)
              estudio.compilar(claude, cfg, todos)
              ok, salida = render.renderizar(ruta_plan, crudo)
              if not ok:
                  raise RuntimeError("Falló el render:\n" + salida[-2000:])
          final = trabajo / f"{variante}.mp4"
          pista = render.elegir_musica(PUBLICO / "musica", len(memoria()))
          render.preparar_para_facebook(crudo, final, pista, cfg["produccion"].get("volumen_musica", 0.16))
          videos.append(final)
      return videos

    videos = renderizar_todo()

    # 6b. Control de calidad del video terminado: errores -> reglas para los próximos
    from . import autocontrol
    def momentos_voz():
        return [(e["inicio"], e["duracion"], guion["escenas"][k]["voz"] if k < len(guion["escenas"]) else "")
                for k, e in enumerate(planes["A"]["escenas"])]

    control = autocontrol.revisar_video(claude, guion, videos[0], PUBLICO / tiempos["A"]["audio"],
                                        tiempos["A"]["total"], trabajo, momentos=momentos_voz())
    aprendidas = len(control["nuevas"])

    # 6c. Arreglo automático: si hay errores graves, se corrige solo, se vuelve a revisar y sigue
    arreglos = []
    for intento in range(int(cfg["claude"].get("intentos_arreglo", 2))):
        if not control["graves"]:
            break
        quedan = cfg["produccion"].get("tiempo_maximo_min", 170) - (time.monotonic() - INICIO) / 60
        if quedan < 35:
            print(f"Quedan {quedan:.0f} min: no da tiempo a otro arreglo.")
            break
        graves = control["graves"]
        print(f"Arreglo {intento + 1}: errores graves", [g["problema"] for g in graves])
        hecho = []
        try:
            # Voz: se narra de nuevo (en el segundo intento, con la voz de respaldo)
            if any(g.get("area") == "voz" for g in graves):
                if intento >= 1:
                    cfg["produccion"]["voz_motor"] = "edge"
                ESTADO_VIDEO["cobertura_voz"] = None
                try:
                    tiempos = narrar_guion(guion, cfg, trabajo / "voz", PUBLICO)
                except ValueError:
                    cfg["produccion"]["velocidad_voz"] = "+18%"
                    tiempos = narrar_guion(guion, cfg, trabajo / "voz", PUBLICO)
                planes, rutas_plan = armar_planes()
                hecho.append("rehice la voz")
            # Imagen: se rehacen las escenas donde se vio el error
            visuales = [g for g in graves if g.get("area") != "voz"]
            if visuales:
                por_escena = {}
                escenas_a = planes["A"]["escenas"]
                for g in visuales:
                    nombre = None
                    seg = g.get("segundo")
                    if isinstance(seg, (int, float)):
                        for e in escenas_a:
                            if e["inicio"] - 0.3 <= seg < e["inicio"] + e["duracion"]:
                                nombre = e["componente"]
                    if not nombre:  # sin momento: la escena peor puntuada
                        peores = sorted(notas.items(), key=lambda kv: float(kv[1].get("nota", 10)))
                        nombre = peores[0][0] if peores else escenas_a[0]["componente"]
                    texto = f"ERROR GRAVE en el video terminado: {g['problema']}. Regla: {g.get('regla', '')}."
                    if g.get("area") == "edicion":
                        texto += (" Los subtítulos van en la franja inferior y el título arriba: deja esas "
                                  "zonas libres de cosas importantes y de etiquetas, y nada pegado a los bordes.")
                    por_escena.setdefault(nombre, []).append(texto)
                por_escena = dict(list(por_escena.items())[:4])
                with ThreadPoolExecutor(max_workers=4) as hilos:
                    def rehacer(kv):
                        foto = trabajo / "fotos" / f"{kv[0]}.png"
                        return dibujar_una(kv[0], " ".join(kv[1]), codigos.get(kv[0], ""),
                                           foto if foto.exists() else None)
                    codigos.update(dict(hilos.map(rehacer, por_escena.items())))
                compilar_seguro()
                hecho.append("rehice " + ", ".join(n.replace("Escena", "la escena ") for n in por_escena))
            videos = renderizar_todo()
            control = autocontrol.revisar_video(claude, guion, videos[0], PUBLICO / tiempos["A"]["audio"],
                                                tiempos["A"]["total"], trabajo, aprender=False,
                                                momentos=momentos_voz())
        except LimiteDeSuscripcion:
            print("Se acabó el límite de Claude durante el arreglo.")
            break
        except Exception as e:  # noqa: BLE001
            print("El arreglo falló:", e)
            telegram.aviso_seguro(f"No pude terminar un arreglo ({str(e)[:300]}); sigo con la mejor versión.")
            break
        arreglos.append(" y ".join(hecho))

    if control["problemas"] or arreglos:
        lineas = [f"- {p['problema']}" for p in control["problemas"][:6]]
        aviso = ("Control de calidad de este video:\n" + "\n".join(lineas)) if lineas else "Control de calidad:"
        if arreglos:
            aviso += "\nArreglé solo: " + "; ".join(arreglos) + "."
            aviso += (" Ya no quedan errores graves." if not control["graves"]
                      else " Aún queda algún error grave, pero lo publico igual.")
        if aprendidas:
            aviso += f"\nAprendí {aprendidas} regla(s) nueva(s) para no repetirlo."
        telegram.aviso_seguro(aviso)

    # 7. Guardar como pendiente y pedir aprobación
    notas_num = [float(v.get("nota", 0)) for v in notas.values() if v.get("nota") is not None]
    nota_media = round(sum(notas_num) / len(notas_num), 1) if notas_num else None
    est = estado()
    est["pendientes"][id_video] = {
        "titulo": guion["titulo"],
        "descripcion": (guion.get("descripcion", "").strip()
                        + (("\n\n" + guion["pregunta_comentarios"].strip()) if guion.get("pregunta_comentarios") else "")),
        "hashtags": _hashtags(guion, cfg),
        "duracion": tiempos["A"]["total"],
        "tema": tema["tema"],
        "tendencia": tema.get("tendencia", ""),
        "serie": ({"titulo": tema["serie"]["serie"], "parte": tema["serie"]["parte"], "total": tema["serie"]["total"]}
                  if tema.get("serie") else ({"titulo": guion["serie"].get("titulo", ""), "parte": 1,
                                              "total": guion["serie"].get("total", 2)} if guion.get("serie") else None)),
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

    # Un video roto (escenas vacías, nota muy baja) no se publica nunca: se descarta y se hace otro.
    piso = cfg["claude"].get("nota_para_descartar", 4)
    if not cfg["aprobacion"]["activa"] and isinstance(nota_media, (int, float)) and nota_media < piso:
        e = estado()
        e["pendientes"].pop(id_video, None)
        guardar_estado(e)
        reanudar.terminar()
        hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        e = estado()
        cuenta = e.get("descartes", {}) if e.get("descartes", {}).get("dia") == hoy else {"dia": hoy, "n": 0}
        cuenta["n"] = cuenta.get("n", 0) + 1
        e["descartes"] = cuenta
        guardar_estado(e)
        otro = cuenta["n"] <= cfg["claude"].get("descartes_por_dia", 2)
        telegram.aviso_seguro(
            f"Descarté «{guion['titulo']}»: salió muy mal (nota {nota_media}"
            + (f": {revisor.ULTIMO_COMENTARIO}" if revisor.ULTIMO_COMENTARIO else "")
            + ("). No lo publico; ya empecé otro video para ese horario." if otro else
               "). No lo publico. Ya van varios descartes hoy, así que no rehago otro para no gastar "
               "el límite de Claude: sigo en el próximo horario."))
        if otro:
            e = estado()
            e["rehacer_turno"] = True
            guardar_estado(e)
        return

    minima = cfg["claude"].get("nota_para_publicar", 0)
    publicar_igual = cfg["claude"].get("publicar_si_no_se_arregla", True)
    floja = (isinstance(nota_media, (int, float)) and nota_media < minima) or \
        (bool(control["graves"]) and not publicar_igual)
    if not cfg["aprobacion"]["activa"] and floja:
        motivo = ("tiene un error grave: " + control["graves"][0]["problema"]) if control["graves"] \
            else f"sacó {nota_media} (mínimo {minima})"
        telegram.aviso_seguro(f"Este video {motivo}, así que no lo publico solo. Míralo y decide; "
                              "el error ya quedó apuntado para no repetirlo.")
    if not cfg["aprobacion"]["activa"] and not floja:
        from . import horarios, meta
        # El horario que le tocaba a esta producción (según cuándo empezó). Si ya pasó (por ejemplo,
        # porque se esperó a que se renovara el límite de Claude), se publica en el momento.
        cuando = horarios.proximo(cfg, reanudar.inicio())
        if cuando <= datetime.now(timezone.utc) + timedelta(minutes=12):
            cuando = None
        try:
            video_fb = publicar(id_video, "A", videos[0], cuando)
        except Exception as e:  # noqa: BLE001  (sin conexión, token vencido...): el video no se pierde
            print("No se pudo publicar:", e)
            reanudar.terminar()
            subir_pendiente(id_video, videos, guion["titulo"])
            telegram.video(videos[0], f"«{guion['titulo']}»")
            telegram.mensaje(f"No pude publicar «{guion['titulo']}» en Facebook: {str(e)[:400]}\n"
                             "Lo dejé guardado. Cuando esté resuelto, toca Publicar.",
                             [[{"text": "Publicar", "callback_data": f"pub:{id_video}:A"}],
                              [{"text": "Descartar", "callback_data": f"descartar:{id_video}"}]])
            return
        reanudar.terminar()
        if meta.ULTIMA.get("programado"):
            aviso = f"Programado para {horarios.texto(cuando)}: «{guion['titulo']}»"
            if tema.get("tendencia"):
                aviso += f"\nTendencia: {tema['tendencia']}"
        elif cuando is None:
            aviso = f"Publicado ya (su horario ya había pasado): «{guion['titulo']}»"
        else:
            aviso = f"Publicado ya (Facebook no aceptó programarlo): «{guion['titulo']}»"
        nota = f"\nNota del revisor: {nota_media}" + (f" · {revisor.ULTIMO_COMENTARIO}" if revisor.ULTIMO_COMENTARIO else "")
        telegram.video(videos[0], aviso)
        telegram.mensaje(aviso + nota + "\nSi no te gusta, puedes cancelarlo:",
                         [[{"text": "Cancelar publicación", "callback_data": f"borrar:{video_fb}"}]])
        return

    reanudar.terminar()
    subir_pendiente(id_video, videos, guion["titulo"])
    cambios = guion.get("verificacion", {}).get("cambios", [])
    resumen = (f"Nuevo video: «{guion['titulo']}»\nTema: {tema['tema']}\n"
               f"Nota del revisor: {nota_media}\n"
               + (f"Opinión del revisor: {revisor.ULTIMO_COMENTARIO}\n" if revisor.ULTIMO_COMENTARIO else "")
               + 
               f"Verificación de datos: {guion.get('verificacion', {}).get('confianza', 'sin dato')}"
               + (f" ({len(cambios)} correcciones)" if cambios else ""))
    for video_ruta in videos:
        v = video_ruta.stem
        nombre_version = f"Versión {v}. " if len(videos) > 1 else ""
        telegram.video(video_ruta, f"{nombre_version}Gancho: «{est['pendientes'][id_video]['ganchos'][v]}»")
    botones = [[{"text": f"Publicar {v.stem}" if len(videos) > 1 else "Publicar",
                 "callback_data": f"pub:{id_video}:{v.stem}"} for v in videos],
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


def _guardar_avance_en_repo(mensaje: str = "Memoria: avance guardado por límite de Claude") -> bool:
    """Sube data/ al repo. Si otra tarea cambió los datos a la vez (conflicto), los une quedándose
    con lo de esta tarea en lo que choque, y comprueba que los archivos sigan siendo válidos."""
    def git(*a):
        return subprocess.run(["git", *a], check=False, capture_output=True, text=True)

    if git("rev-parse", "--is-inside-work-tree").returncode != 0:
        return False
    firma = ["-c", "user.name=bot-explicativos", "-c", "user.email=bot@users.noreply.github.com"]
    git("add", "data")
    git(*firma, "commit", "-q", "-m", mensaje)
    rama = git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip() or "main"
    for _ in range(3):
        if git("pull", "-q", "--rebase", "--autostash").returncode != 0:
            git("rebase", "--abort")
            copia = {f: f.read_bytes() for f in config.DATOS_PRINCIPAL.rglob("*.json")}
            git("fetch", "-q", "origin", rama)
            if git(*firma, "merge", "-q", "-X", "ours", "--no-edit", f"origin/{rama}").returncode != 0:
                git("merge", "--abort")
                continue
            for f, contenido in copia.items():  # un JSON roto por la unión se cambia por el nuestro
                try:
                    json.loads(f.read_text(encoding="utf-8"))
                except (ValueError, OSError):
                    f.write_bytes(contenido)
            git("add", "data")
            git(*firma, "commit", "-q", "-m", mensaje + " (unido)")
        if git("push", "-q").returncode == 0:
            return True
    print("No se pudo subir data/ al repo")
    return False


def _relanzar_produccion() -> bool:
    """Lanza la siguiente tarea de la cadena (queda en fila hasta que termine esta)."""
    for _ in range(3):
        r = subprocess.run(["gh", "workflow", "run", "bot.yml", "-f", "tarea=producir"], check=False,
                           capture_output=True, text=True)
        if getattr(r, "returncode", 0) == 0:
            return True
        print("No se pudo lanzar la siguiente tarea:", (getattr(r, "stderr", "") or "")[-300:])
        time.sleep(20)
    telegram.aviso_seguro("No pude dejar lanzada la siguiente tarea del bot en GitHub. El vigilante o los "
                          "horarios fijos la retomarán; si en unas horas no hay videos, entra a Actions y "
                          "ejecuta «producir».")
    return False


def _latido():
    """Marca que hay una tarea viva (el vigilante relanza la cadena si deja de latir)."""
    from .memoria import cadena, guardar_cadena
    c = cadena()
    c["latido"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    guardar_cadena(c)
    _guardar_avance_en_repo("Memoria: el bot sigue trabajando")


def _atender_botones():
    """Atiende los botones de Telegram (cancelar, elegir voz...) sin esperar a la revisión periódica."""
    try:
        from . import aprobaciones
        aprobaciones.procesar(espera=0, caducar=False)
    except Exception as e:  # noqa: BLE001
        print("No se pudieron revisar los botones de Telegram:", e)


def _dormir(esperar, minutos: float):
    """Espera en tramos de 10 minutos, atendiendo los botones de Telegram y dando señales de vida."""
    restante = max(0.0, minutos)
    vueltas = 0
    while restante > 0:
        tramo = min(10.0, restante)
        esperar(tramo * 60)
        restante -= tramo
        vueltas += 1
        _atender_botones()
        if restante > 0 and vueltas % 3 == 0:
            _latido()


# ---------- Turnos de producción (de todas las páginas) ----------
def _lista_turnos(cfg: dict) -> list[tuple[str, str]]:
    """(hora RD, página) de cada turno. Las páginas sin configurar o sin secretos no tienen turno."""
    turnos = cfg["produccion"].get("turnos")
    if not turnos:
        horas = cfg["produccion"].get("horas_produccion", ["03:17", "09:17", "15:17"])
        turnos = [{"hora": h, "canal": config.PRINCIPAL} for h in horas]
    disponibles = set(config.canales())
    lista = [(t["hora"], t.get("canal", config.PRINCIPAL)) for t in turnos]
    lista = [(h, c) for h, c in lista if c in disponibles and config.canal_listo(c)]
    return lista or [(t["hora"], config.PRINCIPAL) for t in turnos]


def _turnos(cfg: dict, ahora: datetime):
    """Turnos alrededor de `ahora`, del más viejo al más nuevo: [(momento, página)]."""
    from .horarios import _zona
    zona = _zona(cfg)
    local = ahora.astimezone(zona)
    lista = []
    for dias in (-1, 0, 1):
        f = (local + timedelta(days=dias)).date()
        for h, canal in _lista_turnos(cfg):
            hh, mm = (int(x) for x in h.split(":"))
            lista.append((datetime(f.year, f.month, f.day, hh, mm, tzinfo=zona), canal))
    return sorted(lista)


def _id_turno(momento: datetime, canal: str) -> str:
    base = momento.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M")
    return base if canal == config.PRINCIPAL else f"{canal}@{base}"


def turno_actual(cfg: dict, ahora: datetime | None = None) -> tuple[datetime, str, str]:
    """(momento, id, página) del último turno que ya empezó."""
    ahora = ahora or datetime.now(timezone.utc)
    t, canal = max(x for x in _turnos(cfg, ahora) if x[0] <= ahora)
    return t, _id_turno(t, canal), canal


def proximo_turno(cfg: dict, ahora: datetime | None = None) -> datetime:
    ahora = ahora or datetime.now(timezone.utc)
    return min(x for x in _turnos(cfg, ahora) if x[0] > ahora)[0]


def _a_medias() -> tuple[str, str] | None:
    """(página, id del turno) de un video que quedó a medias, en cualquier página."""
    for canal in config.canales():
        archivo = config.ruta_datos(canal) / "en_curso.json"
        if archivo.exists() and config.canal_listo(canal):
            try:
                inicio = datetime.fromisoformat(json.loads(archivo.read_text())["inicio"])
            except (ValueError, KeyError, OSError):
                inicio = datetime.now(timezone.utc)
            momento = max((x for x in _turnos(cargar_config(config.PRINCIPAL), inicio)
                           if x[0] <= inicio and x[1] == canal), default=(inicio, canal))[0]
            return canal, _id_turno(momento, canal)
    return None


def _esperar_turno(esperar, arranque: float, tope: float, necesita: float, cfg: dict):
    """Decide qué toca. Devuelve (página, turno) a producir, o None si pasó el relevo.

    - Hay un video a medias (en cualquier página): se sigue con él.
    - El turno de ahora aún no tiene video: se hace ya (aunque sea tarde).
    - Si ya está hecho: se espera al próximo turno aquí mismo, o se pasa el relevo si no cabe."""
    from .memoria import cadena
    medias = _a_medias()
    if medias:
        return medias
    _, id_turno, canal = turno_actual(cfg)
    if cadena().get("turno_hecho") != id_turno:
        return canal, id_turno
    siguiente = proximo_turno(cfg)
    falta = (siguiente - datetime.now(timezone.utc)).total_seconds() / 60
    usado = (time.monotonic() - arranque) / 60
    if usado + falta + necesita <= tope:
        print(f"El turno de ahora ya está hecho; espero {falta:.0f} min al siguiente.")
        _dormir(esperar, falta + 1)
        _, id_sig, canal_sig = turno_actual(cfg, siguiente + timedelta(minutes=1))
        return canal_sig, id_sig
    margen = max(0.0, min(falta, tope - usado - 10))
    print(f"El siguiente turno es en {falta:.0f} min: espero {margen:.0f} y paso el relevo.")
    _dormir(esperar, margen)
    _relanzar_produccion()
    return None


# ---------- Producción continua (cola de videos programados) ----------
def _cola(canal: str, ahora: datetime | None = None) -> list[datetime]:
    """Horas de publicación ya programadas a futuro en una página."""
    ahora = ahora or datetime.now(timezone.utc)
    archivo = config.ruta_datos(canal) / "memoria.json"
    try:
        items = json.loads(archivo.read_text(encoding="utf-8")) if archivo.exists() else []
    except ValueError:
        items = []
    horas = []
    for m in items:
        if m.get("publicado_en") and not m.get("cancelado"):
            try:
                t = datetime.fromisoformat(m["publicado_en"])
            except ValueError:
                continue
            if t > ahora:
                horas.append(t)
    return sorted(horas)


def _esperar_trabajo(esperar, arranque: float, tope: float, necesita: float, cfg: dict):
    """Modo continuo: elige la página que necesita video (la de menos videos en cola) y lo hace ya.
    Si todas tienen la cola llena, espera a que se publique el siguiente (o pasa el relevo).
    Devuelve (página, id) o None si pasó el relevo."""
    medias = _a_medias()
    if medias:
        return medias
    maximo = int(cfg["produccion"].get("cola_maxima", 5))
    paginas = [c for c in config.canales() if config.canal_listo(c)]
    ahora = datetime.now(timezone.utc)
    colas = {c: _cola(c, ahora) for c in paginas}
    canal = min(paginas, key=lambda c: (len(colas[c]), paginas.index(c)))
    if len(colas[canal]) < maximo:
        return canal, f"{canal}@{ahora:%Y-%m-%dT%H:%M}"
    # Todas llenas: se espera a que salga el próximo video programado (hay hueco de nuevo)
    libera = min(paginas, key=lambda c: colas[c][0])  # la página cuyo próximo video sale antes
    proximo = colas[libera][0]
    falta = max(1.0, (proximo - ahora).total_seconds() / 60 + 1)
    usado = (time.monotonic() - arranque) / 60
    if usado + falta + necesita <= tope:
        print(f"Todas las páginas tienen {maximo} videos en cola; espero {falta:.0f} min.")
        _dormir(esperar, falta)
        # Ya salió ese video: su página tiene hueco
        return libera, f"{libera}@{datetime.now(timezone.utc):%Y-%m-%dT%H:%M}"
    margen = max(0.0, min(falta, tope - usado - 10))
    print(f"Colas llenas: espero {margen:.0f} min y paso el relevo.")
    _dormir(esperar, margen)
    _relanzar_produccion()
    return None


def _esperar_renovacion(esperar, arranque: float, tope: float, necesita: float) -> bool:
    """Si el límite de Claude está agotado (es el mismo para todas las páginas), espera aquí mismo.

    True = ya es hora: seguir produciendo en esta tarea.
    False = la espera no cabe en esta tarea: se esperó lo que se pudo y se lanzó otra tarea que
    sigue esperando (un relevo en cadena que no depende de la revisión de cada 20 minutos)."""
    from .memoria import cadena, guardar_cadena
    c = cadena()
    cuando = c.get("reintentar_desde")
    if not cuando:
        return True
    falta = (datetime.fromisoformat(cuando) - datetime.now(timezone.utc)).total_seconds() / 60
    if falta <= 0:
        return True
    c["esperando"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    guardar_cadena(c)
    _latido()
    usado = (time.monotonic() - arranque) / 60
    if usado + falta + necesita <= tope:
        print(f"Espero {falta:.0f} min a que se renueve el límite de Claude y sigo.")
        _dormir(esperar, falta + 1)
        return True
    # No cabe esperar y además producir: espera todo lo que permite esta tarea y pasa el relevo
    margen = max(0.0, min(falta, tope - usado - 10))
    print(f"Faltan {falta:.0f} min: espero {margen:.0f} y paso el relevo a otra tarea.")
    _dormir(esperar, margen)
    c = cadena()
    c.pop("esperando", None)
    guardar_cadena(c)
    _guardar_avance_en_repo()
    _relanzar_produccion()
    return False


def ejecutar(esperar=time.sleep):
    """El bot trabaja solo, siempre, en cadena, para todas sus páginas:
    1. Si el límite de Claude está agotado, espera a que se renueve.
    2. Si hay un video a medias, lo termina; si el turno de ahora no tiene video, lo hace (en la
       página de ese turno); si ya lo tiene, espera al próximo turno.
    3. Al terminar, deja lanzada la siguiente tarea, que repite lo mismo.
    Si una espera no cabe en una tarea de GitHub, pasa el relevo a otra. Si una tarea muere de
    golpe, el vigilante (revisión periódica) relanza la cadena al ver que dejó de latir."""
    global INICIO
    from .claude import LimiteDeSuscripcion
    from . import reanudar
    from .memoria import cadena, guardar_cadena
    cfg = cargar_config(config.PRINCIPAL)
    arranque = time.monotonic()
    # Lo que dura como máximo la tarea de GitHub (lo fija bot.yml; 175 si es el bot.yml viejo de 180 min)
    tope = float(os.environ.get("MINUTOS_TAREA", "175"))
    necesita = float(cfg["produccion"].get("tiempo_maximo_min", 170))
    _latido()
    _atender_botones()
    if not _esperar_renovacion(esperar, arranque, tope, necesita):
        return
    continuo = cfg["produccion"].get("modo_cadena", "turnos") == "continuo"
    elegir = _esperar_trabajo if continuo else _esperar_turno
    elegido = elegir(esperar, arranque, tope, necesita, cfg)
    if elegido is None:
        return
    canal, turno = elegido
    config.usar_canal(canal)
    print(f"Página: {canal} · turno {turno}")
    for vuelta in range(12 if continuo else 5):
        if (time.monotonic() - arranque) / 60 + necesita > tope:
            _relanzar_produccion()  # no da tiempo a un video entero en esta tarea
            return
        INICIO = time.monotonic()  # el tiempo para terminar el video cuenta desde ahora
        try:
            producir()
        except LimiteDeSuscripcion as e:
            cuando = reanudar.guardar_por_limite(str(e))
            hora = cuando.astimezone(timezone(timedelta(hours=-4))).strftime("%I:%M %p").lstrip("0")
            c = cadena()
            if c.get("avisado_limite") != c.get("reintentar_desde"):  # un solo aviso por límite
                c["avisado_limite"] = c.get("reintentar_desde")
                guardar_cadena(c)
                a_medias = reanudar.EN_CURSO.exists()
                telegram.aviso_seguro(
                    "Se acabó el límite de uso de Claude"
                    + (" a mitad del video. Guardé el avance y a las " if a_medias else ". A las ")
                    + f"{hora} (hora de RD) sigo solo"
                    + (" desde donde se quedó." if a_medias else " con el video.")
                    + " Si su horario ya pasó para entonces, lo publico en cuanto esté listo.")
            if vuelta == 4 or not _esperar_renovacion(esperar, arranque, tope, necesita):
                return
            continue
        e = estado()
        if e.pop("rehacer_turno", None):  # salió roto y se descartó: se rehace este mismo turno
            guardar_estado(e)
            continue
        c = cadena()
        c["turno_hecho"] = turno
        guardar_cadena(c)
        _guardar_avance_en_repo(f"Memoria: video {datetime.now(timezone.utc):%Y-%m-%d}")
        if continuo:
            # Sigue con el próximo video en esta misma tarea si da el tiempo (aprovecha el uso
            # de Claude disponible); si no, la siguiente tarea de la cadena continúa.
            if (time.monotonic() - arranque) / 60 + necesita > tope:
                break
            config.usar_canal(config.PRINCIPAL)
            elegido = _esperar_trabajo(esperar, arranque, tope, necesita, cfg)
            if elegido is None:
                return
            canal, turno = elegido
            config.usar_canal(canal)
            print(f"Página: {canal} · {turno}")
            continue
        _relanzar_produccion()  # la siguiente tarea espera al próximo turno
        return
    _relanzar_produccion()


if __name__ == "__main__":
    try:
        ejecutar()
    except Exception:
        error = traceback.format_exc()
        print(error)
        telegram.aviso_seguro("El bot falló al producir el video:\n" + error[-1500:])
        raise

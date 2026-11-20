"""Comprueba que todas las claves funcionan, sin producir ni publicar nada.

Uso: python -m bot.diagnostico
"""
import os
import sys

import requests

from .meta import GRAPH

RESULTADOS = []


def informar(nombre: str, ok: bool, detalle: str = ""):
    RESULTADOS.append((nombre, ok, detalle))
    print(("OK   " if ok else "FALLA"), nombre, "-", detalle)


def revisar_claude():
    clave = os.environ.get("ANTHROPIC_API_KEY", "")
    if not clave:
        return informar("Claude", False, "falta el secreto ANTHROPIC_API_KEY")
    try:
        from .claude import Claude
        c = Claude()
        respuesta = c.texto("Eres una prueba de conexión.", "Responde solo: listo", max_tokens=20)
        modo = "tu suscripción (Claude Code)" if c.suscripcion else "la API (pago por uso)"
        informar("Claude", bool(respuesta.strip()), f"responde usando {modo}")
    except Exception as e:  # noqa: BLE001
        informar("Claude", False, str(e)[:300])


def revisar_telegram():
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN", ""), os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat:
        return informar("Telegram", False, "faltan TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID")
    r = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=30)
    if not r.ok:
        return informar("Telegram", False, "el token del bot no es válido")
    r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      data={"chat_id": chat, "text": "Prueba del bot: Telegram funciona."}, timeout=30)
    if r.ok:
        informar("Telegram", True, "te envié un mensaje de prueba")
    else:
        informar("Telegram", False, "no pude escribirte: ¿le enviaste /start a tu bot? ¿el chat id es correcto?")


def revisar_meta():
    pagina, token = os.environ.get("META_PAGE_ID", ""), os.environ.get("META_PAGE_TOKEN", "")
    if not pagina or not token:
        return informar("Facebook", False, "faltan META_PAGE_ID o META_PAGE_TOKEN")
    r = requests.get(f"{GRAPH}/{pagina}", params={"fields": "name,followers_count", "access_token": token},
                     timeout=30)
    if not r.ok:
        return informar("Facebook", False, f"el token o el id de la página no sirven: {r.text[:300]}")
    datos = r.json()
    informar("Facebook", True, f"página «{datos.get('name')}» ({datos.get('followers_count', '?')} seguidores)")
    r = requests.get(f"{GRAPH}/me/permissions", params={"access_token": token}, timeout=30)
    if r.ok:
        concedidos = {p["permission"] for p in r.json().get("data", []) if p.get("status") == "granted"}
        faltan = {"pages_manage_posts", "pages_read_engagement", "pages_show_list"} - concedidos
        if faltan:
            informar("Permisos de Facebook", False, "faltan: " + ", ".join(sorted(faltan)))
        else:
            extra = "" if "read_insights" in concedidos else " (sin read_insights: no habrá métricas)"
            informar("Permisos de Facebook", True, "puede publicar Reels" + extra)


def main():
    tiene_telegram = os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID")
    if not os.environ.get("ANTHROPIC_API_KEY") and tiene_telegram:
        # Sin clave de Claude todavía: ayudamos a crear el token de la suscripción.
        from .token_suscripcion import generar
        print("No hay ANTHROPIC_API_KEY: inicio la creación del token de suscripción por Telegram.")
        sys.exit(0 if generar() else 1)
    revisar_claude()
    revisar_telegram()
    revisar_meta()
    resumen = "\n".join(f"{'OK' if ok else 'FALLA'} · {n}: {d}" for n, ok, d in RESULTADOS)
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN", ""), os.environ.get("TELEGRAM_CHAT_ID", "")
    if token and chat:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      data={"chat_id": chat, "text": "Diagnóstico del bot:\n" + resumen}, timeout=30)
    if not all(ok for _, ok, _ in RESULTADOS):
        sys.exit(1)


if __name__ == "__main__":
    main()

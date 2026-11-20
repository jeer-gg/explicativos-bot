"""Cliente de Claude con tope de llamadas y extracción de JSON.

Funciona de dos formas, según lo que haya en el secreto ANTHROPIC_API_KEY:
- Una clave de la API (empieza por "sk-ant-api"): se paga por uso en console.anthropic.com.
- Un token de tu suscripción de Claude (empieza por "sk-ant-oat"), creado con
  `claude setup-token`: usa Claude Code con tu plan y no cuesta nada extra, pero
  comparte el límite de uso de tu suscripción.
"""
import base64
import json
import os
import re
import shutil
import subprocess
import threading
import time

from .config import RAIZ, SALIDA, cargar_config, secreto


class LimiteDeLlamadas(RuntimeError):
    pass


class LimiteDeSuscripcion(RuntimeError):
    pass


def es_token_de_suscripcion(clave: str) -> bool:
    return clave.startswith("sk-ant-oat")


class Claude:
    def __init__(self):
        cfg = cargar_config()["claude"]
        self.modelo = cfg["modelo"]
        self.modelo_escenas = cfg["modelo_escenas"]
        self.busqueda_web = bool(cfg.get("busqueda_web", True))
        self.max_llamadas = int(cfg.get("max_llamadas", 45))
        self.llamadas = 0
        self._candado = threading.Lock()
        self.clave = secreto("ANTHROPIC_API_KEY")
        self.suscripcion = es_token_de_suscripcion(self.clave)
        if self.suscripcion:
            print("Usando tu suscripción de Claude (Claude Code).")
            instalar_claude_code()
        else:
            import anthropic
            self._anthropic = anthropic
            self.cliente = anthropic.Anthropic(api_key=self.clave)

    def _contar(self):
        with self._candado:
            self.llamadas += 1
            excedido = self.llamadas > self.max_llamadas
        if excedido:
            raise LimiteDeLlamadas(
                f"Se alcanzó el tope de {self.max_llamadas} llamadas a Claude para este video."
            )

    def texto(self, system: str, usuario, modelo: str | None = None,
              max_tokens: int = 4000, web: bool = False) -> str:
        """Envía un mensaje y devuelve el texto de la respuesta."""
        self._contar()
        contenido = usuario if isinstance(usuario, list) else [{"type": "text", "text": usuario}]
        if self.suscripcion:
            return self._texto_claude_code(system, contenido, modelo or self.modelo, web)
        return self._texto_api(system, contenido, modelo or self.modelo, max_tokens, web)

    # ---------- Modo suscripción: Claude Code en modo no interactivo ----------
    def _texto_claude_code(self, system: str, contenido: list, modelo: str, web: bool) -> str:
        partes, imagenes = [], []
        for bloque in contenido:
            if bloque.get("type") == "text":
                partes.append(bloque["text"])
            elif bloque.get("type") == "image" and bloque.get("ruta"):
                imagenes.append(str(bloque["ruta"]))
                partes.append(f"[Imagen: {bloque['ruta']}]")
        if imagenes:
            partes.insert(0, "Antes de responder, abre y mira con la herramienta Read cada imagen "
                             "indicada como [Imagen: ruta]. Son fotogramas reales del video.")
        herramientas = ["Read"]
        if web and self.busqueda_web:
            herramientas += ["WebSearch", "WebFetch"]
        comando = [
            "claude", "-p",
            "--model", modelo,
            "--system-prompt", system,
            "--output-format", "json",
            "--max-turns", "20",
            "--allowedTools", ",".join(herramientas),
            "--add-dir", str(RAIZ),
        ]
        entorno = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        entorno["CLAUDE_CODE_OAUTH_TOKEN"] = self.clave
        SALIDA.mkdir(parents=True, exist_ok=True)
        for intento in range(3):
            proc = subprocess.run(comando, input="\n\n".join(partes), capture_output=True,
                                  text=True, cwd=SALIDA, env=entorno, timeout=1800)
            salida = proc.stdout.strip()
            try:
                datos = json.loads(salida.splitlines()[-1]) if salida else {}
            except (json.JSONDecodeError, IndexError):
                datos = {}
            texto = datos.get("result", "") or ""
            error = proc.stderr[-1500:] + " " + (texto if datos.get("is_error") else "")
            if proc.returncode == 0 and not datos.get("is_error") and texto:
                return texto
            if re.search(r"usage limit|limit reached|hit your limit|rate.?limit|l[ií]mite", error, re.I):
                raise LimiteDeSuscripcion(
                    "Se agotó el límite de uso de tu suscripción de Claude. El bot lo intentará "
                    "en el próximo horario; también puedes lanzarlo a mano cuando se renueve.")
            if re.search(r"invalid|unauthori|expired|401|authentication", error, re.I):
                raise RuntimeError("El token de tu suscripción no es válido o caducó. "
                                   "Genera otro con `claude setup-token`. Detalle: " + error[-500:])
            espera = 20 * (intento + 1)
            print(f"Claude Code falló (intento {intento + 1}): {error[-800:]}; reintento en {espera}s")
            time.sleep(espera)
        raise RuntimeError("Claude Code no respondió tras varios intentos: " + error[-1000:])

    # ---------- Modo API: pago por uso ----------
    def _texto_api(self, system: str, contenido: list, modelo: str, max_tokens: int, web: bool) -> str:
        anthropic = self._anthropic
        limpio = [{k: v for k, v in b.items() if k != "ruta"} for b in contenido]
        args = dict(model=modelo, max_tokens=max_tokens, system=system,
                    messages=[{"role": "user", "content": limpio}])
        if web and self.busqueda_web:
            args["tools"] = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 6}]
        for intento in range(4):
            try:
                resp = self.cliente.messages.create(**args)
                return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
            except anthropic.BadRequestError as e:
                # Si la búsqueda web no está disponible, seguimos sin ella.
                if "tools" in args and ("web_search" in str(e) or "tool" in str(e).lower()):
                    print("Aviso: búsqueda web no disponible, sigo sin ella:", e)
                    args.pop("tools")
                    continue
                raise
            except (anthropic.RateLimitError, anthropic.APIConnectionError,
                    anthropic.InternalServerError) as e:
                espera = 15 * (intento + 1)
                print(f"Error temporal de la API ({e}); reintento en {espera}s")
                time.sleep(espera)
        raise RuntimeError("La API de Claude no respondió tras varios intentos.")

    def json(self, system: str, usuario, **kw) -> dict:
        """Igual que texto(), pero exige y devuelve un objeto JSON."""
        crudo = self.texto(system + "\n\nResponde SOLO con un objeto JSON válido, sin texto extra.",
                           usuario, **kw)
        try:
            return extraer_json(crudo)
        except ValueError:
            reparado = self.texto(
                "Convierte el contenido a un único objeto JSON válido. Responde solo el JSON.",
                crudo, max_tokens=kw.get("max_tokens", 4000))
            return extraer_json(reparado)


def instalar_claude_code():
    """Instala la herramienta `claude` en la máquina de GitHub si no está."""
    if shutil.which("claude"):
        return
    print("Instalando Claude Code...")
    for comando in (["npm", "install", "-g", "@anthropic-ai/claude-code"],
                    ["sudo", "npm", "install", "-g", "@anthropic-ai/claude-code"]):
        if subprocess.run(comando).returncode == 0 and shutil.which("claude"):
            return
    raise RuntimeError("No se pudo instalar Claude Code en la máquina de GitHub.")


def extraer_json(texto: str) -> dict:
    bloque = re.search(r"```(?:json)?\s*(\{.*\})\s*```", texto, re.S)
    if bloque:
        texto = bloque.group(1)
    ini, fin = texto.find("{"), texto.rfind("}")
    if ini == -1 or fin == -1:
        raise ValueError("No hay JSON en la respuesta")
    return json.loads(texto[ini:fin + 1])


def extraer_codigo(texto: str) -> str:
    bloque = re.search(r"```(?:tsx|typescript|ts|jsx)?\s*\n(.*?)```", texto, re.S)
    return (bloque.group(1) if bloque else texto).strip() + "\n"


def imagen(ruta) -> dict:
    datos = base64.standard_b64encode(open(ruta, "rb").read()).decode()
    return {"type": "image", "ruta": str(ruta),
            "source": {"type": "base64", "media_type": "image/png", "data": datos}}

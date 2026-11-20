"""Cliente de la API de Claude con tope de gasto y extracción de JSON."""
import base64
import json
import re
import threading
import time

import anthropic

from .config import cargar_config, secreto


class LimiteDeLlamadas(RuntimeError):
    pass


class Claude:
    def __init__(self):
        cfg = cargar_config()["claude"]
        self.modelo = cfg["modelo"]
        self.modelo_escenas = cfg["modelo_escenas"]
        self.busqueda_web = bool(cfg.get("busqueda_web", True))
        self.max_llamadas = int(cfg.get("max_llamadas", 45))
        self.llamadas = 0
        self._candado = threading.Lock()
        self.cliente = anthropic.Anthropic(api_key=secreto("ANTHROPIC_API_KEY"))

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
        args = dict(
            model=modelo or self.modelo,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": contenido}],
        )
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
    return {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": datos}}

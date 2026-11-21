"""Elige la próxima hora buena para publicar (en la zona horaria de la página)."""
from datetime import datetime, timedelta, timezone

from .memoria import memoria


def _zona(cfg: dict):
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(cfg["publicacion"].get("zona_horaria", "America/Santo_Domingo"))
    except Exception:  # noqa: BLE001  (República Dominicana: UTC-4 todo el año)
        return timezone(timedelta(hours=-4))


def ocupados() -> set[str]:
    """Horas (UTC, ISO) que ya tienen un video publicado o programado."""
    return {m["publicado_en"] for m in memoria() if m.get("publicado_en") and not m.get("cancelado")}


def proximo(cfg: dict, ahora: datetime | None = None) -> datetime:
    """La primera hora de la lista que esté al menos 20 minutos en el futuro y libre."""
    zona = _zona(cfg)
    ahora = (ahora or datetime.now(timezone.utc)).astimezone(zona)
    horas = sorted(cfg["publicacion"].get("horarios", ["09:00", "13:00", "20:00"]))
    tomadas = ocupados()
    for dias in range(0, 8):
        fecha = (ahora + timedelta(days=dias)).date()
        for h in horas:
            hh, mm = (int(x) for x in h.split(":"))
            cuando = datetime(fecha.year, fecha.month, fecha.day, hh, mm, tzinfo=zona)
            clave = cuando.astimezone(timezone.utc).isoformat(timespec="seconds")
            if cuando >= ahora + timedelta(minutes=20) and clave not in tomadas:
                return cuando
    return ahora + timedelta(minutes=30)


def texto(cuando: datetime) -> str:
    hora = cuando.strftime("%I:%M").lstrip("0")
    sufijo = "a. m." if cuando.hour < 12 else "p. m."
    dias = (cuando.date() - datetime.now(cuando.tzinfo).date()).days
    dia = "hoy" if dias == 0 else "mañana" if dias == 1 else cuando.strftime("%d/%m")
    return f"{dia} a las {hora} {sufijo}"

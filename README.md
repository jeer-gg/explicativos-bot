# Bot de videos explicativos

Produce cada día un Reel animado de "explicativos de la vida cotidiana" y lo publica en tu
página de Facebook. Tú solo tocas un botón en Telegram.

## Cómo funciona

1. **Director:** lee lo ya publicado y las estadísticas de tus Reels, sortea paleta, gancho y
   estructura, y elige un tema nuevo con demanda.
2. **Guion:** Claude investiga, escribe el guion con dos versiones del gancho (A y B) y otra
   llamada verifica cada dato.
3. **Voz:** Edge TTS narra cada escena. Su duración y el momento de cada palabra marcan el ritmo
   de toda la animación.
4. **Estudio:** Claude dibuja cada escena como código de Remotion (ilustración animada desde
   cero, sin clips de stock). La cámara recorre las escenas en un solo plano continuo.
5. **Revisor:** Claude mira un fotograma real de cada escena, la puntúa y manda a rehacer las
   flojas.
6. **Render:** Remotion y ffmpeg generan el MP4 vertical con las especificaciones de Reels.
7. **Aprobación:** te llegan las versiones A y B a Telegram con los botones *Publicar A*,
   *Publicar B*, *Rehacer otro* y *Descartar*.
8. **Publicación y aprendizaje:** se sube el Reel a tu página y, al día siguiente, el bot lee
   sus métricas para elegir mejor el próximo tema.

Todo corre en GitHub Actions: tu iPhone puede estar apagado.

---

## Configuración (una sola vez, unos 30 minutos)

Consejo para el iPhone: en Safari, toca **aA** y luego **Solicitar sitio web de escritorio**
cuando estés en GitHub o en Meta for Developers.

### 1. Clave de Claude
1. Entra a [console.anthropic.com](https://console.anthropic.com), ve a **API Keys** y toca
   **Create Key**.
2. Copia la clave (empieza por `sk-ant-`). Solo se muestra una vez.
3. En **Billing**, carga saldo. Puedes poner un límite mensual de gasto.

### 2. Bot de Telegram
1. En Telegram, abre **@BotFather** y envía `/newbot`. Ponle nombre y usuario.
2. Copia el **token** que te da.
3. Abre tu bot nuevo y envíale `/start` (si no, no podrá escribirte).
4. Abre **@userinfobot**, envíale cualquier mensaje y copia tu **Id** (un número).

### 3. Token de tu página de Facebook
1. Entra a [developers.facebook.com](https://developers.facebook.com) → **Mis apps** →
   **Crear app**. Elige el caso de uso para administrar páginas. Como la app es solo para tu
   propia página, no hace falta pasar la revisión de Meta.
2. Abre el [Explorador de la API Graph](https://developers.facebook.com/tools/explorer/),
   elige tu app y toca **Generate Access Token** con estos permisos:
   `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`, `read_insights`.
3. Copia ese token, ábrelo en el
   [Depurador de tokens](https://developers.facebook.com/tools/debug/accesstoken/) y toca
   **Extend Access Token**. Copia el token largo.
4. Vuelve al Explorador, pega el token largo y consulta `me/accounts`. Busca tu página y copia:
   - su `id` → será **META_PAGE_ID**
   - su `access_token` → será **META_PAGE_TOKEN** (este no caduca)

### 3b. Subir el código a GitHub (solo con el iPhone)
1. En tu repo: **Add file → Create new file**. Como nombre escribe
   `.github/workflows/bot.yml`, pega el contenido de ese archivo y toca **Commit changes**.
2. Luego **Add file → Upload files**, elige `explicativos-bot.zip` y toca **Commit changes**.
3. En **Actions** verás la tarea **Bot de videos** instalándose. En un minuto el repo tendrá
   todas las carpetas del bot.

### 4. Secretos en GitHub
En tu repo: **Settings → Secrets and variables → Actions → New repository secret**. Crea:

| Nombre | Valor |
| --- | --- |
| `ANTHROPIC_API_KEY` | la clave de Claude |
| `TELEGRAM_BOT_TOKEN` | el token de @BotFather |
| `TELEGRAM_CHAT_ID` | tu Id de @userinfobot |
| `META_PAGE_ID` | el id de tu página |
| `META_PAGE_TOKEN` | el token de tu página |

Los secretos nunca se ven en el código, aunque el repositorio sea público.

### 5. Permisos de Actions
**Settings → Actions → General → Workflow permissions → Read and write permissions → Save.**

### 6. Comprobar las claves
**Actions → Bot de videos → Run workflow**, elige la tarea `diagnostico` y toca **Run workflow**. En un minuto te llega a Telegram qué
funciona y qué falta, sin producir ni publicar nada.

### 7. Primera prueba
**Actions → Bot de videos → Run workflow**, con la tarea `producir`. Tarda de 20 a 40 minutos. Al terminar te llegan
los videos a Telegram. Recomendado: haz las primeras pruebas con una página de Facebook de
prueba.

---

## Uso diario

- Se produce un video cada día a las 7:17 a. m. (hora dominicana). Para cambiar la hora, edita
  el primer `cron` en `.github/workflows/bot.yml` (va en hora UTC, que son 4 horas más).
- Toca un botón en Telegram. El bot revisa tus respuestas cada 20 minutos.
- Para cambiar subtemas, voz, paletas, duración o el modo automático, edita `config.yaml`
  desde github.com (botón del lápiz).
- Para publicar sin aprobación: en `config.yaml` pon `aprobacion: activa: false`.

## Costos

- **GitHub Actions:** gratis e ilimitado si el repo es público. En un repo privado tienes 2.000
  minutos al mes, y este bot usa cerca de eso. Por eso se recomienda un repo público.
- **Claude:** pago por uso. El tope `max_llamadas` de `config.yaml` limita cuánto puede gastar
  cada video.
- **Voz, render, Telegram y Meta:** gratis.

## Si algo falla

- El bot te avisa por Telegram con el error.
- En **Actions** abre la ejecución fallida y descarga el artefacto **trabajo**: incluye el
  guion, los fotogramas revisados y el código de cada escena.
- Si una escena no compila tras 3 intentos, el bot usa una escena de respaldo para no perder el
  video.

## Simulación sin claves

`python pruebas/simulacion.py` recorre todo el proceso (producir, aprobar, publicar y leer
métricas) con Claude, la voz, Remotion, Telegram y Meta simulados. Sirve para comprobar que
un cambio en el código no rompe nada. Solo necesita Python, PyYAML, requests y ffmpeg.

## Estructura

```
config.yaml              ajustes del canal
bot/                     cerebro (Python)
  producir.py            orquesta todo el proceso
  director.py            elige tema y estilo
  guionista.py           guion y verificación de datos
  voz.py                 narración con marcas de tiempo
  estudio.py             Claude dibuja las escenas
  revisor.py             control de calidad visual
  aprobaciones.py        botones de Telegram
  publicador.py, meta.py subida a Facebook
  estadisticas.py        métricas de cada Reel
  diagnostico.py         prueba de claves
  prompts/escena.md      guía de estilo para dibujar
remotion/                animación (React + Remotion)
  src/Video.tsx          cámara continua, audio y efectos
  src/Subtitulos.tsx     subtítulos cortos
  src/lib.tsx            herramientas para las escenas
  src/escenas/Ejemplo.tsx  escena de referencia de calidad
data/                    memoria del canal (se actualiza sola)
pruebas/simulacion.py    prueba completa sin internet
```

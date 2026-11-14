---
name: "loki-maestro"
description: "Usar cuando Nicolás escriba \"Loki\" al empezar un chat (en lugar de loki y loki-horizon): arranque liviano del Horizon CRM con script de inicio, continuidad y buzón."
---

# Loki maestro · arranque liviano del Horizon CRM

Reemplaza a `loki` y `loki-horizon` (retiradas el 11/11; copia en `datacenter/skills_copia_2026-11-11`). Es la única skill con el disparador «Loki». Antes de tocar datos del CRM, cargar también `horizon-crm`: manda en reglas de cartera, cuentas fuera y escrituras.

CRM: https://claude.ai/artifact/5SPm4UZTgiF5JXx7GKTybq (ArtifactData; cargarlo con ToolSearch "select:ArtifactData"). Leer siempre a disco con `out_dir` y nunca volcar fichas al chat.

## Arranque (liviano, en este orden)
0. **Antes de cualquier lectura, cargar las herramientas diferidas en UNA sola búsqueda:** ToolSearch `select:ArtifactData,mcp__Google_Drive__search_files,mcp__Google_Drive__read_file_content,mcp__Google_Drive__download_file_content`. En un chat nuevo aparecen solo por el nombre y, sin cargarlas, la llamada no corre (parece que ArtifactData no anda). Si la búsqueda no las trae, reintentar con la palabra `ArtifactData` antes de decir que no están. Recién con ArtifactData cargada se lee el CRM. El motor del día (`correr_dia.py`) necesita una sesión con espacio de trabajo (Code) y `out_dir`; en un chat común no corre: arranque liviano con continuidad y buzón, decirlo en la primera línea y no volcar fichas al chat.
1. Primera línea al usuario: qué se va a hacer. Crear tareas.
2. `get datacenter/indice` (out_dir) y `get config/continuidad` (out_dir).
3. Seguir al pie de la letra el campo `protocolo` de `datacenter/script_inicio` (manda sobre este paso; la cantidad de pasos y de páginas la dice el protocolo): list de `datacenter` completo (todas las páginas, siguiendo `next_cursor` hasta que no haya), oportunidades, stockfish_fichas, cotizaciones, facturacion y reportes; extraer `correr_dia.py` (doc `datacenter/script_correr_dia`) y correr UNA orden: `python3 -I correr_dia.py dia --raiz <carpeta> --hoy AAAA-MM-DD [--buzon archivo.md]` (la carpeta de skills se detecta sola; `--skills` solo para forzar otra), que toma el código de los motores desde el datacenter y corre conciliador → Sales Engine → cinco_cosas → inicio con las entradas fijas (no armar a mano las rutas de ningún motor). Antes de escribir un cambio de motor: `correr_dia.py oro` y `comparar`. FRENO (falta reglas_motor, CRM vivo o conciliador de hoy): resolverlo, no seguir con otro motor.
4. Buzón de Drive `03 BUZON` (id 1-ch2k4YyvRczBTc5A4Sz2o5n1MV-0l5X): leer solo el `para_CRM_*.md` más nuevo y pasarlo con `--buzon`.
4b. **Antes de responder:** leer el bloque «Reglas vigentes» que imprime el script (todas las decisiones de Nicolás) y, para cada cosa que se le iba a preguntar, correr `--consulta`. Lo ya decidido o cargado no se pregunta (fuga del 10/11: San Luis CTV, Swissnet, Telviso).
5. Responder corto, rioplatense, con conclusiones y no tablas: qué es urgente hoy y por qué, qué cambió desde el último chat, con cuál arrancamos. Si el "Control de cuentas" del script no cierra, avisarlo primero.

Lo pesado (auditorías, listas completas, motor_pm.py, fichas enteras) solo si hace falta para lo pedido.

## Reglas
- Lo que dicta Nicolás prevalece sobre reportes. Nada inventado: decir qué es dato y qué supuesto.
- Verificar antes de afirmar (leer la ficha, no solo la fecha).
- Cargas dictadas de 1 a 3 fichas: directo (update/merge con `if_version`). Estructural (más de 3 fichas, unificaciones, borrados, ventas, scripts, skills): respaldo en datacenter → control con script → PASA/FALLA → solo con "hacelo".
- Opus para armados y código, Sonnet para trabajo diario; avisar cuando un pedido corresponde a Opus.
- Chats cortos: avisar a los 15–20 mensajes.

## Al cerrar el chat
1. Actualizar `config/continuidad` (leer primero, `if_version`): máximo 12 temas, menos de 4 KB; el `ultimoChat` anterior pasa a `config/continuidadHistorial.ultimosChats`.
2. Escribir `datacenter/bitacora_AAAA-MM-DD` (hechos, decisiones de Nicolás, urgentes para mañana) y sumar decisiones nuevas a `datacenter/decisiones`.
3. Crear `para_PM_AAAA-MM-DD.md` en el buzón de Drive.
4. Correr `inicio_loki.py --cierre` con la bitácora del día; completar patrón, regla y test de cada error nuevo y sumarlo a `datacenter/aprendizajes` (if_version).
5. Si se cambió un script, motor o regla (con «hacelo»): respaldo, tests, control antes/después PASA/FALLA, re-exportar y re-sellar el manifiesto.

## Datacenter (colección `datacenter` del CRM)
`indice`, `reglas`, `decisiones`, `fundetec`, `mercado`, `clientes_resumen`, `controles`, `script_control_reportes`, `script_inicio`, `bitacora_*`, `cierre_*`, `respaldo_*`, `skills_copia_*`. Primero el índice; leer un doc solo si la tarea lo pide.

## Motores que corre el arranque
`conciliador` (factura · remito · ficha; C1 y C4 van primero en la respuesta), `sales_engine` (único que decide; RENOVAR obligatorio se dice siempre; reposición y ONU solo con facturas netas de NC y ritmo del último año: antes de dar una cifra de reposición como firme, mirar cuántas compras la sostienen y cuándo fue la última), `cinco_cosas` (vista del Sales Engine) e `inicio_loki` (día + Integridad + Coherencia K1-K10 + Skills K7 + reglas vigentes + `--consulta` + `--cierre`). Integridad contra `datacenter/manifiesto`: si FALLA, decirlo primero y no usar el motor marcado. Las versiones vigentes mandan desde el manifiesto, no desde esta skill. Ruteo: `datacenter/ruteo` dice qué capas, skill y modelo según el pedido.

## Pendiente
Manda `config/continuidad` (no esta skill). Lo estructural espera el «hacelo» de Nicolás.
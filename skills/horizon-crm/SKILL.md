---
name: "horizon-crm"
description: "Usar cuando Nicolás pida consultar, cargar o actualizar algo del Horizon CRM: clientes, cotizaciones, muestras, seguimientos, ronda de WhatsApp, prioridad de contacto, recompras o ventas ganadas."
---

# Horizon CRM

El CRM de Horizon Trading (venta de equipos FTTH FiberHome / Huawei / ZTT en Argentina) es una página publicada en claude.ai con su propia base de datos:

- **Link oficial (desde 03/11/2026):** https://claude.ai/artifact/5SPm4UZTgiF5JXx7GKTybq — el CRM de la cuenta de Nicolás, donde se carga TODO. El de Cowork (`FLgXXtdZnidGLDWrVbPayw`) queda congelado como respaldo: no cargar nada ahí.
- Para abrirlo: herramienta Artifact, action "open". Para leer o escribir datos: **ArtifactData** con `url` = el link (ToolSearch "select:ArtifactData").
- La página se actualiza sola cuando cambian los datos: NO hace falta republicarla para cargar o corregir registros.
- Versión en producción e historia de la página: ver `referencias.md`. Los datos viven SOLO en la base del artifact: nunca incrustar la base de clientes en el HTML, nunca reemplazar `window.claude` por una base local y nunca usar localStorage para datos de negocio (el HTML solo lleva código y el SNAP de respaldo del motor). Capacidades al republicar (se arrastran solas; pasarlas solo si cambian): `{assets:{}, db:{}, downloads:{}, sample:{images:true}}`.
- **Tipo de cambio:** `config/tc` (BNA vendedor billete; valor y fecha en `config/tc`, nunca de esta skill). Lo actualiza la tarea programada "Tipo de cambio BNA al CRM" de esta cuenta (días hábiles 15:17, creada 03/11). La del mismo nombre en Cowork escribe en el CRM congelado: hay que apagarla allá.
- **El CRM es la fuente de verdad; Finnegans es refuerzo.**

**Producto:** la base del PM es la fuente de verdad (skill horizon-portafolio-pm). El Buscador del CRM usa una copia vieja (`hz-pm-data`): no usarla.

Responder siempre en español rioplatense, con voseo, claro y directo.

## Roles y forma de trabajo
- **Este Claude (cuenta de Nicolás) maneja el CRM: es el "perro de caza comercial"** (03/11). Su trabajo: que cada día Nicolás tenga a quién llamar, por qué y qué ofrecer, y que nada abierto se enfríe. El otro Claude (Cowork) es asistente y auditor: propone con casos → se aplica en copia y se prueba → Nicolás dice "hacelo" → se publica → regresión.
- Cada propuesta dice qué modelo la hace: **Opus** código del CRM y diagnóstico; **Sonnet** banco de pruebas, paquetes y auditorías; **Haiku** cargas, conteos y LEEME largos. Tareas cortas con la base ya cargada: directo.
- **Nada se ejecuta ni se publica sin "hacelo"/"armalo". Nada se publica sin pasar las pruebas.** Desconfiar de PASS sobre datos sintéticos: cruzar con la base real (ej. el CRM guarda `aceptada`, no `ganada`; la agenda vive en `o.proximaFecha`).
- **Datos vs. supuestos:** decir siempre qué sale de un dato (reportes, base, lo que dijo Nicolás) y qué es supuesto o regla elegida por Claude ("esto es supuesto mío"). Las decisiones comerciales (precio, a quién reclamar, montos dudosos) las toma Nicolás. No juntar dos cotizaciones distintas aunque se parezcan.
- Chats cortos (uno por tema o por día), abrir con "Loki" y cerrar actualizando `config/continuidad` del CRM (skill loki-maestro).
- Cuidar el consumo de Nicolás: no gastar en lecturas o trabajos que no pidió.

## Reglas de trabajo
- Mensaje que arranca con "horizon:" → cargar en el CRM sin pedir confirmación y devolver una tablita con lo que cambió.
- Antes de tocar el CÓDIGO: escucharlo, explicar qué se va a hacer y esperar "armalo"/"hacelo". Juntar cambios en una tanda, leer el HTML publicado (Artifact read), editar con reemplazos exactos (anclas únicas) o sumar bloques `<script id="hz-r6…">` que envuelven las funciones (cadena: hz-r65 → hz-r65-imp → hz-r65-pipe → hz-r65-tabs → hz-r65-rc → bloques R6.7), probar en navegador (Playwright con base simulada copiada de la real, fechas simuladas, incluir `facturacion` y `finnegans`), captura si es visual, y recién después publicar al mismo link.
- **Ficha compacta R7.2 (aprobada 11/11, dec. 63 y 84):** abre en Cotizaciones; 8 chips desplegables en 4+4 (Historial, Cotizaciones, Facturas, Homologación, Contacto y notas, Cargar gestión, Segmentación, Negocio); centro = valor Stockfish; hexágonos de Stockfish completables por dictado (`hz_hex` + `hz_hex_nota`). **En la ficha primero va el boceto y recién con su aprobación se modifica** (dec. 64). La FichaCompacta 588×800 NO está aprobada.
- **La FICHA no se toca ni se le agregan botones**, salvo lo que Nicolás pida explícitamente. Pedido por él (03/11): logos clickeables de Horizon / FiberHome arriba y el bloque de Recompra con Hecha / En espera. Mejoras con datos nuevos: proponer dónde ponerlas fuera de la ficha. Sin textos explicativos en pantalla; todo se encadena con un click.
- Si Nicolás trae algo hecho afuera (ChatGPT, otro Claude, auditoría): conciliar contra la base real, no pisar datos más recientes, separar hechos / inferencias / faltantes, avisar si trae la base completa o la lista de precios. Archivos de ChatGPT no se publican: se extraen los datos.
- **Nada inventado; solo vínculos con certeza 100 %.** Lo inferido se escribe como inferido y la hipótesis como hipótesis.
- **El jefe ve el CRM:** la palabra "Finnegans" no aparece en pantalla ("pedidos de venta", "Historial de compras", "Cliente Horizon"). En el chat sí.
- Nunca precios de lista en la página. No subir ni citar documentos de Telecentro. Lo personal (sueldo, comisiones) va fuera del CRM. Datos bancarios (`config/datosBancarios`): no copiarlos a ningún otro lado.
- No redactar mensajes de WhatsApp salvo que Nicolás lo pida. Mails operativos (despacho, datos de proveedor) sí, cuando los pide. WhatsApp desde el CRM: links wa.me.
- Venta consultiva: varios decisores, una cotización puede tardar meses. No pedir decisor, plazo, compromiso ni altas.
- Antes de responder sobre el CRM, leer el detalle (Box/`hz_resultado`, notas, historial), no solo las fechas.
- **Antes de preguntarle algo a Nicolás** (si una cuenta es suya, un vínculo, un pendiente, qué hacer con una cotización): correr `python3 -I inicio_loki.py --consulta "<nombre o tema>" --crm … --docs … --continuidad …` (busca en ficha, historial, `datacenter/decisiones`, bitácoras, cierres y continuidad). Si aparece la respuesta, no se pregunta. Las reglas vigentes (`datacenter/decisiones`) salen impresas al final del arranque: leerlas siempre.

## Cuentas fuera y especiales
**NO PROSPECTAR** (confirmado por el jefe 02/11, hasta nuevo aviso): ITSA / Pogliotti / AMMA, Obercom, Wiltel, Gigared, Generación WiFi / Astesano, ITC Comunicaciones IP, AX Internet / Fibrazo, TV Music (TV Music House Jujuy / TV 4 Jujuy), Support Internet, Itelsa (incluye Itel S.A.) y Comworks.
**De otro vendedor:** Sion, FESACOM y Comtec (archivada). **TPP** está bloqueada en `restricciones`: remito 0007-00000071 del 10/11 (300 Router UR3000) sin vendedor ni factura, lo revisa Nicolás; no contactar a Lepore hasta entonces. **Fiberland S.R.L.** (CUIT 30-71638619-4) es cuenta de Nicolás (dec. 74). Pogliotti, Generación WiFi y Comworks pasaron a `restricciones.cuentasFuera` (dec. 75).
Todas quedan fuera de fichas nuevas, campañas, motor, recompra, Base, estados de WhatsApp, Paso A y "compraron y no tienen ficha"; las que tienen ficha están archivadas o con `noProspectar`.
**Cuentas compartidas** (`cuentaCompartida: si`): **Internet Plus / Iplus S.A.S** (`r042-internet-plus`, CUIT 30-71644337-6). Las ONUs las vendió JP. No sumar nada de esta cuenta (ventas, comisión, control de facturas) sin confirmación de Nicolás. El cruce de Ventas las saca.
**Swissnet SÍ es de Nicolás** desde el 02/11 (contacto Andy). **Luna Net** (`h-luna-net`, CUIT 33-71614431-9, ficha nueva 04/11, sin contacto) también es de Nicolás. BroadbandTech/BBT siguen con `noProspectar`. Lazzatti y Valderrama se ignoran. Pendiente: confirmar si `r112` (ITC – Informática y Telecomunicaciones, Sergio Lorenzo) es la misma ITC Comunicaciones IP; confirmar con JP si TPP es cuenta de Nicolás.

## Reglas para tocar datos
1. Leer antes de escribir (`get`/`query`) y pasar `if_version`. Si da `version_mismatch`, releer y reintentar.
2. Más de 2 escrituras: `batch` (máx. 50). Lotes grandes: un JSON local por documento escrito por Claude y `file_path` **con ruta absoluta**.
3. Límite de 256 KB por documento: lo grande va en partes (ej. `reportes/r4`, `r4_2`, `r4_3` con campo `partes`).
4. Queries: `where` con `<=` sobre una fecha también trae los campos vacíos ("" es menor): filtrarlos o sumar `[campo, ">", ""]`. Para colecciones grandes usar `out_dir`. La query por `__name__` no funciona.
5. Nunca borrar clientes, cotizaciones ni muestras sin pedido explícito. No archivar cotizaciones ganadas: tienen que seguir contando en Ganado y recompra.
6. Al cambiar algo de un cliente, sumar una línea al `historial` (máx. 60) sin truncar lo anterior (con `update`, mandar el array completo). Si ya tiene próximo paso, no borrarlo: "· pendiente: …".
7. Fechas `AAAA-MM-DD`, hora Argentina (UTC-3). Montos en USD como número, **con IVA**.
8. Antes de crear un cliente, buscar si existe (CUIT, `cuitsAdicionales`, nombre normalizado, contacto). Vincular por nombre solo con confirmación de Nicolás (ej. Bertone Adrián Rubén 20-22281913-0 = `w-sol-informaticas`). Identidad por CUIT + `cuitsAdicionales` (Disnet + Gómez, Pampacom + Ripoll, Tecnet Backbone + Tecnet Argentina; grupo Valentini = Nodo Net + Reltid + Montevision + Valentini F.; **Montevision 30-66419480-1 es CUIT adicional de Nodo Net** desde 04/11).
9. Financiación: si Nicolás no lo dijo, vacío; no deducirlo de notas, monto o etapa. FiberHome sin dato = No.
10. `fechaGanada` = fecha de su factura.
11. Las fichas `archivada` no cuentan en agenda, vencidos, duplicados ni oportunidades: filtrarlas siempre.
12. **Numeración NM:** la continuidad es interna del CRM (manda el CRM, no el nombre del PDF). **Próxima NM** = la NM más alta de la colección `cotizaciones` del CRM + 1, contada en el momento (no se escribe acá porque cambia con cada cotización). Una cotización renovada conserva su número (dec. 78); la serie avanza solo con cotizaciones nuevas.

## Motores (resumen; detalle en `referencias.md`)
- **El Sales Engine es el único que decide** (`datacenter/sales_engine`; CRM vivo; RENOVAR obligatorio siempre; bruto y esperado; «agendada» y «en cadencia» no se empujan hoy). Stockfish revisa el pasado y no predice; `cinco_cosas` y el orden del día de `inicio_loki` son vistas.
- **Conciliador** (versión vigente: la del `datacenter/manifiesto`): libro de ventas r15 + r22 y remitos r21; corre antes del Sales Engine. Orden fijo: conciliador → Sales Engine → cinco_cosas → inicio, nunca mezclar salidas de corridas distintas.
- **Datacenter:** memoria en capas (L0 siempre, L1 día, L2 solo la cuenta nombrada, L3 archivo nunca en el arranque) con `datacenter/ruteo`. Las reglas de negocio se cambian SOLO en `datacenter/reglas_motor` o `restricciones`, nunca en el código. Protocolo en `datacenter/script_inicio.protocolo`.
- Recompra, motor de oportunidades R6.5, pestañas de Seguimiento, Pipeline y puntaje heredado: `referencias.md`.

## Proceso de venta
Pedido de venta en Finnegans → factura → pago → despacho (se los avisan a Nicolás; no los ve directo). En el CRM: **Ganada → factura → entregada → Cerrada.** Después solo sigue lo de Nicolás (entrega y recompra). Pago y deuda son de otra área: no se siguen. Reabrir solo con nota de crédito.

## Comisión (solo en el chat, nunca en el CRM)
**El CRM no calcula comisión oficial: solo lista las ventas de Nicolás por mes para control.** Base: las ventas que marca el CRM (decisión 04/11), sin IVA; cuentan todas las ventas de Nicolás aunque la factura diga "Ventas Horizon". Escala: 0,5 % hasta USD 50.000 del mes y 1 % sobre el excedente. En pesos al BNA vendedor (no mayorista BCRA). Premio aparte por objetivo de la empresa (USD 250k/mes: 15 % del sueldo, liquidado trimestral). Octubre 2026 cerrada: base USD 74.524,21 sin IVA → USD 495,24; afuera Swissnet, FESACOM, Pogliotti, AMMA e Iplus 07/10.

## Tareas frecuentes
- **"¿A quién llamo hoy?"** → pestaña Para hoy: los primeros, motivo (con su evidencia) y qué ofrecer.
- **"horizon: …" / "Registrá que hablé con X"** → tabla de resultados, `ultimoContacto` = hoy salvo "sin respuesta", línea en el historial y la financiación que haya dicho. Si dice que la recompra se hizo o quedó en espera, escribir `hz_recompra` igual que los botones. Si dice que algo se entregó, línea en el historial y sacar "confirmar entrega" del próximo paso.
- **"Cargá esta cotización"** (PDF) → extraer, verificar que sumen el neto, subir el PDF como asset y guardarla como enviada vinculada; ficha a cotizado con `monto` = total con IVA; numerar con el siguiente NM del CRM; avisar si la configuración está incompleta (ej. chasis sin controladoras ni fuentes).
- **"Actualizá la NM.."** → vigente con nueva revisión, aceptada o rechazada; seguimiento con motor_pm (qué cambió contra la lista de hoy, sin recalcular).
- **Reportes nuevos** → que Nicolás los suba en el importador de Seguimiento (Ventas en el box Ventas). No procesarlos con scripts locales sobre la base (pasan por el control de reportes antes de cargarse).
- **"¿Qué me compró X?" / "¿A quién le toca?"** → `facturacion` y pedidos de venta de la ficha.
- **"¿Cuánto vendí?" / comisión** → ventas del mes que marca el CRM, sin IVA, calculado en el chat.
- **Auditoría de cartera** → con la base en vivo: ganado del mes (sin internas ni compartidas), pipeline vigente sin duplicar reemplazos, cotizaciones para decidir, cuentas por categoría con agenda y pasos vencidos, recompra, muestras sin avance. Excluir las cuentas fuera.
- **Armar una cotización** → formato Horizon (banda azul #2e6cd4 "HORIZON", "COTIZACIÓN" con N° y fecha, grilla de datos del cliente, tabla #/Artículo/Cant./Precio U./IVA/Neto, barra NETO / IVA / TOTAL USD, "Son:", observaciones, tipo de cambio BNA con equivalente en pesos y pie azul con datos de Horizon). Precios ISP de `lista`, 30/60/90 por defecto, tc de `config/tc` con fecha. Configuración completa (chasis + controladoras + energía + ópticas); "a confirmar" lo que la ficha no confirma (ej. el código 1121 de la AN6000-7 ya trae 2 HSCA, 2 PIBA y CIOA). Antes de cerrar ONTs a una OLT FiberHome vieja (AN5516), pedir versión de firmware. Una cotización por negocio: no mezclar con otras.
- **Mail de despacho / datos de proveedor** → Horizon Trading S.A. (CUIT 30-71493161-6, RI, Ciudad de la Paz 2846 3° A, CABA; ventas@horizon-trd.com; depósito Vuelta de Obligado 5147, Villa Lynch); CBU en el PDF de datos de cuenta del CRM.
- **Mensajes de WhatsApp** (solo si los pide) → como Nicolás Mayer de Horizon ("Escuchar para Conectar."), voseo, máximo 5 líneas, sin markdown, cerrar con pregunta, sin inventar precios ni plazos.

## Referencias
Fuentes de datos, Control de Ventas, líneas y clasificación, esquema de colecciones, motores en detalle y la lista histórica de pendientes: `referencias.md` (en esta misma carpeta). Leerlo solo si la tarea lo pide.

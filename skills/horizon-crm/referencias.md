# Horizon CRM · referencias

Archivo de consulta de la skill horizon-crm: esquema, fuentes, motores en detalle e historia. Las reglas que mandan están en `SKILL.md`; si algo de acá choca con `SKILL.md`, `config/continuidad` o el datacenter, manda eso.

## Versión de la página
- **Producción: v192 · R7.2** (11/11/2026). Historia: v181 R6.7.2 (04/11, refacturación y descuentos) → v190 (chip «Cargar gestión» y tabla de días) → v192 (ficha compacta R7.2 en vivo). Contrato 0.2.72, compartido "cualquiera con el link". Los datos viven SOLO en la base del artifact: nunca incrustar la base de clientes en el HTML, nunca reemplazar `window.claude` por una base local y nunca usar localStorage para datos de negocio (el HTML solo lleva código y el SNAP de respaldo del motor). Capacidades al republicar (se arrastran solas; pasarlas solo si cambian): `{assets:{}, db:{}, downloads:{}, sample:{images:true}}`.

## Fuentes de datos
- **Cotizaciones** = proyectos de venta.
- **Reporte de Ventas (desde 04/11, R6.7):** facturación por renglón. JP lo pasa **una vez por semana, los lunes**: `Ventas_2026_AAAA-MM-DD.xlsx` en Drive `10 FINNEGANS` (id `1hIHz6z7nUM0BJY5s9CNWOODTLtjhZcq_`; tomar siempre el archivo de fecha más nueva; también hay `Ventas_2025.xlsx`). Se sube en el **box Ventas** de Pedidos (Seguimiento). Siembra la colección `facturacion` sin precios y arma el control en `config/ventasControl`. Siembra inicial hecha el 04/11 con Ventas 2025 + 2026 (96 clientes). Pendiente: Nicolás vuelve a subir los dos Ventas una vez para limpiar refacturaciones.
- **Reporte_6** (pedidos pendientes) es optativo. **Reporte_7** = facturas pendientes de cobro: no hace falta pedirlo. Reporte_3 / Reporte_4 / Reporte_14 siguen sirviendo para historia y motor de recompra.
- **Un pedido "Pendiente" en Finnegans no prueba que no esté facturado** (Full Sat y Howard figuraban pendientes ya facturados): tratarlo como sugerencia. Lo mismo con "pendiente de destino" en una factura: si Nicolás dice que se entregó, manda lo que dice él.
- Pedido nuevo → cruzar con su cotización para saber el producto; la facturación confirma. Si cotización y factura difieren, **manda la factura**. Lo importante arranca el 13/08/2026.
- Solo Empresa = HORIZON TRADING S.A.; **SUR TECHNOLOGY S.A. (PV 00012) y PRESUPUESTO HORIZON quedan fuera de todo.**
- Duplicados: mismo cliente + fecha + bruto = una compra. Pedidos en pesos (2021-2023) cuentan por fecha, su monto no se usa.
- "HW" en facturación mezcla Cisco CMTS (HFC, discontinuado) con Huawei (GPCMM, CHS STE, RCT100): discontinuado solo si es Cisco.
- Cruzar datos antes de preguntar: IVA 10,5 % = equipo y también fibra 48F y drop (confirmado con cotizaciones enviadas); 21 % = otros pasivos; monto ÷ precio ISP da el producto.
- **Bajar la base a disco depende de la sesión.** En sesiones con espacio de trabajo (Code) ArtifactData acepta `out_dir`: guarda cada documento como JSON y no vuelca nada al chat (verificado 12/11). En un chat común la herramienta no trae `out_dir`: ahí NO se baja el CRM al chat; se hace el arranque liviano con la nota de continuidad y el buzón, avisando que el motor no corrió. Es lo que usa el arranque Loki (`correr_dia.py`). Colecciones grandes (oportunidades, stockfish_fichas, facturacion, reportes, datacenter) siempre con `out_dir`, nunca leídas al chat. Si `out_dir` está disponible y lo rechaza, decir el error textual en vez de asumir que no se puede. Lecturas puntuales: `get` o `query` acotada.

## Control de Ventas (R6.7 → R6.7.2)
- Cruce cotización ↔ factura por **N° de factura** (de la cotización y de la ficha); las aceptadas sin número se emparejan por fecha (±20 días).
- Facturas anuladas con NC se descartan. **Refacturación** (NC + factura rehecha en ≤10 días) cuenta una vez. **Descuentos dentro de la factura** = ajuste, no NC.
- Saca las cuentas compartidas (Internet Plus).
- Detecta: aceptada sin factura, factura sin cotización, NC y renglones sin entregar → alerta en Seguimiento con botón **Entregado** (escribe `config/ventasEntregas`; el doc se crea con el primer click). Si Nicolás dice en el chat que algo se entregó: línea en el historial de la ficha y pedirle que toque Entregado en la alerta (no inventar la estructura del doc).
- Venta facturada sin cotización previa: cotización `aceptada` sin NM (`numero` "S/N · FA <comprobante>"), monto con IVA (ej. Armstrong FA1678: USD 222,64 = 184 neto + 21 %).

## Líneas y clasificación
- **Líneas del motor:** FiberHome (+Ousent), Huawei (OLT, placas y energía; ONU Huawei = reemplazo por FH) y ZTT. Switches Huawei (S5735/S6730) fuera del motor: venta puntual / stock a empujar. Lo demás, solo confirmado.
- **Discontinuados:** I-con, ZTE, Netconn, Intelbras, China Mobile, Zikun, Wolk, HFC (cable modem/CMTS) y notebooks/HPE. No usarlos para recompra ni puntaje; ofrecer reemplazo.
- **Clasificación = letra A/B/C** (valor, abc.py v8) **+ recencia por último pedido:** Activo ≤183 días · Se va 184-548 · Dormido >548.
- Segmento de Nicolás: ventas chicas (hasta ~USD 8.000), pero el ticket NO decide de quién es la cuenta (10/11). **Cuenta con cotización cargada en el CRM y sin otroVendedor / noProspectar / cuentaCompartida = de Nicolás** (ej. San Luis CTV, NM22). Solo se consulta lo que no tenga dato, y antes se corre `--consulta`.

## Colecciones

### `oportunidades` (un documento por cliente)
- `empresa`, `contacto`, `telefono`, `email`, `tipo`, `zona`, `cuit`, `cuitsAdicionales`, `condIva`, `domicilio`, `transporte` (ej. Cablenet: Expreso Santa Rosa vía Rafaela · Fibernext: El Vasquito → Viedma · Coop Villa del Rosario: Credifin), `contactosAdicionales` (de bases externas; no se muestra), `cuentaCompartida`.
- `etapa`: prospecto | contactado | calificado | cotizado | negociacion | ganado | pausa (= "Sin requerimiento") | perdido
- `monto` (con IVA), `productos`, `pago`, `ultimoContacto` (se edita desde el encabezado de la ficha), `proximaFecha`, `proximaAccion`, `notas`, `motivoPerdida`, `fechaGanado`
- Segmentación: `usaFH` (si | no), `fhTipo` (activo = ONU/ONT | pasivo = fibra/cajas | ambos), `oltFH`, `clienteHorizon` (si = tiene pedidos/facturas), `facturacionId` (CUIT sin guiones), `marcaOlt`, `modeloOlt`, `versionOlt`. En la ficha, `usaFH` y `clienteHorizon` en "si" se ven como logo arriba. El ▶ de FiberHome abre Activo / Pasivo.
- `hz_recompra` `{estado: hecha | espera, t, hasta, ciclo}`: lo escriben los botones Hecha / En espera. Hecha → la recompra sale hasta hoy + ciclo; En espera → sale 15 días. Al llegar `hasta`, vuelve a Postventa con esa fecha.
- Financiación: `financiacionEstado` (con_fondos | en_aprobacion | sin_fondos | ""), `financiacionRevision`
- Campos viejos que no se piden ni cargan: `altas`, `plazo`, `decisor`, `compromisoCompra`, `estadoConsultivo`, `productosUsa`, `productosCompra`, `productosDesarrollar`, `lineas`, `prioridad`.
- `noProspectar` (si) + `noProspectarMotivo`; `otroVendedor`; `archivada` (+ `archivadaMotivo`, `unificadaEn`); `historial` `{t, txt}`; `creado`, `actualizado`.

### `cotizaciones`
- `numero` (NM..), `cliente`, `cuit`, `condIva`, `condPago`, `fecha`, `vence`, `tc`, `items`, `neto`, `ivaTotal`, `total`, `marca`, `familia`, `pdf`, `notas`, `archivada`, `oportunidadId`, `revisionFecha`, `fechaGanada`, `hz_operacion`, `hz_resultado` (el **Box**: estado, fechaSeguimiento, historial).
- `familia`: Cajas y NAP | ONT / ONU | OLT y placas | Ópticas y transceivers | Energía | Cables de fibra | Conectores y accesorios | Otros.
- **Para Nicolás una cotización tiene 3 estados: vigente, aceptada, rechazada.** No manda borradores: toda cotización cargada es un negocio real. **Nada se da por perdido solo:** toda cotización que Nicolás no marcó perdida sigue viva y **se renueva** (10/11). Si venció su validez, el Sales Engine pone el empujón **RENOVAR** (obligatorio, no se saltea ni se saca; también sale en el box como alerta de cotizaciones vencidas). Varias abiertas del mismo cliente suman todas (ej. Telviso NM29 + NM33 + NM46). Si la ficha dice que una NM «nunca se envió», esa no suma: manda la enviada (ej. Swissnet: renovar la 0000-00018, no la NM48). Vigente con revisión hoy = seguimiento.
- **Siguen sumando al pipeline hasta que se marcan en el Box** (aceptada, perdida, postergada, sin fondos).
- **Condición de pago FiberHome (dec. 85, 11/11):** siempre «30-60-90 días» (el «sin interés» es tácito, no se escribe), precio ISP; contado = 3 % de descuento sobre el neto, más IVA. Para el resto de las marcas sigue «A convenir» si no está dicha.
- **La cotización enviada marca lo que es:** no se recalcula y manda sobre la lista (si la lista bajó, se propone renovarla más barata; si subió, cerrar al precio enviado).
- Montos de cotizaciones y fichas **con IVA**, exactos ("USD 15.357,18 con IVA").
- Las cotizaciones a nombre de Horizon Trading S.A. (o sin CUIT de cliente) son internas y no cuentan.
- Estados técnicos guardados: borrador | enviada | espera_decision | espera_aprobacion | sin_fondos | postergada | aceptada | rechazada; `hz_resultado.estado` con el detalle. Si una NM reemplaza a otra, la vieja queda marcada como reemplazada (nota con el NM nuevo).
- Ganada → cliente a `ganado`, `monto` = total. Perdida → cliente a `perdido` solo si no le quedan otras abiertas ni ganadas.
- Una cotización pasada que se carga "como dato" va `aceptada` (si se ganó) y no suma al pipeline. Una cotización de prueba de formato no se carga.

### `muestras` (Homologación)
`oportunidadId`, `productos`, `estado` (pedida | sin_retirar | enviada | prueba | aprobada | rechazada | no_se_envia | devuelta), `fechaPedido`, `fechaEnvio`, `seguimiento`, `envio`, `devolver`, `notas`. Muestra activa no se guarda sin fecha de próximo seguimiento (pedida 2 días, sin retirar 2, enviada 7, en prueba 7, aprobada 3). No poner fechas de prueba sin la fecha real de entrega.

### `estadosWsp`
Un documento por estado `{fecha, tema, marca, vistos:[{id, empresa, quien, resultado (interesa | no_ahora | sin_respuesta), resFecha}]}`; se consulta el día hábil siguiente. Le interesa → calificado y "Cotizar: <marca>"; No por ahora → 30 días; Sin respuesta → 3. Ver un estado no es contacto. Dudosos, proveedores, archivadas y cuentas fuera no se suman. Por chat: "horizon: estado <marca>" con capturas.

### `finnegans` (pedidos de venta; en pantalla "pedidos de venta")
Un documento por razón social `{cliente, pedidos:[{numero, fecha, estado, moneda, cliente, items}]}`. Alias en `finnegansAlias`. Pedidos que no son de Nicolás (ej. P-1458 de otro vendedor, P-1469 Cámara Argentina de Internet) no cuentan. `finnegansResumen` = resumen por cliente.

### `facturacion` (facturación sin precios)
Un documento por CUIT `{cliente, cuit, lineas:[{fecha, tipo (F | NC), comprobante, producto, cantidad, familia, subfamilia, marca}]}`. Nunca precios ni importes. Sin Sur Technology ni Presupuesto Horizon. Se vincula por `facturacionId` o `cuit`. Desde R6.7 la siembra el box Ventas.

### `lista` y `productos`
`lista` = lista de precios ISP (89 artículos, campos isp/sub/lista/iva): consultarla ahí, no pedírsela a Nicolás; nunca mostrar precios en la página. Precios: fibra FiberHome = lista de JP vigente 26/10; resto = PDF lista 02/11; ADSS ZTT = lista ZTT (24F seco 0,53/m). `productos` = lista Huawei/ZTT con `condiciones` y `descuentoContado` = 4 (línea Huawei OLT/placas/rectificador, efectivo o transferencia).

### `reportes`
`reportes/r3`, `r3_2`, `r4`, `r4_2`, `r4_3`: los últimos Reporte_3 y Reporte_4 empaquetados (diccionario de textos, partes de 100.000 caracteres, campo `partes`). Los escribe el importador.

### `config`
`tc` (tipo de cambio), `salesEngine` (v4: letras A/B/C, `prod` por cuenta, pesos), `rueda` (cupo diario de la Base del día: **5 fichas**), `oportunidadesR65` (ranking del motor que lee Seguimiento; si falta, usa el SNAP del HTML), `ventasControl` (control cotización ↔ factura / NC / sin entregar, R6.7), `ventasEntregas` (lo escribe el botón Entregado), `datosBancarios` (no copiar).

## Motores

**Stockfish y Sales Engine (decisión 20, 09/11):** Stockfish revisa el pasado (facturas, entregas, cotizaciones, restricciones, valor de la cuenta; no predice). El **Sales Engine** (`datacenter/sales_engine`, reglas fijas) decide qué hacer ahora y empuja las cuentas con **un solo criterio: USD con evidencia que pueden entrar este mes** (cotización abierta = total → RENOVAR si venció / CERRAR; entrega pendiente = factura → ASEGURAR; reposición con ciclo cumplido = compra típica → REPONER; ONU discontinuada comprada en 12 m = REEMPLAZAR). Número de la cuenta = el mayor componente; empate = valor Stockfish. La ficha es la entrada de todo; las palabras del empujón van a la ficha como desplegables (pendiente de armar). `config/salesEngine` v3.0 queda como respaldo, no se usa para empujar.

**Datacenter v2.0 (11/11, dec. 77, 80 y 81):** memoria única en capas (L0 núcleo siempre, L1 día, L2 solo la cuenta nombrada, L3 archivo nunca en el arranque) con despachador `datacenter/ruteo` (motor, capas, skill y modelo por pedido), `aprendizajes` (error → regla → test), manifiesto con integridad y control de coherencia K1-K9 (K7 skills, K9 motores sin contradecirse). Reglas únicas en `datacenter/reglas_motor` y `datacenter/restricciones`; las reglas de negocio se cambian ahí, nunca en el código. **El Sales Engine es el único que decide** (CRM vivo; RENOVAR obligatorio siempre; bruto y esperado; «agendada» y «en cadencia» no se empujan hoy; cuenta dormida con ONU discontinuada = REACTIVACIÓN y no suma plata del mes, dec. 82); `cinco_cosas` v2.0 y el orden del día de `inicio_loki` son vistas. **Conciliador** (versión vigente: la del `datacenter/manifiesto`; libro de ventas r15 + r22, remitos r21; reglas C1-C7: facturado sin despachar, compró y la ficha no lo sabe, remito sin factura): corre antes del Sales Engine; lo decidido por Nicolás no se vuelve a preguntar (`restricciones.decididoConciliador`). Orden fijo del arranque: conciliador → Sales Engine → cinco_cosas → inicio (nunca mezclar salidas de corridas distintas). Detalle en `datacenter/script_inicio.protocolo`.

**Recompra:** sale de los pedidos/facturas. Ciclo = mediana de días entre compras (con ≥3 compras). Estados: le toca / atrasada / sin ciclo. OLT, placas, switches, CMTS, fuentes, EDFA, ODF, anticipos y ajustes no generan ciclo. Cada recompra tiene **Hecha / En espera** en la tarjeta de Postventa y en la ficha (`hz_recompra`). Ej. Howard: ~21 días (15-20 HG6543D por compra).

**Motor de oportunidades R6.5 (en producción):** unidad = ficha del CRM (cuit + `facturacionId` + `cuitsAdicionales`). Niveles en orden comercial:
0. **Cierre:** cotización vigente.
1. **Recompra con evidencia:** ≥3 compras de la línea con ciclo cumplido (ratio 0,8-2,5) o ≥4 pedidos en 36 meses.
2. **Reemplazo** (≥50 ONU discontinuadas o Huawei como marca principal, sin ONU FH en 12 m) o **venta cruzada** (≥50 ONU FH y nunca compró fibra).
3. **Retomar:** hipótesis (dormidos).
Exclusiones: cuentas fuera, cuentas compartidas, otro vendedor con más del 50 % (va a "Consultar"), neto < USD 300, solo HFC. Cada oportunidad muestra su evidencia al final de la tarjeta. Estos umbrales los eligió Claude: Nicolás puede ajustarlos. Backtest al 30/04: top 10 del motor = 50 % compró, contra 20 % ordenando por facturación histórica.
**Importador:** en el box de Pedidos de Seguimiento se suben Reporte_3 / Reporte_4 y, desde R6.7, el **Ventas** (xlsx); reconoce cuál es por columnas, muestra qué entra / sale / cambia y al Guardar escribe `reportes/*`, `facturacion`, `config/ventasControl` y `config/oportunidadesR65`.
**Pendiente aparte:** motor de cierre (maqueta `H1K9uZ6fXXB4bRPyP9FLF5`), esperando "hacelo".

**Seguimiento, 4 pestañas por prioridad:**
- **Para hoy:** vencido + hoy + las 3 mejores oportunidades del motor + alertas de Ventas (sin entregar / aceptada sin factura). Una tarjeta por cliente.
- **Próximos.**
- **Chip Limpieza** (base con fecha vencida o sin fecha; tope 5 fichas sin fecha por día) con tres botones: Contactado 7 días, Sin requerimiento 15 días, En seguimiento 5 días. Las cuentas con plata no entran (ya las empuja el Sales Engine) y en ellas los botones no cambian la etapa (dec. 61 y 65).
- **Postventa:** atrasados primero; recompras con Hecha / En espera.
- **Base para trabajar:** oportunidades 4 a 8 del motor + 5 prospectos de la rueda del día. No repite las de Para hoy, ni cuentas con agenda o contactadas en los últimos 7 días.
Orden dentro de cada pestaña: cotización / vencimiento / financiación / muestra › recompra / postventa › nivel del motor › puntaje › fecha. Sin fichas de métricas arriba.

**Pipeline:** suma, con IVA, las cotizaciones **vigentes** de cada cliente abierto (prospecto, contactado, calificado, cotizado, negociación); si el cliente no tiene cotizaciones, el `monto` de la ficha; más las vigentes de clientes ganados (recompra). Vigente = borrador, enviada, espera_aprobacion o espera_decision, no archivada, con fecha límite (mayor entre `vence`, `revisionFecha`, `hz_resultado.fechaSeguimiento`) de hoy en adelante. Vencidas, postergadas, sin fondos o sin cliente van a "Cotizaciones abiertas que no suman" con su motivo.

**Heredado de v27:** puntaje de cierre `prioInfo` (0-100) por etapa, cotización abierta, monto, muestra, recompra y financiación (alta ≥60, media 35-59, baja <35). Ganado del mes: cotizaciones `aceptada` con IVA por `fechaGanada`. Semáforo de contacto: negociación 3 días, cotizado 5, calificado 7, contactado 10, prospecto 14, ganado 30. **Tabla única de días (dec. 62 y 65):** Contactado 7, Seguimiento 5, Sin requerimiento 15 si ya compró (`clienteHorizon = si`) y 30 si nunca compró, Sin respuesta 3 (supuesto de Claude); vale para el chip, Registrar gestión, Próximo paso de la ficha y «No por ahora» de Estados WhatsApp.

## Pendientes
> Manda `config/continuidad` del CRM (se actualiza al cerrar cada chat); esta lista es histórica.
- Decisiones de Nicolás / con JP: SuperCanal (¿es suyo?), lista "Consultar" (25 cuentas), monto de Humac (7.000 o 0), NM48 Swissnet (precio 48F 1,7735 vs 1,5873; troncal vanos 100–120 m: AS80 no sirve, ver AS100/120; stock PK/PKP), Swissnet 0000-00023 (aceptada 05/10 sin factura: ¿se facturó?), TPP (¿es de Nicolás?).
- Comisión ago/sep para revisar con JP: Mónica FA1663 USD 3.000 y NM12 USD 1.275; Howard NM20 USD 510; Armstrong FA1678 USD 184 neto (cargada); Nodo Net FA1661 USD 5.456,25 neto y Frappa Gretix FA1657 USD 2.776 neto (sin decidir si son de Nicolás).
- Nicolás vuelve a subir los dos Ventas para limpiar refacturaciones; después, cada lunes, el de JP.
- Mejoras propuestas, esperando "hacelo": motor de cierre, botones de resultado por oportunidad (sirvió / no sirvió), limpieza de Vencidos, stock al lado de la recompra, filtro ≤ USD 8.000, medir el motor el 10/11, libro de partidas (Fullsat, Wisp, Telviso).
- De listas anteriores (verificar si ya están): Validación técnica en 3 niveles (🟢 AN6000 + ONT FH nada · 🟡 AN5516 o sin versión: pedir versión y placa · 🔴 otra marca o desconocida: muestra/OMCI), fix "2 PDF de cliente nuevo = 2 fichas", panel "No se guardó" con reintentar, Seguimiento sin escribir al abrir, mostrar `contactosAdicionales`, artículos por clasificar.
- Evaluar punto por punto la propuesta LOKI de CRM determinístico (ficha única, motores M1-M7, orquestador sin IA, A1-A20, migración en 5 fases).
- Subir el PDF de la factura de Villa del Rosario.
- Apagar en Cowork la tarea "Tipo de cambio BNA al CRM" vieja.


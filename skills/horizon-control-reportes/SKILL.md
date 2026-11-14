---
name: "horizon-control-reportes"
description: "Usar cuando Nicolás suba un Excel o CSV (Finnegans u otro reporte) para cargar al datacenter del Horizon CRM: control de calidad y auditoría PASA/FALLA antes de cargar."
---

# Control de reportes · datacenter Horizon CRM

Todo Excel/CSV que suba Nicolás pasa por el mismo script, con reglas fijas, antes de tocar el datacenter. **El script decide; Claude lee el informe y lo explica.** El script no escribe en el CRM.

CRM: `https://claude.ai/artifact/5SPm4UZTgiF5JXx7GKTybq`. El código vive en el CRM, documento `datacenter/script_control_reportes` (campo `codigo`, versión en `version`; la vigente la dice el manifiesto). Esa es la única copia válida.

## Pasos (siempre iguales)
1. Bajar el script: ArtifactData `get` de `datacenter/script_control_reportes` con `out_dir` al scratchpad y guardar el campo `codigo` como `control_reportes.py` (con json.load, nunca reescrito a mano).
2. Bajar el cruce: ArtifactData `get` de `datacenter/clientes_resumen` con `out_dir` al scratchpad.
3. Si el reporte ya se cargó antes, bajar `datacenter/controles` y guardar su campo con el id del reporte (ej. `r15`) como `anterior.json` para pasarlo con `--anterior`.
4. Copiar cada archivo subido a su propia carpeta y correr:
   `python3 -I control_reportes.py ARCHIVOS --crm <clientes_resumen.json> [--anterior anterior.json] --salida <scratchpad>/control`
5. Leer `informe.md` de cada archivo/hoja y responder a Nicolás corto: la línea PASA/FALLA, qué significa para vender (corte, ventas nuevas, clientes sin ficha, qué quedó en cuarentena y por qué) y qué falta para cargar. Sin volcarle tablas.
6. No se carga nada sin PASA **y** su «hacelo». Con las dos cosas:
   - Respaldo de cada documento existente que se toca (ej. `datacenter/indice_respaldo_AAAA-MM-DD`).
   - Datos en la colección `reportes` con id nuevo (`rN`, `rN_2`…, partes de ~110 KB, formato v2: `f` campos, `dic` diccionarios, `d` filas). Nunca se pisa un reporte cargado.
   - Releer lo escrito y comparar fila por fila contra lo enviado: PASA/FALLA en una línea.
   - Actualizar `datacenter/indice` (fuente, corte, límite) y guardar el `resultado.json` en `datacenter/controles` bajo el id del reporte.
   - Todo en un solo `batch` con `if_version` en lo existente.

## Qué controla (reglas fijas del script v1.1)
- Lectura: .xlsx/.xlsm (todas las hojas), .csv/.txt (UTF-8 o CP1252, separador `;` `,` tab), .xls que en realidad es HTML (Finnegans). Un .xls binario viejo → pedir que lo guarde como .xlsx o .csv.
- Encuentra la fila de títulos aunque haya encabezados arriba y reconoce el tipo: cuenta corriente, saldos, crédito, ventas por línea, comprobantes, clientes. «Documento» en Finnegans es tipo de comprobante, no CUIT.
- Aparta a cuarentena (con fila de Excel y motivo): totales/subtotales, duplicados exactos, fechas ilegibles o futuras, CUIT sin dígito verificador válido o vacío, importes ilegibles.
- FALLA si supera topes: fecha ilegible >2 %, fecha futura >2 %, CUIT inválido >5 %, sin CUIT >20 %, importes ilegibles >1 %, Bruto + Otros ≠ Total en más del 1 %, saldo acumulado que no cierra con Debe−Haber >1 %, reporte más viejo que lo ya cargado, ninguna fila válida.
- Comprobantes: signo (NC negativa, factura/ND positiva), comprobante repetido (tipo + número), tipo de cambio coherente con la moneda (pesos = 1), totales por tipo. **Las ND/NC por diferencia de cambio no son venta.** Totales sin IVA (Bruto) cuando existe la columna.
- Monedas siempre separadas; si no hay columna de moneda, avisa y no suma. Cuenta corriente = Debe−Haber, nunca sumar saldos.
- Compara con la carga anterior: mismo archivo, meses cerrados con menos filas o con importe distinto (NC/refacturación), CUIT nuevos.
- Cruce con el CRM por CUIT; avisa CUIT sin ficha y nombres con varios CUIT. Si el reporte no trae CUIT, lo asigna por **nombre exacto** (sin forma societaria) contra `clientes_resumen`; nombre que no coincide o que tiene dos CUIT queda sin CUIT (`cuitPorNombre=1` marca los asignados). Nunca por parecido.
- Reglas: marca otro vendedor y no prospectar (se cargan como dato, no se trabajan); Full Sat y Telviso son de Nicolás aunque otra fuente diga lo contrario. Si hay columna de vendedor, la lista: las ventas de Nicolás cuentan aunque figuren como «Ventas Horizon».

## Salidas
`informe.md` (para leer), `resultado.json` (veredicto, corte, totales por moneda y por mes; sirve de `--anterior`), `limpio.json` (filas que pasaron, normalizadas, listas para el datacenter), `cuarentena.csv` (filas apartadas con motivo; se le manda a Nicolás si pide verlas).

## Cargado hasta ahora
- `reportes/r15` (+ r15_2–r15_4): Reporte_15 Finnegans, libro de ventas 2.990 comprobantes 01/12/2020–05/11/2026, PASA el 08/11/2026.

## Cambiar el script
Los topes y reglas solo cambian con el «hacelo» de Nicolás y con Opus: editar, correr los casos de prueba y el último reporte real, subir la versión en `datacenter/script_control_reportes` (leer y pasar `if_version`) y anotar qué cambió en el campo `probado`. Actualizar esta skill si cambia el procedimiento.

## Modelo
Correr el control y explicarlo: Sonnet. Cambiar el código o decidir una unificación por lo que salga del control: Opus.
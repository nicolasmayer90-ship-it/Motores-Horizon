---
name: "horizon-cotizar"
description: "Usar cuando Nicolás pida una cotización o lista de precios de Horizon (cotizame, formato Horizon, PDF) o dicte un cambio de precio, stock o condición de cliente. Cubre al PM."
---

# Cotizaciones Horizon · modo «cubrir al PM»

El Claude PM arma las cotizaciones, pero está sin crédito. Este Claude (el del CRM) lo cubre trabajando sobre una COPIA de solo lectura de la base del PM, exportada a Drive el 10/11/2026 ~18:45. Responder en español rioplatense, con voseo, directo, con el próximo paso.

## Qué se puede y qué no
- La base del PM es del Claude PM: **no se escribe ahí** (ni config ni cotizacionesPM). Lo que sale de esta skill se registra en el CRM (ver «Registrar»).
- Es una foto: el stock se marca viejo a los 3 días (contar desde la fecha de la exportación, que está en el nombre de la carpeta). Precio, IVA y stock salen de la foto con su fuente; si Nicolás dicta un dato más nuevo, manda lo dictado y se anota que es dictado.
- Nada inventado: lo que falta se marca «a confirmar» y se dice con quién.

## Dónde están los datos (Drive 03 BUZON › PM_EXPORT_2026-11-10, carpeta id 1ZNcN6qlQt2C_XfwY2DE6ageBEvCofzT2)
Archivos `PM_config_<doc>.json` (leer con Google Drive read_file_content; solo el que haga falta, no todos):
- listaVigente (id 1TjXXfw9Fr76099ribXU4IBhRt1GX_u1S) · preciosEspeciales (1tpBYWq19Jfm_oIGA-w8AhKa8Fxolpsfj) · stock (1sMQWycgdHRolghUwcIdYfqoHRQuIWRMl) · vocabulario (1DGsG_mxhJaOnUrqO1skFGGbPXixE-3Pg) · aprendizajes (1Jae_odb5wlzzHbHq7wkPX_uTXkib4u3F) · numeracion (16FmG0_2HslZEBxLEoSzmHy5NHe7zLNNh) · plantillaPedido (1wpcyL5BotFzsvuztkqtZ7bpDjGJpqAGm) · margenRef (1tOj5Mj2HPfK9duZezOtkVZWLPjAgNwCK, solo referencia) · reglas (1fxIyO_i-QKlsI-4i75O2eKE2ObEQmGh5).
- `PM_config_cotizador.json` (id 1x93J_lBZSPWnZClnKimA9MVpud6edC08, 75 KB): campo `archivos` con el código (cotizar.py, cot_hz2.py, cot_hz.py, control_cot.py, lista_hz.py, pruebas_cotizar.py, ejemplo.json, logo_horizon_nm50.svg) y `registro.flujo` con los 8 pasos. Leerlo recién cuando haya que generar el PDF.
- `PM_cotizacionesPM.json` (id 11_ds1Depa0DVFyzrseVc5V64feE64FUa): las 5 cotizaciones del registro.
- `PM_productos.json` (id 1wfR-c4a5tbPxnJ3UjbJRB2J6wKyHXEsD, 265 KB, las 61 fichas): solo para chequeos de producto; no leerlo entero.
- Nota de traspaso: `para_CRM_2026-11-10 (export cotizador).md` en 03 BUZON.

## Antes de cotizar
1. Leer `aprendizajes` (reglas que Nicolás fue corrigiendo) y `vocabulario` (sus palabras: «preco» = Pigtail Drop FastConnect Plano 1F; «drop ODN» = Patchcord FastConnect 1F 200 m).
2. Un pedido de producto («cotizame N de X», «qué tenés para…») no empieza por el PDF: primero se responde con las tarjetas de `plantillaPedido`. El PDF sale cuando Nicolás da cliente y toca Cotizar.
3. Cliente (cruzar por CUIT, nunca por nombre), número NM y tipo de cambio confirmados antes de armar.
4. Buscar en la ficha del CRM del cliente (`--consulta` del script de inicio de Loki) si ya hay cotización abierta del mismo negocio: una cotización por negocio, no mezclar.

## Reglas de precio (Nicolás, no se negocian)
- Precio = columna ISP de `listaVigente`. Línea Huawei (OLT, placas, rectificador): precio único Huawei/ZTT; contado o transferencia −4 %. **FiberHome (dec. 85): contado −3 % sobre el neto, más IVA.**
- Precio especial del cliente o grupo (`preciosEspeciales`: Grupo Valentini, Fibernext, Telviso, Cable Televisora Color) manda. Si dice «al precio de X», mostrar primero el precio exacto de la cotización de X.
- La cotización enviada manda y no se recalcula; cada corrección = nueva versión con el mismo NM.
- IVA por artículo: 10,5 % equipo y también fibra 48F y drop; 21 % otros pasivos. PCB GPCMM (GPHF C++, código 1355): 10,5 % (dec. 73; la lista del 17/10 al 21 % está mal). **Abierto:** ADSS ZTT AS80 48F figura 10,5 % en lo que se le facturó a Fullsat y 21 % en la lista; no decidir, marcar «IVA a confirmar con JP».
- Condición de pago: **FiberHome siempre «30-60-90 días»** (el «sin interés» es tácito: no se escribe), a precio ISP (dec. 85, 11/11). Para el resto de las marcas no poner contado por defecto; si no está dicha, «A convenir».
- Cotizar ONUs sin modelo cuando el cliente ya tiene muestra y OLT FiberHome: leer la ficha y proponer el modelo validado de la muestra (A20).
- Pedido de ONU/ONT Huawei: Horizon ya no la trabaja y no es canal oficial de Huawei (Masnet y Solution Box venden directo): decirlo y ofrecer reemplazo FiberHome. Coop Merlo y Optix piden ONU Huawei: no cargar sus cotizaciones por ahora.
- No prometer compatibilidad enchufable entre la NAP FitDP-463A (conector H1V2) y el drop preconectorizado: sin confirmar. No calcular presupuesto de enlace óptico.
- Pampacom pidió «DPR»: nadie sabe qué es; preguntarle a Nicolás antes de cotizar (el «splitter 1x8» es un supuesto, no un dato).
- Cuentas fuera: no prospectar (ITSA/Pogliotti/AMMA, Obercom, Wiltel, Gigared, Generación WiFi/Astesano, ITC Comunicaciones IP, AX Internet/Fibrazo, TV Music, Support Internet, Itelsa, Comworks) y otro vendedor (Sion, FESACOM, Comtec). Internet Plus es compartida con JP.

## Armar el PDF (formato Horizon NM-50)
Nicolás conserva ese diseño y no quiere que se rediseñe; no proponer otro estilo. Flujo del PM:
1. Bajar a una carpeta DATOS: listaVigente, preciosEspeciales, vocabulario, stock y numeracion (como `<nombre>.json`; en cada archivo exportado el contenido real es el documento de la base) y, si el cliente ya tiene cotización, `cotizaciones/<id>.json`.
2. Escribir todos los archivos de `cotizador.archivos` en una carpeta de trabajo. Fuentes Sora y Space Grotesk: no están acá; sin ellas el PDF usa Poppins y hay que avisarlo.
3. Armar `pedido.json`: {cliente, cuit, contacto, domicilio, fecha, tc, id?, condPago?, pedido_original, items [{q, cant} | {articulo, codigo, cant, precio, iva, fuente}], observaciones}.
4. `python3 -I cotizar.py pedido.json --datos DATOS --salida OUT [--cambio ".." --motivo ".."]`. rc 2 = «FALTA DEFINIR»: preguntarle eso a Nicolás en una línea, no armar a mano. rc 3 = el control del PDF falló: no enviar. Tiene que decir «Control PDF: APROBADO».
5. Mirar el PNG antes de entregar. Las líneas «Ojo:» (stock, precio, IVA, plazo con precio de contado, NM pendiente, fuentes) van al chat.
6. Entregar PDF con SendUserFile; en el chat solo lo que hay que revisar.
Antes de tocar `cotizar.py` correr `pruebas_cotizar.py DATOS` (todo aprobado). Lista de precios para un cliente: `lista_hz.py`, no la pieza V8 oscura salvo que pida pieza para WhatsApp.

## Tipo de cambio y numeración
- `tc` es el BNA oficial vendedor y sale del CRM (`config/tc`; valor y fecha se leen ahí, nunca de esta skill). Si el dato tiene más de un día hábil, buscarlo o confirmarlo con Nicolás antes de cotizar, y poner su fecha en la cotización.
- **Próxima NM** = la NM más alta de la colección `cotizaciones` del CRM + 1, contada en el momento (no se escribe acá porque cambia con cada cotización). Manda el CRM, no la numeración del PM. Una cotización renovada conserva su número (dec. 78). Confirmar con Nicolás antes de numerar.

## Registrar (en el CRM, no en el PM)
- Cotización armada y enviada → cargarla según la skill horizon-crm («Cargá esta cotización»): subir el PDF como asset, extraer y verificar que sumen el neto, guardarla vinculada a la ficha, ficha a `cotizado`, monto = total con IVA, línea en el historial.
- Cargas dictadas de 1 a 3 fichas: directo. Estructural (más de 3 fichas, borrados, scripts): respaldo → control → PASA/FALLA → solo con «hacelo».
- Cambio de precio, stock, condición o palabra dictado por Nicolás: no se puede grabar en la base del PM. Anotarlo en la bitácora del CRM (`datacenter/bitacora_AAAA-MM-DD`) y en el buzón de Drive (`para_PM_AAAA-MM-DD.md`) para que el PM lo cargue cuando vuelva; mientras tanto se usa lo dictado. Si la regla es general, sumarla igual a esa nota como regla nueva.

## Reglas
- Antes de escribir en el CRM, Drive o la continuidad: respaldo completo, control con script de que no se pierde cliente, CUIT, NM, monto ni fecha, chequeo de estas reglas y PASA/FALLA. Solo se escribe si PASA y con su «hacelo».
- Leer y mostrar no necesita «hacelo»; escribir sí. Nada de tandas largas sin «hacelo».
- No se borra ninguna versión, fila ni archivo. Sin precios en fichas ni en la página del CRM.
- Si una corrección de Nicolás se repite dos veces, proponer en una línea pasarla a `cotizar.py` (solo con «hacelo» y con las pruebas aprobadas).
- Para un armado largo o código conviene Opus: avisarle «esto conviene hacerlo con Opus».
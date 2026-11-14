---
name: "horizon-investigar-cuenta"
description: "Usar cuando Nicolás pida investigar una empresa o cliente de Horizon, buscar contactos, dueños, decisores o LinkedIn de una cuenta, o cuando el estado de un cliente no tenga contacto de compras."
---

# Investigar una cuenta (Horizon)

Objetivo: llegar al DECISOR (dueño, socio gerente, gerente técnico o compras), no a cualquier empleado. En ISPs y cooperativas chicas del interior el decisor casi siempre es el dueño, y casi nunca está en Lusha. La precisión y la fuente valen más que la cantidad de contactos.

**Activador automático:** "estado de <empresa>" o "buscar contactos de <empresa>". Si la ficha no tiene un contacto válido o su cargo no está verificado, correr este proceso sin que Nicolás tenga que pedir "buscá en LinkedIn".

## Orden obligatorio (no saltear pasos)
1. **Qué ya tenemos:** ficha del CRM (contacto, `contactosAdicionales`, historial, notas), nota `config/continuidad` del PM y bitácora en Drive (02 BITACORA). No buscar lo que ya está.
2. **Fijar identidad:** razón social, nombre comercial, CUIT, ciudad, web. Desambiguar homónimos (ej. Fiberland Cipolletti ≠ empresa italiana de seguridad informática). Un nombre que coincide no prueba vínculo.
3. **Dueños y socios (web + prensa local + registros):** WebSearch en modo **extended** desde el arranque, varias consultas en el mismo turno:
   - web corporativa: Nosotros / Equipo / Contacto
   - `<empresa> <ciudad> fundadores` / `dueño` / `socio gerente`
   - diario local (ej. LM Cipolletti, Río Negro, La Voz, El Litoral) + nombre de la empresa
   - razón social + CUIT (boletín oficial, constitución de sociedad)
   - licencia ENACOM (titular); cámaras y eventos (CAPPI, CABASE, Fecosur, Colsecor, Nplay)
   Leer el artículo con WebFetch y anotar TODOS los nombres y roles (no solo el primero).
4. **LinkedIn de cada persona y de la empresa:** WebSearch extended:
   - `"<nombre>" "<empresa>" linkedin` y `<empresa> linkedin`
   - `site:linkedin.com/in/ "<empresa>" (fundador OR socio OR gerente OR compras OR ingeniería OR redes OR operaciones)`
   - `site:linkedin.com/in/ "<marca comercial>" "<provincia>"`
   - `"<empresa>" "gerente técnico" OR "responsable de compras" OR "director"`
   Guardar la URL directa del perfil; si no hay URL, decirlo.
5. **Recién después, Lusha** (cuesta créditos): `prospecting_contact_search` (filtros de cargo y seniority resueltos antes con `prospecting_contact_filters`; o `decision_makers_buying_group_search` con el dominio) para empleados técnicos/compras. No revelar mails ni teléfonos sin ok de Nicolás (avisar cuántos créditos).
6. **Canal institucional:** web oficial, Guía Cores, Facebook (WhatsApp, fijo, mail). No tratarlo como contacto de compras.

No eludir logins ni bloqueos. No recolectar mails o celulares personales que no estén publicados profesionalmente. Si no hay búsqueda web, decirlo y no simularla.

## Prioridad de personas
(a) socios, fundadores y dirección · (b) compras · (c) gerencia técnica, ingeniería, redes, operaciones · (d) comercial y administración. No inferir que alguien compra por su cargo: "socio" no es "comprador".

## Nivel de validación de cada persona
- **CONFIRMADO:** fuente fiable del vínculo con la empresa y del cargo (con link y fecha).
- **POTENCIAL:** perfil individual asociado a la empresa, pero cargo actual, vigencia o rol en compras sin confirmar. Decir qué falta.
- **BÚSQUEDA PENDIENTE:** nombre respaldado sin URL de perfil individual. Dar solo un link real a resultados de búsqueda de LinkedIn, marcado como búsqueda, nunca como perfil.
- **NO ENCONTRADO:** decir qué se buscó y dar el canal institucional.

## Antes de entregar (control propio)
- ¿Encontré al menos un dueño/decisor con fuente? Si no, decir explícitamente qué busqué y que no apareció; no presentar empleados como si fueran decisores.
- Cada dato con su fuente (link) y fecha. Separar **verificado** (fuente vista por Claude) de **dato de otra herramienta** (ChatGPT, otro Claude) y de **suposición**.
- Si Nicolás trae resultados de otra herramienta: verificarlos y completarlos (ej. otros socios que no nombró), no solo copiarlos.
- Una búsqueda "standard" que vuelve vacía o con ruido NO alcanza: repetir en extended con otra formulación antes de decir que no hay datos.
- Nunca armar de memoria un slug `linkedin.com/in/...` ni asignar perfil por parecido de nombre. Distinguir "perfil directo" de "búsqueda".
- Si una fuente vieja contradice una más reciente, avisarlo.
- Facturas, remitos, pedidos y cotizaciones no son lo mismo; sumar personas no cambia cantidades ni estados.

## Dónde guardar
- Es investigación puntual por pedido, no un rastreo permanente. No contactar a nadie por iniciativa propia.
- Cliente con ficha: `contactosAdicionales` + línea de historial en el CRM, con `nombre`, `cargo`, `estado_validacion`, `linkedin_tipo` (perfil | búsqueda), `linkedin_url`, `url_evidencia`, `fecha_verificacion`, `fuente`.
- Sin ficha (o cuenta sin confirmar si es de Nicolás): bitácora en Drive 02 BITACORA (id 1TJgAwxeUQ2w6N2AJUtv026njvwoLevHQ) + línea en `config/continuidad` del PM.
- Nunca guardar datos personales sensibles; solo datos comerciales y perfiles públicos.

## Presentación
Dentro de la tarjeta LOKI · INTELIGENCIA COMERCIAL: bloque **"Contactos identificados"** con decisores primero. Por persona: nombre — cargo verificable o "cargo sin confirmar" · nivel · vínculo probado (dato concreto) · LinkedIn (URL real + "perfil directo" o "búsqueda") · evidencia (link) · fecha de verificación · qué falta validar. Después técnicos/administrativos y al final el canal institucional.
Diseño: Manrope títulos y KPIs, Inter detalles, tarjeta principal con borde azul, "Antes de avanzar" y "Próxima acción sugerida" a ~14 px. **Sin "Mensaje listo para enviar" ni botón Copiar** salvo que Nicolás lo pida.

## Caso de control: Fiberland S.R.L. (05/11/2026, revalidar antes de reusar)
Cipolletti, Río Negro · CUIT 30-71638619-4 · fundada 15/03/2019.
- **Juan Manuel Rosales**, cofundador — CONFIRMADO (LM Cipolletti 03/10/2026: https://www.lmcipolletti.com/cipolletti/fiberland-conectividad-alta-velocidad-adn-cipoleno-n1255050). LinkedIn perfil directo: https://www.linkedin.com/in/juan-manuel-rosales-33468619/ (figura en Fiberland SRL). Rol en compras sin confirmar.
- **Manuel Alberto Rosales**, cofundador — CONFIRMADO (misma nota). LinkedIn: búsqueda pendiente.
- **Javier Bustamante**, "Redes" — POTENCIAL. https://www.linkedin.com/in/javier-bustamante-a2bba3123/ (también en Lusha). Rol en compras sin confirmar.
- Lusha: Enrique Godoy (técnico IT), Romina Arce y Samanta Torres (administración) — POTENCIAL.
- Empresa: https://ar.linkedin.com/company/fiberlandpatagonia · https://fiberland.com.ar/contacto/ · info@fiberland.com.ar.
Error que originó la regla: se empezó por empleados en Lusha y con búsqueda standard; la prensa local tenía a los dueños. ChatGPT encontró la nota pero no el perfil directo ni al segundo socio.
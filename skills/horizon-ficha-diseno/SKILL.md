---
name: "horizon-ficha-diseno"
description: "Usar cuando Nicolás pida una ficha de cliente, presentación, tótem de feria o pieza con la Base de diseño Horizon (azul noche, hexágonos). Entrega PNG. Cubre al PM."
---

# Diseño Horizon · fichas, presentaciones y tótem · modo «cubrir al PM»

El Claude PM era además el diseñador y está sin crédito. Este Claude lo cubre. Los flyers, piezas de WhatsApp (chat o estado), portadas, fichas de producto y listas de precios con el motor V8 se resuelven con la skill `horizon-diseno`; esta skill agrega fichas de cliente, presentaciones, tótem de feria y la Base de diseño.

## Regla siempre (Nicolás 09/11)
Toda ficha, presentación o pieza parte de `config/plantillaFicha` (copia en Drive: `PM_config_plantillaFicha.json`, id 1eg4a2zXOFq63nWZq3jVsGLoumyNTBORT, 113 KB) y de la Base de diseño Horizon (https://claude.ai/artifact/NzRAv1pmx1ZqfTdjNE1SXi). Nunca rediseñar de cero. Antes de entregar correr el control de calidad `calidad_diseno.py` y mostrar PASA/FALLA. El script vive en el campo `calidad` de `config/plantillaFicha` (misma copia de Drive): guardarlo como `calidad_diseno.py` en una carpeta aparte y correr `python3 -I calidad_diseno.py <tokens.json> <base_aprobada.dc.html> <ficha.dc.html>` (la base aprobada es la referencia: ninguna ficha trae colores, fuentes o textos fuera de los tokens o de la base; código 1 si algo falla); si no se puede correr, decirlo y no afirmar que pasó.

## Estilo Horizon
Azul noche plano, hexágonos, Manrope + Inter, un solo azul fuerte (#2f6bff), sin degradés ni brillos, sin luz de contorno por defecto. Cotización y lista de precios: formato NM-50 (skill horizon-cotizar), no la pieza V8 oscura salvo WhatsApp.

## Entrega
Nicolás no trabaja con Adobe Illustrator: entregar la pieza terminada en PNG (más el PDF si lo pide), no SVG ni archivos editables para retocar. Mirar el resultado antes de entregarlo.

## Ficha de cliente
- Maqueta: `Maqueta_ficha_cliente_Horizon.html` y la nota `para_CRM_2026-11-10 (ficha MAQUETA…)` en Drive 03 BUZON. Es solo maqueta: los datos los carga el CRM desde la ficha viva.
- Pedidos de Nicolás para el banner (plantillaFicha 1.1): sin «Cliente Horizon» (redundante con el logo), chip de pago más chico en la fila del CUIT, letra de datos igual a los chips, logos más grandes. Muestra D con Full Sat aprobada.
- La ficha grande (980×1100) sigue con el diseño viejo: pasar al diseño nuevo espera su «armalo». En el CRM, la ficha no se toca ni se le agregan botones salvo lo que pida.
- Dato centrado en el valor Stockfish (decisión 09/11); sin niveles alto/medio/bajo; la barra queda. Hexágonos: los llena Stockfish donde hay evidencia y el resto por dictado (regla de hexágonos: supuesto a revisar).

## Fotos y logos (límites reales)
- Fotos de las cajas HUB FitDP-461C y 461D: aprobadas (ids de asset 50d4af4fd9ffb5b3bf009cb520ba090e y 9a2d4cb650fb6680760f1da74ff8f54e en la base del PM; el CRM no las tiene).
- **No usar fotos de las NAP FitDP-462A y 463A**: llevan impreso el logo de un cliente (ufinet). No hay foto sin marca de la NAP: dejar un lugar rotulado, no inventar.
- Fotos de ~617–717 px y logos de baja resolución: a tamaño tótem se ven blandos; pedir originales en alta o vector.
- Los assets (fotos, fuentes Poppins, logos, referencias, PDFs) no se pueden bajar de la base del PM por Drive. El motor de diseño viaja en `Horizon_motor_diseno_2026-11-10.zip` (4,7 MB, lo subió Nicolás a mano; el conector de Drive no abre zips): hay que pedirle que lo adjunte extraído. No usar el zip viejo; manda la base del PM (`PM_config_motorV8.json`, id 1ziL7mjRcSIGZ1Pwj8Cv2UJexq4mQOMMI, y `PM_config_motorV8_plantilla.json`, id 1xJYt6rAziXb3rmdSbmHdkmURp_H-imZX).

## Tótem de feria (en curso, esperando al PM)
180×240 cm, vertical, 1 px = 1 mm. Canvas publicado: https://claude.ai/artifact/4mb2q6Me823PUjW2Ls8vin (logos Horizon y FiberHome, título «Red FTTH preconectorizada», diagrama OLT → HUB → NAP → DROP → ONT, pie con contacto; solo usa datos de las fichas). Lo que pidió ahora: un esquema con las fotos de las cajas, en diseño de feria (referencia: panel con cajas colgadas de un stand). Falta poner las fotos de HUB 461C/461D en el esquema; la NAP va con lugar rotulado.

## Contenido
- Solo datos de las fichas de producto y del CRM; nada inventado. Compatibilidad NAP FitDP-463A (H1V2) con drop preconectorizado: sin confirmar, no prometerla. No presupuesto de enlace óptico.
- Contacto en piezas: Nicolás Mayer, tel. 11 2751-6349, horizon-trd.com, «Escuchar para Conectar.»
- Antes de escribir en el CRM, Drive o continuidad: respaldo, control con script, PASA/FALLA y su «hacelo».
- Piezas largas o código del motor: conviene Opus; avisarle.
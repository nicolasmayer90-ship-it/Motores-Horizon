-- Horizon DB · esquema v2.2 (Etapa 1: solo lectura)
-- v2.2 (17/11): tabla grupos (datacenter/grupos) para la tarjeta de estado.
-- v2.1 (17/11): los controles de duplicados miran solo fichas activas y usan todos los CUIT de la ficha;
-- compradores sin ficha como vista.
-- v2.0 (17/11): la base guarda la ficha y la cotización enteras (columna doc, JSON tal cual el CRM)
-- y suma lo que leen los motores: CUIT adicionales, contactos, operación de la cotización,
-- remitos (reporte 21), tc/otros/usuario del libro y Stockfish. comparar.py controla doc por doc.
-- La llave de todo es el CUIT normalizado (solo dígitos). Las fichas sin CUIT quedan con cuit NULL.
-- En la Etapa 1 la base se arma entera en cada carga desde la exportación del CRM:
-- no se edita a mano y no tiene herramientas que escriban.

PRAGMA foreign_keys = ON;

CREATE TABLE carga (
    id            INTEGER PRIMARY KEY,
    cargado       TEXT NOT NULL,   -- cuándo se armó la base (hora local de la PC)
    origen        TEXT NOT NULL,   -- carpeta de la exportación del CRM
    hoy_motor     TEXT,            -- fecha del día que corrió correr_dia (si había salida)
    corte_stock   TEXT,            -- foto de HIVE copiada en el CRM
    corte_lineas  TEXT,            -- última fecha con líneas de factura
    corte_libro   TEXT,            -- última fecha del libro de ventas (reporte 15 + 22)
    conteos       TEXT             -- JSON: cuántas filas entraron por tabla
);

CREATE TABLE clientes (
    id               TEXT PRIMARY KEY,   -- id de la ficha en el CRM
    empresa          TEXT NOT NULL,
    cuit             TEXT,               -- solo dígitos
    etapa            TEXT,
    prioridad        TEXT,
    tipo             TEXT,
    zona             TEXT,
    contacto         TEXT,
    telefono         TEXT,
    email            TEXT,
    marca_olt        TEXT,
    modelo_olt       TEXT,
    cliente_horizon  TEXT,
    productos        TEXT,
    proxima_accion   TEXT,
    proxima_fecha    TEXT,
    ultimo_contacto  TEXT,
    monto            REAL,
    no_prospectar    TEXT,
    notas            TEXT,
    actualizado      TEXT,
    -- v2.0: lo que leen los motores y no estaba
    creado           TEXT,
    pago             TEXT,
    tecnologia       TEXT,
    abonados         TEXT,
    facturacion_id   TEXT,
    no_prospectar_motivo TEXT,
    otro_vendedor    TEXT,
    cuenta_compartida TEXT,
    archivada        TEXT,
    archivada_fecha  TEXT,
    archivada_motivo TEXT,
    unificada_en     TEXT,
    motivo_perdida   TEXT,
    fecha_ganado     TEXT,
    fijado           TEXT,
    doc              TEXT NOT NULL      -- la ficha entera, JSON tal cual el CRM
);
CREATE INDEX clientes_cuit ON clientes(cuit);
CREATE INDEX clientes_fecha ON clientes(proxima_fecha);

CREATE TABLE historial (
    cliente_id  TEXT NOT NULL REFERENCES clientes(id),
    t           TEXT,
    txt         TEXT
);
CREATE INDEX historial_cliente ON historial(cliente_id, t);

-- Todos los CUIT de una ficha: el principal y los adicionales (cuitsAdicionales)
CREATE TABLE cliente_cuits (
    cliente_id  TEXT NOT NULL REFERENCES clientes(id),
    cuit        TEXT NOT NULL,
    nombre      TEXT,
    cond_iva    TEXT,
    principal   INTEGER NOT NULL      -- 1 = el CUIT de la ficha
);
CREATE INDEX cliente_cuits_cuit ON cliente_cuits(cuit);

CREATE TABLE contactos (
    cliente_id  TEXT NOT NULL REFERENCES clientes(id),
    nombre      TEXT,
    cargo       TEXT,
    celular     TEXT,
    mail        TEXT,
    fuente      TEXT
);
CREATE INDEX contactos_cliente ON contactos(cliente_id);

CREATE TABLE cotizaciones (
    id             TEXT PRIMARY KEY,
    numero         TEXT,
    cliente_id     TEXT,          -- oportunidadId (puede no tener ficha)
    cuit           TEXT,
    cliente        TEXT,
    fecha          TEXT,
    vence          TEXT,
    estado         TEXT,
    cond_pago      TEXT,
    neto           REAL,
    total          REAL,
    notas          TEXT,
    actualizado    TEXT,
    -- v2.0
    marca          TEXT,
    familia        TEXT,
    cond_iva       TEXT,
    tc             REAL,
    iva_total      REAL,
    fecha_ganada   TEXT,
    archivada      TEXT,
    reemplazada_por TEXT,
    doc            TEXT NOT NULL      -- la cotización entera, JSON tal cual el CRM
);
CREATE INDEX cotizaciones_cliente ON cotizaciones(cliente_id);
CREATE INDEX cotizaciones_cuit ON cotizaciones(cuit);

CREATE TABLE cotizacion_items (
    cotizacion_id  TEXT NOT NULL REFERENCES cotizaciones(id),
    codigo         TEXT,
    articulo       TEXT,
    marca          TEXT,
    cantidad       REAL,
    precio         REAL,
    iva            TEXT,
    descripcion    TEXT,
    neto           REAL
);
CREATE INDEX items_codigo ON cotizacion_items(codigo);

-- Operación de la cotización (hz_operacion): pedido, pago, despacho, entrega, factura
CREATE TABLE cotizacion_operacion (
    cotizacion_id     TEXT PRIMARY KEY REFERENCES cotizaciones(id),
    pedido_confirmado TEXT,
    pago              TEXT,
    pago_at           TEXT,
    despacho          TEXT,
    despacho_at       TEXT,
    entrega           TEXT,
    entrega_at        TEXT,
    factura           TEXT,
    cierre            TEXT,
    doc               TEXT NOT NULL   -- hz_operacion entero
);

-- Líneas de factura por producto (colección facturacion del CRM)
CREATE TABLE factura_lineas (
    cuit         TEXT NOT NULL,
    cliente      TEXT,
    comprobante  TEXT,
    fecha        TEXT,
    tipo         TEXT,
    cod          TEXT,
    producto     TEXT,
    marca        TEXT,
    familia      TEXT,
    cantidad     REAL,
    vendedor     TEXT,
    subfamilia   TEXT,
    pendiente    REAL
);
CREATE INDEX lineas_cuit ON factura_lineas(cuit, fecha);
CREATE INDEX lineas_comp ON factura_lineas(comprobante);

-- Libro de ventas de Finnegans (reportes 15 y 22): una fila por comprobante
CREATE TABLE libro_ventas (
    tipocomp     TEXT NOT NULL,
    comprobante  TEXT NOT NULL,
    fecha        TEXT,
    cuit         TEXT,
    cliente      TEXT,
    moneda       TEXT,
    bruto        REAL,
    total        REAL,
    reporte      TEXT,
    -- v2.0
    otros        REAL,
    tc           REAL,            -- pesos por dólar en las filas en USD; las filas en pesos traen 1
                                  -- (casi todas ND/NC por diferencia de cambio, que no son venta)
    detalle      TEXT,
    fecha_alta   TEXT,
    usuario      TEXT,            -- quien la dio de alta en Finnegans, no el vendedor
    cuit_por_nombre INTEGER,      -- 1 = el CUIT se asignó por nombre exacto
    PRIMARY KEY (tipocomp, comprobante)
);
CREATE INDEX libro_cuit ON libro_ventas(cuit, fecha);

-- Remitos y devoluciones de venta (reporte 21): los despachos reales, sin importes
CREATE TABLE remitos (
    fecha        TEXT,
    tipo         TEXT,            -- Remito de Venta o Devolución de Venta
    cliente      TEXT,
    cuit         TEXT,
    cuit_por_nombre INTEGER,
    comprobante  TEXT,
    producto     TEXT,
    detalle      TEXT,
    cantidad     REAL,
    pendiente    REAL,
    vendedor     TEXT,
    marca        TEXT,
    familia      TEXT,
    subfamilia   TEXT,
    deposito     TEXT,
    fila         INTEGER,
    reglas       TEXT
);
CREATE INDEX remitos_cuit ON remitos(cuit, fecha);
CREATE INDEX remitos_comp ON remitos(comprobante);

-- Stockfish (historial auditado por cuenta; nunca manda sobre el CRM vivo)
CREATE TABLE stockfish (
    id            TEXT PRIMARY KEY,
    empresa       TEXT,
    n_facturas    INTEGER,
    primera       TEXT,
    ultima        TEXT,
    usd_bruto_neto REAL,
    n_hallazgos   INTEGER,
    doc           TEXT NOT NULL    -- la ficha de Stockfish entera
);

CREATE TABLE stock (
    codigo      TEXT PRIMARY KEY,
    nombre      TEXT,
    marca       TEXT,
    familia     TEXT,
    subfamilia  TEXT,
    stock       REAL,
    transito    REAL,
    produccion  REAL,
    eta         TEXT
);

-- Lo que decidió el Sales Engine en la última corrida (el único que decide)
CREATE TABLE motor_filas (
    cliente_id         TEXT,
    empresa            TEXT,
    puesto             INTEGER,
    empujon            TEXT,
    palabras           TEXT,
    usd                REAL,
    esperado           REAL,
    obligatorio        INTEGER,
    en_cadencia_hasta  TEXT,
    agendada           TEXT,
    evidencia          TEXT,
    hoy                INTEGER   -- 1 = el motor lo empuja hoy (no está en cadencia ni agendado)
);
CREATE INDEX motor_cliente ON motor_filas(cliente_id);

CREATE TABLE resumen (
    clave  TEXT PRIMARY KEY,
    texto  TEXT
);

-- Cuentas que no se trabajan (restricciones del CRM): por id de ficha o por CUIT
CREATE TABLE cuentas_fuera (
    clave    TEXT PRIMARY KEY,
    cuit     TEXT,
    empresa  TEXT,
    motivo   TEXT
);

-- v2.2: grupos económicos (datacenter/grupos del CRM): fichas que compran o deciden juntas
CREATE TABLE grupos (
    grupo       TEXT NOT NULL,
    nombre      TEXT,
    cliente_id  TEXT NOT NULL,
    fuente      TEXT,
    PRIMARY KEY (grupo, cliente_id)
);
CREATE INDEX grupos_cliente ON grupos(cliente_id);

CREATE TABLE decisiones (
    n      INTEGER PRIMARY KEY,
    texto  TEXT
);

CREATE TABLE aprendizajes (
    id      TEXT PRIMARY KEY,
    error   TEXT,
    patron  TEXT,
    regla   TEXT,
    test    TEXT
);

-- Controles que antes se hacían a mano
-- v2.1: una ficha unificada en otra (unificada_en) o archivada ya está resuelta: no cuenta como duplicado.
CREATE VIEW v_fichas_activas AS
    SELECT * FROM clientes
    WHERE unificada_en IS NULL AND (archivada IS NULL OR archivada NOT IN ('True', 'true', '1'));

-- Mismo CUIT (principal o adicional) en dos fichas activas
CREATE VIEW v_duplicados_cuit AS
    SELECT cc.cuit, COUNT(DISTINCT a.id) AS fichas,
           GROUP_CONCAT(DISTINCT a.id || ' (' || a.empresa || ')') AS cuales
    FROM cliente_cuits cc JOIN v_fichas_activas a ON a.id = cc.cliente_id
    GROUP BY cc.cuit HAVING COUNT(DISTINCT a.id) > 1;

-- Mismo nombre y sin CUIT, entre fichas activas: el CUIT no los puede atajar (ej. dos «Berisys»)
CREATE VIEW v_duplicados_nombre AS
    SELECT LOWER(TRIM(empresa)) AS nombre, COUNT(*) AS fichas, GROUP_CONCAT(id, ' · ') AS cuales
    FROM v_fichas_activas WHERE cuit IS NULL
    GROUP BY LOWER(TRIM(empresa)) HAVING COUNT(*) > 1;

-- Lo ya resuelto (para mostrarlo, no para contarlo como problema)
CREATE VIEW v_unificadas AS
    SELECT id, empresa, cuit, unificada_en FROM clientes WHERE unificada_en IS NOT NULL;

-- CUIT que compraron (facturas del libro) y no tienen ficha ni están en cuentas fuera.
-- usd_facturado = solo facturas en USD (las filas en pesos traen tc 1: no se convierten acá).
-- vendedor = el que más aparece en sus remitos (reporte 21), dato para decidir si es de otro vendedor.
CREATE VIEW v_compradores_sin_ficha AS
    SELECT l.cuit, MAX(l.cliente) AS cliente, COUNT(*) AS facturas,
           ROUND(SUM(CASE WHEN l.moneda = 'USD' THEN l.bruto ELSE 0 END)) AS usd_facturado,
           SUM(l.moneda <> 'USD') AS facturas_en_pesos,
           MIN(l.fecha) AS primera, MAX(l.fecha) AS ultima,
           (SELECT r.vendedor FROM remitos r WHERE r.cuit = l.cuit AND r.vendedor IS NOT NULL
            GROUP BY r.vendedor ORDER BY COUNT(*) DESC LIMIT 1) AS vendedor
    FROM libro_ventas l
    WHERE l.cuit IS NOT NULL AND l.tipocomp LIKE '%Factura%'
      AND l.cuit NOT IN (SELECT cuit FROM cliente_cuits)
      AND l.cuit NOT IN (SELECT cuit FROM cuentas_fuera WHERE cuit IS NOT NULL)
    GROUP BY l.cuit;

CREATE VIEW v_facturas_sin_lineas AS
    SELECT l.* FROM libro_ventas l
    WHERE l.tipocomp LIKE '%Factura%'
      -- el número se repite entre series (una NC y una factura vieja pueden tener el mismo): se cruza también por CUIT y tipo
      AND NOT EXISTS (SELECT 1 FROM factura_lineas f WHERE f.comprobante = l.comprobante
                      AND f.cuit = l.cuit AND f.tipo = 'F');

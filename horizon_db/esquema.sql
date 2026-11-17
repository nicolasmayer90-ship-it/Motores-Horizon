-- Horizon DB · esquema v1.0 (Etapa 1: solo lectura)
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
    actualizado      TEXT
);
CREATE INDEX clientes_cuit ON clientes(cuit);
CREATE INDEX clientes_fecha ON clientes(proxima_fecha);

CREATE TABLE historial (
    cliente_id  TEXT NOT NULL REFERENCES clientes(id),
    t           TEXT,
    txt         TEXT
);
CREATE INDEX historial_cliente ON historial(cliente_id, t);

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
    actualizado    TEXT
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
    iva            TEXT
);
CREATE INDEX items_codigo ON cotizacion_items(codigo);

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
    vendedor     TEXT
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
    PRIMARY KEY (tipocomp, comprobante)
);
CREATE INDEX libro_cuit ON libro_ventas(cuit, fecha);

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
CREATE VIEW v_duplicados_cuit AS
    SELECT cuit, COUNT(*) AS fichas, GROUP_CONCAT(id || ' (' || empresa || ')', ' · ') AS cuales
    FROM clientes WHERE cuit IS NOT NULL AND cuit <> ''
    GROUP BY cuit HAVING COUNT(*) > 1;

-- Mismo nombre y sin CUIT: el CUIT no los puede atajar (ej. dos «Berisys»)
CREATE VIEW v_duplicados_nombre AS
    SELECT LOWER(TRIM(empresa)) AS nombre, COUNT(*) AS fichas, GROUP_CONCAT(id, ' · ') AS cuales
    FROM clientes WHERE cuit IS NULL
    GROUP BY LOWER(TRIM(empresa)) HAVING COUNT(*) > 1;

CREATE VIEW v_facturas_sin_lineas AS
    SELECT l.* FROM libro_ventas l
    WHERE l.tipocomp LIKE '%Factura%'
      -- el número se repite entre series (una NC y una factura vieja pueden tener el mismo): se cruza también por CUIT y tipo
      AND NOT EXISTS (SELECT 1 FROM factura_lineas f WHERE f.comprobante = l.comprobante
                      AND f.cuit = l.cuit AND f.tipo = 'F');

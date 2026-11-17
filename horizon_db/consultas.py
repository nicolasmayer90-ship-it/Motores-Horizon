#!/usr/bin/env python3
"""Horizon DB · consultas v1.0 (Etapa 1: solo lectura).

Cada función recibe una conexión de solo lectura y devuelve texto corto, listo para leer.
Reglas que respeta: el Sales Engine es el único que decide (acá solo se muestra su orden);
lo que viene de la ficha se marca como dato, no como decisión; el precio vigente sale de
HIVE (decisión 111), acá solo hay el último precio cotizado como referencia.
"""
import datetime, json, os, re, sqlite3
from pathlib import Path

ETAPAS_CERRADAS = ("perdido",)


def abrir(db):
    """Conexión de solo lectura: cualquier intento de escribir falla."""
    if not os.path.exists(db):
        raise FileNotFoundError(f"No está la base {db}: correr primero cargar.py")
    cx = sqlite3.connect(Path(db).resolve().as_uri() + "?mode=ro", uri=True)
    cx.row_factory = sqlite3.Row
    return cx


def ar(v, dec=0):
    """Número con formato argentino: 11.962,50."""
    s = f"{v:,.{dec}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def usd(v):
    return "—" if v is None else "USD " + ar(v)


def hoy_ar():
    return (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)).date().isoformat()


def _carga(cx):
    r = cx.execute("SELECT * FROM carga WHERE id = 1").fetchone()
    return dict(r) if r else {}


def estado_base(cx, hoy=None):
    hoy = hoy or hoy_ar()
    c = _carga(cx)
    if not c:
        return "FALLA · la base está vacía: correr cargar.py"
    avisos = []
    if (c.get("cargado") or "")[:10] < hoy:
        avisos.append(f"la base se armó el {c['cargado'][:10]}: re-cargar con la exportación de hoy")
    if c.get("hoy_motor") and c["hoy_motor"] < hoy:
        avisos.append(f"el Sales Engine corrió el {c['hoy_motor']}, no hoy")
    if not c.get("hoy_motor"):
        avisos.append("sin salida del Sales Engine en la carga: el orden del día no está")
    linea = (f"Base del {c['cargado'][:16].replace('T', ' ')} · stock HIVE al {c.get('corte_stock') or '—'}"
             f" · líneas de factura al {c.get('corte_lineas') or '—'} · libro de ventas al {c.get('corte_libro') or '—'}")
    return linea + "".join(f"\n- AVISO {a}" for a in avisos)


def _es_fuera(cx, cliente_id, cuit):
    r = cx.execute("SELECT motivo FROM cuentas_fuera WHERE clave = ? OR (cuit IS NOT NULL AND cuit = ?)",
                   (cliente_id, cuit or "-")).fetchone()
    return r["motivo"] if r else None


def apertura_loki(cx, hoy=None):
    hoy = hoy or hoy_ar()
    partes = [estado_base(cx, hoy)]
    filas = cx.execute("SELECT * FROM motor_filas WHERE empujon IS NOT NULL AND empujon <> '—' "
                       "ORDER BY puesto").fetchall()

    def linea(f):
        marca = " · obligatorio" if f["obligatorio"] else ""
        cad = f" · en cadencia hasta {f['en_cadencia_hasta']}" if f["en_cadencia_hasta"] else ""
        ag = f" · agendada {f['agendada']}" if f["agendada"] else ""
        return (f"- {f['empresa']} · {f['empujon']} · {f['palabras']} · {usd(f['usd'])} "
                f"(esperado {usd(f['esperado'])}){marca}{cad}{ag}")
    hoy_f = [f for f in filas if f["hoy"]]
    resto = [f for f in filas if not f["hoy"]]
    partes.append(f"\nSales Engine (el único que decide) · empujes de hoy: {len(hoy_f)}")
    partes += [linea(f) for f in hoy_f] or ["- ninguno"]
    if resto:
        partes.append(f"En cadencia o agendadas (no se empujan hoy): {len(resto)}")
        partes += [linea(f) for f in resto]
    venc = _agenda(cx, hoy, solo_vencidas=True)
    desde = (datetime.date.fromisoformat(hoy) - datetime.timedelta(days=7)).isoformat()
    recientes = [r for r in venc if r["proxima_fecha"] >= desde]
    partes.append(f"\nAgenda de las fichas de los últimos 7 días y hoy (dato, no decisión): {len(recientes)}"
                  f" · {len(venc) - len(recientes)} más viejas en seguimientos_hoy")
    for r in recientes[:12]:
        partes.append(f"- {r['proxima_fecha']} · {r['empresa']} · {r['proxima_accion'] or '(sin acción)'}")
    if len(recientes) > 12:
        partes.append(f"- … y {len(recientes) - 12} más")
    sin = facturas_sin_lineas_filas(cx, dias=45, hoy=hoy)
    dup = cx.execute("SELECT COUNT(*) FROM v_duplicados_cuit").fetchone()[0]
    dupn = cx.execute("SELECT COUNT(*) FROM v_duplicados_nombre").fetchone()[0]
    sinf = cx.execute("SELECT COUNT(*) FROM v_compradores_sin_ficha").fetchone()[0]
    partes.append(f"\nControles: {len(sin)} facturas de los últimos 45 días sin líneas cargadas · "
                  f"{dup} CUIT con más de una ficha activa · {dupn} nombres repetidos sin CUIT · "
                  f"{sinf} CUIT que compraron sin ficha")
    r = cx.execute("SELECT texto FROM resumen WHERE clave = 'resumen.txt'").fetchone()
    if r:
        partes.append("\n--- Resumen de correr_dia ---\n" + r["texto"].strip())
    return "\n".join(partes)


def _agenda(cx, hoy, solo_vencidas):
    q = ("SELECT * FROM clientes WHERE proxima_fecha IS NOT NULL AND proxima_fecha <> '' "
         "AND COALESCE(etapa, '') NOT IN ({}) AND COALESCE(no_prospectar, '') IN ('', 'no') "
         .format(",".join("?" * len(ETAPAS_CERRADAS))))
    args = list(ETAPAS_CERRADAS)
    if solo_vencidas:
        q += "AND proxima_fecha <= ? "
        args.append(hoy)
    q += "ORDER BY proxima_fecha, COALESCE(prioridad, 'Z'), empresa"
    return [r for r in cx.execute(q, args).fetchall() if not _es_fuera(cx, r["id"], r["cuit"])]


def seguimientos_hoy(cx, hoy=None):
    hoy = hoy or hoy_ar()
    salida = [estado_base(cx, hoy)]
    filas = cx.execute("SELECT * FROM motor_filas WHERE empujon <> '—' ORDER BY puesto").fetchall()
    salida.append(f"\n1) Orden del Sales Engine ({len(filas)}):")
    salida += [f"- {f['puesto']}. {f['empresa']} · {f['empujon']} · {f['palabras']}" for f in filas] or ["- ninguno"]
    ag = _agenda(cx, hoy, solo_vencidas=True)
    salida.append(f"\n2) Agenda de las fichas, vencida o de hoy ({len(ag)}) · dato de la ficha, no decisión:")
    for r in ag:
        salida.append(f"- {r['proxima_fecha']} · {r['prioridad'] or '-'} · {r['empresa']} ({r['id']}) · "
                      f"{r['proxima_accion'] or '(sin acción)'}")
    return "\n".join(salida)


def _buscar_clientes(cx, consulta):
    q = (consulta or "").strip()
    dig = re.sub(r"\D", "", q)
    if len(dig) >= 8:
        rs = cx.execute("SELECT * FROM clientes WHERE cuit = ?", (dig,)).fetchall()
        if rs:
            return rs
    rs = cx.execute("SELECT * FROM clientes WHERE id = ?", (q,)).fetchall()
    if rs:
        return rs
    return cx.execute("SELECT * FROM clientes WHERE empresa LIKE ? OR contacto LIKE ? ORDER BY empresa",
                      (f"%{q}%", f"%{q}%")).fetchall()


def ficha_cliente(cx, consulta):
    rs = _buscar_clientes(cx, consulta)
    if not rs:
        return f"Sin coincidencias para «{consulta}»."
    if len(rs) > 1:
        return (f"Ambiguo: {len(rs)} fichas para «{consulta}». Decir cuál:\n" +
                "\n".join(f"- {r['id']} · {r['empresa']} · CUIT {r['cuit'] or '—'} · {r['etapa']}" for r in rs[:15]))
    c = rs[0]
    s = [f"{c['empresa']} ({c['id']}) · CUIT {c['cuit'] or '—'} · etapa {c['etapa'] or '—'} · prioridad {c['prioridad'] or '—'}"]
    fuera = _es_fuera(cx, c["id"], c["cuit"])
    if fuera:
        s.append(f"- CUENTA FUERA: {fuera}")
    s.append(f"- {c['tipo'] or ''} · {c['zona'] or ''} · contacto {c['contacto'] or '—'}")
    s.append(f"- OLT {c['marca_olt'] or '—'} {c['modelo_olt'] or ''} · cliente Horizon: {c['cliente_horizon'] or '—'}")
    s.append(f"- Próxima: {c['proxima_fecha'] or '—'} · {c['proxima_accion'] or '—'} (dato de la ficha)")
    m = cx.execute("SELECT * FROM motor_filas WHERE cliente_id = ?", (c["id"],)).fetchone()
    if m:
        s.append(f"- Sales Engine: {m['empujon']} · {m['palabras'] or ''} · puesto {m['puesto']}")
    cots = cx.execute("SELECT * FROM cotizaciones WHERE cliente_id = ? OR (cuit IS NOT NULL AND cuit = ?) "
                      "ORDER BY fecha DESC LIMIT 6", (c["id"], c["cuit"] or "-")).fetchall()
    if cots:
        s.append("Cotizaciones:")
        s += [f"- {k['numero'] or k['id']} · {k['fecha']} · {k['estado']} · {usd(k['total'])} · vence {k['vence'] or 'sin vence'}"
              for k in cots]
    if c["cuit"]:
        comp = cx.execute("SELECT comprobante, fecha, tipo, GROUP_CONCAT(CAST(CAST(ABS(cantidad) AS INT) AS TEXT) || ' × ' || producto, ' + ') AS q "
                          "FROM factura_lineas WHERE cuit = ? GROUP BY comprobante, fecha, tipo ORDER BY fecha DESC LIMIT 6",
                          (c["cuit"],)).fetchall()
        if comp:
            s.append("Últimos comprobantes (líneas de factura):")
            nombre = {"F": "factura", "NC": "NOTA DE CRÉDITO (resta)", "ND": "nota de débito", "AJ": "ajuste"}
            s += [f"- {k['fecha']} · {nombre.get(k['tipo'], k['tipo'] or '?')} {k['comprobante']} · {k['q']}" for k in comp]
        lib = cx.execute("SELECT COUNT(*) n, MAX(fecha) ult FROM libro_ventas WHERE cuit = ? AND tipocomp LIKE '%Factura%'",
                         (c["cuit"],)).fetchone()
        if lib["n"]:
            s.append(f"- Libro de ventas: {lib['n']} facturas, la última el {lib['ult']}")
    hist = cx.execute("SELECT t, txt FROM historial WHERE cliente_id = ? ORDER BY t DESC LIMIT 5", (c["id"],)).fetchall()
    if hist:
        s.append("Historial reciente:")
        s += [f"- {(h['t'] or '')[:10]} · {h['txt']}" for h in hist]
    return "\n".join(s)


def buscar_producto(cx, texto):
    q = (texto or "").strip()
    rs = cx.execute("SELECT * FROM stock WHERE codigo = ? OR nombre LIKE ? ORDER BY nombre LIMIT 15",
                    (q, f"%{q}%")).fetchall()
    corte = _carga(cx).get("corte_stock") or "—"
    if not rs:
        return f"Sin productos para «{q}» en la copia de HIVE (foto al {corte})."
    s = [f"Stock según la copia de HIVE, foto al {corte} (para el dato de hoy, consultar HIVE):"]
    for p in rs:
        s.append(f"- {p['codigo']} · {p['nombre']} · {p['marca'] or ''} · stock {p['stock'] or 0:g}"
                 f" · tránsito {p['transito'] or 0:g}{' (ETA ' + p['eta'] + ')' if p['eta'] else ''}")
        u = cx.execute("SELECT i.precio, c.numero, c.fecha, c.cliente FROM cotizacion_items i "
                       "JOIN cotizaciones c ON c.id = i.cotizacion_id WHERE i.codigo = ? AND i.precio IS NOT NULL "
                       "ORDER BY c.fecha DESC LIMIT 1", (p["codigo"],)).fetchone()
        if u:
            s.append(f"  último precio cotizado: USD {u['precio']:g} ({u['numero']} {u['fecha']}, {u['cliente']})"
                     " · referencia, no lista: el precio vigente sale de HIVE")
    return "\n".join(s)


def facturas_sin_lineas_filas(cx, dias=60, hoy=None):
    hoy = hoy or hoy_ar()
    desde = (datetime.date.fromisoformat(hoy) - datetime.timedelta(days=int(dias))).isoformat()
    return cx.execute("SELECT * FROM v_facturas_sin_lineas WHERE fecha >= ? ORDER BY fecha DESC", (desde,)).fetchall()


def facturas_sin_cargar(cx, dias=60, hoy=None):
    filas = facturas_sin_lineas_filas(cx, dias, hoy)
    corte = _carga(cx).get("corte_lineas") or "—"
    if not filas:
        return f"Todas las facturas de los últimos {dias} días tienen sus líneas cargadas (líneas al {corte})."
    s = [f"Facturas del libro de ventas sin líneas de producto en el CRM (últimos {dias} días; líneas al {corte}):"]
    for f in filas:
        nota = "posterior al corte de líneas: llega con el próximo reporte" if corte != "—" and f["fecha"] > corte else "FALTA CARGAR"
        s.append(f"- {f['fecha']} · {f['comprobante']} · {f['cliente']} · {f['moneda']} {ar(f['bruto'] or 0, 2)} sin IVA · {nota}")
    return "\n".join(s)


def duplicados_cuit(cx):
    rs = cx.execute("SELECT * FROM v_duplicados_cuit ORDER BY fichas DESC, cuit").fetchall()
    rn = cx.execute("SELECT * FROM v_duplicados_nombre ORDER BY fichas DESC, nombre").fetchall()
    s = [f"{len(rs)} CUIT con más de una ficha activa (unificar solo con «hacelo»; las ya unificadas no cuentan):"]
    s += [f"- {r['cuit']} · {r['fichas']} fichas: {r['cuales']}" for r in rs] or ["- ninguno"]
    s.append(f"{len(rn)} nombres repetidos en fichas sin CUIT (falta el CUIT para confirmar si son la misma):")
    s += [f"- «{r['nombre']}» · {r['fichas']} fichas: {r['cuales']}" for r in rn] or ["- ninguno"]
    return "\n".join(s)


def buscar_memoria(cx, tema, limite=15):
    t = f"%{(tema or '').strip()}%"
    s = []
    for r in cx.execute("SELECT n, texto FROM decisiones WHERE texto LIKE ? ORDER BY n DESC LIMIT ?", (t, limite)):
        s.append(f"- [decisión {r['n']}] {r['texto'][:400]}")
    for r in cx.execute("SELECT * FROM aprendizajes WHERE error LIKE ? OR patron LIKE ? OR regla LIKE ? LIMIT ?",
                        (t, t, t, limite)):
        s.append(f"- [aprendizaje {r['id']}] {r['error']} → regla: {r['regla']}")
    for r in cx.execute("SELECT h.t, h.txt, c.empresa FROM historial h JOIN clientes c ON c.id = h.cliente_id "
                        "WHERE h.txt LIKE ? OR c.empresa LIKE ? ORDER BY h.t DESC LIMIT ?", (t, t, limite)):
        s.append(f"- [historial {r['empresa']} {(r['t'] or '')[:10]}] {r['txt'][:300]}")
    if not s:
        return f"Nada en decisiones, aprendizajes ni historial sobre «{tema}»: recién ahí se le pregunta a Nicolás."
    return f"Memoria sobre «{tema}» ({len(s)}):\n" + "\n".join(s)

#!/usr/bin/env python3
"""Horizon DB · cargador v2.0 (Etapa 1).

v2.0: guarda la ficha y la cotización enteras (doc), CUIT adicionales, contactos, operación de
la cotización, remitos (reporte 21), tc/otros/usuario del libro y Stockfish.

Arma la base SQLite desde la exportación del CRM: la misma carpeta que usa correr_dia
(--raiz), con oportunidades/, cotizaciones/, facturacion/, reportes/, datacenter/ y, si
corrió el día, salida/. La base se arma entera en un archivo temporal y recién al final
reemplaza a la anterior: si algo falla, la base vieja queda intacta.

Uso:
    python -I cargar.py --raiz C:\\HorizonDB\\crm [--db C:\\HorizonDB\\horizon.db]

Solo biblioteca estándar. No escribe nada en el CRM ni en HIVE.
"""
import argparse, datetime, glob, json, os, re, sqlite3, sys

AQUI = os.path.dirname(os.path.abspath(__file__))
DB_POR_DEFECTO = os.path.join(os.path.expanduser("~"), "HorizonDB", "horizon.db")


def solo_digitos(v):
    d = re.sub(r"\D", "", str(v or ""))
    return d or None


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def leer_json(ruta):
    with open(ruta, encoding="utf-8") as fh:
        return json.load(fh)


def docs(raiz, coleccion):
    for ruta in sorted(glob.glob(os.path.join(raiz, coleccion, "*.json"))):
        yield os.path.splitext(os.path.basename(ruta))[0], leer_json(ruta)


def insertar(cx, tabla, fila):
    """INSERT con nombres de columna: el orden del esquema no importa."""
    cols = list(fila)
    cx.execute(f"INSERT INTO {tabla} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
               [fila[c] for c in cols])


def texto(v):
    """Campos que en el CRM pueden venir como texto, número, lista o booleano: se guardan como texto."""
    if v is None or v == "":
        return None
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    return str(v)


def doc_json(d):
    """El documento entero, canónico (claves ordenadas): comparar.py lo controla contra el CRM."""
    return json.dumps(d, ensure_ascii=False, sort_keys=True)


def cargar_clientes(cx, raiz):
    n = h = cu = co = 0
    for doc_id, d in docs(raiz, "oportunidades"):
        cuit = solo_digitos(d.get("cuit"))
        insertar(cx, "clientes", {
            "id": doc_id, "empresa": d.get("empresa") or doc_id, "cuit": cuit, "etapa": d.get("etapa"),
            "prioridad": d.get("prioridad"), "tipo": d.get("tipo"), "zona": d.get("zona"),
            "contacto": d.get("contacto"), "telefono": d.get("telefono"), "email": d.get("email"),
            "marca_olt": d.get("marcaOlt"), "modelo_olt": d.get("modeloOlt"),
            "cliente_horizon": texto(d.get("clienteHorizon")), "productos": texto(d.get("productos")),
            "proxima_accion": d.get("proximaAccion"), "proxima_fecha": d.get("proximaFecha") or None,
            "ultimo_contacto": d.get("ultimoContacto") or None, "monto": num(d.get("monto")),
            "no_prospectar": texto(d.get("noProspectar")), "notas": d.get("notas"),
            "actualizado": d.get("actualizado"), "creado": d.get("creado"), "pago": texto(d.get("pago")),
            "tecnologia": texto(d.get("tecnologia")), "abonados": texto(d.get("abonados")),
            "facturacion_id": texto(d.get("facturacionId")),
            "no_prospectar_motivo": texto(d.get("noProspectarMotivo")),
            "otro_vendedor": texto(d.get("otroVendedor")), "cuenta_compartida": texto(d.get("cuentaCompartida")),
            "archivada": texto(d.get("archivada")), "archivada_fecha": texto(d.get("archivadaFecha")),
            "archivada_motivo": texto(d.get("archivadaMotivo")), "unificada_en": texto(d.get("unificadaEn")),
            "motivo_perdida": texto(d.get("motivoPerdida")), "fecha_ganado": texto(d.get("fechaGanado")),
            "fijado": texto(d.get("fijado")), "doc": doc_json(d)})
        n += 1
        for e in d.get("historial") or []:
            if isinstance(e, dict):
                cx.execute("INSERT INTO historial VALUES (?,?,?)", (doc_id, e.get("t"), e.get("txt")))
                h += 1
        vistos = set()
        if cuit:
            insertar(cx, "cliente_cuits", {"cliente_id": doc_id, "cuit": cuit, "nombre": d.get("empresa"),
                                           "cond_iva": texto(d.get("condIva")), "principal": 1})
            vistos.add(cuit)
            cu += 1
        for c in d.get("cuitsAdicionales") or []:
            es_dict = isinstance(c, dict)
            c2 = solo_digitos(c.get("cuit") if es_dict else c)
            if c2 and c2 not in vistos:
                insertar(cx, "cliente_cuits", {"cliente_id": doc_id, "cuit": c2,
                                               "nombre": c.get("nombre") if es_dict else None,
                                               "cond_iva": texto(c.get("condIva")) if es_dict else None,
                                               "principal": 0})
                vistos.add(c2)
                cu += 1
        for c in d.get("contactosAdicionales") or []:
            if isinstance(c, dict):
                insertar(cx, "contactos", {"cliente_id": doc_id, "nombre": c.get("nombre"), "cargo": c.get("cargo"),
                                           "celular": texto(c.get("celular")), "mail": texto(c.get("mail")),
                                           "fuente": texto(c.get("fuente"))})
                co += 1
    return {"clientes": n, "historial": h, "cliente_cuits": cu, "contactos": co}


def cargar_cotizaciones(cx, raiz):
    n = i = o = 0
    for doc_id, d in docs(raiz, "cotizaciones"):
        insertar(cx, "cotizaciones", {
            "id": doc_id, "numero": d.get("numero"), "cliente_id": d.get("oportunidadId"),
            "cuit": solo_digitos(d.get("cuit")), "cliente": d.get("cliente"), "fecha": d.get("fecha"),
            "vence": d.get("vence") or None, "estado": d.get("estado"), "cond_pago": texto(d.get("condPago")),
            "neto": num(d.get("neto")), "total": num(d.get("total")), "notas": d.get("notas"),
            "actualizado": d.get("actualizado"), "marca": texto(d.get("marca")), "familia": texto(d.get("familia")),
            "cond_iva": texto(d.get("condIva")), "tc": num(d.get("tc")), "iva_total": num(d.get("ivaTotal")),
            "fecha_ganada": texto(d.get("fechaGanada")), "archivada": texto(d.get("archivada")),
            "reemplazada_por": texto(d.get("reemplazadaPor")), "doc": doc_json(d)})
        n += 1
        for it in d.get("items") or []:
            insertar(cx, "cotizacion_items", {
                "cotizacion_id": doc_id, "codigo": str(it.get("codigo") or ""), "articulo": it.get("articulo"),
                "marca": it.get("marca"), "cantidad": num(it.get("cantidad")), "precio": num(it.get("precio")),
                "iva": texto(it.get("iva")), "descripcion": it.get("descripcion"), "neto": num(it.get("neto"))})
            i += 1
        op = d.get("hz_operacion")
        if isinstance(op, dict):
            insertar(cx, "cotizacion_operacion", {
                "cotizacion_id": doc_id, "pedido_confirmado": texto(op.get("pedidoConfirmado")),
                "pago": texto(op.get("pago")), "pago_at": texto(op.get("pagoAt")),
                "despacho": texto(op.get("despacho")), "despacho_at": texto(op.get("despachoAt")),
                "entrega": texto(op.get("entrega")), "entrega_at": texto(op.get("entregaAt")),
                "factura": texto(op.get("factura")), "cierre": texto(op.get("cierre")), "doc": doc_json(op)})
            o += 1
    return {"cotizaciones": n, "cotizacion_items": i, "cotizacion_operacion": o}


def cargar_lineas(cx, raiz):
    n = 0
    for doc_id, d in docs(raiz, "facturacion"):
        cuit = solo_digitos(d.get("cuit")) or solo_digitos(doc_id)
        for l in d.get("lineas") or []:
            insertar(cx, "factura_lineas", {
                "cuit": cuit, "cliente": d.get("cliente"), "comprobante": l.get("comprobante"),
                "fecha": l.get("fecha"), "tipo": l.get("tipo"), "cod": l.get("cod"), "producto": l.get("producto"),
                "marca": l.get("marca"), "familia": l.get("familia"), "cantidad": num(l.get("cantidad")),
                "vendedor": l.get("vend"), "subfamilia": l.get("subfamilia"), "pendiente": num(l.get("pte"))})
            n += 1
    return {"factura_lineas": n}


def cargar_libro(cx, raiz):
    """Reportes 15 (en partes r15, r15_2...) y 22: filas compactas con índices en 'dic'.
    El 22 actualiza al 15: si un comprobante aparece en los dos, queda el del 22."""
    n = 0
    for base in ("r15", "r22"):
        principal = os.path.join(raiz, "reportes", base + ".json")
        if not os.path.exists(principal):
            continue
        cab = leer_json(principal)
        dic, campos = cab.get("dic") or {}, cab["formato"]["f"]
        partes = [principal] + sorted(glob.glob(os.path.join(raiz, "reportes", base + "_*.json")))
        for ruta in partes:
            for fila in leer_json(ruta).get("d") or []:
                r = dict(zip(campos, fila))
                def de(clave):
                    v = r.get(clave)
                    lista = dic.get(clave)
                    return lista[v] if isinstance(v, int) and lista and 0 <= v < len(lista) else v
                if not r.get("comprobante"):
                    continue
                cx.execute("INSERT OR REPLACE INTO libro_ventas (tipocomp, comprobante, fecha, cuit, cliente, moneda, "
                           "bruto, total, reporte, otros, tc, detalle, fecha_alta, usuario, cuit_por_nombre) "
                           "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                           (de("tipocomp"), r["comprobante"], r.get("fecha"), solo_digitos(r.get("cuit")),
                            de("cliente"), de("moneda"), num(r.get("bruto")), num(r.get("total")), base,
                            num(r.get("otros")), num(r.get("tc")), texto(r.get("detalle")),
                            texto(r.get("fechaAlta")), texto(de("usuario")),
                            1 if r.get("cuitPorNombre") else 0))
                n += 1
    # libro_ventas = filas que quedaron en la tabla (antes se informaban las leídas y el número confundía:
    # 3.263 leídas contra 2.992 guardadas el 17/11). Las reemplazadas son comprobantes repetidos, casi
    # siempre el mismo en r15 y r22, donde manda el r22.
    guardadas = cx.execute("SELECT COUNT(*) FROM libro_ventas").fetchone()[0]
    return {"libro_ventas": guardadas, "libro_ventas_leidas": n, "libro_ventas_reemplazadas": n - guardadas}


def filas_reporte(raiz, base):
    """Filas de un reporte compacto (r21...) con los índices de 'dic' ya traducidos."""
    principal = os.path.join(raiz, "reportes", base + ".json")
    if not os.path.exists(principal):
        return
    cab = leer_json(principal)
    dic, campos = cab.get("dic") or {}, cab["formato"]["f"]
    for ruta in [principal] + sorted(glob.glob(os.path.join(raiz, "reportes", base + "_*.json"))):
        for fila in leer_json(ruta).get("d") or []:
            r = dict(zip(campos, fila))
            for clave, lista in dic.items():
                v = r.get(clave)
                if isinstance(v, int) and isinstance(lista, list) and 0 <= v < len(lista):
                    r[clave] = lista[v]
            yield r


def cargar_remitos(cx, raiz):
    n = 0
    for r in filas_reporte(raiz, "r21"):
        insertar(cx, "remitos", {
            "fecha": r.get("fecha"), "tipo": r.get("tipo"), "cliente": r.get("cliente"),
            "cuit": solo_digitos(r.get("cuit")), "cuit_por_nombre": 1 if r.get("cuitPorNombre") else 0,
            "comprobante": r.get("comprobante"), "producto": r.get("producto"), "detalle": texto(r.get("detalle")),
            "cantidad": num(r.get("cantidad")), "pendiente": num(r.get("pendiente")), "vendedor": r.get("vendedor"),
            "marca": r.get("marca"), "familia": r.get("familia"), "subfamilia": r.get("subfamilia"),
            "deposito": r.get("deposito"), "fila": r.get("_fila"), "reglas": texto(r.get("reglas"))})
        n += 1
    return {"remitos": n}


def cargar_stockfish(cx, raiz):
    n = 0
    for doc_id, d in docs(raiz, "stockfish_fichas"):
        c = d.get("sf_compras") or {}
        nh = d.get("sf_nHallazgos") or {}
        insertar(cx, "stockfish", {
            "id": doc_id, "empresa": d.get("empresa"), "n_facturas": c.get("nFacturas"),
            "primera": texto(c.get("primera")), "ultima": texto(c.get("ultima")),
            "usd_bruto_neto": num(c.get("usdBrutoNeto")),
            "n_hallazgos": sum(v for v in nh.values() if isinstance(v, (int, float))) if isinstance(nh, dict) else None,
            "doc": doc_json(d)})
        n += 1
    return {"stockfish": n}


def cargar_datacenter(cx, raiz):
    dc = os.path.join(raiz, "datacenter")
    out = {}
    ruta = os.path.join(dc, "hive_stock.json")
    corte = None
    if os.path.exists(ruta):
        d = leer_json(ruta)
        corte = d.get("corte")
        for cod, p in (d.get("productos") or {}).items():
            cx.execute("INSERT OR REPLACE INTO stock VALUES (?,?,?,?,?,?,?,?,?)",
                       (str(cod), p.get("nombre"), p.get("marca"), p.get("familia"), p.get("subfamilia"),
                        num(p.get("stock")), num(p.get("transito")), num(p.get("produccion")), p.get("eta")))
        out["stock"] = len(d.get("productos") or {})
    ruta = os.path.join(dc, "decisiones.json")
    if os.path.exists(ruta):
        lineas = leer_json(ruta).get("lineas") or []
        for i, txt in enumerate(lineas, 1):
            m = re.match(r"\s*(\d+)\.\s", txt)
            cx.execute("INSERT OR REPLACE INTO decisiones VALUES (?,?)", (int(m.group(1)) if m else i, txt))
        out["decisiones"] = len(lineas)
    ruta = os.path.join(dc, "aprendizajes.json")
    if os.path.exists(ruta):
        aps = leer_json(ruta).get("aprendizajes") or []
        for a in aps:
            cx.execute("INSERT OR REPLACE INTO aprendizajes VALUES (?,?,?,?,?)",
                       (a.get("id"), a.get("error"), a.get("patron"), a.get("regla"), a.get("test")))
        out["aprendizajes"] = len(aps)
    ruta = os.path.join(dc, "restricciones.json")
    if os.path.exists(ruta):
        d = leer_json(ruta)
        n = 0
        for clave, v in (d.get("cuentasFuera") or {}).items():
            v = v if isinstance(v, dict) else {"motivo": str(v)}
            cx.execute("INSERT OR REPLACE INTO cuentas_fuera VALUES (?,?,?,?)",
                       (clave, solo_digitos(v.get("cuit")), v.get("empresa"), v.get("motivo")))
            n += 1
        out["cuentas_fuera"] = n
    return out, corte


def cargar_salida(cx, raiz):
    """Lo que corrió correr_dia ese día: el Sales Engine sigue siendo el único que decide."""
    sal = os.path.join(raiz, "salida")
    hoy, n = None, 0
    ruta = os.path.join(sal, "sales_hoy.json")
    if os.path.exists(ruta):
        d = leer_json(ruta)
        hoy = d.get("hoy")
        for f in d.get("filas") or []:
            cx.execute("INSERT INTO motor_filas VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                       (f.get("id"), f.get("empresa"), f.get("puesto"), f.get("empujon"), f.get("palabras"),
                        num(f.get("usd")), num(f.get("esperado")), 1 if f.get("obligatorio") else 0,
                        f.get("enCadenciaHasta") or None, f.get("agendada") or None,
                        " · ".join(f.get("evidencia") or []), 1 if f.get("hoy") else 0))
            n += 1
    for nombre in ("resumen.txt",):
        ruta = os.path.join(sal, nombre)
        if os.path.exists(ruta):
            with open(ruta, encoding="utf-8") as fh:
                cx.execute("INSERT OR REPLACE INTO resumen VALUES (?,?)", (nombre, fh.read()))
    return {"motor_filas": n}, hoy


def armar(raiz, db):
    if not os.path.isdir(os.path.join(raiz, "oportunidades")):
        raise SystemExit(f"FALLA · {raiz} no tiene oportunidades/: no es una exportación del CRM")
    os.makedirs(os.path.dirname(os.path.abspath(db)), exist_ok=True)
    tmp = db + ".nueva"
    if os.path.exists(tmp):
        os.remove(tmp)
    cx = sqlite3.connect(tmp)
    try:
        with open(os.path.join(AQUI, "esquema.sql"), encoding="utf-8") as fh:
            cx.executescript(fh.read())
        conteos = {}
        conteos.update(cargar_clientes(cx, raiz))
        conteos.update(cargar_cotizaciones(cx, raiz))
        conteos.update(cargar_lineas(cx, raiz))
        conteos.update(cargar_libro(cx, raiz))
        conteos.update(cargar_remitos(cx, raiz))
        conteos.update(cargar_stockfish(cx, raiz))
        dc, corte_stock = cargar_datacenter(cx, raiz)
        conteos.update(dc)
        sal, hoy = cargar_salida(cx, raiz)
        conteos.update(sal)
        corte_lineas = cx.execute("SELECT MAX(fecha) FROM factura_lineas").fetchone()[0]
        corte_libro = cx.execute("SELECT MAX(fecha) FROM libro_ventas").fetchone()[0]
        cx.execute("INSERT INTO carga VALUES (1,?,?,?,?,?,?,?)",
                   (datetime.datetime.now().isoformat(timespec="seconds"), os.path.abspath(raiz), hoy,
                    corte_stock, corte_lineas, corte_libro, json.dumps(conteos, ensure_ascii=False)))
        cx.commit()
    finally:
        cx.close()
    os.replace(tmp, db)
    return conteos


def main():
    ap = argparse.ArgumentParser(description="Arma Horizon DB desde la exportación del CRM")
    ap.add_argument("--raiz", required=True, help="carpeta con la exportación del CRM")
    ap.add_argument("--db", default=os.environ.get("HORIZON_DB", DB_POR_DEFECTO))
    a = ap.parse_args()
    conteos = armar(a.raiz, a.db)
    print(f"Base armada: {a.db}")
    for k, v in conteos.items():
        if k in ("libro_ventas_leidas", "libro_ventas_reemplazadas"):
            continue
        if k == "libro_ventas":
            print(f"  libro_ventas: {v} (leídas {conteos['libro_ventas_leidas']}, "
                  f"{conteos['libro_ventas_reemplazadas']} reemplazadas: mismo comprobante en r15 y r22, manda el r22)")
            continue
        print(f"  {k}: {v}")
    print("RESULTADO: PASA")


if __name__ == "__main__":
    sys.exit(main())

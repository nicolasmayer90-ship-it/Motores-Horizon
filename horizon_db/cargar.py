#!/usr/bin/env python3
"""Horizon DB · cargador v1.0 (Etapa 1).

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


def cargar_clientes(cx, raiz):
    n = h = 0
    for doc_id, d in docs(raiz, "oportunidades"):
        cx.execute(
            "INSERT INTO clientes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (doc_id, d.get("empresa") or doc_id, solo_digitos(d.get("cuit")), d.get("etapa"),
             d.get("prioridad"), d.get("tipo"), d.get("zona"), d.get("contacto"), d.get("telefono"),
             d.get("email"), d.get("marcaOlt"), d.get("modeloOlt"), d.get("clienteHorizon"),
             d.get("productos"), d.get("proximaAccion"), d.get("proximaFecha") or None,
             d.get("ultimoContacto") or None, num(d.get("monto")), d.get("noProspectar"),
             d.get("notas"), d.get("actualizado")))
        n += 1
        for e in d.get("historial") or []:
            if isinstance(e, dict):
                cx.execute("INSERT INTO historial VALUES (?,?,?)", (doc_id, e.get("t"), e.get("txt")))
                h += 1
    return {"clientes": n, "historial": h}


def cargar_cotizaciones(cx, raiz):
    n = i = 0
    for doc_id, d in docs(raiz, "cotizaciones"):
        cx.execute(
            "INSERT INTO cotizaciones VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (doc_id, d.get("numero"), d.get("oportunidadId"), solo_digitos(d.get("cuit")),
             d.get("cliente"), d.get("fecha"), d.get("vence") or None, d.get("estado"),
             d.get("condPago"), num(d.get("neto")), num(d.get("total")), d.get("notas"),
             d.get("actualizado")))
        n += 1
        for it in d.get("items") or []:
            cx.execute("INSERT INTO cotizacion_items VALUES (?,?,?,?,?,?,?)",
                       (doc_id, str(it.get("codigo") or ""), it.get("articulo"), it.get("marca"),
                        num(it.get("cantidad")), num(it.get("precio")), it.get("iva")))
            i += 1
    return {"cotizaciones": n, "cotizacion_items": i}


def cargar_lineas(cx, raiz):
    n = 0
    for doc_id, d in docs(raiz, "facturacion"):
        cuit = solo_digitos(d.get("cuit")) or solo_digitos(doc_id)
        for l in d.get("lineas") or []:
            cx.execute("INSERT INTO factura_lineas VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                       (cuit, d.get("cliente"), l.get("comprobante"), l.get("fecha"), l.get("tipo"),
                        l.get("cod"), l.get("producto"), l.get("marca"), l.get("familia"),
                        num(l.get("cantidad")), l.get("vend")))
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
                cx.execute("INSERT OR REPLACE INTO libro_ventas VALUES (?,?,?,?,?,?,?,?,?)",
                           (de("tipocomp"), r["comprobante"], r.get("fecha"), solo_digitos(r.get("cuit")),
                            de("cliente"), de("moneda"), num(r.get("bruto")), num(r.get("total")), base))
                n += 1
    return {"libro_ventas": n}


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
        print(f"  {k}: {v}")
    print("RESULTADO: PASA")


if __name__ == "__main__":
    sys.exit(main())

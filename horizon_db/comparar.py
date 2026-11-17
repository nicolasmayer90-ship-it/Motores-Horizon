#!/usr/bin/env python3
"""Horizon DB · comparación completa contra el CRM v1.0.

Controla que la base tenga exactamente lo que tiene la exportación del CRM (--raiz):
  - cada ficha, cotización y ficha de Stockfish: el documento entero, campo por campo (columna doc);
  - las líneas de factura, el libro de ventas (r15 + r22) y los remitos (r21): mismas filas.
Si algo no coincide lo nombra (colección, documento y campo) y termina en FALLA.

Uso:
    python -I comparar.py --raiz C:\\HorizonDB\\crm [--db C:\\HorizonDB\\horizon.db]

Solo lectura: abre la base en modo ro y no toca el CRM.
"""
import argparse, glob, json, os, sqlite3, sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import cargar  # noqa: E402

MAX_DETALLE = 20


def campos_distintos(a, b):
    ks = sorted(set(a) | set(b))
    return [k for k in ks if a.get(k, "<falta>") != b.get(k, "<falta>")]


def comparar_docs(cx, raiz, coleccion, tabla):
    crm = {i: d for i, d in cargar.docs(raiz, coleccion)}
    base = {i: json.loads(doc) for i, doc in cx.execute(f"SELECT id, doc FROM {tabla}")}
    dif = []
    for i in sorted(set(crm) - set(base)):
        dif.append(f"{coleccion}/{i}: está en el CRM y falta en la base")
    for i in sorted(set(base) - set(crm)):
        dif.append(f"{coleccion}/{i}: está en la base y no en el CRM")
    for i in sorted(set(crm) & set(base)):
        if crm[i] != base[i]:
            dif.append(f"{coleccion}/{i}: distinto en {', '.join(campos_distintos(crm[i], base[i])[:8])}")
    return len(crm), dif


def contar_lineas(raiz):
    return sum(len(d.get("lineas") or []) for _, d in cargar.docs(raiz, "facturacion"))


def comparar(raiz, db):
    cx = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        res, dif = [], []
        for col, tabla in (("oportunidades", "clientes"), ("cotizaciones", "cotizaciones"),
                           ("stockfish_fichas", "stockfish")):
            if not os.path.isdir(os.path.join(raiz, col)):
                dif.append(f"{col}: no está en la exportación")
                continue
            n, d = comparar_docs(cx, raiz, col, tabla)
            res.append(f"{col}: {n} documentos · {len(d)} diferencias")
            dif += d

        n_crm = contar_lineas(raiz)
        n_db = cx.execute("SELECT COUNT(*) FROM factura_lineas").fetchone()[0]
        res.append(f"facturacion: {n_crm} líneas en el CRM · {n_db} en la base")
        if n_crm != n_db:
            dif.append(f"facturacion: {n_crm} líneas en el CRM y {n_db} en la base")

        claves = set()
        for base in ("r15", "r22"):
            for r in cargar.filas_reporte(raiz, base):
                if r.get("comprobante"):
                    claves.add((r.get("tipocomp"), r["comprobante"]))
        en_db = set(cx.execute("SELECT tipocomp, comprobante FROM libro_ventas").fetchall())
        res.append(f"libro de ventas: {len(claves)} comprobantes en el CRM · {len(en_db)} en la base")
        for k in sorted(claves - en_db)[:MAX_DETALLE]:
            dif.append(f"libro: {k[0]} {k[1]} falta en la base")
        for k in sorted(en_db - claves)[:MAX_DETALLE]:
            dif.append(f"libro: {k[0]} {k[1]} está en la base y no en el CRM")
        sin_tc = cx.execute("SELECT COUNT(*) FROM libro_ventas WHERE tc IS NULL").fetchone()[0]
        if sin_tc:
            dif.append(f"libro: {sin_tc} comprobantes sin tc (no se pueden pasar a USD)")

        n_r21 = sum(1 for _ in cargar.filas_reporte(raiz, "r21"))
        n_rem = cx.execute("SELECT COUNT(*) FROM remitos").fetchone()[0]
        res.append(f"remitos (r21): {n_r21} filas en el CRM · {n_rem} en la base")
        if n_r21 != n_rem:
            dif.append(f"remitos: {n_r21} filas en el CRM y {n_rem} en la base")
        return res, dif
    finally:
        cx.close()


def main():
    ap = argparse.ArgumentParser(description="Compara Horizon DB con la exportación del CRM")
    ap.add_argument("--raiz", required=True)
    ap.add_argument("--db", default=os.environ.get("HORIZON_DB", cargar.DB_POR_DEFECTO))
    a = ap.parse_args()
    res, dif = comparar(a.raiz, a.db)
    for r in res:
        print("  " + r)
    for d in dif[:MAX_DETALLE]:
        print("  DIFERENCIA · " + d)
    if len(dif) > MAX_DETALLE:
        print(f"  … y {len(dif) - MAX_DETALLE} más")
    print(f"RESULTADO: {'PASA · 0 diferencias' if not dif else f'FALLA · {len(dif)} diferencias'}")
    return 0 if not dif else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Horizon DB · estado de un cliente v1.0 (tarjeta «LOKI · INTELIGENCIA COMERCIAL»).

Arma en una consulta lo que antes se juntaba a mano para «estado / status / ficha de X»:
ficha e historial, compras por comprobante con las anuladas marcadas por Stockfish (regla A60),
último precio por unidad, grupo económico y sus cotizaciones abiertas, decisión del Sales Engine,
stock de la copia de HIVE y las alertas de la plantilla. Devuelve el resumen en texto y la
tarjeta en HTML, lista para mostrar.

Reglas que aplica en el código (para no depender de la memoria):
  A24  el estado de un cliente es la tarjeta, no texto suelto;
  A56  las compras salen de Stockfish (sf_comprobantes y sf_lineas), no de las últimas facturas;
  A60  las anulaciones se miran por comprobante, nunca agrupando por mes.
El Sales Engine es el único que decide: acá solo se muestra su fila. El precio vigente sale de
HIVE: si se lo pasa (precio_isp, stock_hive), la tarjeta lo usa; si no, lo pide.

Solo lectura.
"""
import datetime, html, json, os, re

AQUI = os.path.dirname(os.path.abspath(__file__))
PLANTILLA = os.path.join(AQUI, "tarjeta_cliente.html")
COT_CERRADAS = ("ganada", "perdida", "archivada", "anulada", "reemplazada")
RX_ITEM = re.compile(r"^\s*(-?[\d.,]+)\s*×\s*(.+?)(?:\s*\[(.*?)\])?\s*$")


def _ar(v, dec=0):
    s = f"{v:,.{dec}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def _usd(v, dec=2):
    return "—" if v is None else "USD " + _ar(v, dec)


def _f(d):
    """AAAA-MM-DD → DD/MM."""
    return f"{d[8:10]}/{d[5:7]}" if d and len(d) >= 10 else (d or "—")


def _num(s):
    try:
        return float(str(s).replace(".", "").replace(",", ".")) if "," in str(s) else float(s)
    except ValueError:
        return None


def items_de(lineas):
    """'200 × Ont Gpon HG6145F3 [FiberHome]' → (200, 'Ont Gpon HG6145F3', 'FiberHome'); descuentos (0 ×) afuera."""
    out = []
    for t in lineas or []:
        m = RX_ITEM.match(str(t))
        if not m:
            continue
        q = _num(m.group(1))
        prod = m.group(2).strip()
        if not q or q == 0 or prod.lower().startswith("descuento"):
            continue
        out.append((q, prod, m.group(3) or ""))
    return out


def compras(sf):
    """Facturas válidas (no anuladas) con sus productos, desde la ficha de Stockfish."""
    if not sf:
        return []
    lineas = {}
    for l in sf.get("sf_lineas") or []:
        lineas.setdefault(l.get("comp"), []).extend(items_de(l.get("items")))
    out = []
    for c in sf.get("sf_comprobantes") or []:
        if c.get("tipo") != "F" or c.get("anulada"):
            continue
        out.append({"fecha": c.get("fecha"), "comp": c.get("comp"), "moneda": c.get("moneda"),
                    "bruto": c.get("bruto"), "total": c.get("total"),
                    "items": [i for i in lineas.get(c.get("comp"), []) if i[0] > 0]})
    return sorted(out, key=lambda x: x["fecha"] or "")


def anuladas(sf):
    return [c for c in (sf or {}).get("sf_comprobantes") or [] if c.get("tipo") == "F" and c.get("anulada")]


def _abiertas(cots):
    return [k for k in cots if (k["estado"] or "").lower() not in COT_CERRADAS]


def datos(cx, cliente_id, hoy, precio_isp=None, stock_hive=None, fecha_hive=None):
    c = dict(cx.execute("SELECT * FROM clientes WHERE id = ?", (cliente_id,)).fetchone())
    doc = json.loads(c["doc"])
    r = cx.execute("SELECT doc FROM stockfish WHERE id = ?", (cliente_id,)).fetchone()
    sf = json.loads(r[0]) if r else None
    comp = compras(sf)
    motor = cx.execute("SELECT * FROM motor_filas WHERE cliente_id = ?", (cliente_id,)).fetchone()
    motor = dict(motor) if motor else None
    carga = dict(cx.execute("SELECT * FROM carga WHERE id = 1").fetchone() or {})
    cots = [dict(k) for k in cx.execute(
        "SELECT * FROM cotizaciones WHERE cliente_id = ? OR (cuit IS NOT NULL AND cuit = ?) ORDER BY fecha DESC",
        (cliente_id, c["cuit"] or "-"))]
    grupo = cx.execute("SELECT grupo, nombre FROM grupos WHERE cliente_id = ?", (cliente_id,)).fetchone()
    socios, cots_grupo = [], []
    if grupo:
        socios = [dict(s) for s in cx.execute(
            "SELECT g.cliente_id, c.empresa, c.cuenta_compartida FROM grupos g JOIN clientes c ON c.id = g.cliente_id "
            "WHERE g.grupo = ? AND g.cliente_id <> ?", (grupo["grupo"], cliente_id))]
        for s in socios:
            for k in _abiertas([dict(x) for x in cx.execute(
                    "SELECT * FROM cotizaciones WHERE cliente_id = ? ORDER BY fecha DESC", (s["cliente_id"],))]):
                k["_empresa"], k["_compartida"] = s["empresa"], s["cuenta_compartida"]
                k["_items"] = [dict(i) for i in cx.execute(
                    "SELECT articulo, cantidad, precio FROM cotizacion_items WHERE cotizacion_id = ?", (k["id"],))]
                cots_grupo.append(k)
    unidades = {}
    for x in comp:
        for q, p, _ in x["items"]:
            unidades[p] = unidades.get(p, 0) + q
    principal = max(unidades, key=unidades.get) if unidades else None
    precio_ult = None
    for x in reversed(comp):
        prods = {p for _, p, _ in x["items"]}
        if prods == {principal} and x["moneda"] == "USD" and x["bruto"]:
            q = sum(q for q, p, _ in x["items"])
            precio_ult = {"precio": x["bruto"] / q, "comp": x["comp"], "fecha": x["fecha"]}
            break
    hace_un_anio = (datetime.date.fromisoformat(hoy) - datetime.timedelta(days=365)).isoformat()
    cant_recientes = [sum(q for q, p, _ in x["items"] if p == principal) for x in comp
                      if x["fecha"] >= hace_un_anio and any(p == principal for _, p, _ in x["items"])]
    stock = None
    if principal:
        s = cx.execute("SELECT * FROM stock WHERE nombre = ?", (principal,)).fetchone()
        stock = dict(s) if s else None
    return {"c": c, "doc": doc, "sf": sf, "compras": comp, "anuladas": anuladas(sf), "motor": motor,
            "carga": carga, "cots": cots, "grupo": dict(grupo) if grupo else None, "socios": socios,
            "cots_grupo": cots_grupo, "principal": principal, "precio_ult": precio_ult,
            "cant_recientes": cant_recientes, "stock": stock, "hoy": hoy,
            "hive": {"precio_isp": precio_isp, "stock": stock_hive, "fecha": fecha_hive}}


def alertas(d):
    c, hoy, out = d["c"], d["hoy"], []
    dias = lambda a, b: (datetime.date.fromisoformat(b) - datetime.date.fromisoformat(a)).days  # noqa: E731
    ult = d["compras"][-1]["fecha"] if d["compras"] else ""
    rec = [h for h in d["doc"].get("historial") or [] if "recompra hecha" in str(h.get("txt", "")).lower()
           and str(h.get("t", ""))[:10] > ult]
    anul = [h for h in d["doc"].get("historial") or [] if "se anula" in str(h.get("txt", "")).lower()
            and "recompra" in str(h.get("txt", "")).lower()]
    if rec and not anul:
        out.append(("A1", f"«Recompra hecha» el {_f(rec[-1]['t'][:10])} sin factura posterior"))
    if c["proxima_fecha"] and c["proxima_fecha"] < hoy:
        out.append(("A2", f"Seguimiento vencido desde el {_f(c['proxima_fecha'])}"))
    if not (c["marca_olt"] or "").strip():
        out.append(("A3", "OLT sin cargar en la ficha"))
    cargado = (d["carga"].get("cargado") or "")[:10]
    if cargado and dias(cargado, hoy) > 2:
        out.append(("A4", f"La base es del {_f(cargado)}: re-cargar"))
    for k in _abiertas(d["cots"]):
        if k["vence"] and k["vence"] < hoy:
            out.append(("A5", f"{k['numero'] or k['id']} venció el {_f(k['vence'])}"))
        if (k["estado"] or "").lower() == "enviada" and k["fecha"] and dias(k["fecha"][:10], hoy) >= 14:
            out.append(("A9", f"{k['numero'] or k['id']} lleva {dias(k['fecha'][:10], hoy)} días sin respuesta"))
    for campo, txt in (("otro_vendedor", "otro vendedor"), ("no_prospectar", "no prospectar")):
        v = (c[campo] or "").strip()
        if v and v.lower() not in ("no", "false", "0"):
            out.append(("A6", f"Marcada {txt}: {v}"))
    corte = d["carga"].get("corte_stock")
    if corte and dias(corte, hoy) > 3 and not d["hive"]["stock"]:
        out.append(("A7", f"Stock de la copia de HIVE del {_f(corte)}: mirar HIVE"))
    for k in d["cots_grupo"]:
        out.append(("A8", f"{k['_empresa']} (mismo grupo) tiene la {k['numero'] or k['id']} abierta"))
    return out


def _fila(a, b, warn=False):
    est = ' style="color:var(--text-warning)"' if warn else ""
    return f'<div class="rw"><span class="mu">{html.escape(a)}</span><span{est}>{html.escape(b)}</span></div>'


def _ck(t, hecho=False):
    icono = "ti-circle-check" if hecho else "ti-circle"
    return f'<div class="ck"><i class="ti {icono}" aria-hidden="true"></i><span>{html.escape(t)}</span></div>'


def armar(d):
    """Devuelve (texto, html) de la tarjeta."""
    c, doc, m, hoy, al = d["c"], d["doc"], d["motor"], d["hoy"], alertas(d)
    anio = hoy[:4]
    grupo = d["grupo"]["nombre"] if d["grupo"] else None
    cab = [f"CUIT {doc.get('cuit') or c['cuit'] or '—'}", f"Cliente Horizon: {c['cliente_horizon'] or '—'}",
           f"OLT: {c['marca_olt'] or 'sin cargar'}"]
    if grupo:
        cab.append(grupo)
    banda = []
    if m and m["empujon"] and m["empujon"] != "—":
        banda.append(f"Sales Engine: {m['empujon']} · {m['palabras'] or ''}"
                     f"{' (obligatorio)' if m['obligatorio'] else ''}. {m['evidencia'] or ''}")
    else:
        banda.append("El Sales Engine no la empuja hoy")
    banda += [t for k, t in al if k in ("A2", "A6")]
    principal = d["principal"]
    abiertas = _abiertas(d["cots"])
    filas = []
    if abiertas:
        k = abiertas[0]
        req = {"t": f"Cotización {k['numero'] or k['id']}", "s": f"{k['estado']} · vence {_f(k['vence'])}",
               "q": _usd(k["total"]), "u": "con IVA"}
        filas.append(_fila("Cotización", f"{k['estado']}"))
    else:
        rango = d["cant_recientes"]
        q = (f"{_ar(min(rango))}–{_ar(max(rango))}" if rango and min(rango) != max(rango)
             else _ar(rango[0]) if rango else "—")
        req = {"t": f"Reposición {principal or ''}".strip(), "s": "Compra típica del último año (Stockfish)",
               "q": q, "u": "unidades"}
        filas.append(_fila("Cotización", "sin cotizar", warn=True))
    if principal:
        filas.insert(0, _fila("Modelo", principal + (f" · {d['stock']['codigo']}" if d["stock"] else "")))
    pu = d["precio_ult"]
    if pu:
        filas.append(_fila("Último precio", f"USD {_ar(pu['precio'], 3).rstrip('0').rstrip(',')} + IVA ({pu['comp'][-4:]}, {_f(pu['fecha'])})"))
    h = d["hive"]
    filas.append(_fila("Precio ISP HIVE", f"USD {_ar(h['precio_isp'], 2)}" if h["precio_isp"] else "consultar HIVE",
                       warn=not h["precio_isp"]))
    if h["stock"] is not None:
        filas.append(_fila(f"Stock HIVE {_f(h['fecha'] or hoy)}", _ar(h["stock"])))
    elif d["stock"]:
        s = d["stock"]
        filas.append(_fila(f"Stock copia {_f(d['carga'].get('corte_stock'))}",
                           f"{_ar(s['stock'] or 0)}" + (f" (+{_ar(s['transito'])} tránsito)" if s["transito"] else "")))
    del_anio = [x for x in d["compras"] if (x["fecha"] or "").startswith(anio)]
    fact_filas, cant = [], 0
    for x in del_anio:
        txt = " + ".join(f"{_ar(q)} {p if p != principal else ''}".strip() for q, p, _ in x["items"])
        cant += sum(q for q, p, _ in x["items"] if p == principal)
        fact_filas.append(_fila(f"{_f(x['fecha'])} · FA {x['comp'][-4:]}", txt or "—"))
    total = sum(x["total"] or 0 for x in del_anio if x["moneda"] == "USD")
    antes = [t for k, t in al if k not in ("A2", "A6")]
    for k in d["cots_grupo"]:
        it = "; ".join(f"{_ar(i['cantidad'])} {i['articulo']} a USD {_ar(i['precio'], 3).rstrip('0').rstrip(',')}"
                       for i in k["_items"])
        antes.append(f"{k['_empresa']}: {k['numero']} {k['estado']}, {it}, {_usd(k['total'])} c/IVA, vence {_f(k['vence'])}"
                     + (" · cuenta compartida" if (k["_compartida"] or "").strip() else ""))
    an = d["anuladas"]
    if an:
        antes.append("Anuladas con NC (no cuentan): " + ", ".join(f"FA {a['comp'][-4:]} del {_f(a['fecha'])}" for a in an))
    if not d["sf"]:
        antes.append("Sin ficha de Stockfish: las compras no están auditadas")
    ck = []
    if d["cots_grupo"]:
        k = d["cots_grupo"][0]
        ck.append(_ck(f"Ver cómo sigue la {k['numero']} de {k['_empresa']} y si incluye esta compra"))
    if m and m["empujon"] not in (None, "—"):
        tel = f" ({c['telefono']})" if c["telefono"] else ""
        ck.append(_ck(f"{m['empujon'].capitalize()}: contactar a {c['contacto'] or 'compras'}{tel}"
                      + (f", ofrecer {req['q']} {principal}" if not abiertas and principal else "")
                      + (f", pago {doc.get('pago')}" if doc.get("pago") else "")))
    if pu or h["precio_isp"]:
        ck.append(_ck("Definir precio: " + " o ".join(filter(None, [
            f"USD {_ar(pu['precio'], 3).rstrip('0').rstrip(',')} de la última compra" if pu else None,
            f"ISP {_ar(h['precio_isp'], 2)} de HIVE" if h["precio_isp"] else None]))))
    if any(k == "A3" for k, _ in al):
        ck.append(_ck("Cargar la OLT en la ficha"))
    if any(k == "A2" for k, _ in al):
        ck.append(_ck("Actualizar la próxima fecha de la ficha"))
    rempl = {
        "RESUMEN": f"Estado de {c['empresa']} al {_f(hoy)}: " + "; ".join(banda),
        "FECHA": _f(hoy), "RAZON_SOCIAL": c["empresa"], "CABECERA": " · ".join(cab),
        "BANDA": ". ".join(banda), "REQ_TITULO": req["t"], "REQ_SUB": req["s"], "REQ_CANT": req["q"],
        "REQ_UNIDAD": req["u"], "REQ_BOTON": f"Armame la cotización de {c['empresa']}",
        "ANIO": anio, "FACT_SUB": f"{principal or 'Compras'} (Stockfish, sin anuladas)",
        "FACT_CANT": _ar(cant), "FACT_UNIDAD": "unidades", "FACT_TOTAL": _usd(total),
        "FACT_BOTON": f"Mostrame el historial completo de {c['empresa']}"}
    crudo = {"REQ_FILAS": "\n".join(filas), "FACT_FILAS": "\n".join(fact_filas) or _fila("Sin compras este año", ""),
             "ANTES": "<br>".join(html.escape(a) for a in antes) or "Nada pendiente de verificar",
             "CHECKLIST": "\n".join(ck) or _ck("Sin acción sugerida")}
    with open(PLANTILLA, encoding="utf-8") as fh:
        t = fh.read()
    for k, v in rempl.items():
        t = t.replace("{{" + k + "}}", html.escape(str(v), quote=True).replace("'", "&#39;"))
    for k, v in crudo.items():
        t = t.replace("{{" + k + "}}", v)
    faltan = re.findall(r"\{\{(\w+)\}\}", t)
    if faltan:
        raise ValueError(f"la plantilla quedó con campos sin llenar: {faltan}")
    texto = [rempl["RESUMEN"]] + [f"- {k} {t_}" for k, t_ in al]
    if not h["precio_isp"]:
        texto.append("- falta el precio vigente: consultar HIVE (precio_producto) y volver a pedir la tarjeta con precio_isp")
    return "\n".join(texto), t


def estado_cliente(cx, consulta, hoy, buscar, precio_isp=None, stock_hive=None, fecha_hive=None):
    rs = buscar(cx, consulta)
    if not rs:
        return f"Sin coincidencias para «{consulta}»."
    if len(rs) > 1:
        return (f"Ambiguo: {len(rs)} fichas para «{consulta}». Decir cuál:\n" +
                "\n".join(f"- {r['id']} · {r['empresa']} · CUIT {r['cuit'] or '—'}" for r in rs[:15]))
    d = datos(cx, rs[0]["id"], hoy, precio_isp, stock_hive, fecha_hive)
    texto, tarjeta = armar(d)
    return (texto + "\n\nMostrar la tarjeta con show_widget tal cual (debajo, 1-2 líneas como mucho):\n"
            "<<<TARJETA\n" + tarjeta + "\nTARJETA>>>")

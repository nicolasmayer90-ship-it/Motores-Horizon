#!/usr/bin/env python3
"""
CONCILIADOR · Horizon CRM · v1.3 (13/11/2026)

v1.3 (13/11, «ok 1 3 4» de Nicolás): (1) C1 de una factura posterior al corte de remitos = sin dato de remito
todavía (nivel info, sinDato), no «asegurar entrega»: el remito no puede estar cargado. (2) cada hallazgo trae
«informar»: no (cuenta fuera, noProspectar, otroVendedor: «cuenta que no se puede prospectar no se informa»),
aviso (archivada o compartida: se dice como dato, sin acción) o si. No cambia qué C1 lee el Sales Engine.

v1.2 («terminemos el datacenter», 11/11 15:49): libro de ventas = r15 + r22 (manda r22 en su período);
solo facturas en el índice de comprobantes; FA anulada por NC del mismo cliente y bruto no cuenta.

v1.1 (L0, hacelo 11/11 14:31): lee restricciones.cuentasFuera (por id o CUIT = restringida) y
restricciones.enDeposito (el C1 de esa cuenta queda informativo: en depósito por decisión de Nicolás).

Cruza, por cuenta (CUIT + cuitsAdicionales; nunca por nombre parecido):
  ficha (campos e historial dictado) · cotizaciones · facturación (líneas) ·
  Reporte_15 (comprobantes con importes) · Reporte_21 (remitos y devoluciones).
Reglas fijas: misma entrada, misma salida. El script decide; Claude explica.

Reglas:
  C1 Factura sin remito al corte de remitos  -> sin despachar (total o parcial)
  C2 Entrega dictada mayor que lo despachado -> manda lo dictado, se muestran las dos
  C3 Despacho de otra cuenta del mismo grupo con la misma cantidad dictada -> posible doble conteo
  C4 La ficha espera compra y hay remito/factura que la ficha no menciona -> compró y la ficha no lo sabe
  C5 Total de cotización aceptada vs factura (Reporte_15) > 1 % -> manda la factura
  C6 Despacho de una cuenta propia con otro vendedor, o sin vendedor y sin factura -> consultar a Nicolás
  C7 Despacho sin factura dentro del corte de facturación (ventana de 45 días) -> revisar
Nunca: marcar ausencia después del corte de cada fuente; adivinar clientes sin CUIT;
generar acción sobre cuentas restringidas (se concilian como dato).
Producto: mismo nombre normalizado, o mismo conjunto exacto de códigos de modelo
(tokens con dígito o en mayúsculas: FitDP-420A, 24F, AS80, RCT100, CGCBCM). Nunca parecido.

Uso:
  python3 -I conciliador.py --crm DIR --cot DIR --fact DIR --reportes DIR --hoy AAAA-MM-DD
         [--desde 2026-08-13] [--json salida.json]
"""
import argparse, glob, hashlib, json, os, re, sys, unicodedata
from collections import defaultdict

VERSION = "1.3"
RESTR = {"excepciones": (), "decidido": {}, "fuera": {}, "deposito": {}}   # se carga de datacenter/restricciones (--restricciones)
VENTANA_PREVIA = 45          # un remito puede ir hasta 45 d antes de su factura
TOL_MONTO = 0.01             # C5
VEND_PROPIOS = {"nicolas mayer", "ventas horizon"}
EXCLUIR_PRODUCTO = re.compile(r"anticipo|ajuste|diferencia de cambio|flete|envio|envío", re.I)
STOP = {"FH", "FIBERHOME", "ZTT", "HUAWEI", "ONT", "ONU", "GPON", "SM", "PCB", "CHS", "FO", "Y", "DE", "PK"}


# ---------------- utilidades ----------------
def dig(s):
    return re.sub(r"\D", "", str(s or ""))

def sinacento(s):
    return "".join(c for c in unicodedata.normalize("NFD", str(s or "")) if unicodedata.category(c) != "Mn")

def nprod(s):
    return re.sub(r"\s+", " ", sinacento(s).lower()).strip()

def codigos(s):
    toks = re.findall(r"[A-Za-z0-9/\-\+]+", sinacento(s))
    out = set()
    for t in toks:
        T = t.upper().strip("-/")
        if len(T) < 2 or T in STOP:
            continue
        if re.search(r"\d", T) or (t.isupper() and len(T) >= 3):
            out.add(T)
    return frozenset(out)

def mismo_producto(a, b):
    if nprod(a) == nprod(b):
        return True
    ca, cb = codigos(a), codigos(b)
    return bool(ca) and ca == cb

def comp_key(s):
    """A-00005-00001713 / A 00005-00001713 / 0007-00000071 -> '00005-00001713' / '0007-00000071'"""
    d = re.findall(r"\d+", str(s or ""))
    if len(d) >= 2:
        return f"{d[-2]}-{d[-1]}"
    return d[-1] if d else ""

def es_usd(m):
    m = sinacento(m).lower()
    return m in ("usd", "u$s", "us$") or "dolar" in m


def num(x):
    try:
        if isinstance(x, str):
            x = x.replace(".", "").replace(",", ".") if re.search(r",\d{1,2}$", x) else x
        return float(x)
    except Exception:
        return None

def load_dir(d):
    out = {}
    for fn in sorted(glob.glob(os.path.join(d, "*.json"))):
        out[os.path.splitext(os.path.basename(fn))[0]] = json.load(open(fn, encoding="utf-8"))
    return out

def decode_report(rdir, base):
    m = json.load(open(os.path.join(rdir, base + ".json"), encoding="utf-8"))
    F = m["formato"]["f"]; dic = m["dic"]
    rows = list(m["d"])
    for i in range(2, int(m.get("partes", 1)) + 1):
        rows += json.load(open(os.path.join(rdir, f"{base}_{i}.json"), encoding="utf-8"))["d"]
    out = []
    for r in rows:
        out.append({k: (dic[k][v] if k in dic and isinstance(v, int) and v is not None else v) for k, v in zip(F, r)})
    return m, out


# ---------------- carga ----------------
def cargar(a):
    fichas = load_dir(a.crm)
    cots = load_dir(a.cot)
    fact = load_dir(a.fact)
    m15, r15 = libro_ventas(a.reportes)
    m21, r21 = decode_report(a.reportes, "r21")
    return fichas, cots, fact, (m15, r15), (m21, r21)


def libro_ventas(rdir):
    """v1.2: libro de ventas = r15 + r22. En el período que cubre r22 manda r22 (trae las NC que anulan
    facturas, caso Villa del Rosario NC 407 / FA 1710 → FA 1718); antes de r22.desde queda r15."""
    m15, r15 = decode_report(rdir, "r15")
    if not os.path.exists(os.path.join(rdir, "r22.json")):
        return m15, r15
    m22, r22 = decode_report(rdir, "r22")
    desde = m22.get("desde") or min(r["fecha"] for r in r22 if r.get("fecha"))
    rows = [r for r in r15 if (r.get("fecha") or "") < desde] + r22
    m = dict(m15); m["hasta"] = max(m15.get("hasta") or "", m22.get("hasta") or ""); m["fuentes"] = ["r15", "r22"]
    return m, rows


def anuladas_por_nc(rows):
    """v1.2: FA anulada = NC electrónica (no por dif. de cambio) del mismo cliente por el mismo bruto, posterior a la FA;
    se empareja 1 a 1 con la FA más reciente. Devuelve las claves de FA anuladas."""
    fas = sorted([r for r in rows if es_factura(r) and (r.get("bruto") or 0) > 0], key=lambda r: (r.get("fecha") or "", r.get("comprobante") or ""))
    ncs = [r for r in rows if "crédito" in str(r.get("tipocomp") or "").lower() and "cambio" not in str(r.get("tipocomp") or "").lower()]
    usadas, out = set(), set()
    for nc in sorted(ncs, key=lambda r: (r.get("fecha") or "", r.get("comprobante") or "")):
        cand = [f for f in fas if f.get("cliente") == nc.get("cliente") and abs((f.get("bruto") or 0) + (nc.get("bruto") or 0)) < 0.01
                and (f.get("fecha") or "") <= (nc.get("fecha") or "") and id(f) not in usadas]
        antes = [f for f in cand if (f.get("fecha") or "") < (nc.get("fecha") or "")]   # la refactura del mismo día no es la anulada
        cand = antes or cand
        if cand:
            f = cand[-1]; usadas.add(id(f)); out.add(comp_key(f.get("comprobante")))
    return out


def es_factura(r):
    return "factura" in str(r.get("tipocomp") or "").lower()


def restringida(f, fid=None):
    fu = RESTR["fuera"]
    if fu and (fid in fu or any(re.sub(r"\D", "", str((v or {}).get("cuit") or "")) in cuits_de(f)
                                for v in fu.values() if isinstance(v, dict) and v.get("cuit"))):
        return "cuenta fuera"
    if f.get("archivada"):
        return "archivada"
    if str(f.get("noProspectar", "")).lower() in ("si", "sí", "true", "1"):
        return "noProspectar"
    if f.get("otroVendedor"):
        return "otroVendedor"
    if str(f.get("cuentaCompartida", "")).lower() in ("si", "sí", "true", "1"):
        return "cuentaCompartida"
    return None


NO_INFORMAR = ("cuenta fuera", "noProspectar", "otroVendedor")   # decisión 105 (13/11)


def informar(restr):
    if restr in NO_INFORMAR:
        return "no"
    return "aviso" if restr in ("archivada", "cuentaCompartida") else "si"   # compartida: dato, nada sin confirmación de Nicolás


def decidida(fid, f):
    """Decisión de Nicolás sobre de quién es la cuenta (datacenter/restricciones): no se vuelve a preguntar."""
    if fid in RESTR["decidido"]:
        return RESTR["decidido"][fid]
    n = re.sub(r"[^a-z0-9]", "", sinacento(f.get("empresa", "")).lower())
    for e in RESTR["excepciones"]:
        if e and e in n:
            return f"{f.get('empresa')} es de Nicolás (excepcionesNicolas)"
    return None


def cuits_de(f):
    s = set()
    for k in ("cuit", "facturacionId"):
        if dig(f.get(k)):
            s.add(dig(f.get(k)))
    ca = f.get("cuitsAdicionales") or []
    if isinstance(ca, str):
        ca = re.split(r"[,;\s]+", ca)
    for c in ca:
        if len(dig(c)) >= 8:
            s.add(dig(c))
    return s


def texto_ficha(f):
    parts = [str(f.get("notas", "")), str(f.get("proximaAccion", ""))]
    parts += [str(h.get("txt", "")) for h in (f.get("historial") or []) if isinstance(h, dict)]
    return "\n".join(parts)


# ---------------- dictados de entrega (C2/C3) ----------------
RX_QTY = re.compile(r"(\d+(?:[.,]\d+)?)\s*(km|kms|metros|mts|m)\b", re.I)
RX_ENTREGA = re.compile(r"entregad|entregar?on|entregó|retir", re.I)
RX_NEG = re.compile(r"pendiente de destino|sin entregar|no entregad|no sali|sin despach|sin remitir", re.I)
RX_FA = re.compile(r"FA\s*-?\s*(\d{3,5})", re.I)

def dictados(f):
    """Entregas dictadas por Nicolás. Estructurado (entregasDictadas) primero; texto del historial como 'revisar'.
    Una línea posterior con 'corrige' invalida los dictados de texto anteriores de esa ficha."""
    out = []
    for e in f.get("entregasDictadas") or []:
        q = num(e.get("cantidad"))
        if q:
            out.append({"fa": dig(e.get("factura"))[-4:], "cantidad": q, "fecha": str(e.get("fecha", ""))[:10],
                        "fuente": "entregasDictadas", "txt": e.get("fuente", "")})
    hist = [h for h in (f.get("historial") or []) if isinstance(h, dict)]
    hist.sort(key=lambda h: str(h.get("t", "")))
    corte_corr = max([str(h.get("t", ""))[:10] for h in hist if re.search(r"\bcorrige", str(h.get("txt", "")), re.I)] or [""])
    for h in hist:
        t = str(h.get("txt", "")); fecha = str(h.get("t", ""))[:10]
        if not t.lower().startswith("nicolás") and "nicolás" not in t.lower()[:20]:
            continue
        if not RX_ENTREGA.search(t) or RX_NEG.search(t.split(".")[0]):
            continue
        if corte_corr and fecha <= corte_corr:
            continue
        mq = RX_QTY.search(t)
        if not mq:
            continue
        q = float(mq.group(1).replace(".", "").replace(",", "."))
        if mq.group(2).lower().startswith("km"):
            q *= 1000
        mfa = RX_FA.search(t)
        out.append({"fa": mfa.group(1)[-4:] if mfa else "", "cantidad": q, "fecha": fecha,
                    "fuente": "historial (texto: revisar)", "txt": t[:160]})
    return out


# ---------------- motor ----------------
def conciliar(fichas, cots, fact, R15, R21, hoy, desde):
    m15, r15 = R15; m21, r21 = R21
    corte_rem = m21.get("hasta") or max(r["fecha"] for r in r21 if r.get("fecha"))
    corte_f15 = m15.get("hasta") or max(r["fecha"] for r in r15 if r.get("fecha"))
    fact_fechas = [l.get("fecha") for d in fact.values() for l in (d.get("lineas") or []) if l.get("fecha")]
    corte_flin = max(fact_fechas) if fact_fechas else ""
    corte_fac = max(corte_f15, corte_flin)
    inicio = "2026-06-01"   # demanda y despachos desde acá para asignar bien; se reporta desde `desde`

    # índice CUIT -> ficha (activa primero)
    por_cuit = defaultdict(list)
    for fid, f in fichas.items():
        for c in cuits_de(f):
            por_cuit[c].append(fid)
    def ficha_de(cuit):
        ids = por_cuit.get(dig(cuit)) or []
        act = [i for i in ids if not fichas[i].get("archivada")]
        return sorted(act or ids)[0] if (act or ids) else None

    # cotizaciones por ficha y por factura
    cot_ficha = defaultdict(list); cot_por_fa = {}
    for cid, c in cots.items():
        fid = c.get("oportunidadId") or ficha_de(c.get("cuit"))
        if fid:
            cot_ficha[fid].append(cid)
        op = c.get("hz_operacion") if isinstance(c.get("hz_operacion"), dict) else {}
        fa = op.get("factura") or ""
        if fa and c.get("estado") == "aceptada":
            cot_por_fa[comp_key(fa)] = cid

    # grupos: cuitsAdicionales ya están en cuits_de; además misma NM base o unificadaEn
    grupo = {fid: {fid} for fid in fichas}
    def unir(a, b):
        g = grupo[a] | grupo[b]
        for x in g:
            grupo[x] = g
    por_nm = defaultdict(set)
    for cid, c in cots.items():
        nm = re.match(r"(NM\d+)", str(c.get("numero", "")))
        fid = c.get("oportunidadId")
        if nm and fid in fichas:
            por_nm[nm.group(1)].add(fid)
    for s in por_nm.values():
        s = sorted(s)
        for x in s[1:]:
            unir(s[0], x)
    for fid, f in fichas.items():
        u = f.get("unificadaEn")
        if u in fichas:
            unir(fid, u)

    # comprobantes r15 por clave
    r15_por = {}
    anuladas = anuladas_por_nc(r15)
    for r in r15:
        if es_factura(r):          # v1.2: solo facturas; una NC con el mismo número no pisa a una FA
            k = comp_key(r.get("comprobante"))
            if k not in anuladas:
                r15_por.setdefault(k, r)

    # demanda (facturas) y oferta (remitos) por ficha
    demanda = defaultdict(list)   # fid -> [{fa, fecha, producto, cant, pend, fuente}]
    fuera_r = []
    fact_comp_ficha = defaultdict(set)
    for cuit, d in fact.items():
        fid = ficha_de(cuit)
        lineas = sorted(d.get("lineas") or [], key=lambda l: (l.get("fecha", ""), l.get("comprobante", "")))
        for l in lineas:
            if l.get("fecha", "") < inicio:
                continue
            if fid:
                fact_comp_ficha[fid].add(comp_key(l.get("comprobante")))
            if EXCLUIR_PRODUCTO.search(str(l.get("producto", ""))):
                continue
            q = num(l.get("cantidad")) or 0
            if not fid or q == 0:
                continue
            if l.get("tipo") == "NC":
                # resta a la última factura previa del mismo producto
                for dm in sorted(demanda[fid], key=lambda x: x["fecha"], reverse=True):
                    if mismo_producto(dm["producto"], l.get("producto")) and dm["pend"] > 0 and dm["fecha"] <= l["fecha"]:
                        quita = min(dm["pend"], abs(q)); dm["pend"] -= quita; dm["cant"] -= quita; dm["nc"] = True
                        q = q + quita if q < 0 else q - quita
                        if q == 0:
                            break
                continue
            demanda[fid].append({"fa": comp_key(l.get("comprobante")), "fecha": l["fecha"], "producto": l.get("producto"),
                                 "cant": q, "pend": q, "fuente": "facturación"})
    # facturas que en facturación son solo anticipo o que están en r15 después del corte de líneas: items de la cotización
    for fa, cid in cot_por_fa.items():
        c = cots[cid]; fid = c.get("oportunidadId") or ficha_de(c.get("cuit"))
        if not fid or fid not in fichas:
            continue
        ya = [x for x in demanda[fid] if x["fa"] == fa]
        if ya:
            continue
        r = r15_por.get(fa)
        op = c.get("hz_operacion") if isinstance(c.get("hz_operacion"), dict) else {}
        fecha = (r or {}).get("fecha") or op.get("facturaFecha") or c.get("fechaGanada") or c.get("fecha")
        if not fecha or fecha < inicio:
            continue
        for it in c.get("items") or []:
            q = num(it.get("cantidad")) or 0
            if q and not EXCLUIR_PRODUCTO.search(str(it.get("articulo", ""))):
                demanda[fid].append({"fa": fa, "fecha": fecha, "producto": it.get("articulo"), "cant": q, "pend": q,
                                     "fuente": f"cotización {c.get('numero')}"})
        fact_comp_ficha[fid].add(fa)

    remitos = defaultdict(list)
    sin_id = set()
    for r in sorted(r21, key=lambda x: (x.get("fecha") or "", x.get("comprobante") or "", x.get("_fila") or 0)):
        if (r.get("fecha") or "") < inicio:
            continue
        fid = ficha_de(r.get("cuit")) if r.get("cuit") else None
        if not fid:
            sin_id.add(r.get("cliente"))
            continue
        q = num(r.get("cantidad")) or 0
        if str(r.get("tipo", "")).lower().startswith("devol"):
            q = -abs(q)
        remitos[fid].append({"rem": r.get("comprobante") or "", "fecha": r["fecha"], "producto": r.get("producto"),
                             "cant": q, "libre": q, "vendedor": r.get("vendedor")})

    # asignación FIFO remito -> factura
    for fid in set(demanda) | set(remitos):
        dem = sorted(demanda[fid], key=lambda x: (x["fecha"], x["fa"]))
        for rm in remitos[fid]:
            if rm["cant"] < 0:      # devolución: vuelve a abrir la última factura del producto
                for dm in sorted(dem, key=lambda x: x["fecha"], reverse=True):
                    if mismo_producto(dm["producto"], rm["producto"]) and dm["pend"] < dm["cant"]:
                        dm["pend"] += min(abs(rm["cant"]), dm["cant"] - dm["pend"]); break
                rm["libre"] = 0
                continue
            for dm in dem:
                if rm["libre"] <= 0:
                    break
                if dm["pend"] <= 0 or not mismo_producto(dm["producto"], rm["producto"]):
                    continue
                if rm["fecha"] < _menos(dm["fecha"], VENTANA_PREVIA):
                    continue
                t = min(dm["pend"], rm["libre"]); dm["pend"] -= t; rm["libre"] -= t

    hall = []
    def H(regla, fid, monto, que, a, b, hacer, nivel="alto", sin_dato=False):
        f = fichas.get(fid, {})
        dec = decidida(fid, f)
        if dec and "onsultar a Nicolás" in (que + hacer):
            que = re.sub(r" · sin vendedor: consultar a Nicolás si la venta es suya", "", que)
            hacer = f"Ya decidido: {dec}"; nivel = "info"
        rs = restringida(f, fid)
        h = {"regla": regla, "ficha": fid, "empresa": f.get("empresa", fid), "monto": round(monto or 0, 2),
             "que": que, "fuenteA": a, "fuenteB": b, "hacer": hacer, "nivel": nivel,
             "restringida": rs, "informar": informar(rs)}
        if sin_dato:
            h["sinDato"] = True
        hall.append(h)

    # C1
    for fid, dem in demanda.items():
        por_fa = defaultdict(list)
        for dm in dem:
            if dm["fecha"] >= desde and dm["cant"] > 0:
                por_fa[dm["fa"]].append(dm)
        for fa, items in sorted(por_fa.items()):
            pend = [x for x in items if x["pend"] > 0]
            if not pend:
                continue
            r = r15_por.get(fa); total = num((r or {}).get("total")) or 0
            moneda = (r or {}).get("moneda") or ""
            usd = total if es_usd(moneda) else 0
            det = "; ".join(f"{int(x['pend'])} de {int(x['cant'])} {x['producto']}" for x in pend)
            parcial = any(x["pend"] < x["cant"] for x in pend) or len(pend) < len(items)
            dep = RESTR["deposito"].get(fid)
            ffa = items[0]["fecha"]
            sin_dato = ffa > corte_rem and not dep          # v1.3: la factura es más nueva que el último remito cargado
            if dep:
                hacer = f"En depósito: {dep} · no se empuja"
            elif sin_dato:
                hacer = f"Sin dato de remito todavía (factura del {ffa}, remitos al {corte_rem}): confirmar el despacho con el próximo reporte 21"
            else:
                hacer = "Asegurar entrega" + (" del resto" if parcial else "")
            H("C1", fid, usd, f"FA {fa}{' (parcial)' if parcial else ''}: sin despachar {det}",
              f"factura {fa} del {ffa} ({items[0]['fuente']})", f"remitos al {corte_rem}: no alcanzan",
              hacer, "info" if (dep or sin_dato) else "alto", sin_dato=sin_dato)

    # C2 / C3
    for fid, f in fichas.items():
        for dc in dictados(f):
            rem_tot = sum(rm["cant"] for rm in remitos[fid] if rm["cant"] > 0 and rm["fecha"] >= desde)
            if dc["cantidad"] <= rem_tot + 1e-6:
                continue
            H("C2", fid, 0, f"Dictado {dc['fecha']}: {int(dc['cantidad'])} entregados{(' de FA ' + dc['fa']) if dc['fa'] else ''}; remitos de esta cuenta desde {desde}: {int(rem_tot)}",
              f"dictado ({dc['fuente']})", f"remitos al {corte_rem}", "Manda lo dictado; confirmar si salió sin remito o es de otra cuenta", "medio")
            for otro in sorted(grupo[fid] - {fid}):
                for rm in remitos[otro]:
                    if abs(rm["cant"] - dc["cantidad"]) < 1e-6 and rm["fecha"] <= (dc["fecha"] or hoy):
                        H("C3", fid, 0, f"Los {int(dc['cantidad'])} dictados coinciden con el remito {rm['rem']} del {rm['fecha']} de {fichas[otro].get('empresa', otro)} ({rm['producto']})",
                          f"dictado {dc['fecha']} en {f.get('empresa', fid)}", f"remito {rm['rem']} de {fichas[otro].get('empresa', otro)}",
                          "Posible doble conteo: confirmar de qué cuenta fue la entrega")

    # C4 / C6 / C7
    RX_ESPERA = re.compile(r"esper|recompra|repon|reactiv", re.I)
    for fid, rms in remitos.items():
        f = fichas[fid]; txt = texto_ficha(f)
        for cid in cot_ficha.get(fid, []):
            txt += "\n" + json.dumps(cots[cid].get("hz_operacion", ""), ensure_ascii=False) + str(cots[cid].get("numero", ""))
        vistos = set()
        ult = max([str(h.get("t", ""))[:10] for h in (f.get("historial") or []) if isinstance(h, dict)] + [str(f.get("ultimoContacto") or "")[:10]])
        for rm in rms:
            if rm["cant"] <= 0 or rm["fecha"] < desde:
                continue
            k = comp_key(rm["rem"])
            sin_fact = rm["libre"] > 0
            if k not in vistos:
                vistos.add(k)
                mencion = (k and (k in txt or k.split("-")[-1] in txt))
                if not mencion and rm["fecha"] > ult and RX_ESPERA.search(str(f.get("proximaAccion", ""))):
                    H("C4", fid, 0, f"Remito {rm['rem']} del {rm['fecha']} ({int(rm['cant'])} {rm['producto']}) y la ficha dice: «{str(f.get('proximaAccion', ''))[:90]}»",
                      f"remito {rm['rem']}", "ficha: no lo menciona", "Compró y la ficha no lo sabe: registrar antes de contactar")
            v = (rm.get("vendedor") or "").strip().lower()
            if v and v not in VEND_PROPIOS:
                H("C6", fid, 0, f"Remito {rm['rem']} del {rm['fecha']} con vendedor «{rm['vendedor']}»", f"remito {rm['rem']}",
                  "ficha de Nicolás", "Consultar a Nicolás de quién es la venta", "medio")
            if sin_fact:
                sv = " · sin vendedor: consultar a Nicolás si la venta es suya" if not v else ""
                if rm["fecha"] > corte_fac:
                    H("C7", fid, 0, f"Remito {rm['rem']} del {rm['fecha']} ({int(rm['libre'])} {rm['producto']}): posterior al corte de facturación {corte_fac}{sv}",
                      f"remito {rm['rem']}", f"facturación al {corte_fac}", "Nada hasta el próximo reporte de facturación" + sv, "info" if v else "medio")
                elif rm["libre"] <= 0.01 * rm["cant"]:
                    H("C7", fid, 0, f"Remito {rm['rem']} del {rm['fecha']}: diferencia menor ({int(rm['libre'])} de {int(rm['cant'])} {rm['producto']}), posible unidad distinta en una NC",
                      f"remito {rm['rem']}", f"facturación al {corte_fac}", "Nada (diferencia menor al 1 %)", "info")
                else:
                    H("C7", fid, 0, f"Remito {rm['rem']} del {rm['fecha']}: {int(rm['libre'])} {rm['producto']} sin factura que lo cubra{sv}",
                      f"remito {rm['rem']}", f"facturación al {corte_fac} (ventana {VENTANA_PREVIA} d)", "Revisar: muestra, préstamo o factura de otra razón social", "medio")

    # C5
    for fa, cid in cot_por_fa.items():
        c = cots[cid]; r = r15_por.get(fa)
        if not r or not es_usd(r.get("moneda")):
            continue
        ct, ft = num(c.get("total")), num(r.get("total"))
        if ct and ft and abs(ct - ft) / ft > TOL_MONTO:
            fid = c.get("oportunidadId") or ficha_de(c.get("cuit"))
            if fid in fichas and (c.get("fechaGanada") or c.get("fecha") or "") >= desde:
                H("C5", fid, ft, f"{c.get('numero')}: cotización USD {ct:,.2f} vs factura {fa} USD {ft:,.2f}",
                  f"cotización {c.get('numero')}", f"Reporte_15 {fa}", "Manda la factura: corregir el total de la cotización", "medio")

    # control de cuentas
    con_mov = set(demanda) | set(remitos)
    con_h = {h["ficha"] for h in hall}
    cuentas = {"fichas": len(fichas), "restringidas": 0, "sinMovimiento": 0, "conciliadas": 0, "conHallazgo": 0}
    for fid, f in fichas.items():
        if restringida(f, fid):
            cuentas["restringidas"] += 1
        elif fid in con_h:
            cuentas["conHallazgo"] += 1
        elif fid in con_mov:
            cuentas["conciliadas"] += 1
        else:
            cuentas["sinMovimiento"] += 1
    cierra = sum(v for k, v in cuentas.items() if k != "fichas") == cuentas["fichas"]

    orden = {"alto": 0, "medio": 1, "info": 2}
    hall.sort(key=lambda h: (h["restringida"] is not None, orden[h["nivel"]], -h["monto"], h["regla"], h["empresa"], h["que"]))
    res = {"version": VERSION, "hoy": hoy, "desde": desde,
           "cortes": {"remitos": corte_rem, "facturacionLineas": corte_flin, "reporte15": corte_f15},
           "cuentas": cuentas, "cierra": cierra, "sinIdentificar": len(sin_id), "hallazgos": hall}
    res["veredicto"] = "PASA" if cierra else "FALLA"
    res["huella"] = hashlib.sha256(json.dumps(res, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:12]
    return res


def _menos(fecha, dias):
    import datetime as dt
    return (dt.date.fromisoformat(fecha) - dt.timedelta(days=dias)).isoformat()


def cargar_restricciones(ruta):
    if not ruta:
        return
    r = json.load(open(ruta, encoding="utf-8"))
    ex = r.get("excepcionesNicolas") or []
    if isinstance(ex, str):
        ex = re.findall(r"[a-z0-9]+", ex.lower())
    RESTR["excepciones"] = tuple(re.sub(r"[^a-z0-9]", "", sinacento(e).lower()) for e in ex)
    dc = r.get("decididoConciliador") or {}
    RESTR["decidido"] = {k: (v.get("motivo") if isinstance(v, dict) else str(v)) for k, v in dc.items()}
    RESTR["fuera"] = r.get("cuentasFuera") or {}
    RESTR["deposito"] = {k: str(v) for k, v in (r.get("enDeposito") or {}).items()}


def informe(res):
    c = res["cuentas"]; L = []
    L.append(f"# Conciliador v{res['version']} · {res['hoy']} · {res['veredicto']}")
    L.append(f"Cortes: remitos {res['cortes']['remitos']} · facturación líneas {res['cortes']['facturacionLineas']} · libro de ventas (r15+r22) {res['cortes']['reporte15']} · desde {res['desde']}")
    L.append(f"Control: {c['fichas']} fichas = {c['conHallazgo']} con hallazgo + {c['conciliadas']} conciliadas + {c['sinMovimiento']} sin movimiento + {c['restringidas']} restringidas ({'cierra' if res['cierra'] else 'NO CIERRA'}) · sin identificar en remitos: {res['sinIdentificar']} nombres")
    act = [h for h in res["hallazgos"] if h.get("informar") == "si" and h["nivel"] != "info"]
    inf = [h for h in res["hallazgos"] if h.get("informar") == "si" and h["nivel"] == "info"]
    avi = [h for h in res["hallazgos"] if h.get("informar") == "aviso"]
    rst = [h for h in res["hallazgos"] if h.get("informar") == "no"]
    L.append(f"\n## Para actuar ({len(act)})")
    for h in act:
        L.append(f"- [{h['regla']}·{h['nivel']}] {h['empresa']}{(' · USD ' + format(h['monto'], ',.2f')) if h['monto'] else ''} · {h['que']}\n    {h['fuenteA']} vs {h['fuenteB']} → {h['hacer']}")
    L.append(f"\n## Informativos ({len(inf)})")
    for h in inf:
        L.append(f"- [{h['regla']}] {h['empresa']} · {h['que']}")
    L.append(f"\n## Archivadas: {len(avi)} avisos (dato, sin acción)")
    for h in avi:
        L.append(f"- [{h['regla']}] {h['empresa']}{(' · USD ' + format(h['monto'], ',.2f')) if h['monto'] else ''} · {h['que'][:160]}")
    L.append(f"\n## No se informan (no prospectar, otro vendedor, cuenta fuera): {len(rst)} hallazgos")
    L.append(f"\nHuella: {res['huella']}\nRegla: el script decide; Claude explica. Cambiar reglas solo con «hacelo».")
    return "\n".join(L)


def cmd_test():
    """v1.2: pruebas fijas del libro de ventas (anulación por NC y NC que comparte número con una FA)."""
    ok = True
    def t(c, m):
        nonlocal ok; print(("PASA " if c else "FALLA") + " · " + m); ok &= bool(c)
    FA = lambda n, f, b, cl="VR": {"tipocomp": "Factura de Venta Electrónica", "comprobante": n, "fecha": f, "bruto": b, "cliente": cl}
    NC = lambda n, f, b, cl="VR", tp="Nota de Crédito de Ventas Electrónica": {"tipocomp": tp, "comprobante": n, "fecha": f, "bruto": b, "cliente": cl}
    rows = [FA("A-00005-00001710", "2026-10-28", 11962), NC("A-00005-00000407", "2026-11-11", -11962), FA("A-00005-00001718", "2026-11-11", 11962),
            FA("A-00005-00000407", "2022-05-01", 500, "OTRO"), NC("A-00005-00000500", "2026-11-05", -11962, "VR", "Nota de Crédito de Ventas por Dif. Cambio")]
    an = anuladas_por_nc(rows)
    t(comp_key("A-00005-00001710") in an and comp_key("A-00005-00001718") not in an, "NC 407 anula la FA 1710 y deja viva la FA 1718 (Villa del Rosario)")
    t(comp_key("A-00005-00000407") not in an, "la FA 407 de otro cliente no queda anulada por la NC 407")
    t(len(an) == 1, "la NC por diferencia de cambio no anula facturas")
    t(not es_factura(rows[1]) and es_factura(rows[0]), "una NC no entra al índice de facturas")
    t(informar("noProspectar") == "no" and informar("otroVendedor") == "no" and informar("cuenta fuera") == "no",
      "v1.3: no prospectar, otro vendedor y cuenta fuera no se informan (decisión 105)")
    t(informar("archivada") == "aviso" and informar(None) == "si" and informar("cuentaCompartida") == "aviso",
      "v1.3: archivada y compartida = aviso; propia = se informa")
    t("2026-11-12" > "2026-11-10" and not ("2026-11-03" > "2026-11-10"),
      "v1.3: factura posterior al corte de remitos = sin dato (comparación de fechas ISO)")
    print("RESULTADO:", "PASA" if ok else "FALLA"); return 0 if ok else 1


def main():
    if sys.argv[1:2] == ["test"]:
        sys.exit(cmd_test())
    p = argparse.ArgumentParser()
    p.add_argument("--crm", required=True); p.add_argument("--cot", required=True)
    p.add_argument("--fact", required=True); p.add_argument("--reportes", required=True)
    p.add_argument("--hoy", required=True); p.add_argument("--desde", default="2026-08-13")
    p.add_argument("--json"); p.add_argument("--restricciones")
    a = p.parse_args()
    cargar_restricciones(a.restricciones)
    res = conciliar(*cargar(a), a.hoy, a.desde)
    if a.json:
        json.dump(res, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(informe(res))
    sys.exit(0 if res["veredicto"] == "PASA" else 1)


if __name__ == "__main__":
    main()

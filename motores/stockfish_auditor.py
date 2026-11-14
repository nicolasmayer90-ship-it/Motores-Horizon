#!/usr/bin/env python3
"""Stockfish auditor v2.0 · Horizon CRM
Auditor del pasado: reglas fijas, misma entrada -> misma salida. No predice ni filtra.
Analiza TODAS las cuentas (incluye archivadas, no prospectar, otro vendedor, compartidas
y clientes sin ficha) y entrega una ficha a detalle por cuenta: campos de `oportunidades`
+ campos sf_ (compras, cotizaciones con estado real, entregas, hallazgos, huecos, sello).

Uso:
  python3 -I stockfish_auditor.py test
  python3 -I stockfish_auditor.py correr --src <carpeta exportada> --hoy AAAA-MM-DD --out <carpeta salida>
La carpeta exportada tiene: oportunidades/, cotizaciones/, facturacion/, muestras/, finnegans/,
reportes/ (r15, r15_2..), config/ (operaciones, ventasControl, ventasEntregas).
"""
import sys, os, json, glob, re, hashlib, unicodedata, datetime, collections

VERSION = "2.6"
INTERNO_CUIT = "30714931616"  # Horizon Trading S.A.
ESTADOS_VIVOS = {"borrador", "enviada", "espera_decision", "espera_aprobacion"}
ETAPAS_PRE = {"prospecto", "contactado", "calificado"}
DIF_CAMBIO = "Dif. Cambio"
TOL_MONTO = 0.01      # 1 % para comparar montos
VENTANA_COT_FACT = 20  # días cotización aceptada <-> factura
VENTANA_REFACT = 10    # días NC -> factura rehecha
DESDE_NICOLAS = "2026-08-13"
RE_BANCARIO = re.compile(r"bancari|^cbu$|^cvu$|iban|^alias_?cbu", re.I)
SUPUESTOS = ["ANT (anticipo) suma como venta: pendiente confirmar con Nicolás",
             "ND comercial (no dif. de cambio) suma como venta: pendiente confirmar con Nicolás"]

# ---------------------------------------------------------------- utilidades
SANEADOS = [0]

def sanear(o):
    """Saca de raíz cualquier clave de datos bancarios: nunca entran al auditor ni a la salida."""
    if isinstance(o, dict):
        out = {}
        for k, v in o.items():
            if RE_BANCARIO.search(str(k)):
                SANEADOS[0] += 1
                continue
            out[k] = sanear(v)
        return out
    if isinstance(o, list):
        return [sanear(x) for x in o]
    return o

def load(p):
    d = json.load(open(p, encoding="utf-8"))
    d = d.get("data", d) if isinstance(d, dict) and "data" in d and isinstance(d["data"], dict) else d
    return sanear(d)

def load_dir(path):
    out = {}
    for f in sorted(glob.glob(os.path.join(path, "*.json"))):
        out[os.path.basename(f)[:-5]] = load(f)
    return out

def dig(s):
    return re.sub(r"\D", "", str(s or ""))

def cuit_valido(c):
    c = dig(c)
    if len(c) != 11:
        return False
    w = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    s = sum(int(c[i]) * w[i] for i in range(10))
    v = 11 - s % 11
    v = 0 if v == 11 else (9 if v == 10 else v)
    return v == int(c[10])

def norm_nombre(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().upper()
    s = re.sub(r"[^A-Z0-9]+", " ", s).strip()
    # "S A" -> "SA", "S R L" -> "SRL" (siglas partidas por puntos)
    toks, out, buf = s.split(), [], ""
    for t in toks:
        if len(t) == 1 and t.isalpha():
            buf += t
        else:
            if buf: out.append(buf); buf = ""
            out.append(t)
    if buf: out.append(buf)
    return " ".join(out)

def d2(s):
    try:
        return datetime.date.fromisoformat(str(s)[:10])
    except Exception:
        return None

def dias(a, b):
    a, b = d2(a), d2(b)
    return (b - a).days if a and b else None

def iso(s):
    """Fecha normalizada AAAA-MM-DD; '' si no es una fecha válida (nunca compara texto crudo)."""
    d = d2(s)
    return d.isoformat() if d else ""

def en_ventana(a, b, lo, hi):
    """True si lo <= dias(a,b) <= hi. Cero es un valor válido (mismo día); fecha inválida = False."""
    n = dias(a, b)
    return n is not None and lo <= n <= hi

def cerca(a, b, tol=TOL_MONTO):
    try:
        a, b = float(a), float(b)
    except Exception:
        return False
    if a == 0 and b == 0:
        return True
    return abs(a - b) <= tol * max(abs(a), abs(b))

def comp_norm(s):
    """'A 00005-00001713' / 'FC 00005-00001713' / 'A-00005-00001713' -> 'A-00005-00001713' (letra opcional)."""
    s = str(s or "").upper()
    m = re.search(r"([AB])?\s*-?\s*(\d{4,5})\s*-\s*(\d{8})", s)
    if not m:
        return ""
    return f"{m.group(1) or '?'}-{int(m.group(2)):05d}-{m.group(3)}"

def comp_match(a, b):
    a, b = comp_norm(a), comp_norm(b)
    if not a or not b:
        return False
    if a == b:
        return True
    return a[1:] == b[1:] and ("?" in (a[0], b[0]))

def sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]

# ---------------------------------------------------------------- carga
def cargar(src):
    S = {}
    S["fichas"] = load_dir(os.path.join(src, "oportunidades"))
    S["cots"] = load_dir(os.path.join(src, "cotizaciones"))
    S["fact"] = load_dir(os.path.join(src, "facturacion"))
    S["muestras"] = load_dir(os.path.join(src, "muestras"))
    S["finn"] = load_dir(os.path.join(src, "finnegans"))
    rep = os.path.join(src, "reportes")
    r15 = load(os.path.join(rep, "r15.json"))
    rows = list(r15["d"])
    for i in range(2, int(r15.get("partes", 1)) + 1):
        rows += load(os.path.join(rep, f"r15_{i}.json"))["d"]
    S["r15_meta"] = {k: r15.get(k) for k in ("desde", "hasta", "lineas", "cargado", "control")}
    def decodificar(meta, filas):
        f, dic, out = meta["formato"]["f"], meta["dic"], []
        for x in filas:
            r = dict(zip(f, x))
            for k in ("tipocomp", "moneda", "cliente", "usuario"):
                if isinstance(r.get(k), int):
                    r[k] = dic[k][r[k]]
            out.append(r)
        return out
    S["r15"] = decodificar(r15, rows)
    # v2.5 (plan cerebro, definiciones.fuentes.libroVentas): libro de ventas = r15 + r22; en el período de r22 manda r22
    p22 = os.path.join(rep, "r22.json")
    if os.path.exists(p22):
        r22 = load(p22)
        rows22 = list(r22["d"])
        for i in range(2, int(r22.get("partes", 1)) + 1):
            rows22 += load(os.path.join(rep, f"r22_{i}.json"))["d"]
        d22 = decodificar(r22, rows22)
        desde = r22.get("desde") or min(r["fecha"] for r in d22 if r.get("fecha"))
        S["r15"] = [r for r in S["r15"] if (r.get("fecha") or "") < desde] + d22
        S["r15_meta"] = dict(S["r15_meta"], hasta=max(r15.get("hasta") or "", r22.get("hasta") or ""),
                             lineas=len(S["r15"]), fuentes=["r15", "r22"], r22desde=desde)
    cfg = os.path.join(src, "config")
    def opt(n):
        p = os.path.join(cfg, n + ".json")
        return load(p) if os.path.exists(p) else {}
    S["operaciones"] = opt("operaciones")
    S["ventasControl"] = opt("ventasControl")
    S["ventasEntregas"] = opt("ventasEntregas")
    return S

def aporte(tipo, bruto):
    """Venta neta sin IVA: F/ND/ANT suman, NC resta (en r15 la NC ya viene negativa), dif. de cambio no cuenta."""
    b = abs(float(bruto or 0))
    return b if tipo in ("F", "ND", "ANT") else -b if tipo == "NC" else 0.0

def tipo_r15(t):
    t = str(t)
    if DIF_CAMBIO in t:
        return "NDC" if "Débito" in t else "NCC"   # diferencia de cambio: NO es venta
    if "Crédito" in t:
        return "NC"
    if "Débito" in t:
        return "ND"
    if "Anticipo" in t:
        return "ANT"
    return "F"

# ---------------------------------------------------------------- cuentas
class UF:
    def __init__(s): s.p = {}
    def f(s, x):
        s.p.setdefault(x, x)
        while s.p[x] != x:
            s.p[x] = s.p[s.p[x]]; x = s.p[x]
        return x
    def u(s, a, b):
        a, b = s.f(a), s.f(b)
        if a != b:
            s.p[max(a, b)] = min(a, b)

def cuits_ficha(o):
    cs = set()
    for c in [o.get("cuit"), o.get("facturacionId")] + list(o.get("cuitsAdicionales") or []):
        c = dig(c)
        if len(c) in (7, 8, 11):   # DNI (7-8) o CUIT (11); otros largos no unen cuentas (se informan)
            cs.add(c)
    return cs

def cuits_raros(o):
    out = []
    for c in [o.get("cuit"), o.get("facturacionId")] + list(o.get("cuitsAdicionales") or []):
        c = dig(c)
        if c and len(c) not in (7, 8, 11):
            out.append(c)
    return out

def armar_cuentas(S):
    fichas = S["fichas"]
    uf = UF()
    cuit2f = collections.defaultdict(set)
    for fid, o in fichas.items():
        uf.f("F:" + fid)
        for c in cuits_ficha(o):
            cuit2f[c].add(fid)
            uf.u("F:" + fid, "C:" + c)
        u = o.get("unificadaEn")
        if u and u in fichas:
            uf.u("F:" + fid, "F:" + u)
    # CUIT y nombres de fuentes
    nombre2cuit = {}
    for r in S["r15"]:
        c = dig(r.get("cuit"))
        if c:
            uf.f("C:" + c)
            nombre2cuit.setdefault(norm_nombre(r["cliente"]), set()).add(c)
    for k, d in S["fact"].items():
        c = dig(d.get("cuit") or k)
        uf.f("C:" + c)
        nombre2cuit.setdefault(norm_nombre(d.get("cliente")), set()).add(c)
    return uf, cuit2f, nombre2cuit

def canonica(grupo_fichas, fichas):
    if not grupo_fichas:
        return None
    destinos = {fichas[f].get("unificadaEn") for f in grupo_fichas}
    def clave(f):
        o = fichas[f]
        return (1 if o.get("archivada") else 0, 0 if f in destinos else 1, f)
    return sorted(grupo_fichas, key=clave)[0]

# ---------------------------------------------------------------- motor
def auditar(S, hoy):
    fichas = S["fichas"]
    uf, cuit2f, nombre2cuit = armar_cuentas(S)
    # agrupar raíces
    miembros = collections.defaultdict(lambda: {"fichas": set(), "cuits": set()})
    for k in list(uf.p.keys()):
        r = uf.f(k)
        if k.startswith("F:"):
            miembros[r]["fichas"].add(k[2:])
        else:
            miembros[r]["cuits"].add(k[2:])
    cuentas = {}
    raiz2id = {}
    for r, m in miembros.items():
        can = canonica(m["fichas"], fichas)
        aid = can if can else "sf-c" + sorted(m["cuits"])[0]
        raiz2id[r] = aid
        cuentas[aid] = {"id": aid, "ficha": can, "fichas": sorted(m["fichas"]), "cuits": sorted(m["cuits"]),
                        "r15": [], "fact": [], "cots": [], "pedidos": [], "remitos": [], "muestras": [],
                        "ptes": [], "nombres": set(), "vinculo": set()}
    def cuenta_por_cuit(c):
        c = dig(c)
        return raiz2id.get(uf.f("C:" + c)) if ("C:" + c) in uf.p else None
    def cuenta_por_ficha(fid):
        seen = set()
        while fid in fichas and fichas[fid].get("unificadaEn") and fid not in seen:
            seen.add(fid)
            if fichas[fid]["unificadaEn"] in fichas:
                fid = fichas[fid]["unificadaEn"]
            else:
                break
        return raiz2id.get(uf.f("F:" + fid)) if ("F:" + fid) in uf.p else None
    def cuenta_por_nombre(n):
        cs = nombre2cuit.get(norm_nombre(n), set())
        if len(cs) == 1:
            return cuenta_por_cuit(next(iter(cs))), "nombre_exacto"
        return None, ("nombre_ambiguo" if cs else "sin_vinculo")
    sin_vinc = {"r15": [], "pedidos": [], "remitos": [], "cots": [], "ptes": [], "muestras": []}
    internas = []
    ctl = collections.Counter()

    # r15
    for i, r in enumerate(S["r15"]):
        ctl["r15_in"] += 1
        row = {"fecha": r["fecha"], "tipo": tipo_r15(r["tipocomp"]), "comp": r["comprobante"], "moneda": r["moneda"],
               "bruto": r["bruto"], "total": r["total"], "tc": r.get("tc"), "usuario": r.get("usuario"),
               "cuitPorNombre": r.get("cuitPorNombre"), "detalle": (r.get("detalle") or "")[:80], "_fila": r.get("_fila", i)}
        aid = cuenta_por_cuit(r["cuit"]) if r.get("cuit") else None
        how = "cuit" if aid else None
        if not aid:
            aid, how = cuenta_por_nombre(r["cliente"])
        if aid:
            cuentas[aid]["r15"].append(row); cuentas[aid]["nombres"].add(r["cliente"]); cuentas[aid]["vinculo"].add("r15:" + how)
            ctl["r15_out"] += 1
        else:
            row["cliente"] = r["cliente"]; sin_vinc["r15"].append(row); ctl["r15_out"] += 1
    # facturación
    for k, d in S["fact"].items():
        aid = cuenta_por_cuit(d.get("cuit") or k)
        for l in d.get("lineas", []):
            ctl["fact_in"] += 1
            cuentas[aid]["fact"].append(dict(l)); ctl["fact_out"] += 1
        cuentas[aid]["nombres"].add(d.get("cliente") or "")
    # cotizaciones
    for cid, c in S["cots"].items():
        ctl["cot_in"] += 1
        if dig(c.get("cuit")) == INTERNO_CUIT or "HORIZON TRADING" in norm_nombre(c.get("cliente")):
            internas.append(cid); ctl["cot_out"] += 1; continue
        aid = cuenta_por_ficha(c.get("oportunidadId")) if c.get("oportunidadId") else None
        if not aid and dig(c.get("cuit")):
            aid = cuenta_por_cuit(c["cuit"])
        if aid:
            cuentas[aid]["cots"].append((cid, c))
        else:
            sin_vinc["cots"].append(cid)
        ctl["cot_out"] += 1
    # pedidos finnegans
    for k, d in S["finn"].items():
        for p in d.get("pedidos", []):
            ctl["ped_in"] += 1
            aid, how = cuenta_por_nombre(p.get("cliente") or d.get("cliente"))
            item = {"numero": p.get("numero"), "fecha": p.get("fecha"), "estado": p.get("estado"), "moneda": p.get("moneda"),
                    "items": [f"{it.get('cantidad')} × {it.get('producto')}" for it in p.get("items", [])]}
            if aid:
                cuentas[aid]["pedidos"].append(item); cuentas[aid]["vinculo"].add("pedidos:" + how)
            else:
                item["cliente"] = d.get("cliente"); sin_vinc["pedidos"].append(item)
            ctl["ped_out"] += 1
    # operaciones: remitos y pedidos pendientes
    op = S["operaciones"] or {}
    for rm in op.get("remitos", []):
        ctl["rem_in"] += 1
        aid, how = cuenta_por_nombre(rm.get("cliente"))
        if aid:
            cuentas[aid]["remitos"].append({"fecha": rm.get("fecha"), "nro": rm.get("nro")})
        else:
            sin_vinc["remitos"].append(rm)
        ctl["rem_out"] += 1
    for num, p in sorted((op.get("pedidos") or {}).items()):
        ctl["opped_in"] += 1
        aid, how = cuenta_por_nombre(p.get("cliente"))
        item = {"numero": num, "fecha": p.get("fecha"), "pendiente": p.get("pendiente"), "desc": p.get("desc"),
                "neto": p.get("neto"), "vend": p.get("vend"),
                "items": [f"{it.get('q')} × {it.get('prod')}" for it in p.get("items", [])]}
        if aid:
            cuentas[aid]["pedidos"].append(item)
        else:
            item["cliente"] = p.get("cliente"); sin_vinc["pedidos"].append(item)
        ctl["opped_out"] += 1
    # entregas pendientes (ventasControl)
    ent = {comp_norm(k): v for k, v in (S["ventasEntregas"] or {}).items() if comp_norm(k)}
    ent_raw = S["ventasEntregas"] or {}
    for p in (S["ventasControl"] or {}).get("ptes", []):
        ctl["pte_in"] += 1
        aid = cuenta_por_ficha(p["ficha"]) if p.get("ficha") else cuenta_por_nombre(p.get("cliente"))[0]
        item = {"comp": p.get("comp"), "fecha": p.get("fecha"), "items": p.get("items", []),
                "entregado": ent.get(comp_norm(p.get("comp"))) or ent_raw.get(p.get("comp"), "")}
        if aid:
            cuentas[aid]["ptes"].append(item)
        else:
            item["cliente"] = p.get("cliente"); sin_vinc["ptes"].append(item)
        ctl["pte_out"] += 1
    # muestras
    for mid, m in S["muestras"].items():
        ctl["mue_in"] += 1
        aid = cuenta_por_ficha(m.get("oportunidadId"))
        if aid:
            cuentas[aid]["muestras"].append((mid, m))
        else:
            sin_vinc["muestras"].append(mid)
        ctl["mue_out"] += 1

    # ------------------------------------------------ fichas a detalle + reglas
    salida = {}
    totales = collections.Counter()
    for aid in sorted(cuentas):
        A = cuentas[aid]
        if not (A["fichas"] or A["r15"] or A["fact"] or A["cots"] or A["pedidos"]):
            continue
        doc = ficha_detalle(A, fichas, hoy)
        salida[aid] = doc
        totales["usd_bruto_neto"] += A["usd_raw"]
        totales["ars_bruto_neto"] += A["ars_raw"]
    descartadas = [a for a, A in cuentas.items() if a not in salida and (A["fichas"] or A["r15"] or A["fact"] or A["cots"] or A["pedidos"] or A["remitos"] or A["ptes"] or A["muestras"])]
    # totales de control de montos
    # control independiente: se recalcula desde la fuente cruda, por tipo de comprobante
    usd_in = 0.0
    for r in S["r15"]:
        if r["moneda"] != "USD" or DIF_CAMBIO in r["tipocomp"]:
            continue
        usd_in += (-abs(r["bruto"] or 0)) if "Crédito" in r["tipocomp"] else abs(r["bruto"] or 0)
    ars_in = 0.0
    for r in S["r15"]:
        if r["moneda"] == "USD" or DIF_CAMBIO in r["tipocomp"]:
            continue
        ars_in += (-abs(r["bruto"] or 0)) if "Crédito" in r["tipocomp"] else abs(r["bruto"] or 0)
    usd_sin = sum(aporte(x["tipo"], x["bruto"]) for x in sin_vinc["r15"] if x["moneda"] == "USD")
    ars_sin = sum(aporte(x["tipo"], x["bruto"]) for x in sin_vinc["r15"] if x["moneda"] != "USD")
    sv_monto = {"n": len(sin_vinc["r15"]), "usd": round(usd_sin, 2), "ars": round(ars_sin, 2)}
    glob_h = hallazgos_globales(S, salida, sin_vinc, internas, sv_monto)
    ctl = medir(S, salida, sin_vinc, internas)
    control = cierre(ctl, usd_in, totales["usd_bruto_neto"] + usd_sin, salida, glob_h,
                     ars_in, totales["ars_bruto_neto"] + ars_sin, descartadas)
    return salida, {"sinVinculo": sin_vinc, "sinVinculoMonto": sv_monto, "internas": internas, "control": control, "globales": glob_h}

def medir(S, salida, sin_vinc, internas):
    """Control MEDIDO: entradas contadas en la fuente cruda, salidas contadas en lo que realmente quedó escrito."""
    D = salida.values()
    ctl = collections.Counter()
    ctl["r15_in"] = len(S["r15"])
    ctl["r15_out"] = sum(len(d["sf_comprobantes"]) for d in D) + len(sin_vinc["r15"])
    ctl["fact_in"] = sum(len(d.get("lineas", [])) for d in S["fact"].values())
    ctl["fact_out"] = sum(len(e["items"]) for d in D for e in d["sf_lineas"])
    ctl["cot_in"] = len(S["cots"])
    ctl["cot_out"] = sum(len(d["sf_cotizaciones"]) for d in D) + len(sin_vinc["cots"]) + len(internas)
    op = S["operaciones"] or {}
    ctl["pedidos_in"] = sum(len(d.get("pedidos", [])) for d in S["finn"].values()) + len(op.get("pedidos") or {})
    ctl["pedidos_out"] = sum(len(d["sf_pedidos"]) for d in D) + len(sin_vinc["pedidos"])
    ctl["rem_in"] = len(op.get("remitos", []))
    ctl["rem_out"] = sum(len(d["sf_remitos"]) for d in D) + len(sin_vinc["remitos"])
    ctl["pte_in"] = len((S["ventasControl"] or {}).get("ptes", []))
    ctl["pte_out"] = sum(len(d["sf_entregas"]) for d in D) + len(sin_vinc["ptes"])
    ctl["mue_in"] = len(S["muestras"])
    ctl["mue_out"] = sum(len(d["sf_muestras"]) for d in D) + len(sin_vinc["muestras"])
    ctl["fichas_in"] = len(S["fichas"])
    ctl["fichas_out"] = sum(len(d["sf_fichas"]) for d in D)
    return ctl

def hallazgos_globales(S, salida, sin_vinc, internas, sv_monto=None):
    h = []
    pv12 = sum(1 for d in S["fact"].values() for l in d.get("lineas", []) if "-00012-" in (l.get("comprobante") or ""))
    if pv12:
        h.append({"regla": "G01_PV12", "sev": "media",
                  "txt": f"facturacion trae {pv12} líneas de PV 00012 que el libro de ventas (r15) no tiene; la regla vigente dice PV 00012 = Sur Technology (fuera). Se listan marcadas pv12 y no cuentan como compra Horizon."})
    if sin_vinc["r15"]:
        h.append({"regla": "G02_R15_SIN_CLIENTE", "sev": "media",
                  "txt": f"{len(sin_vinc['r15'])} comprobantes del libro de ventas sin CUIT ni nombre único: quedan en sinVinculo (USD {sv_monto['usd'] if sv_monto else '?'} y ARS {sv_monto['ars'] if sv_monto else '?'} sin IVA, netos de NC)."})
    if sin_vinc["pedidos"]:
        h.append({"regla": "G03_PEDIDOS_SIN_CUENTA", "sev": "baja",
                  "txt": f"{len(sin_vinc['pedidos'])} pedidos de venta sin cuenta (nombre sin CUIT conocido)."})
    if sin_vinc["cots"]:
        h.append({"regla": "G04_COT_SIN_CUENTA", "sev": "alta", "txt": "Cotizaciones sin ficha ni CUIT: " + ", ".join(sin_vinc["cots"])})
    return h

def ficha_detalle(A, fichas, hoy):
    can = A["ficha"]
    base = {}
    if can:
        base = json.loads(json.dumps(fichas[can]))
    else:
        nom = sorted(n for n in A["nombres"] if n)
        base = {"empresa": nom[0] if nom else A["id"], "cuit": A["cuits"][0] if A["cuits"] else "", "etapa": ""}
    H, huecos = [], []
    def hall(regla, sev, txt, ev=None):
        H.append({"regla": regla, "sev": sev, "txt": txt, "evidencia": ev or []})

    # ---- compras (r15 = importes, facturacion = qué)
    r15 = sorted(A["r15"], key=lambda x: (x["fecha"], x["comp"], x["_fila"]))
    ventas = [x for x in r15 if x["tipo"] in ("F", "ANT")]
    ncs = [x for x in r15 if x["tipo"] == "NC"]
    # ---- anulaciones (una sola regla para todo el motor): cada NC anula UNA factura de igual monto (±1 %)
    # dentro de los 10 días previos; se prefiere la anterior a la NC y, si solo hay del mismo día, la de número menor.
    # Así una refactura del mismo día que la NC nunca se toma como anulada.
    anula = {}
    for n in sorted(ncs, key=lambda n: (n["fecha"], n["comp"])):
        cand = [x for x in ventas if x["moneda"] == n["moneda"] and id(x) not in anula
                and cerca(x["total"], abs(n["total"] or 0)) and en_ventana(x["fecha"], n["fecha"], 0, VENTANA_REFACT)]
        if cand:
            a = sorted(cand, key=lambda x: (0 if dias(x["fecha"], n["fecha"]) > 0 else 1, dias(x["fecha"], n["fecha"]), x["comp"]))[0]
            anula[id(a)] = n
    usd = collections.defaultdict(float); ars = collections.defaultdict(float)
    for x in r15:
        (usd if x["moneda"] == "USD" else ars)[x["fecha"][:4]] += aporte(x["tipo"], x["bruto"])
    A["usd_raw"] = sum(usd.values()); A["ars_raw"] = sum(ars.values())
    lineas = sorted(A["fact"], key=lambda l: (l.get("fecha") or "", l.get("comprobante") or "", l.get("producto") or ""))
    por_comp = collections.OrderedDict()
    for l in lineas:
        k = l.get("comprobante") or "(sin comprobante)"
        e = por_comp.setdefault(k, {"comp": k, "fecha": l.get("fecha"), "tipo": l.get("tipo"), "pv12": "-00012-" in k, "items": []})
        e["items"].append(f"{l.get('cantidad')} × {l.get('producto')} [{l.get('marca') or '-'}]")
    hz_lineas = [l for l in lineas if "-00012-" not in (l.get("comprobante") or "")]
    marcas = collections.Counter((l.get("marca") or "-") for l in hz_lineas if l.get("tipo") == "F")
    familias = collections.Counter((l.get("familia") or "-") for l in hz_lineas if l.get("tipo") == "F")
    compra_fh = any((l.get("marca") or "").lower() == "fiberhome" and l.get("tipo") == "F" for l in hz_lineas)
    compra_drop = any("drop" in (l.get("producto") or "").lower() and l.get("tipo") == "F" for l in hz_lineas)
    fechas_venta = sorted({x["fecha"] for x in ventas} | {l["fecha"] for l in hz_lineas if l.get("tipo") == "F" and l.get("fecha")})
    dias_ult = dias(fechas_venta[-1], hoy) if fechas_venta else None
    compras = {
        "primera": fechas_venta[0] if fechas_venta else "",
        "ultima": fechas_venta[-1] if fechas_venta else "",
        "nFacturas": len({x["comp"] for x in ventas}),
        "nNC": len(ncs),
        "nDifCambio": sum(1 for x in r15 if x["tipo"] in ("NCC", "NDC")),
        "usdBrutoNeto": round(sum(usd.values()), 2),
        "usdBrutoPorAnio": {k: round(v, 2) for k, v in sorted(usd.items())},
        "arsBrutoPorAnio": {k: round(v, 2) for k, v in sorted(ars.items())},
        "usdDesdeNicolas": round(sum(aporte(x["tipo"], x["bruto"]) for x in r15 if x["moneda"] == "USD" and x["fecha"] >= DESDE_NICOLAS), 2),
        "marcas": dict(sorted(marcas.items())), "familias": dict(sorted(familias.items())),
        "compraFiberHome": compra_fh, "compraDrop": compra_drop,
        "lineasPV12": sum(1 for l in lineas if "-00012-" in (l.get("comprobante") or "")),
    }
    # ---- cotizaciones con estado real
    corte_r15 = S_CORTES.get("r15", hoy)
    cots_ord = sorted(A["cots"], key=lambda t: (t[1].get("fecha") or "", t[0]))
    reclamadas = set()   # cada comprobante del libro de ventas se asigna a UNA sola cotización
    asign = {}
    ES_VENTA = ("F", "ANT")
    for cid, c in cots_ord:          # pasada 1: referencia explícita a la factura
        ho = c.get("hz_operacion") or {}
        ref = ho.get("factura") or c.get("factura") or ""
        fx = [x for x in r15 if x["tipo"] in ES_VENTA and comp_match(x["comp"], ref)
              and id(x) not in reclamadas] if ref else []
        asign[cid] = fx
        reclamadas.update(id(x) for x in fx)
    for cid, c in cots_ord:          # pasada 2: aceptadas sin referencia, por monto/fecha o por número en notas
        if asign[cid] or c.get("estado") != "aceptada":
            continue
        fg = c.get("fechaGanada") or c.get("fecha")
        cand = [x for x in r15 if x["tipo"] in ES_VENTA and x["moneda"] == "USD" and id(x) not in reclamadas
                and en_ventana(fg, x["fecha"], -VENTANA_COT_FACT, VENTANA_COT_FACT) and cerca(x["total"], c.get("total"))]
        if len(cand) > 1:
            vivas = [f for f in cand if id(f) not in anula] or cand
            cand = sorted(vivas, key=lambda f: (abs(dias(fg, f["fecha"])), f["fecha"], f["comp"]))[:1]
        if not cand:
            m = re.search(r"(?<![A-Z0-9])F[AC]?\s*(\d{3,5})\b", ((c.get("numero") or "") + " " + (c.get("notas") or "")).upper())
            if m:
                n = int(m.group(1))
                cand = [x for x in r15 if x["tipo"] in ES_VENTA and x["comp"].endswith(f"{n:08d}") and id(x) not in reclamadas][:1]
        asign[cid] = cand
        reclamadas.update(id(x) for x in cand)
    cots = []
    for cid, c in cots_ord:
        hr = c.get("hz_resultado") or {}; ho = c.get("hz_operacion") or {}
        for campo, val in (("fecha", c.get("fecha")), ("vence", c.get("vence")), ("revisionFecha", c.get("revisionFecha")),
                           ("fechaSeguimiento", hr.get("fechaSeguimiento"))):
            if val and not iso(val):
                hall("R13_FECHA_INVALIDA", "media", f"Cotización {c.get('numero') or cid}: {campo}='{val}' no es una fecha válida (AAAA-MM-DD).", [cid])
        # v2.6 (decisión 108, Nicolás 13/11: «siempre hay que revisar y renovar; nunca se dan de baja hasta que yo diga»):
        # la vigencia la da solo «vence»; revisionFecha y fechaSeguimiento agendan, no dan vigencia; sin vence = vencida (RENOVAR)
        limite = iso(c.get("vence")) or ""
        fact_ref = ho.get("factura") or c.get("factura") or ""
        fx = asign.get(cid, [])
        if c.get("archivada"):
            real = "archivada"
        elif c.get("estado") == "aceptada":
            fg0 = iso(c.get("fechaGanada") or c.get("fecha"))
            real = "aceptada_facturada" if fx else ("aceptada_dentro_corte" if fg0 and fg0 > corte_r15 else "aceptada_sin_factura")
        elif c.get("estado") == "rechazada":
            real = "rechazada"
        elif c.get("estado") in ESTADOS_VIVOS:
            real = "vigente" if limite and limite >= hoy else "vencida_sin_estado"
        else:
            real = c.get("estado") or "sin_estado"
        e = {"id": cid, "numero": c.get("numero"), "fecha": c.get("fecha"), "estado": c.get("estado"),
             "box": hr.get("estado", ""), "estadoReal": real, "total": c.get("total"), "neto": c.get("neto"),
             "vence": c.get("vence", ""), "limite": limite, "fechaGanada": c.get("fechaGanada", ""),
             "factura": fact_ref, "facturaR15": [x["comp"] for x in fx], "despacho": ho.get("despacho", ""),
             "familia": c.get("familia"), "marca": c.get("marca")}
        if fx and real == "aceptada_facturada":
            tot = sum(x["total"] or 0 for x in fx if x["moneda"] == "USD")
            e["facturaTotal"] = round(tot, 2)
            if tot and not cerca(tot, c.get("total")):
                hall("R05_MONTO_COT_FACTURA", "media",
                     f"{c.get('numero')}: cotización USD {c.get('total')} con IVA vs factura USD {round(tot,2)} (manda la factura).",
                     [cid] + e["facturaR15"])
        if real == "aceptada_dentro_corte":
            hall("R01_ACEPTADA_DENTRO_DEL_CORTE", "baja", f"{c.get('numero') or cid} aceptada el {c.get('fechaGanada') or c.get('fecha')}, posterior al corte del libro de ventas ({corte_r15}): esperar la próxima carga antes de dar por faltante la factura.", [cid])
        if real == "aceptada_sin_factura":
            hall("R01_ACEPTADA_SIN_FACTURA", "alta", f"{c.get('numero') or cid} aceptada el {c.get('fechaGanada') or c.get('fecha')} sin factura en el libro de ventas.", [cid])
        if real == "vencida_sin_estado":
            hall("R03_COT_VENCIDA_SIN_ESTADO", "alta", f"{c.get('numero') or cid} venció el {limite or c.get('fecha')}: elegir estado (vigente con nueva fecha, aceptada o perdida).", [cid])
        if (c.get("estado") == "aceptada" and ho.get("despacho") == "pendiente"):
            hall("R07_DESPACHO_PENDIENTE", "media", f"{c.get('numero') or cid}: ganada con despacho pendiente.", [cid])
        cots.append(e)
    # ---- R02 factura sin cotización (desde que entró Nicolás)
    usadas = {f for e in cots for f in e["facturaR15"]}
    for x in ventas:
        anulada = id(x) in anula
        if iso(x["fecha"]) >= DESDE_NICOLAS and x["comp"] not in usadas and not anulada:
            hall("R02_FACTURA_SIN_COTIZACION", "media",
                 f"Factura {x['comp']} del {x['fecha']} ({x['moneda']} {x['total']} con impuestos) sin cotización vinculada.", [x["comp"]])
    # ---- R08 NC sin cierre: la refactura tiene que ser por un monto equivalente (±1 %)
    consumidas = set(anula)   # factura anulada por una NC: no puede contar a la vez como su refactura
    for n in sorted(ncs, key=lambda n: (n["fecha"], n["comp"])):
        if iso(n["fecha"]) < "2025-01-01":
            continue
        en_v = [x for x in ventas if x["moneda"] == n["moneda"] and id(x) not in consumidas
                and en_ventana(n["fecha"], x["fecha"], 0, VENTANA_REFACT)]
        if any(cerca(x["total"], abs(n["total"] or 0)) for x in en_v):
            continue
        if en_v:
            hall("R08_NC_REFACTURA_OTRO_MONTO", "baja",
                 f"NC {n['comp']} del {n['fecha']} ({n['moneda']} {n['total']}): hay factura dentro de {VENTANA_REFACT} días pero de otro monto ({', '.join(x['comp'] for x in en_v[:3])}).", [n["comp"]] + [x["comp"] for x in en_v[:3]])
        else:
            hall("R08_NC_SIN_REFACTURAR", "media" if (iso(n["fecha"]) >= DESDE_NICOLAS and abs(n["total"] or 0) >= 100) else "baja",
                 f"NC {n['comp']} del {n['fecha']} ({n['moneda']} {n['total']}) sin factura rehecha en {VENTANA_REFACT} días.", [n["comp"]])
    # ---- R07 entregas abiertas
    entregas = []
    for p in sorted(A["ptes"], key=lambda p: (p.get("fecha") or "", p.get("comp") or "")):
        entregas.append(p)
        falta = "; ".join(f"{i.get('pte')} de {i.get('q')} {i.get('prod')}" for i in p.get("items", []))
        parcial = [i for i in p.get("items", []) if 0 < (i.get("pte") or 0) < (i.get("q") or 0)]
        if not p.get("entregado"):
            hall("R07_ENTREGA_ABIERTA", "alta", f"{p.get('comp')} del {p.get('fecha')}: sin entregar ({falta}).", [p.get("comp")])
        elif parcial:
            hall("R07_ENTREGA_PARCIAL", "alta", f"{p.get('comp')} figura entregado el {p.get('entregado')} pero quedan pendientes: {falta}.", [p.get("comp")])
    # ---- R04 etapa vs ventas
    etapa = base.get("etapa", "")
    if can:
        if etapa in ETAPAS_PRE and ventas:
            hall("R04_ETAPA_VS_VENTAS", "media" if (dias_ult if dias_ult is not None else 9999) <= 548 else "baja",
                 f"Etapa '{etapa}' pero tiene {len(ventas)} facturas (última {compras['ultima']}).")
        if etapa == "ganado" and not ventas and not any(e["estadoReal"].startswith("aceptada") for e in cots):
            hall("R04_ETAPA_VS_VENTAS", "media", "Etapa 'ganado' sin facturas ni cotización aceptada.")
        if etapa == "perdido" and any(e["estadoReal"] == "vigente" for e in cots):
            hall("R04_ETAPA_VS_VENTAS", "media", "Etapa 'perdido' con cotización vigente.")
        # R05 monto ficha vs cotización
        viv = [e for e in cots if e["estadoReal"] in ("vigente", "vencida_sin_estado", "aceptada_facturada", "aceptada_sin_factura", "aceptada_dentro_corte")]
        if viv and base.get("monto") not in (None, "", 0):
            ult = viv[-1]
            if not any(cerca(base.get("monto"), e["total"]) for e in viv):
                hall("R05_MONTO_FICHA_VS_COT", "baja", f"Monto de la ficha USD {base.get('monto')} no coincide con ninguna cotización abierta ni aceptada (última {ult['numero']}: USD {ult['total']}).")
        # R09 promesa vencida
        pf_raw = base.get("proximaFecha") or ""
        pf = iso(pf_raw)
        if pf_raw and not pf:
            hall("R13_FECHA_INVALIDA", "media", f"proximaFecha='{pf_raw}' no es una fecha válida (AAAA-MM-DD).")
        if pf and pf < hoy and not base.get("archivada"):
            hall("R09_PROMESA_VENCIDA", "media" if etapa not in ("pausa", "prospecto") else "baja",
                 f"Próxima acción vencida desde {pf}: {str(base.get('proximaAccion') or '')[:90]}")
        # USA FH sin marcar
        if compra_fh and not base.get("usaFH"):
            hall("R11_FH_SIN_MARCAR", "baja", "Compró FiberHome (facturado) y la ficha no tiene usaFH." + (" Compró drop." if compra_drop else ""))
        if base.get("usaFH") == "si" and not compra_fh:
            hall("R11_FH_SIN_EVIDENCIA", "baja", "usaFH=si sin FiberHome facturado (puede venir de otro proveedor).")
        # contacto
        if ventas and not (base.get("telefono") or base.get("email")):
            huecos.append("compró y la ficha no tiene teléfono ni email")
        if not dig(base.get("cuit")) and not A["cuits"]:
            huecos.append("sin CUIT")
        if etapa in ("ganado", "cotizado", "negociacion") and not (base.get("marcaOlt") or base.get("oltFH") or base.get("olt")):
            huecos.append("OLT desconocida (marca/modelo/versión)")
    else:
        if ventas:
            hall("R06_COMPRO_SIN_FICHA", "alta" if compras["ultima"] >= DESDE_NICOLAS else "media",
                 f"Compró ({len(ventas)} facturas, última {compras['ultima']}, USD {compras['usdBrutoNeto']} sin IVA neto de NC) y no tiene ficha.")
        elif A["fact"]:
            hall("R06_COMPRO_SIN_FICHA", "baja", f"Tiene líneas de facturación (última {compras['ultima'] or '-'}) y no tiene ficha.")
        huecos.append("sin ficha en el CRM")
    # ---- R10 CUIT duplicado / inválido
    vivas = [f for f in A["fichas"] if not fichas[f].get("archivada")]
    if len(vivas) > 1:
        hall("R10_CUIT_DUPLICADO", "media", "Varias fichas vivas comparten CUIT o unificación: " + ", ".join(vivas))
    for f in A["fichas"]:
        for c in cuits_raros(fichas[f]):
            hall("R10_CUIT_FORMATO", "media", f"Ficha {f}: CUIT/DNI '{c}' con {len(c)} dígitos (esperado 7-8 o 11); no se usó para unir cuentas.")
    for c in A["cuits"]:
        if len(c) == 11 and not cuit_valido(c):
            hall("R10_CUIT_INVALIDO", "media", f"CUIT {c} no pasa el dígito verificador.")
    # ---- muestras
    mues = []
    for mid, m in sorted(A["muestras"], key=lambda t: t[0]):
        mues.append({"id": mid, "estado": m.get("estado"), "productos": m.get("productos"), "seguimiento": m.get("seguimiento", "")})
        if m.get("estado") in ("pedida", "sin_retirar", "enviada", "prueba", "aprobada") and (iso(m.get("seguimiento")) or "") < hoy:
            hall("R09_MUESTRA_VENCIDA", "media", f"Muestra {mid} ({m.get('estado')}) con seguimiento vencido {m.get('seguimiento') or 'sin fecha'}.")
    # ---- R12 consistencia entre fuentes (desde 2025, corte común)
    corte = min(S_CORTES.get("fact", hoy), S_CORTES.get("r15", hoy))
    cf = {comp_norm(k) for k, v in por_comp.items() if v["tipo"] == "F" and not v["pv12"] and "2025-01-01" <= (v["fecha"] or "") <= corte}
    cr = {comp_norm(x["comp"]) for x in ventas if "2025-01-01" <= x["fecha"] <= corte}
    solo_f, solo_r = sorted(cf - cr - {""}), sorted(cr - cf - {""})
    if solo_f or solo_r:
        hall("R12_FUENTES_NO_CUADRAN", "baja",
             f"Desde 2025: {len(solo_f)} facturas solo en facturación y {len(solo_r)} solo en libro de ventas.", (solo_f + solo_r)[:10])
    # ---- documento
    sev_ord = {"alta": 0, "media": 1, "baja": 2}
    H.sort(key=lambda h: (sev_ord[h["sev"]], h["regla"], h["txt"]))
    restr = {k: base.get(k) for k in ("archivada", "noProspectar", "otroVendedor", "cuentaCompartida") if base.get(k)}
    doc = dict(base)
    doc.update({
        "sf_cuenta": A["id"], "sf_fichas": A["fichas"], "sf_cuits": A["cuits"], "sf_sinFicha": not bool(can),
        "sf_nombresFuente": sorted(n for n in A["nombres"] if n), "sf_vinculo": sorted(A["vinculo"]),
        "sf_restricciones": restr,
        "sf_compras": compras,
        "sf_comprobantes": [dict({k: x[k] for k in ("fecha", "tipo", "comp", "moneda", "bruto", "total", "tc", "usuario")}, anulada=id(x) in anula) for x in r15],
        "sf_lineas": list(por_comp.values()),
        "sf_cotizaciones": cots,
        "sf_pedidos": sorted(A["pedidos"], key=lambda p: (p.get("fecha") or "", p.get("numero") or "")),
        "sf_remitos": sorted(A["remitos"], key=lambda r: (r.get("fecha") or "", r.get("nro") or "")),
        "sf_entregas": entregas, "sf_muestras": mues,
        "sf_hallazgos": H, "sf_huecos": huecos,
        "sf_nHallazgos": {s: sum(1 for h in H if h["sev"] == s) for s in ("alta", "media", "baja")},
    })
    return doc

S_CORTES = {}

def cierre(ctl, usd_in, usd_out, salida, glob_h, ars_in=0.0, ars_out=0.0, descartadas=()):
    checks = []
    for k in ("r15", "fact", "cot", "pedidos", "rem", "pte", "mue", "fichas"):
        a, b = ctl.get(k + "_in", 0), ctl.get(k + "_out", 0)
        checks.append({"que": k, "entrada": a, "salida": b, "ok": a == b})
    checks.append({"que": "usd_bruto_neto_r15", "entrada": round(usd_in, 2), "salida": round(usd_out, 2), "ok": abs(usd_in - usd_out) < 0.01})
    checks.append({"que": "ars_bruto_neto_r15", "entrada": round(ars_in, 2), "salida": round(ars_out, 2), "ok": abs(ars_in - ars_out) < 0.01})
    checks.append({"que": "cuentas_descartadas_con_datos", "entrada": len(descartadas), "salida": 0, "ok": not descartadas})
    sin_id = [k for k, d in salida.items() if not d.get("sf_cuenta")]
    checks.append({"que": "cuentas_con_id", "entrada": len(salida), "salida": len(salida) - len(sin_id), "ok": not sin_id})
    ok = all(c["ok"] for c in checks)
    return {"resultado": "PASA" if ok else "FALLA", "checks": checks}

# ---------------------------------------------------------------- correr
# ====================================================================== VALOR DE CUENTA
# Decisión de Nicolás (09/11): el número de la ficha es el VALOR de la cuenta, no la chance de cerrar.
# Solo datos, reglas fijas. Cada componente se puntúa por percentil dentro de la cartera elegible
# (cuentas sin restricción). Cuentas con restricción: sin valor ("—").
PESOS_VALOR = {"compras24": 40, "recencia": 20, "frecuencia": 15, "amplitud": 10, "abierta": 15}
VENTANA_VALOR = 730
# v2.4 (Nicolás 09/11): la cotización vencida sin estado sigue sumando hasta que se elija su estado
ABIERTA_SUMA = ("vigente", "vencida_sin_estado")

def _usd(x):
    if x["moneda"] == "USD":
        return aporte(x["tipo"], x["bruto"])
    tc = x.get("tc") or 0
    return aporte(x["tipo"], x["bruto"]) / tc if tc and tc > 1 else 0.0

def valor_cuentas(salida, hoy):
    desde = (d2(hoy) - datetime.timedelta(days=VENTANA_VALOR)).isoformat()
    datos, restr = {}, {}
    for k, d in salida.items():
        r = sorted(x for x in ("archivada", "noProspectar", "otroVendedor") if (d.get("sf_restricciones") or {}).get(x))
        if r:
            restr[k] = r
            continue
        cmp_ = [x for x in d["sf_comprobantes"] if iso(x["fecha"]) >= desde]
        c = d["sf_compras"]
        datos[k] = {
            "compras24": round(sum(_usd(x) for x in cmp_), 2),
            "recencia": dias(c["ultima"], hoy) if c["ultima"] else None,
            "frecuencia": len({x["comp"] for x in cmp_ if x["tipo"] in ("F", "ANT") and not x.get("anulada")}),
            "amplitud": len([f for f in c["familias"] if f != "-"]) + len([m for m in c["marcas"] if m != "-"]),
            "abierta": round(sum(float(e.get("total") or 0) for e in d["sf_cotizaciones"] if e["estadoReal"] in ABIERTA_SUMA), 2)}
    def pct(comp, v, menor_mejor=False):
        if v is None or (not menor_mejor and v <= 0):
            return 0.0
        vals = [x[comp] for x in datos.values() if x[comp] is not None and (menor_mejor or x[comp] > 0)]
        peor = sum(1 for x in vals if (x > v if menor_mejor else x < v)); igual = sum(1 for x in vals if x == v)
        return (peor + 0.5 * igual) / len(vals)
    cuentas = {}
    for k, x in sorted(datos.items()):
        comp = {}
        for c, w in PESOS_VALOR.items():
            comp[c] = {"dato": x[c], "puntos": round(w * pct(c, x[c], c == "recencia"), 1), "max": w}
        cuentas[k] = {"valor": int(round(sum(v["puntos"] for v in comp.values()))), "componentes": comp}
    for k, r in sorted(restr.items()):
        cuentas[k] = {"valor": None, "motivo": r}
    return {"version": VERSION, "hoy": hoy, "pesos": PESOS_VALOR, "ventanaDias": VENTANA_VALOR,
            "elegibles": len(datos), "cuentas": cuentas,
            "nota": "Valor de la cuenta por datos (no es chance de cierre). Cada componente: percentil dentro de las cuentas sin restricción × peso. compras24 en USD netos de NC, sin dif. de cambio, ARS al tc del comprobante; recencia en días desde la última compra; frecuencia = facturas en 24 meses sin las anuladas por NC; amplitud = familias + marcas compradas (histórico); abierta = USD con IVA de cotizaciones vigentes o vencidas sin estado (v2.4)."}


def correr(src, hoy, out, publicado=None):
    SANEADOS[0] = 0
    S = cargar(src)
    fechas_f = [l.get("fecha") for d in S["fact"].values() for l in d.get("lineas", []) if l.get("fecha")]
    S_CORTES["fact"] = max(fechas_f) if fechas_f else hoy
    S_CORTES["r15"] = S["r15_meta"].get("hasta") or hoy
    huella_in = sha({"f": S["fichas"], "c": S["cots"], "fa": S["fact"], "m": S["muestras"], "fi": S["finn"],
                     "r": S["r15"], "o": S["operaciones"], "v": S["ventasControl"], "e": S["ventasEntregas"]})
    salida, meta = auditar(S, hoy)
    huella_out = sha(salida)
    sello = {"version": VERSION, "hoy": hoy, "huellaEntrada": huella_in, "huellaSalida": huella_out,
             "cortes": {"oportunidades": "vivo", "facturacion": S_CORTES["fact"], "r15": S_CORTES["r15"]},
             "camposSensiblesEliminados": SANEADOS[0], "supuestos": SUPUESTOS}
    for d in salida.values():
        d["sf_sello"] = {"version": VERSION, "huellaDoc": sha(d)}   # sha antes de agregar el sello
    os.makedirs(os.path.join(out, "fichas"), exist_ok=True)
    for k, d in salida.items():
        json.dump(d, open(os.path.join(out, "fichas", k + ".json"), "w", encoding="utf-8"), ensure_ascii=False, sort_keys=True)
    cnt = collections.Counter(h["regla"] for d in salida.values() for h in d["sf_hallazgos"])
    sev = collections.Counter(h["sev"] for d in salida.values() for h in d["sf_hallazgos"])
    resumen = {"sello": sello, "control": meta["control"], "cuentas": len(salida),
               "conFicha": sum(1 for d in salida.values() if not d["sf_sinFicha"]),
               "sinFicha": sum(1 for d in salida.values() if d["sf_sinFicha"]),
               "hallazgosPorRegla": dict(sorted(cnt.items())), "hallazgosPorSeveridad": dict(sev),
               "globales": meta["globales"], "internas": meta["internas"],
               "sinVinculo": {k: len(v) for k, v in meta["sinVinculo"].items()},
               "sinVinculoMonto": meta["sinVinculoMonto"]}
    json.dump(resumen, open(os.path.join(out, "resumen.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
    json.dump(meta["sinVinculo"], open(os.path.join(out, "sin_vinculo.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
    val = valor_cuentas(salida, hoy)
    json.dump(val, open(os.path.join(out, "valor.json"), "w", encoding="utf-8"), ensure_ascii=False, sort_keys=True)
    resumen["valor"] = {"elegibles": val["elegibles"], "conValor": sum(1 for v in val["cuentas"].values() if v["valor"] is not None), "huella": sha(val)}
    json.dump(resumen, open(os.path.join(out, "resumen.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
    if publicado:
        resumen["plan"] = plan_escritura(salida, publicado, out)
        json.dump(resumen, open(os.path.join(out, "resumen.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
    return resumen

def plan_escritura(salida, publicado, out, lote=50):
    """Compara con lo publicado en stockfish_fichas (exportado a disco): solo se escribe lo que cambió."""
    pub = load_dir(publicado)
    escribir = sorted(k for k, d in salida.items() if (pub.get(k) or {}).get("sf_sello", {}).get("huellaDoc") != d["sf_sello"]["huellaDoc"])
    borrar = sorted(set(pub) - set(salida))
    lotes = [escribir[i:i + lote] for i in range(0, len(escribir), lote)]
    plan = {"escribir": len(escribir), "iguales": len(salida) - len(escribir), "borrar": borrar, "lotes": lotes}
    json.dump(plan, open(os.path.join(out, "plan.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return {"escribir": len(escribir), "iguales": plan["iguales"], "borrar": len(borrar), "lotes": len(lotes)}

# ---------------------------------------------------------------- tests
def _mini(tmp):
    import shutil
    if os.path.exists(tmp): shutil.rmtree(tmp)
    for d in ("oportunidades", "cotizaciones", "facturacion", "muestras", "finnegans", "reportes", "config"):
        os.makedirs(os.path.join(tmp, d))
    W = lambda p, o: json.dump(o, open(os.path.join(tmp, p), "w"))
    W("oportunidades/a.json", {"empresa": "Alfa", "cuit": "30-71449817-3", "etapa": "contactado", "telefono": "1", "proximaFecha": "2026-11-01", "proximaAccion": "x", "noProspectar": "si"})
    W("oportunidades/a2.json", {"empresa": "Alfa vieja", "cuit": "30714498173", "etapa": "prospecto", "archivada": True, "unificadaEn": "a"})
    W("oportunidades/b.json", {"empresa": "Beta", "etapa": "ganado", "monto": 100})
    W("cotizaciones/c1.json", {"numero": "NM1", "oportunidadId": "a", "estado": "aceptada", "fecha": "2026-10-01", "fechaGanada": "2026-10-02", "total": 1105, "cuit": "30-71449817-3"})
    W("cotizaciones/c2.json", {"numero": "NM2", "oportunidadId": "a2", "estado": "enviada", "fecha": "2026-10-01", "vence": "2026-10-10", "total": 50})
    W("cotizaciones/c3.json", {"numero": "NM3", "cliente": "HORIZON TRADING S.A.", "estado": "enviada", "total": 1})
    W("facturacion/30714498173.json", {"cliente": "Alfa SA", "cuit": "30714498173", "lineas": [{"fecha": "2026-10-03", "tipo": "F", "comprobante": "A-00005-00000001", "producto": "Cable drop", "cantidad": 1, "marca": "FiberHome"}]})
    W("facturacion/20000000001.json", {"cliente": "Gamma", "cuit": "20000000001", "lineas": [{"fecha": "2026-09-01", "tipo": "F", "comprobante": "A-00005-00000002", "producto": "ONU", "cantidad": 2, "marca": "FiberHome"}]})
    W("finnegans/ALFA.json", {"cliente": "ALFA S.A.", "pedidos": [{"numero": "P1", "fecha": "2026-10-01", "estado": "Activa", "moneda": "Dólares", "items": []}]})
    W("finnegans/ZETA.json", {"cliente": "ZETA", "pedidos": [{"numero": "P2", "fecha": "2026-10-01", "estado": "Activa", "moneda": "Dólares", "items": []}]})
    dic = {"tipocomp": ["Factura de Venta Electrónica", "Nota de Crédito de Ventas Electrónica", "Nota de Débito de Ventas por Dif. Cambio"],
           "moneda": ["USD"], "cliente": ["Alfa SA", "Gamma", "Nadie", "Delta SA", "Omega", "Pi"], "usuario": ["u"]}
    f = ["fecha", "tipocomp", "moneda", "cliente", "cuit", "cuitPorNombre", "comprobante", "bruto", "otros", "total", "tc", "detalle", "fechaAlta", "usuario", "_fila"]
    d = [["2026-10-03", 0, 0, 0, "30714498173", 1, "A-00005-00000001", 1000, 105, 1105, 1, None, "", 0, 1],
         ["2026-09-01", 0, 0, 1, "20000000001", 1, "A-00005-00000002", 200, 21, 221, 1, None, "", 0, 2],
         ["2026-10-20", 1, 0, 1, "20000000001", 1, "A-00005-00000003", -50, -5, -55, 1, None, "", 0, 3],
         ["2026-10-21", 2, 0, 0, "30714498173", 1, "A-00005-00000004", 9, 0, 9, 1, None, "", 0, 4],
         ["2026-10-22", 0, 0, 2, None, 0, "A-00005-00000005", 7, 0, 7, 1, None, "", 0, 5],
         ["2026-10-11", 0, 0, 3, "20000000002", 1, "A-00005-00000010", 1000, 210, 1210, 1, None, "", 0, 6],
         ["2026-10-15", 0, 0, 3, "20000000002", 1, "A-00005-00000011", 200, 42, 242, 1, None, "", 0, 7],
         ["2026-10-15", 1, 0, 3, "20000000002", 1, "A-00005-00000012", -200, -42, -242, 1, None, "", 0, 8],
         ["2026-09-02", 0, 0, 3, "20000000002", 1, "A-00005-00000100", 4, 1, 5, 1, None, "", 0, 9],
         ["2026-10-01", 0, 0, 4, "20000000003", 1, "A-00005-00000020", 100, 21, 121, 1, None, "", 0, 10],
         ["2026-10-02", 1, 0, 4, "20000000003", 1, "A-00005-00000021", -100, -21, -121, 1, None, "", 0, 11],
         ["2026-10-03", 0, 0, 4, "20000000003", 1, "A-00005-00000021", 100, 21, 121, 1, None, "", 0, 12],
         ["2026-10-15", 0, 0, 5, "20000000004", 1, "A-00005-00000030", 300, 63, 363, 1, None, "", 0, 13],
         ["2026-10-20", 1, 0, 5, "20000000004", 1, "A-00005-00000031", -300, -63, -363, 1, None, "", 0, 14],
         ["2026-10-20", 0, 0, 5, "20000000004", 1, "A-00005-00000032", 300, 63, 363, 1, None, "", 0, 15]]
    W("reportes/r15.json", {"formato": {"f": f}, "dic": dic, "d": d, "partes": 1, "hasta": "2026-11-05"})
    W("config/ventasControl.json", {"ptes": [{"ficha": "a", "comp": "A-00005-00000001", "fecha": "2026-10-03", "items": [{"prod": "drop", "pte": 1, "q": 1}]},
                                              {"ficha": "d", "comp": "A-00005-00000010", "fecha": "2026-10-11", "items": [{"prod": "fibra", "pte": 8, "q": 16}]}]})
    W("config/ventasEntregas.json", {"A 00005-00000010": "2026-11-04"})
    W("oportunidades/d.json", {"empresa": "Delta", "cuit": "20000000002", "etapa": "ganado", "proximaFecha": "09/11/2026", "datosBancarios": {"cbu": "1234"}})
    W("oportunidades/p.json", {"empresa": "Pi", "cuit": "20000000004", "etapa": "ganado"})
    W("cotizaciones/p1.json", {"numero": "NP1", "oportunidadId": "p", "estado": "aceptada", "fecha": "2026-10-14", "fechaGanada": "2026-10-14", "total": 363})
    W("oportunidades/e.json", {"empresa": "Epsilon", "cuit": "307144981", "etapa": "prospecto"})
    W("cotizaciones/d1.json", {"numero": "ND1", "oportunidadId": "d", "estado": "aceptada", "fecha": "2026-10-10", "fechaGanada": "2026-10-10", "total": 1210})
    W("cotizaciones/d2.json", {"numero": "ND2", "oportunidadId": "d", "estado": "aceptada", "fecha": "2026-10-12", "fechaGanada": "2026-10-12", "total": 1210})
    W("cotizaciones/d3.json", {"numero": "ND3", "oportunidadId": "d", "estado": "aceptada", "fecha": "2026-11-07", "fechaGanada": "2026-11-07", "total": 999})
    W("cotizaciones/d4.json", {"numero": "XPF 100", "oportunidadId": "d", "estado": "aceptada", "fecha": "2026-09-01", "fechaGanada": "2026-09-01", "total": 77777})
    W("facturacion/20000000002.json", {"cliente": "Delta SA", "cuit": "20000000002", "lineas": [{"fecha": "2026-10-11", "tipo": "F", "comprobante": "A-00005-00000010", "producto": "Fibra", "cantidad": 16, "marca": "ZTT"}]})
    W("config/operaciones.json", {"remitos": [{"cliente": "Alfa SA", "fecha": "2026-10-04", "nro": "R1"}], "pedidos": {}})
    W("muestras/m1.json", {"oportunidadId": "a2", "estado": "enviada", "seguimiento": "2026-10-01"})
    return tmp

def test():
    tmp = "_sf_test"
    ok = []
    def T(nombre, cond):
        cond = bool(cond); ok.append(cond); print(("PASA " if cond else "FALLA") + " · " + nombre)
    T("CUIT válido Horizon", cuit_valido("30-71493161-6"))
    T("CUIT inválido", not cuit_valido("30-71493161-5"))
    T("comp_norm", comp_norm("FC 00005-00001713") == "?-00005-00001713" and comp_match("A 00005-00001713", "A-00005-00001713"))
    _mini(tmp)
    r1 = correr(tmp, "2026-11-09", tmp + "/o1"); r2 = correr(tmp, "2026-11-09", tmp + "/o2")
    T("determinismo (dos corridas, misma huella)", r1["sello"]["huellaSalida"] == r2["sello"]["huellaSalida"])
    T("control de cierre PASA", r1["control"]["resultado"] == "PASA")
    a = json.load(open(tmp + "/o1/fichas/a.json"))
    T("unificada se suma a la canónica", a["sf_fichas"] == ["a", "a2"])
    T("no filtra restringidas (noProspectar sigue y se informa)", a["sf_restricciones"].get("noProspectar") == "si")
    T("aceptada facturada por monto/fecha", any(c["estadoReal"] == "aceptada_facturada" for c in a["sf_cotizaciones"]))
    T("cotización de ficha archivada pasa a la canónica y se ve vencida", any(c["estadoReal"] == "vencida_sin_estado" for c in a["sf_cotizaciones"]))
    reglas = {h["regla"] for h in a["sf_hallazgos"]}
    T("R04 etapa contactado con facturas", "R04_ETAPA_VS_VENTAS" in reglas)
    T("R07 entrega abierta", "R07_ENTREGA_ABIERTA" in reglas)
    T("R09 promesa vencida", "R09_PROMESA_VENCIDA" in reglas)
    T("R09 muestra vencida", "R09_MUESTRA_VENCIDA" in reglas)
    T("R11 FH sin marcar", "R11_FH_SIN_MARCAR" in reglas)
    T("dif. de cambio no es venta", a["sf_compras"]["usdBrutoNeto"] == 1000 and a["sf_compras"]["nDifCambio"] == 1)
    T("remito por nombre", len(a["sf_remitos"]) == 1)
    g = json.load(open(tmp + "/o1/fichas/sf-c20000000001.json"))
    T("cliente sin ficha incluido", g["sf_sinFicha"] and "R06_COMPRO_SIN_FICHA" in {h["regla"] for h in g["sf_hallazgos"]})
    T("NC sin refacturar", "R08_NC_SIN_REFACTURAR" in {h["regla"] for h in g["sf_hallazgos"]})
    T("NC resta", g["sf_compras"]["usdBrutoNeto"] == 150)
    b = json.load(open(tmp + "/o1/fichas/b.json"))
    T("R04 ganado sin ventas", "R04_ETAPA_VS_VENTAS" in {h["regla"] for h in b["sf_hallazgos"]})
    T("interna no entra a cuentas", r1["internas"] == ["c3"])
    T("sin vínculo contado", r1["sinVinculo"]["r15"] == 1 and r1["sinVinculo"]["pedidos"] == 1)
    d = json.load(open(tmp + "/o1/fichas/d.json"))
    est = {c["numero"]: c["estadoReal"] for c in d["sf_cotizaciones"]}
    reg = [(h["regla"], h["txt"]) for h in d["sf_hallazgos"]]
    T("1 a 1: una factura no se asigna a dos cotizaciones", est["ND1"] == "aceptada_facturada" and est["ND2"] == "aceptada_sin_factura")
    T("aceptada posterior al corte del libro no es faltante", est["ND3"] == "aceptada_dentro_corte" and not any(r == "R01_ACEPTADA_SIN_FACTURA" and "ND3" in t for r, t in reg))
    T("regex anclada: 'XPF 100' no matchea la factura 100", est["XPF 100"] == "aceptada_sin_factura")
    T("NC el mismo día (0 días) anula la factura: sin R02", not any(r == "R02_FACTURA_SIN_COTIZACION" and "A-00005-00000011" in t for r, t in reg))
    T("NC sin refacturar se informa (R08)", any(r == "R08_NC_SIN_REFACTURAR" for r, t in reg))
    T("entrega parcial aunque figure entregada (R07)", any(r == "R07_ENTREGA_PARCIAL" for r, t in reg))
    T("fecha inválida informada y sin falso vencimiento", any(r == "R13_FECHA_INVALIDA" for r, t in reg) and not any(r == "R09_PROMESA_VENCIDA" for r, t in reg))
    T("datos bancarios no entran a la salida", "datosBancarios" not in d and r1["sello"]["camposSensiblesEliminados"] >= 1)
    e = json.load(open(tmp + "/o1/fichas/e.json"))
    T("CUIT de 9 dígitos no une cuentas y se informa", e["sf_fichas"] == ["e"] and any(h["regla"] == "R10_CUIT_FORMATO" for h in e["sf_hallazgos"]))
    T("control ARS y USD cierran en el set de prueba", all(c["ok"] for c in r1["control"]["checks"]))
    T("el control falla si una fila se pierde (r15)", cierre({"r15_in": 5, "r15_out": 4}, 0, 0, {}, [])["resultado"] == "FALLA")
    T("el control falla si una cuenta con datos se descarta", cierre({}, 0, 0, {}, [], 0, 0, ["x"])["resultado"] == "FALLA")
    om = json.load(open(tmp + "/o1/fichas/sf-c20000000003.json"))
    T("NC y refactura con el mismo número (series distintas): no es R08", not any(h["regla"].startswith("R08") for h in om["sf_hallazgos"]))
    pi = json.load(open(tmp + "/o1/fichas/p.json"))
    T("refactura del mismo día que la NC: la cotización apunta a la factura viva", [c["facturaR15"] for c in pi["sf_cotizaciones"]] == [["A-00005-00000032"]])
    T("refactura del mismo día que la NC: sin R08 ni R02", not any(h["regla"][:3] in ("R08", "R02") for h in pi["sf_hallazgos"]))
    V = json.load(open(tmp + "/o1/valor.json"))["cuentas"]
    T("valor: cuenta con restricción no lleva número", V["a"]["valor"] is None and V["a"]["motivo"])
    T("valor: entre 0 y 100 y suma de componentes", all(v["valor"] is None or (0 <= v["valor"] <= 100 and abs(v["valor"] - sum(c["puntos"] for c in v["componentes"].values())) <= 0.5) for v in V.values()))
    T("valor: sin compras ni cotización vigente vale 0", V["e"]["valor"] == 0)
    T("valor: más compras nunca baja el puntaje de compras", V["p"]["componentes"]["compras24"]["puntos"] >= V["sf-c20000000003"]["componentes"]["compras24"]["puntos"])
    T("v2.4 frecuencia no cuenta facturas anuladas por NC", any(c["anulada"] for c in pi["sf_comprobantes"]) and V["p"]["componentes"]["frecuencia"]["dato"] == len({c["comp"] for c in pi["sf_comprobantes"] if c["tipo"] in ("F", "ANT") and not c["anulada"] and c["fecha"] >= "2024-11-09"}))
    _todas = {k: json.load(open(tmp + "/o1/fichas/" + k + ".json")) for k in V if V[k]["valor"] is not None}
    T("v2.4 abierta = vigentes + vencidas sin estado", all(abs(V[k]["componentes"]["abierta"]["dato"] - round(sum(float(e.get("total") or 0) for e in f["sf_cotizaciones"] if e["estadoReal"] in ABIERTA_SUMA), 2)) < 0.01 for k, f in _todas.items()))
    T("ficha estable: no guarda días desde hoy", "diasDesdeUltima" not in d["sf_compras"] and set(d["sf_sello"]) == {"version", "huellaDoc"})
    r3 = correr(tmp, "2026-11-10", tmp + "/o3")
    a3 = json.load(open(tmp + "/o3/fichas/sf-c20000000001.json")); a1 = json.load(open(tmp + "/o1/fichas/sf-c20000000001.json"))
    T("un día más no cambia una ficha sin novedades", a3 == a1)
    T("plan incremental: contra sí misma no hay nada para escribir", correr(tmp, "2026-11-09", tmp + "/o4", tmp + "/o1/fichas")["plan"]["escribir"] == 0)
    T("dias()==0 es ventana válida", en_ventana("2026-10-15", "2026-10-15", 0, 10) and not en_ventana("2026-10-15", "no-fecha", 0, 10))
    import shutil; shutil.rmtree(tmp)
    res = "PASA" if all(ok) else "FALLA"
    print(f"RESULTADO: {res} ({sum(ok)}/{len(ok)})")
    return res == "PASA"

if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] == "test":
        sys.exit(0 if test() else 1)
    if a[0] == "correr":
        kv = dict(zip(a[1::2], a[2::2]))
        r = correr(kv["--src"], kv["--hoy"], kv["--out"], kv.get("--publicado"))
        print(json.dumps(r, ensure_ascii=False, indent=1))

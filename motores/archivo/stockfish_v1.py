#!/usr/bin/env python3
"""
STOCKFISH · motor comercial de Horizon CRM · v1.0 (08/11/2026)

Lógica fija: la misma entrada da SIEMPRE la misma salida (sin azar, sin IA en la decisión).
Claude lee la salida y la explica; este script decide. Solo biblioteca estándar.

Comandos:
  python3 -I stockfish.py dia       --fact DIR --crm DIR --cot DIR [--hoy AAAA-MM-DD] [--registro salida.json]
  python3 -I stockfish.py backtest  --fact DIR [--hasta AAAA-MM-DD]
  python3 -I stockfish.py test

Entradas (exportadas a disco con ArtifactData out_dir):
  --fact  colección facturacion (compras por cliente)   --crm  colección oportunidades (fichas)
  --cot   colección cotizaciones

Módulos:
  RECOMPRA     quién va a comprar en los próximos 30 días. Reglas que compiten entre sí por Elo
               en el pasado (backtest); la campeona está fija en PARAM["campeon"].
  COTIZACION   valor esperado = total con IVA x probabilidad. Las probabilidades son SUPUESTOS
               hasta tener resultados registrados (ver SUPUESTOS).
  Salida "5 cosas del día": REPOSICION, COTIZACION, RESPONDER, REACTIVACION + 1 LIBRE
  (máximo uno por carril; el libre es el siguiente de COTIZACION, o de REPOSICION si no hay).
"""
import argparse, collections as C, datetime as dt, glob, hashlib, json, os, re, statistics as S, sys, tempfile

VERSION = "1.0"
PARAM = {
    "campeon": "F_decay",          # elegida por mayor aciertos/mes en ENTRENAMIENTO y confirmada en PRUEBA (las 4 reglas están casi empatadas); cambiar solo con "hacelo"
    "horizonte_dias": 30,          # ventana de "compra próxima"
    "top_k_backtest": 20,
    "elo_k": 16,
    "min_dias_desde_compra": 15,   # no se recomienda reponer a quien compró hace menos
    "vida_media_dias": 180,        # F_decay: una compra vale la mitad cada 180 días
    "reactivar_min_compras": 3,
    "reactivar_factor_ciclo": 1.5,
    "reactivar_min_dias": 60,
    "por_vencer_dias": 3,
    "por_vencer_boost": 1.5,
    "cot_edad_max": 120,           # SUPUESTO
    "cot_edad_piso": 0.3,          # SUPUESTO
    "familias_excluidas": ("HFC",),  # cable modems / HFC no cuentan como compra de fibra (caso Algitech)
}
# SUPUESTOS (no son datos): sacados de 32 cotizaciones resueltas (24 ganadas / 8 perdidas),
# probablemente sesgadas hacia lo ganado. Recalibrar con los resultados que registre el motor.
SUPUESTOS = {"p_hasta_2k": 0.65, "p_2k_8k": 0.60, "p_mas_8k": 0.40}
EXCEPCIONES_NICOLAS = ("fullsat", "telviso")


# ---------- utilidades ----------
def norm(s):
    import unicodedata
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)


def dig(s):
    return re.sub(r"\D", "", str(s or ""))


def fecha(v):
    try:
        return dt.date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def cargar(carpeta):
    out = []
    for ruta in sorted(glob.glob(os.path.join(carpeta, "*.json"))):
        d = json.load(open(ruta, encoding="utf-8"))
        d = d.get("data", d)
        d["_id"] = os.path.splitext(os.path.basename(ruta))[0]
        out.append(d)
    return out


def compras_por_cliente(fact):
    """cliente_id -> (nombre, [fechas ordenadas]). Un evento por día con factura tipo F (sin NC/ND/AJ)."""
    res = {}
    for d in fact:
        ev = sorted({fecha(l["fecha"]) for l in d.get("lineas", []) if l.get("tipo") == "F" and fecha(l.get("fecha"))
                     and l.get("familia") not in PARAM["familias_excluidas"]})
        if ev:
            res[d["_id"]] = (d.get("cliente", d["_id"]), ev)
    return res


# ---------- reglas de recompra (compiten por Elo) ----------
def _pasado(f, T):
    return [x for x in f if x <= T]


def r_A_recencia(f, T):
    p = _pasado(f, T)
    return -(T - p[-1]).days if p else None


def r_C_frecuencia(f, T):
    p = _pasado(f, T)
    if not p:
        return None
    return len([x for x in p if (T - x).days <= 365]) - (T - p[-1]).days / 10000


def r_F_decay(f, T):
    p = _pasado(f, T)
    if not p:
        return None
    return sum(0.5 ** ((T - x).days / PARAM["vida_media_dias"]) for x in p)


def r_G_mixta(f, T):
    base = r_F_decay(f, T)
    if base is None:
        return None
    p = _pasado(f, T)
    g = [(b - a).days for a, b in zip(p, p[1:]) if (b - a).days > 0]
    if len(g) >= 2:
        r = (T - p[-1]).days / S.median(g)
        if 0.75 <= r <= 1.6:
            base += 0.5
    return base


REGLAS = {"A_recencia": r_A_recencia, "C_frecuencia": r_C_frecuencia, "F_decay": r_F_decay, "G_mixta": r_G_mixta}


def candidatos(compras, T, ids=None):
    out = []
    for c, (_, f) in compras.items():
        if ids is not None and c not in ids:
            continue
        p = _pasado(f, T)
        if p and (T - p[-1]).days >= PARAM["min_dias_desde_compra"]:
            out.append(c)
    return out


def cortes(desde=dt.date(2023, 1, 1), hasta=dt.date(2026, 10, 3)):
    T, out = desde, []
    while T <= hasta:
        out.append(T)
        T = (T.replace(day=1) + dt.timedelta(days=32)).replace(day=1)
    return out


def torneo(compras, lista_cortes):
    K, H, k = PARAM["top_k_backtest"], PARAM["horizonte_dias"], PARAM["elo_k"]
    elo = {r: 1500.0 for r in REGLAS}
    hits = C.Counter()
    azar = 0.0
    n = 0
    for T in lista_cortes:
        comp = {c for c, (_, f) in compras.items() if any(T < x <= T + dt.timedelta(days=H) for x in f)}
        el = candidatos(compras, T)
        if not comp or len(el) < K:
            continue
        n += 1
        azar += len(comp & set(el)) / len(el) * K
        h = {}
        for r, fn in REGLAS.items():
            sc = [(fn(compras[c][1], T), c) for c in el]
            sc = [x for x in sc if x[0] is not None]
            top = {c for _, c in sorted(sc, key=lambda x: (-x[0], x[1]))[:K]}
            h[r] = len(top & comp)
            hits[r] += h[r]
        nom = sorted(REGLAS)
        for i in range(len(nom)):
            for j in range(i + 1, len(nom)):
                a, b = nom[i], nom[j]
                res = 1.0 if h[a] > h[b] else 0.0 if h[a] < h[b] else 0.5
                ea = 1 / (1 + 10 ** ((elo[b] - elo[a]) / 400))
                elo[a] += k * (res - ea)
                elo[b] += k * ((1 - res) - (1 - ea))
    return n, azar, hits, elo


def cmd_backtest(a):
    compras = compras_por_cliente(cargar(a.fact))
    hasta = fecha(a.hasta) or dt.date(2026, 10, 3)
    todos = cortes(hasta=hasta)
    corte_div = dt.date(2025, 4, 1)
    entren = [t for t in todos if t < corte_div]
    prueba = [t for t in todos if t >= corte_div]
    print(f"STOCKFISH {VERSION} · backtest · clientes con compras: {len(compras)}")
    for nombre, L in (("ENTRENAMIENTO (hasta 03/2025)", entren), ("PRUEBA (desde 04/2025, no vista)", prueba)):
        n, azar, hits, elo = torneo(compras, L)
        print(f"\n{nombre}: {n} cortes mensuales · azar {azar / max(n, 1):.2f} aciertos/mes de {PARAM['top_k_backtest']}")
        for r in sorted(REGLAS, key=lambda r: (-elo[r], r)):
            print(f"  {r:13s} aciertos/mes {hits[r] / max(n, 1):5.2f} · Elo {elo[r]:.0f}" + ("  <- campeona vigente" if r == PARAM["campeon"] else ""))
    print("\nElo = fuerza relativa entre estas reglas en esta muestra; no es un Elo absoluto.")


# ---------- elegibilidad de fichas (misma regla que inicio_loki.py) ----------
def ficha_excluida(f, hoy):
    nombre = norm(f.get("empresa"))
    es_n = any(e in nombre for e in EXCEPCIONES_NICOLAS)
    if f.get("archivada"):
        return "archivada"
    if not es_n and f.get("noProspectar"):
        return "noProspectar"
    if not es_n and f.get("otroVendedor"):
        return "otroVendedor"
    if f.get("cuentaCompartida"):
        return "cuentaCompartida"
    rec = f.get("hz_recompra") or {}
    if rec.get("estado") == "espera" and (fecha(rec.get("hasta")) or hoy) > hoy:
        return "recompra en espera"
    return None


def mapa_fichas(fichas):
    por = C.defaultdict(set)
    for f in fichas:
        for k in (f.get("cuit"), f.get("facturacionId")):
            if dig(k):
                por[dig(k)].add(f["_id"])
    return por


def p_cotizacion(total):
    if total <= 2000:
        return SUPUESTOS["p_hasta_2k"]
    if total <= 8000:
        return SUPUESTOS["p_2k_8k"]
    return SUPUESTOS["p_mas_8k"]


def usd(x):
    return "USD " + f"{x:,.0f}".replace(",", ".")


def calcular_dia(fact, fichas, cots, hoy):
    por_cuit = mapa_fichas(fichas)
    fid = {f["_id"]: f for f in fichas}
    compras = compras_por_cliente(fact)
    excl = C.Counter()

    def fichas_de(cid):
        d = next((x for x in fact if x["_id"] == cid), {})
        ids = set()
        for k in (cid, d.get("cuit")):
            ids |= por_cuit.get(dig(k), set())
        return sorted(ids)

    # candidatos de recompra: con ficha elegible
    elegibles = {}
    sin_ficha = 0
    for cid in compras:
        ids = fichas_de(cid)
        if not ids:
            sin_ficha += 1
            continue
        motivos = [ficha_excluida(fid[i], hoy) for i in ids]
        if any(motivos):
            excl[next(m for m in motivos if m)] += 1
            continue
        elegibles[cid] = ids[0]
    cand = candidatos(compras, hoy, ids=set(elegibles))
    fn = REGLAS[PARAM["campeon"]]
    pun = sorted(((fn(compras[c][1], hoy), c) for c in cand), key=lambda x: (-x[0], x[1]))

    def detalle(c):
        nombre, f = compras[c]
        p = _pasado(f, hoy)
        g = [(b - a).days for a, b in zip(p, p[1:]) if (b - a).days > 0]
        n12 = len([x for x in p if (hoy - x).days <= 365])
        ciclo = f"ciclo típico {int(S.median(g))} d" if len(g) >= 2 else "ciclo sin datos"
        return nombre, (hoy - p[-1]).days, n12, ciclo, len(p)

    items = {}
    usados = set()
    # 1 REPOSICION
    if pun:
        s, c = pun[0]
        nm, dias, n12, ciclo, tot = detalle(c)
        items["REPOSICION"] = dict(id=c, ficha=elegibles[c], nombre=nm, score=round(s, 3),
                                   texto=f"{nm}: compró hace {dias} d, {n12} compras en 12 meses, {ciclo} (puntaje {s:.2f}, regla {PARAM['campeon']})")
        usados.add(c)
    # 2 COTIZACION
    cot_rank = []
    for q in cots:
        if q.get("estado") != "enviada" or "horizontrading" in norm(q.get("cliente")):
            continue
        f = fid.get(q.get("oportunidadId"))
        if f is not None and (ficha_excluida(f, hoy) or f.get("etapa") in ("ganado", "perdido")):
            continue
        fq = fecha(q.get("fecha"))
        edad = (hoy - fq).days if fq else 0
        p = p_cotizacion(q.get("total") or 0) * max(PARAM["cot_edad_piso"], 1 - edad / PARAM["cot_edad_max"])
        ev = (q.get("total") or 0) * p
        v = fecha(q.get("vence"))
        dv = (v - hoy).days if v else None
        boost = PARAM["por_vencer_boost"] if dv is not None and 0 <= dv <= PARAM["por_vencer_dias"] else 1.0
        cot_rank.append((ev * boost, q, edad, p, dv))
    cot_rank.sort(key=lambda x: (-x[0], str(x[1].get("numero") or x[1]["_id"])))

    def txt_cot(x):
        sc, q, edad, p, dv = x
        vence = "" if dv is None else (f", venció hace {-dv} d" if dv < 0 else f", vence en {dv} d")
        return dict(id=q["_id"], ficha=q.get("oportunidadId"), nombre=q.get("cliente"), score=round(sc, 1),
                    texto=f"{q.get('cliente')} {q.get('numero') or ''}: {usd(q.get('total') or 0)}, {edad} d de enviada{vence}; "
                          f"valor esperado {usd(sc)} con probabilidad {p:.0%} (SUPUESTO)")
    if cot_rank:
        items["COTIZACION"] = txt_cot(cot_rank[0])
    # 3 RESPONDER
    resp = []
    for f in fichas:
        if ficha_excluida(f, hoy):
            continue
        pf = fecha(f.get("proximaFecha"))
        if "respond" in (f.get("proximaAccion") or "").lower() and pf and pf <= hoy:
            resp.append((-(f.get("monto") or 0), pf, f["_id"], f))
    resp.sort(key=lambda x: (x[0], x[1], x[2]))
    if resp:
        _, pf, _, f = resp[0]
        items["RESPONDER"] = dict(id=f["_id"], ficha=f["_id"], nombre=f.get("empresa"), score=f.get("monto") or 0,
                                  texto=f"{f.get('empresa')}: espera tu respuesta desde {pf:%d/%m} ({(hoy - pf).days} d)" + (f", {usd(f['monto'])}" if f.get("monto") else ""))
    # 4 REACTIVACION
    reac = []
    for c in elegibles:
        if c in usados:
            continue
        nm, dias, n12, ciclo, tot = detalle(c)
        p = _pasado(compras[c][1], hoy)
        g = [(b - a).days for a, b in zip(p, p[1:]) if (b - a).days > 0]
        if tot >= PARAM["reactivar_min_compras"] and len(g) >= 2 and dias >= PARAM["reactivar_min_dias"] \
                and dias > PARAM["reactivar_factor_ciclo"] * S.median(g):
            reac.append((-tot, dias, c))
    reac.sort()
    if reac:
        _, dias, c = reac[0]
        nm, _, _, ciclo, tot = detalle(c)
        items["REACTIVACION"] = dict(id=c, ficha=elegibles[c], nombre=nm, score=tot,
                                     texto=f"{nm}: {tot} compras en total, hace {dias} d que no compra ({ciclo}); se pasó de su ritmo")
    # 5 LIBRE
    if len(cot_rank) > 1:
        items["LIBRE"] = txt_cot(cot_rank[1])
    elif len(pun) > 1:
        s, c = pun[1]
        nm, dias, n12, ciclo, tot = detalle(c)
        items["LIBRE"] = dict(id=c, ficha=elegibles[c], nombre=nm, score=round(s, 3),
                              texto=f"{nm}: compró hace {dias} d, {n12} compras en 12 meses, {ciclo} (puntaje {s:.2f})")
    control = dict(clientes_con_compras=len(compras), sin_ficha=sin_ficha, excluidos=dict(sorted(excl.items())),
                   elegibles=len(elegibles), candidatos_recompra=len(cand), cotizaciones_abiertas_rankeadas=len(cot_rank))
    return items, control


def cmd_dia(a):
    hoy = fecha(a.hoy) or dt.date.today()
    items, ctl = calcular_dia(cargar(a.fact), cargar(a.crm), cargar(a.cot), hoy)
    out = [f"# STOCKFISH {VERSION} · 5 cosas del día · {hoy:%d/%m/%Y}", ""]
    for i, carril in enumerate(["REPOSICION", "COTIZACION", "RESPONDER", "REACTIVACION", "LIBRE"], 1):
        it = items.get(carril)
        out.append(f"{i}. {carril}: " + (it["texto"] if it else "sin candidato hoy"))
    out += ["", "Control: " + json.dumps(ctl, ensure_ascii=False),
            "Chequeo: " + ("cierra" if ctl["elegibles"] + ctl["sin_ficha"] + sum(ctl["excluidos"].values()) == ctl["clientes_con_compras"] else "NO cierra"),
            "Supuestos (no son datos): probabilidades de cotización " + json.dumps(SUPUESTOS) + "; el motor decide el orden, Claude lo explica.",
            f"Huella de la salida: {hashlib.sha256(json.dumps(items, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]}"]
    print("\n".join(out))
    if a.registro:
        reg = dict(fecha=str(hoy), version=VERSION, regla=PARAM["campeon"], recomendaciones=items, control=ctl)
        json.dump(reg, open(a.registro, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


# ---------- pruebas fijas ----------
def cmd_test(_):
    hoy = dt.date(2026, 11, 8)

    def d(n):
        return (hoy - dt.timedelta(days=n)).isoformat()

    def cli(cid, nombre, dias):
        return dict(_id=cid, cliente=nombre, cuit=cid, lineas=[dict(tipo="F", fecha=d(x), cantidad=1) for x in dias])
    hfc = cli("7", "Solo cable modems", [800, 790, 780, 770])
    for l in hfc["lineas"]:
        l["familia"] = "HFC"
    fact = [hfc, cli("1", "Frecuente", [20, 60, 100, 140, 200, 260]),
            cli("2", "Reciente", [3]),
            cli("3", "Vieja", [700, 600, 500, 400]),
            cli("4", "Otro vendedor", [10, 50, 90, 130]),
            cli("5", "Sin ficha", [30, 70, 110]),
            cli("6", "Espera", [25, 65, 105, 145])]
    fichas = [dict(_id="f1", empresa="Frecuente", cuit="1", etapa="contactado"),
              dict(_id="f2", empresa="Reciente", cuit="2", etapa="contactado"),
              dict(_id="f3", empresa="Vieja", cuit="3", etapa="contactado"),
              dict(_id="f4", empresa="Otro vendedor", cuit="4", otroVendedor=True),
              dict(_id="f6", empresa="Espera", cuit="6", hz_recompra=dict(estado="espera", hasta="2026-12-01")),
              dict(_id="f7", empresa="Esperando", proximaAccion="Responder consulta", proximaFecha=d(5), monto=3000),
              dict(_id="f8", empresa="Cot", etapa="cotizado")]
    cots = [dict(_id="c1", cliente="Cot", numero="NM90", estado="enviada", total=5000, fecha=d(10), vence=d(-2), oportunidadId="f8"),
            dict(_id="c2", cliente="Grande", numero="NM91", estado="enviada", total=100000, fecha=d(5), vence=d(-30), oportunidadId="x"),
            dict(_id="c3", cliente="Horizon Trading S.A.", numero="NM92", estado="enviada", total=999999, fecha=d(5), oportunidadId="x"),
            dict(_id="c4", cliente="Cerrada", numero="NM93", estado="aceptada", total=88888, fecha=d(5), oportunidadId="x")]
    it1, ctl = calcular_dia(fact, fichas, cots, hoy)
    it2, _ = calcular_dia(fact, fichas, cots, hoy)
    t = []
    t.append(("determinista", json.dumps(it1, sort_keys=True) == json.dumps(it2, sort_keys=True)))
    t.append(("reposicion = Frecuente", it1["REPOSICION"]["nombre"] == "Frecuente"))
    t.append(("no recomienda recién comprado", all(i.get("nombre") != "Reciente" for i in it1.values())))
    t.append(("excluye otroVendedor y recompra en espera", ctl["excluidos"] == {"otroVendedor": 1, "recompra en espera": 1}))
    t.append(("sin ficha contado", ctl["sin_ficha"] == 1))
    t.append(("control cierra", ctl["elegibles"] + ctl["sin_ficha"] + sum(ctl["excluidos"].values()) == ctl["clientes_con_compras"]))
    t.append(("cotizacion = mayor valor esperado, sin internas ni cerradas", it1["COTIZACION"]["id"] == "c2"))
    t.append(("libre = segunda cotizacion", it1["LIBRE"]["id"] == "c1"))
    t.append(("responder", it1["RESPONDER"]["nombre"] == "Esperando"))
    t.append(("reactivacion = Vieja", it1["REACTIVACION"]["nombre"] == "Vieja"))
    t.append(("HFC no cuenta como compra de fibra", ctl["clientes_con_compras"] == 6))
    for nombre, ok in t:
        print(("PASA  " if ok else "FALLA ") + nombre)
    print("RESULTADO:", "PASA" if all(ok for _, ok in t) else "FALLA")
    return 0 if all(ok for _, ok in t) else 1


def main():
    ap = argparse.ArgumentParser(description="Stockfish · motor comercial Horizon")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("dia")
    d.add_argument("--fact", required=True)
    d.add_argument("--crm", required=True)
    d.add_argument("--cot", required=True)
    d.add_argument("--hoy")
    d.add_argument("--registro")
    b = sub.add_parser("backtest")
    b.add_argument("--fact", required=True)
    b.add_argument("--hasta")
    sub.add_parser("test")
    a = ap.parse_args()
    return {"dia": cmd_dia, "backtest": cmd_backtest, "test": cmd_test}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())

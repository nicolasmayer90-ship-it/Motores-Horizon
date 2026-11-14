#!/usr/bin/env python3
"""Banco de manos v1.0 · Horizon CRM
Reglas fijas: misma entrada -> misma salida. Claude clasifica (manos.json, senales.json); el script cuenta y decide.

Uso:
  python3 -I banco_manos.py test
  python3 -I banco_manos.py pre --chats <dir con chat .txt> --manos manos.json --hoy AAAA-MM-DD --out pre.json
      (incremental: solo mensajes posteriores a la última mano guardada de cada cuenta; propone jugada y nivel; marca ambiguas)
  python3 -I banco_manos.py correr --manos manos.json --senales senales.json --sf <dir stockfish_fichas> --valor valor.json --hoy AAAA-MM-DD --out salida.json

Qué hace:
 1) Control de entrada (PASA/FALLA): jugadas y niveles válidos, fechas, cada mano con cuenta declarada, 25 chats.
 2) Conteo por jugada: respondió (>=1), avanzó (>=2), compromiso (>=3), pedido (4), y "subió" (superó el mejor nivel previo de la cuenta).
    Probabilidad = media Beta(1+éxitos, 1+fracasos) con intervalo del 90 %. Celdas con menos de 5 manos = baja confianza.
 3) Rango inicial por cuenta desde Stockfish (SUPUESTOS de Claude, marcados): fondos, encaje técnico, urgencia; corregido con señales del chat.
 4) Jugada recomendada por cuenta: reglas fijas en orden (R1..R8). Valor esperado = P(avanzar | jugada) x monto en juego.
"""
import sys, json, os, datetime, math, hashlib

VERSION = "1.1"
JUGADAS = ["EP", "AG", "AD", "OF", "RT", "PF", "PP", "SG", "CC", "CP", "ES", "MU", "PV", "RF", "ER"]
MIN_CELDA = 5


def d(s):
    return datetime.date.fromisoformat(s)


def beta_cdf(x, a, b):
    # a, b enteros: P(Beta(a,b) <= x) = P(Bin(a+b-1, x) >= a)
    n = a + b - 1
    return sum(math.comb(n, k) * x ** k * (1 - x) ** (n - k) for k in range(a, n + 1))


def beta_q(p, a, b):
    lo, hi = 0.0, 1.0
    for _ in range(60):
        m = (lo + hi) / 2
        if beta_cdf(m, a, b) < p:
            lo = m
        else:
            hi = m
    return (lo + hi) / 2


def prob(exitos, total):
    a, b = 1 + exitos, 1 + total - exitos
    return {"n": total, "exitos": exitos, "p": round(a / (a + b), 3),
            "ic90": [round(beta_q(0.05, a, b), 3), round(beta_q(0.95, a, b), 3)],
            "confianza": "baja" if total < MIN_CELDA else ("media" if total < 15 else "alta")}


# ------------------------------------------------------------------ 1. control de entrada
def control(M):
    fallas = []
    ids = {c["cuenta"] for c in M["cuentas"]}
    chats = {c["chat"] for c in M["cuentas"]}
    if len(chats) != 25:
        fallas.append(f"se esperaban 25 chats, hay {len(chats)}")
    for i, m in enumerate(M["manos"]):
        if len(m) != 5:
            fallas.append(f"mano {i}: 5 campos"); continue
        c, f, j, n, _ = m
        if c not in ids: fallas.append(f"mano {i}: cuenta {c} no declarada")
        if j not in JUGADAS: fallas.append(f"mano {i}: jugada {j} inválida")
        if n not in (0, 1, 2, 3, 4): fallas.append(f"mano {i}: nivel {n} inválido")
        try: d(f)
        except Exception: fallas.append(f"mano {i}: fecha {f} inválida")
    sin = ids - {m[0] for m in M["manos"]}
    if sin: fallas.append(f"cuentas sin manos: {sorted(sin)}")
    return fallas


# ------------------------------------------------------------------ 2. conteo
def conteo(M):
    tipo = {}
    for c in M["cuentas"]:
        tipo.setdefault(c["cuenta"], c["tipo"])
    manos = sorted(M["manos"], key=lambda m: (m[0], m[1]))
    mejor = {}
    filas = []
    for c, f, j, n, nota in manos:
        sube = n > mejor.get(c, 0)
        mejor[c] = max(mejor.get(c, 0), n)
        filas.append({"c": c, "f": f, "j": j, "n": n, "sube": sube, "tipo": tipo[c]})
    por = {}
    for j in JUGADAS:
        fj = [x for x in filas if x["j"] == j]
        if not fj: continue
        t = len(fj)
        por[j] = {"respondio": prob(sum(x["n"] >= 1 for x in fj), t),
                  "avanzo": prob(sum(x["n"] >= 2 for x in fj), t),
                  "compromiso": prob(sum(x["n"] >= 3 for x in fj), t),
                  "pedido": prob(sum(x["n"] == 4 for x in fj), t),
                  "subio": prob(sum(x["sube"] for x in fj), t)}
    cruce = {}
    for tp in sorted({x["tipo"] for x in filas}):
        for j in JUGADAS:
            fj = [x for x in filas if x["j"] == j and x["tipo"] == tp]
            if len(fj) >= MIN_CELDA:
                cruce[f"{tp}|{j}"] = prob(sum(x["n"] >= 2 for x in fj), len(fj))
    # seguimiento repetido: SG después de un SG sin respuesta
    rep = []
    for i in range(1, len(filas)):
        a, b = filas[i - 1], filas[i]
        if a["c"] == b["c"] and a["j"] == "SG" and a["n"] == 0:
            rep.append(b)
    tras = {}
    for j in sorted({x["j"] for x in rep}):
        fj = [x for x in rep if x["j"] == j]
        tras[j] = prob(sum(x["n"] >= 1 for x in fj), len(fj))
    return filas, por, cruce, tras


# ------------------------------------------------------------------ 3. rango inicial (SUPUESTOS) + señales
def rango(sf, senal, hoy):
    comp = sf.get("sf_compras") or {}
    nf = comp.get("nFacturas", 0) or 0
    ult = comp.get("ultima")
    dias = (hoy - d(ult)).days if ult else None
    if nf >= 3 and dias is not None and dias <= 183: fondos = 0.8
    elif nf >= 1: fondos = 0.65
    else: fondos = 0.4
    if senal.get("fondos_bajos"): fondos = round(fondos * 0.5, 2)
    olt = (sf.get("marcaOlt") or "").lower()
    if sf.get("oltFH") == "si" or "fiberhome" in olt: encaje = 0.9
    elif olt: encaje = 0.6
    else: encaje = 0.5
    if dias is not None and dias <= 60: urg = 0.7
    elif dias is not None and dias <= 183: urg = 0.5
    else: urg = 0.3
    if senal.get("ciclo"): urg = min(0.9, urg + 0.2)
    decisor = 0.7 if senal.get("decisor") else 0.3
    compet = 0.7 if senal.get("competencia") else 0.3
    return {"fondos": fondos, "encaje": encaje, "urgencia": urg, "decisorAfuera": decisor, "competencia": compet,
            "base": {"nFacturas": nf, "ultimaCompra": ult, "diasDesdeUltima": dias, "marcaOlt": sf.get("marcaOlt") or "",
                     "compraFiberHome": comp.get("compraFiberHome", False)},
            "supuesto": "pesos y cortes elegidos por Claude; se calibran con el registro de resultados"}


# ------------------------------------------------------------------ 4. jugada recomendada (reglas fijas en orden)
def recomendar(c, filas_c, sen, rg, sfdoc, por, hoy):
    ult = filas_c[-1]
    dias_ult = (hoy - d(ult["f"])).days
    sg0 = 0
    for x in reversed(filas_c):
        if x["j"] in ("SG", "AG") and x["n"] == 0: sg0 += 1
        else: break
    vig = [q for q in (sfdoc.get("sf_cotizaciones") or []) if q.get("estadoReal") in ("vigente", "vencida_sin_estado")]
    monto = round(sum(float(q.get("total") or 0) for q in vig), 2)
    if not monto and sfdoc.get("etapa") not in ("perdido", "ganado"):
        monto = float(sfdoc.get("monto") or 0)
    pa = (sfdoc.get("proximaAccion") or "").lower()
    if sfdoc.get("etapa") == "perdido" and not vig and not sfdoc.get("_extraGanado"):
        r, j, por_que = "R0", "EP", "perdida en la ficha: no tocar salvo requerimiento nuevo"
    elif "no insistir" in pa or "esperar (nicol" in pa:
        r, j, por_que = "R0", "EP", "Nicolás dictó esperar: manda sobre el motor"
    elif sen.get("pideHuawei"):
        r, j, por_que = "R0H", "MU", "pide Huawei y Horizon no es canal oficial (Masnet/Solution Box venden más barato): no perseguir precio; cotizar una vez y ofrecer FiberHome con muestra solo si la OLT lo permite y el modelo no pide CATV"
    elif sen.get("muestra_sin_fecha"):
        r, j, por_que = "R1", "PP", "muestra entregada sin fecha de resultado: acordar fecha y criterio de prueba"
    elif any(q.get("estadoReal") == "vencida_sin_estado" for q in vig):
        r, j, por_que = "R2", "CP", "cotización vencida sin estado: cierre de prueba con fecha (renovar o perder)"
    elif sen.get("objecion") and sen.get("competencia"):
        r, j, por_que = "R3", "PF", "citan precio/proveedor de otro: preguntar volumen y plazo, después concesión atada"
    elif sen.get("decisor") and ult["n"] <= 2:
        r, j, por_que = "R4", "ES", "decide otro: pedir qué necesita ver y cuándo, o acceso"
    elif sen.get("ciclo"):
        r, j, por_que = "R5", "AD", f"ciclo de compra ({sen['ciclo']}): tocar antes con su última compra"
    elif sg0 >= 2:
        r, j, por_que = "R6", "AD", f"{sg0} toques seguidos sin respuesta: cambiar a apertura con dato o soltar con fecha"
    elif rg["fondos"] < 0.4:
        r, j, por_que = "R7", "PP", "fondos bajos: soltar con fecha de retoma acordada"
    else:
        r, j, por_que = "R8", "AD", "abrir con un dato del cliente (regla 1)"
    p = por.get(j, {}).get("avanzo", {"p": 0.0, "confianza": "baja"})
    return {"regla": r, "jugada": j, "porQue": por_que, "pAvanzar": p["p"], "confianza": p["confianza"],
            "montoEnJuego": monto, "valorEsperado": round(p["p"] * monto, 2),
            "ultimoToque": ult["f"], "diasDesdeUltimo": dias_ult, "nivelMax": max(x["n"] for x in filas_c),
            "toquesSinRespuesta": sg0}


def correr(manos, senales, sfdir, valor, hoy_s, out):
    M = json.load(open(manos)); S = json.load(open(senales)); V = json.load(open(valor))["cuentas"]
    hoy = d(hoy_s)
    fallas = control(M)
    if fallas:
        print("CONTROL: FALLA"); [print(" ·", f) for f in fallas]; return 1
    filas, por, cruce, tras = conteo(M)
    cuentas = {}
    for c in sorted({x["c"] for x in filas}):
        p = os.path.join(sfdir, c + ".json")
        sfdoc = json.load(open(p)) if os.path.exists(p) else {}
        for cc in M["cuentas"]:
            for ex in (cc.get("extra") or []) if cc["cuenta"] == c else []:
                pe = os.path.join(sfdir, ex + ".json")
                if os.path.exists(pe) and json.load(open(pe)).get("etapa") == "ganado":
                    sfdoc["_extraGanado"] = ex
        sen = S.get(c, {})
        rg = rango(sfdoc, sen, hoy)
        fc = [x for x in filas if x["c"] == c]
        cuentas[c] = {"empresa": sfdoc.get("empresa", c), "stockfish": bool(sfdoc),
                      "valorStockfish": (V.get(c) or {}).get("valor"),
                      "restricciones": sfdoc.get("sf_restricciones") or {},
                      "manos": len(fc), "rango": rg, "senales": sen,
                      "recomendada": recomendar(c, fc, sen, rg, sfdoc, por, hoy)}
    res = {"version": VERSION, "hoy": hoy_s, "manos": len(filas), "cuentas": len(cuentas),
           "porJugada": por, "tipoXjugada": cruce, "despuesDeSeguimientoSinRespuesta": tras, "porCuenta": cuentas,
           "huellaEntrada": hashlib.sha256((open(manos).read() + open(senales).read()).encode()).hexdigest()[:12]}
    json.dump(res, open(out, "w"), ensure_ascii=False, indent=1, sort_keys=True)
    print(f"CONTROL: PASA · {len(filas)} manos · {len(cuentas)} cuentas · sin Stockfish: {[c for c,v in cuentas.items() if not v['stockfish']]}")
    return 0


# ------------------------------------------------------------------ 5. preclasificador (incremental, sin IA)
import re
RX_MSG = re.compile(r"\[(\d+)/(\d+)/(\d+), [^\]]+\] ([^:]+): (.*)")
RX = [("PP", r"\bcuit\b|direcci[oó]n|transporte|mando a facturar|env[ií]o la fc|adjunto (fc|guia|guía)|despach"),
      ("CP", r"le damos curso|avanzamos|para avanzar|mandar a facturar|estamos ok"),
      ("SG", r"novedad|te consulto por (el tema|la cotiz|las pruebas|la onu|tema)|pudi(eron|ste) (evaluar|ver|hablar|hacer)|c[oó]mo (te fue|salieron|les fue)|si te lleg"),
      ("AG", r"alg[uú]n requerimiento|est[aá]s? con alg[uú]n|necesitando"),
      ("PF", r"cu[aá]ntos|qu[eé] cantidad|cantidad aprox|para cu[aá]ndo|en transferencia o|forma de pago|contra qu[eé]"),
      ("MU", r"muestra|homolog"),
      ("CC", r"descuento|\bdto\b|podemos dejarlo|bajar(lo)?|\d+ ?%"),
      ("OF", r"cat[aá]logo|lista de precios|curso|capacitaci|remanente|liquidar|\[doc\]")]
RX_N = [(4, r"factura|comprobante|transferencia de|avancemos|echeq|e-cheq|pago"),
        (3, r"cotiz|presupuesto|pasame precio|p[aá]same (los )?costos|mand[aá](me|nos)? (una )?muestra|necesito|necesitamos"),
        (2, r"\d|due[ñn]o|gerencia|jefe|reuni[oó]n|vacaciones|presupuesto 20|semana|lunes|martes|mi[eé]rcoles|jueves|viernes|mes")]


def leer_chat(fn):
    out = []
    for l in open(fn, encoding="utf-8", errors="replace"):
        m = RX_MSG.match(l.strip().replace("\u200e", ""))
        if m:
            f = f"20{int(m.group(3)) % 100:02d}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
            out.append((f, "N" if m.group(4) == "Tú" else "C", m.group(5)))
    return out


def pre_mano(bloque_n, bloque_c):
    tn = " ".join(t for _, _, t in bloque_n).lower()
    tc = " ".join(t for _, _, t in bloque_c).lower()
    j = next((k for k, rx in RX if re.search(rx, tn)), "SG")
    if not bloque_c: n = 0
    else: n = next((k for k, rx in RX_N if re.search(rx, tc)), 1)
    amb = (not tn.strip()) or ("<mensaje de voz" in tc) or ("<imagen" in tc) or ("[audio]" in tc) or (j == "SG" and not re.search(RX[2][1], tn))
    return j, n, amb


def pre(chats, manos, hoy_s, out):
    M = json.load(open(manos)); hoy = d(hoy_s)
    ult = {}
    for c, f, *_ in M["manos"]:
        ult[c] = max(ult.get(c, "0000"), f)
    res = {"version": VERSION, "hoy": hoy_s, "cuentas": {}, "sinCuenta": []}
    mapa = {c["chat"]: c["cuenta"] for c in M["cuentas"]}
    for fn in sorted(os.listdir(chats)):
        if not fn.endswith(".txt"): continue
        base = fn[:-4].split("-", 1)[1] if re.match(r"^[0-9a-f]{8}-", fn) else fn[:-4]
        cta = mapa.get(base)
        msgs = leer_chat(os.path.join(chats, fn))
        if not cta:
            res["sinCuenta"].append(base); continue
        desde = ult.get(cta, "0000")
        nuevos = [m for m in msgs if m[0] > desde]
        manos_p, i = [], 0
        while i < len(nuevos):
            bn = []
            while i < len(nuevos) and nuevos[i][1] == "N": bn.append(nuevos[i]); i += 1
            bc = []
            while i < len(nuevos) and nuevos[i][1] == "C": bc.append(nuevos[i]); i += 1
            if bn:
                j, n, amb = pre_mano(bn, bc)
                manos_p.append({"c": cta, "f": bn[0][0], "j": j, "n": n, "ambigua": amb, "txt": bn[-1][2][:90]})
        ultC = max((m[0] for m in msgs if m[1] == "C"), default=None)
        sin = 0
        for m in reversed(msgs):
            if m[1] == "C": break
            sin += 1
        res["cuentas"][cta] = {"chat": base, "ultimaMano": desde, "nuevas": manos_p,
                               "hablaUltimo": msgs[-1][1] if msgs else None,
                               "diasDesdeUltimoCliente": (hoy - d(ultC)).days if ultC else None,
                               "mensajesTuyosSinRespuesta": sin}
    json.dump(res, open(out, "w"), ensure_ascii=False, indent=1, sort_keys=True)
    n = sum(len(v["nuevas"]) for v in res["cuentas"].values()); a = sum(x["ambigua"] for v in res["cuentas"].values() for x in v["nuevas"])
    print(f"PRE: {len(res['cuentas'])} cuentas · {n} manos nuevas · {a} ambiguas para revisar · sin cuenta: {res['sinCuenta']}")
    return 0


def test():
    ok = True
    def t(c, m):
        nonlocal ok
        print(("PASA " if c else "FALLA") + " · " + m); ok &= bool(c)
    t(abs(beta_cdf(0.5, 1, 1) - 0.5) < 1e-9, "Beta(1,1) uniforme")
    t(prob(0, 0)["p"] == 0.5, "sin datos = 0,5")
    q = prob(8, 10); t(q["ic90"][0] < q["p"] < q["ic90"][1], "intervalo contiene la media")
    M = {"cuentas": [{"chat": f"x{i}", "cuenta": "a", "tipo": "medio"} for i in range(25)],
         "manos": [["a", "2026-11-01", "SG", 0, ""], ["a", "2026-11-02", "SG", 1, ""]]}
    t(control(M) == [], "control acepta entrada válida")
    M2 = {"cuentas": M["cuentas"], "manos": [["a", "2026-11-01", "XX", 7, ""]]}
    t(len(control(M2)) == 2, "control detecta jugada y nivel inválidos")
    f, por, _, tras = conteo(M)
    t(f[1]["sube"] and not f[0]["sube"], "sube solo si supera el mejor nivel previo")
    t("SG" in tras and tras["SG"]["n"] == 1, "cuenta SG tras SG sin respuesta")
    a = conteo(M); b = conteo(json.loads(json.dumps(M)))
    t(json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True), "determinismo")
    t(pre_mano([("2026-11-01", "N", "te consulto si tuviste alguna novedad")], [])[:2] == ("SG", 0), "pre: seguimiento sin respuesta = SG 0")
    t(pre_mano([("2026-11-01", "N", "¿cuántos precisás?")], [("2026-11-01", "C", "500")])[:2] == ("PF", 2), "pre: pregunta de freno con cantidad = PF 2")
    t(pre_mano([("2026-11-01", "N", "te paso cuit y direccion")], [("2026-11-01", "C", "va el comprobante de transferencia de pago")])[:2] == ("PP", 4), "pre: próximo paso con pago = PP 4")
    sen = {"pideHuawei": True}
    r = recomendar("x", [{"f": "2026-11-01", "n": 1, "j": "RT"}], sen, {"fondos": 0.8}, {}, {}, d("2026-11-10"))
    t(r["regla"] == "R0H", "regla Huawei no oficial antes que el resto")
    print("RESULTADO:", "PASA" if ok else "FALLA"); return 0 if ok else 1


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] == "test":
        sys.exit(test())
    kv = dict(zip(a[1::2], a[2::2]))
    if a[0] == "pre":
        sys.exit(pre(kv["--chats"], kv["--manos"], kv["--hoy"], kv["--out"]))
    sys.exit(correr(kv["--manos"], kv["--senales"], kv["--sf"], kv["--valor"], kv["--hoy"], kv["--out"]))

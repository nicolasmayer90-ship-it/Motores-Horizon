#!/usr/bin/env python3
"""Monte Carlo del banco de manos v1.0 · Horizon CRM
Reglas fijas: misma entrada -> misma salida (semilla = huella de la entrada). Solo biblioteca estándar.

Uso:
  python3 -I banco_montecarlo.py test
  python3 -I banco_montecarlo.py correr --banco banco_manos.json --hoy AAAA-MM-DD --out mc.json [--sims 20000]

Qué hace (lee SOLO datacenter/banco_manos: manos + recomendadas):
 1) Por jugada: la respuesta del cliente (nivel 0-4) es incierta dos veces: no sabemos la tasa real (Dirichlet con
    1 de piso por nivel + lo observado) y, con la tasa, la respuesta es azar. Cada simulación sortea las dos.
 2) Por cuenta (las 24 con jugada recomendada): un toque con la jugada recomendada contra dos referencias:
    SG (seguimiento sin dato) y la mezcla con la que Nicolás viene jugando (frecuencia real de sus jugadas).
    Da P(responde), P(avanza >= 2), P(pedido = 4) con intervalo del 90 %, y P(la recomendada le gana a SG).
 3) Cartera: USD que entran por pedido en un toque (solo cuentas con monto en juego, dato de la cotización),
    P10 / P50 / P90, y cuántas cuentas avanzan. R0 (esperar / perdida) no se juega: cuenta 0 y se informa aparte.
 4) Registro: una predicción por cuenta (jugada, p avanzar, p pedido) con 'resultado' vacío para cargar el nivel
    real cuando se juegue la mano. Con eso se calibra (paso siguiente).
Límites: un toque, no secuencias. No usa el rango (fondos/encaje/urgencia), que son supuestos de Claude.
Las tasas no distinguen tipo de cuenta ni objeción (228 manos no alcanzan para eso).
"""
import sys, json, random, hashlib, math

VERSION = "1.0"
NIVELES = 5
NO_SE_JUEGA = {"EP"}


def huella(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]


def conteos(manos):
    c = {}
    for _, _, j, n, _ in manos:
        c.setdefault(j, [0] * NIVELES)[n] += 1
    return c


def mezcla(manos):
    tot = {}
    for _, _, j, _, _ in manos:
        tot[j] = tot.get(j, 0) + 1
    n = sum(tot.values())
    return sorted((j, k / n) for j, k in tot.items())


def dirichlet(rng, alfa):
    g = [rng.gammavariate(a, 1.0) for a in alfa]
    s = sum(g)
    return [x / s for x in g]


def nivel(rng, p):
    u, acc = rng.random(), 0.0
    for k, pk in enumerate(p):
        acc += pk
        if u < acc:
            return k
    return NIVELES - 1


def pct(xs, q):
    xs = sorted(xs)
    if not xs:
        return 0.0
    i = (len(xs) - 1) * q
    lo, hi = math.floor(i), math.ceil(i)
    return xs[lo] + (xs[hi] - xs[lo]) * (i - lo)


def simular(banco, sims, hoy):
    M = banco["manos"]
    R = banco["recomendadas"]
    cnt = conteos(M["manos"])
    mix = mezcla(M["manos"])
    semilla = huella({"m": M["manos"], "r": R, "sims": sims, "v": VERSION})
    rng = random.Random(semilla)
    jug = sorted(cnt)
    alfa = {j: [1 + x for x in cnt[j]] for j in jug}
    cuentas = sorted(R)
    acc = {c: {"rec": [0, 0, 0], "sg": [0, 0, 0], "mix": [0, 0, 0], "gana": 0, "pav": [], "ppe": []} for c in cuentas}
    usd_rec, usd_mix, usd_sg, av_rec, av_mix = [], [], [], [], []
    for _ in range(sims):
        tasas = {j: dirichlet(rng, alfa[j]) for j in jug}
        tr = ur = um = us = am = 0.0
        for c in cuentas:
            r = R[c]
            j = r["jugada"]
            monto = float(r.get("montoEnJuego") or 0)
            a = acc[c]
            if j in NO_SE_JUEGA or j not in tasas:
                continue
            p = tasas[j]
            a["pav"].append(sum(p[2:])); a["ppe"].append(p[4])
            if sum(p[2:]) > sum(tasas["SG"][2:]):
                a["gana"] += 1
            for clave, pj in (("rec", p), ("sg", tasas["SG"])):
                n = nivel(rng, pj)
                a[clave][0] += n >= 1; a[clave][1] += n >= 2; a[clave][2] += n == 4
                if n == 4:
                    if clave == "rec": ur += monto
                    else: us += monto
                if clave == "rec" and n >= 2: tr += 1
            u, accp, jm = rng.random(), 0.0, mix[-1][0]
            for jj, w in mix:
                accp += w
                if u < accp:
                    jm = jj; break
            n = nivel(rng, tasas[jm])
            a["mix"][0] += n >= 1; a["mix"][1] += n >= 2; a["mix"][2] += n == 4
            if n == 4: um += monto
            if n >= 2: am += 1
        usd_rec.append(ur); usd_mix.append(um); usd_sg.append(us); av_rec.append(tr); av_mix.append(am)

    def fr(x): return round(x / sims, 3)
    por = {}
    registro = []
    esperar = []
    for c in cuentas:
        r, a = R[c], acc[c]
        if r["jugada"] in NO_SE_JUEGA or not a["pav"]:
            esperar.append({"cuenta": c, "empresa": r["empresa"], "regla": r["regla"],
                            "montoEnJuego": r.get("montoEnJuego") or 0, "porQue": r["porQue"]})
            continue
        monto = float(r.get("montoEnJuego") or 0)
        pped = fr(a["rec"][2])
        por[c] = {"empresa": r["empresa"], "regla": r["regla"], "jugada": r["jugada"], "montoEnJuego": monto,
                  "recomendada": {"responde": fr(a["rec"][0]), "avanza": fr(a["rec"][1]), "pedido": pped},
                  "SG": {"responde": fr(a["sg"][0]), "avanza": fr(a["sg"][1]), "pedido": fr(a["sg"][2])},
                  "comoVenis": {"responde": fr(a["mix"][0]), "avanza": fr(a["mix"][1]), "pedido": fr(a["mix"][2])},
                  "ic90Avanza": [round(pct(a["pav"], .05), 3), round(pct(a["pav"], .95), 3)],
                  "ic90Pedido": [round(pct(a["ppe"], .05), 3), round(pct(a["ppe"], .95), 3)],
                  "pGanaASG": fr(a["gana"]),
                  "usdEsperadoPorPedido": round(pped * monto, 2),
                  "valorEsperadoBancoV11": r.get("valorEsperado"),
                  "nManosJugada": sum(cnt[r["jugada"]])}
        registro.append({"cuenta": c, "empresa": r["empresa"], "fechaPrediccion": hoy, "jugada": r["jugada"],
                         "regla": r["regla"], "pAvanza": por[c]["recomendada"]["avanza"], "pPedido": pped,
                         "jugadaReal": None, "fechaJugada": None, "nivelReal": None, "nota": None})

    def resumen(xs):
        return {"media": round(sum(xs) / len(xs), 2), "p10": round(pct(xs, .1), 2), "p50": round(pct(xs, .5), 2),
                "p90": round(pct(xs, .9), 2), "pAlgoEntra": round(sum(x > 0 for x in xs) / len(xs), 3)}
    cartera = {"usdRecomendada": resumen(usd_rec), "usdComoVenis": resumen(usd_mix), "usdSoloSG": resumen(usd_sg),
               "cuentasQueAvanzanRecomendada": resumen(av_rec), "cuentasQueAvanzanComoVenis": resumen(av_mix),
               "montoEnJuegoQueSeJuega": round(sum(float(R[c].get("montoEnJuego") or 0) for c in por), 2),
               "montoEnEspera": round(sum(float(x["montoEnJuego"]) for x in esperar), 2)}
    tasas_med = {j: {"n": sum(cnt[j]), "avanza": round(sum(alfa[j][2:]) / sum(alfa[j]), 3),
                     "pedido": round(alfa[j][4] / sum(alfa[j]), 3)} for j in jug}
    return {"version": VERSION, "hoy": hoy, "sims": sims, "semilla": semilla,
            "huellaEntrada": huella({"m": M["manos"], "r": R}), "mezclaComoVenis": dict(mix),
            "tasasMedias": tasas_med, "cartera": cartera, "porCuenta": por, "noSeJuegan": esperar,
            "registro": registro}


def control(banco, res):
    f = []
    R = banco["recomendadas"]
    if len(res["porCuenta"]) + len(res["noSeJuegan"]) != len(R):
        f.append("cuentas: jugadas + no jugadas != recomendadas")
    if len(res["registro"]) != len(res["porCuenta"]):
        f.append("registro no tiene una predicción por cuenta jugada")
    for c, v in res["porCuenta"].items():
        for k in ("recomendada", "SG", "comoVenis"):
            x = v[k]
            if not (x["responde"] >= x["avanza"] >= x["pedido"] >= 0):
                f.append(f"{c}: probabilidades no ordenadas en {k}")
        if v["montoEnJuego"] != float(R[c].get("montoEnJuego") or 0):
            f.append(f"{c}: monto cambió")
    tot = round(sum(float(R[c].get("montoEnJuego") or 0) for c in R), 2)
    if abs(res["cartera"]["montoEnJuegoQueSeJuega"] + res["cartera"]["montoEnEspera"] - tot) > 0.01:
        f.append("monto total no cierra")
    return f


def correr(banco_f, hoy, out, sims):
    B = json.load(open(banco_f))
    B = B.get("data", B)
    res = simular(B, sims, hoy)
    f = control(B, res)
    res2 = simular(json.loads(json.dumps(B)), sims, hoy)
    if json.dumps(res, sort_keys=True) != json.dumps(res2, sort_keys=True):
        f.append("no determinista")
    res["control"] = "PASA" if not f else "FALLA"
    res["fallas"] = f
    json.dump(res, open(out, "w"), ensure_ascii=False, indent=1, sort_keys=True)
    print(f"CONTROL: {res['control']} · {len(res['porCuenta'])} cuentas jugadas · {len(res['noSeJuegan'])} en espera · {sims} sims")
    for x in f:
        print(" ·", x)
    return 0 if not f else 1


def test():
    ok = True
    def t(c, m):
        nonlocal ok
        print(("PASA " if c else "FALLA") + " · " + m); ok &= bool(c)
    rng = random.Random(1)
    ps = [dirichlet(rng, [1, 1, 1, 1, 1]) for _ in range(4000)]
    t(abs(sum(p[0] for p in ps) / 4000 - 0.2) < 0.02, "Dirichlet(1..1) media 0,2 por nivel")
    t(all(abs(sum(p) - 1) < 1e-9 for p in ps[:50]), "Dirichlet suma 1")
    t(abs(pct([1, 2, 3, 4, 5], .5) - 3) < 1e-9, "percentil 50")
    manos = [["a", "2026-11-01", "SG", 0, ""]] * 6 + [["a", "2026-11-02", "CP", 4, ""]] * 6 + [["b", "2026-11-03", "SG", 1, ""]] * 2
    rec = {"a": {"empresa": "A", "regla": "R2", "jugada": "CP", "montoEnJuego": 1000, "porQue": "", "valorEsperado": 0},
           "b": {"empresa": "B", "regla": "R0", "jugada": "EP", "montoEnJuego": 500, "porQue": "", "valorEsperado": 0}}
    B = {"manos": {"manos": manos}, "recomendadas": rec}
    r = simular(B, 3000, "2026-11-10")
    t(r["porCuenta"]["a"]["pGanaASG"] > 0.95, "jugada con 6/6 pedidos le gana a SG con 0/8 avances")
    t(r["porCuenta"]["a"]["recomendada"]["pedido"] > r["porCuenta"]["a"]["SG"]["pedido"], "pedido recomendada > SG")
    t(len(r["noSeJuegan"]) == 1 and r["noSeJuegan"][0]["cuenta"] == "b", "R0/EP no se juega")
    t(control(B, r) == [], "control acepta salida válida")
    t(json.dumps(r, sort_keys=True) == json.dumps(simular(B, 3000, "2026-11-10"), sort_keys=True), "determinismo")
    exp = 7 / 11
    t(abs(r["porCuenta"]["a"]["recomendada"]["pedido"] - exp) < 0.04, "converge a la media Dirichlet (7/11)")
    t(abs(r["cartera"]["usdRecomendada"]["media"] - 1000 * exp) < 40, "USD esperado = P(pedido) x monto")
    print("RESULTADO:", "PASA" if ok else "FALLA"); return 0 if ok else 1


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] == "test":
        sys.exit(test())
    kv = dict(zip(a[1::2], a[2::2]))
    sys.exit(correr(kv["--banco"], kv["--hoy"], kv["--out"], int(kv.get("--sims", 20000))))

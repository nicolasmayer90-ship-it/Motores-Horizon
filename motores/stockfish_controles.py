#!/usr/bin/env python3
"""Controles del Stockfish auditor · Horizon CRM  (v1.3: libro de ventas r15 + r22)

Siete controles independientes del auditor. Cada uno termina en una línea RESULTADO: PASA | FALLA
y devuelve código de salida 0 / 1. Ninguno escribe en el CRM. Fail-closed: ante la duda, FALLA.

Uso:
  python3 -I stockfish_controles.py test
  python3 -I stockfish_controles.py entrada       --src DIR --hoy AAAA-MM-DD
  python3 -I stockfish_controles.py cierre        --src DIR --out DIR [--tope-usd-sin-vinculo 1000]
  python3 -I stockfish_controles.py oro           --out DIR --oro oro.json
  python3 -I stockfish_controles.py cambios       --src DIR --out DIR [--prev DIR] [--umbral 0.25]
  python3 -I stockfish_controles.py determinismo  --src DIR --hoy AAAA-MM-DD --auditor stockfish_auditor.py
  python3 -I stockfish_controles.py restricciones --out DIR --reco recomendaciones.json
  python3 -I stockfish_controles.py escritura     --out DIR --leido DIR
  python3 -I stockfish_controles.py reloj         --src DIR --hoy AAAA-MM-DD --auditor stockfish_auditor.py [--localidad 3]
  python3 -I stockfish_controles.py fuentes       --src DIR [--minimo 0.90]
"""
import sys, os, json, glob, re, hashlib, subprocess, tempfile, shutil, collections, datetime

BANCARIO = re.compile(r"bancari|^cbu$|^cvu$|iban|^alias_?cbu", re.I)
RESTRICCIONES = ("archivada", "noProspectar", "otroVendedor")


# ------------------------------------------------------------------ utilidades (propias, sin importar el auditor)
def _load(p):
    d = json.load(open(p, encoding="utf-8"))
    return d.get("data", d) if isinstance(d, dict) and isinstance(d.get("data"), dict) else d


def _dir(path):
    return {os.path.basename(f)[:-5]: _load(f) for f in sorted(glob.glob(os.path.join(path, "*.json")))}


def _digitos(s):
    return re.sub(r"\D", "", str(s or ""))


def _cuit_ok(c):
    c = _digitos(c)
    if len(c) != 11:
        return False
    w = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    v = 11 - sum(int(c[i]) * w[i] for i in range(10)) % 11
    v = 0 if v == 11 else 9 if v == 10 else v
    return v == int(c[10])


def _fecha(s):
    try:
        return datetime.date.fromisoformat(str(s)[:10])
    except Exception:
        return None


def _tiene_bancarios(o):
    if isinstance(o, dict):
        return any(BANCARIO.search(str(k)) or _tiene_bancarios(v) for k, v in o.items())
    if isinstance(o, list):
        return any(_tiene_bancarios(x) for x in o)
    return False


def _libros(s):
    """Archivos del libro de ventas con su formato: [(ruta, campos, dic)] de r15* y r22* (cada reporte con su diccionario)."""
    rep = os.path.join(s, "reportes")
    out = []
    for base in ("r15", "r22"):
        p0 = os.path.join(rep, base + ".json")
        if not os.path.exists(p0):
            continue
        m = _load(p0)
        for p in sorted(glob.glob(os.path.join(rep, base + "*.json"))):
            out.append((p, m["formato"]["f"], m["dic"]))
    return out


def _r15(src):
    """Decodifica el libro de ventas por su cuenta (implementación independiente de la del auditor).
    v1.2 (plan cerebro, definiciones.fuentes.libroVentas): r15 + r22; en el período de r22 manda r22."""
    rep = os.path.join(src, "reportes")
    def dec(nombre):
        r = _load(os.path.join(rep, nombre + ".json"))
        filas = list(r["d"])
        for i in range(2, int(r.get("partes", 1)) + 1):
            filas += _load(os.path.join(rep, f"{nombre}_{i}.json"))["d"]
        campos, dic = r["formato"]["f"], r["dic"]
        out = []
        for x in filas:
            d = dict(zip(campos, x))
            for k in ("tipocomp", "moneda", "cliente", "usuario"):
                if isinstance(d.get(k), int):
                    d[k] = dic[k][d[k]]
            out.append(d)
        return r, out
    r, out = dec("r15")
    if os.path.exists(os.path.join(rep, "r22.json")):
        m22, o22 = dec("r22")
        desde = m22.get("desde") or min(x["fecha"] for x in o22 if x.get("fecha"))
        out = [x for x in out if (x.get("fecha") or "") < desde] + o22
        r = dict(r, hasta=max(r.get("hasta") or "", m22.get("hasta") or ""), lineas=len(out))
    return r, out


def _signo(tipocomp):
    """+1 suma, -1 resta, 0 no es venta (diferencia de cambio)."""
    t = str(tipocomp)
    if "Dif. Cambio" in t:
        return 0
    return -1 if "Crédito" in t else 1


def _fin(nombre, fallas, detalle=None):
    print(f"[{nombre}] " + ("RESULTADO: PASA" if not fallas else "RESULTADO: FALLA"))
    for f in fallas:
        print("   · " + f)
    if detalle:
        for d in detalle:
            print("   ~ " + d)
    return not fallas


# ------------------------------------------------------------------ 1. entrada (pre-vuelo)
def c_entrada(src, hoy, max_dias_corte=7):
    fallas, avisos = [], []
    for d in ("oportunidades", "cotizaciones", "facturacion", "muestras", "finnegans", "reportes", "config"):
        if not os.path.isdir(os.path.join(src, d)):
            fallas.append(f"falta la carpeta {d}/")
    if fallas:
        return _fin("entrada", fallas)
    fichas = _dir(os.path.join(src, "oportunidades"))
    cots = _dir(os.path.join(src, "cotizaciones"))
    fact = _dir(os.path.join(src, "facturacion"))
    if not fichas: fallas.append("oportunidades vacía")
    if not fact: fallas.append("facturacion vacía")
    try:
        meta, filas = _r15(src)
    except Exception as e:
        return _fin("entrada", fallas + [f"r15 ilegible: {e}"])
    if not filas: fallas.append("r15 sin filas")
    if meta.get("lineas") and int(meta["lineas"]) != len(filas):
        fallas.append(f"r15 declara {meta['lineas']} líneas y trae {len(filas)}")
    obl = ("fecha", "tipocomp", "moneda", "cliente", "comprobante", "bruto", "total")
    malas = [i for i, r in enumerate(filas) if any(r.get(k) in (None, "") for k in obl)]
    if malas: fallas.append(f"{len(malas)} filas de r15 con campos obligatorios vacíos (ej. fila {malas[0]})")
    sin_fecha = [i for i, r in enumerate(filas) if not _fecha(r.get("fecha"))]
    if sin_fecha: fallas.append(f"{len(sin_fecha)} filas de r15 con fecha inválida")
    dup = collections.Counter((r.get("comprobante"), r.get("tipocomp"), r.get("moneda"), r.get("cliente")) for r in filas)
    dups = [k for k, v in dup.items() if v > 1]
    if dups: fallas.append(f"{len(dups)} comprobantes duplicados en r15 (ej. {dups[0][0]})")
    # CUIT
    malos = sorted({_digitos(r.get("cuit")) for r in filas if r.get("cuit") and not _cuit_ok(r.get("cuit"))})
    if malos: avisos.append(f"{len(malos)} CUIT de r15 sin dígito verificador válido (ej. {malos[0]})")
    for k, v in list(fichas.items()):
        for c in [v.get("cuit"), v.get("facturacionId")] + list(v.get("cuitsAdicionales") or []):
            if c and len(_digitos(c)) not in (7, 8, 11):
                fallas.append(f"ficha {k}: CUIT/DNI '{c}' con largo inválido")
    # fechas de fichas y cotizaciones
    for k, v in fichas.items():
        if v.get("proximaFecha") and not _fecha(v["proximaFecha"]):
            avisos.append(f"ficha {k}: proximaFecha '{v['proximaFecha']}' no es ISO")
    for k, v in cots.items():
        for campo in ("fecha", "vence", "revisionFecha"):
            if v.get(campo) and not _fecha(v[campo]):
                avisos.append(f"cotización {k}: {campo} '{v[campo]}' no es ISO")
    # frescura
    h = _fecha(hoy)
    hasta = _fecha(meta.get("hasta"))
    if not h: fallas.append(f"hoy '{hoy}' inválido")
    if hasta and h and (h - hasta).days > max_dias_corte:
        avisos.append(f"r15 llega hasta {hasta} ({(h - hasta).days} días antes de hoy): hay ventas sin cargar")
    if hasta and h and hasta > h: fallas.append(f"r15 llega hasta {hasta}, posterior a hoy {h}")
    fmax = max((l.get("fecha") for d in fact.values() for l in d.get("lineas", []) if l.get("fecha")), default="")
    if fmax and h and _fecha(fmax) and (h - _fecha(fmax)).days > max_dias_corte:
        avisos.append(f"facturacion llega hasta {fmax} ({(h - _fecha(fmax)).days} días antes de hoy)")
    # bancarios en lo exportado
    n_banc = sum(1 for d in (fichas, cots, fact) for v in d.values() if _tiene_bancarios(v))
    if n_banc: fallas.append(f"{n_banc} documentos exportados con datos bancarios: borrarlos del disco antes de correr")
    return _fin("entrada", fallas, [f"aviso: {a}" for a in avisos[:10]] + ([f"aviso: +{len(avisos) - 10} más"] if len(avisos) > 10 else []))


# ------------------------------------------------------------------ 2. cierre independiente
def c_cierre(src, out, tope_usd_sin_vinculo=1000.0):
    fallas = []
    meta, filas = _r15(src)
    docs = _dir(os.path.join(out, "fichas"))
    resumen = _load(os.path.join(out, "resumen.json"))
    # a) por cuenta: USD y ARS recalculados con una segunda implementación
    cuit2cuenta = {}
    for k, d in docs.items():
        for c in d.get("sf_cuits", []):
            cuit2cuenta[c] = k
    esperado = collections.defaultdict(lambda: [0.0, 0.0])      # cuenta -> [usd, ars] por CUIT
    sin_cuit = []
    tot_usd = tot_ars = 0.0
    for r in filas:
        s = _signo(r["tipocomp"])
        monto = s * abs(r["bruto"] or 0)
        if s == 0:
            continue
        if r["moneda"] == "USD": tot_usd += monto
        else: tot_ars += monto
        c = _digitos(r.get("cuit"))
        if c and c in cuit2cuenta:
            esperado[cuit2cuenta[c]][0 if r["moneda"] == "USD" else 1] += monto
        elif c:
            fallas.append(f"CUIT {c} de r15 no pertenece a ninguna cuenta")
        else:
            sin_cuit.append((r, monto))
    por_nombre = collections.defaultdict(list)
    for r, m in sin_cuit:
        por_nombre[r["cliente"]].append((r, m))
    for k, d in docs.items():
        usd, ars = esperado[k]
        extra_usd = extra_ars = 0.0
        for nom in d.get("sf_nombresFuente", []):
            for r, m in por_nombre.get(nom, []):
                if r["moneda"] == "USD": extra_usd += m
                else: extra_ars += m
        c = d["sf_compras"]
        pa_usd = round(sum(c["usdBrutoPorAnio"].values()), 2); pa_ars = round(sum(c["arsBrutoPorAnio"].values()), 2)
        if abs((usd + extra_usd) - pa_usd) > 0.5 or abs((ars + extra_ars) - pa_ars) > 1.0:
            # la diferencia puede ser un vínculo por nombre; sólo falla si no la explican filas sin CUIT con ese nombre
            fallas.append(f"cuenta {k}: USD esperado {usd + extra_usd:.2f} vs auditor {pa_usd:.2f}; ARS esperado {ars + extra_ars:.2f} vs {pa_ars:.2f}")
        if abs(c["usdBrutoNeto"] - pa_usd) > 0.01:
            fallas.append(f"cuenta {k}: usdBrutoNeto {c['usdBrutoNeto']} no coincide con el desglose por año {pa_usd}")
    # b) total: cuentas + sin vínculo = total del libro
    sv = resumen["sinVinculoMonto"]
    suma_usd = sum(round(sum(d["sf_compras"]["usdBrutoPorAnio"].values()), 2) for d in docs.values()) + sv["usd"]
    suma_ars = sum(round(sum(d["sf_compras"]["arsBrutoPorAnio"].values()), 2) for d in docs.values()) + sv["ars"]
    if abs(suma_usd - tot_usd) > 1.0: fallas.append(f"USD total: libro {tot_usd:.2f} vs cuentas+sin vínculo {suma_usd:.2f}")
    if abs(suma_ars - tot_ars) > 10.0: fallas.append(f"ARS total: libro {tot_ars:.2f} vs cuentas+sin vínculo {suma_ars:.2f}")
    # c) sin vínculo: tope de plata sin cliente
    if abs(sv["usd"]) > tope_usd_sin_vinculo:
        fallas.append(f"USD sin vínculo {sv['usd']} supera el tope {tope_usd_sin_vinculo}: hay ventas sin cliente asignado")
    # d) filas en r15 = filas en salida + sin vínculo
    n_sal = sum(len(d["sf_comprobantes"]) for d in docs.values()) + sv["n"]
    if n_sal != len(filas): fallas.append(f"filas r15 {len(filas)} vs salida {n_sal}")
    return _fin("cierre", fallas, [f"libro USD {tot_usd:,.2f} · ARS {tot_ars:,.2f} · sin vínculo USD {sv['usd']} / ARS {sv['ars']} ({sv['n']} comprobantes)"])


# ------------------------------------------------------------------ 3. oro (casos con respuesta conocida)
def _get(d, ruta):
    for p in ruta.split("."):
        d = d.get(p) if isinstance(d, dict) else None
    return d


def c_oro(out, oro_path):
    oro = _load(oro_path)
    fallas, saltados = [], 0
    for caso in oro["casos"]:
        if caso.get("pendiente"):
            saltados += 1
            continue
        f = os.path.join(out, "fichas", caso["cuenta"] + ".json")
        if not os.path.exists(f):
            fallas.append(f"{caso['cuenta']}: no existe en la salida"); continue
        d = _load(f)
        reglas = [h["regla"] for h in d["sf_hallazgos"]]
        txt = " | ".join(h["txt"] for h in d["sf_hallazgos"])
        for r in caso.get("debe_tener", []):
            if r not in reglas: fallas.append(f"{caso['cuenta']}: debía tener {r} y no lo tiene")
        for r in caso.get("no_debe_tener", []):
            if r in reglas: fallas.append(f"{caso['cuenta']}: NO debía tener {r}")
        for t in caso.get("texto_contiene", []):
            if t not in txt: fallas.append(f"{caso['cuenta']}: los hallazgos no mencionan '{t}'")
        for ruta, esperado in (caso.get("igual") or {}).items():
            v = _get(d, ruta)
            if v != esperado: fallas.append(f"{caso['cuenta']}: {ruta} = {v!r}, esperado {esperado!r}")
        for ruta, (lo, hi) in (caso.get("rango") or {}).items():
            v = _get(d, ruta)
            if v is None or not (lo <= v <= hi): fallas.append(f"{caso['cuenta']}: {ruta} = {v!r} fuera de [{lo}, {hi}]")
    return _fin("oro", fallas, [f"{len(oro['casos']) - saltados} casos verificados · {saltados} pendientes de completar con Nicolás"])


# ------------------------------------------------------------------ 4. cambios y fidelidad
def _sin_sf(d):
    return {k: v for k, v in d.items() if not k.startswith("sf_")}


def c_cambios(src, out, prev=None, umbral=0.25):
    fallas, notas = [], []
    docs = _dir(os.path.join(out, "fichas"))
    fichas = _dir(os.path.join(src, "oportunidades"))
    # a) fidelidad: la ficha canónica copiada no cambió ningún campo (sacando sf_ y bancarios)
    def sano(o):
        if isinstance(o, dict): return {k: sano(v) for k, v in o.items() if not BANCARIO.search(str(k))}
        if isinstance(o, list): return [sano(x) for x in o]
        return o
    alterados = []
    cubiertas = {x for d in docs.values() for x in d.get("sf_fichas", [])}
    for k, f in fichas.items():
        if k not in cubiertas:
            fallas.append(f"ficha {k} no está en ninguna cuenta de la salida"); continue
        if k in docs and _sin_sf(docs[k]) != sano(f): alterados.append(k)   # las unificadas viven dentro de su canónica
    if alterados: fallas.append(f"{len(alterados)} fichas canónicas alteradas respecto de oportunidades (ej. {alterados[0]})")
    # b) contra la corrida anterior
    if prev:
        ant = _dir(os.path.join(prev, "fichas"))
        ap = sorted(set(docs) - set(ant)); de = sorted(set(ant) - set(docs))
        if de: fallas.append(f"{len(de)} cuentas desaparecieron (ej. {de[0]})")
        if ap: notas.append(f"{len(ap)} cuentas nuevas (ej. {ap[0]})")
        saltos = []
        for k in set(docs) & set(ant):
            a = sum(ant[k]["sf_compras"]["usdBrutoPorAnio"].values()); n = sum(docs[k]["sf_compras"]["usdBrutoPorAnio"].values())
            if abs(n - a) > 0.01 and abs(n - a) > umbral * max(abs(a), 1):
                saltos.append(f"{k}: USD {a:.0f} → {n:.0f}")
        if saltos: fallas.append(f"{len(saltos)} cuentas con salto de USD mayor al {int(umbral * 100)} % (ej. {saltos[0]}): confirmar que son comprobantes nuevos")
        cr = collections.Counter(h["regla"] for d in docs.values() for h in d["sf_hallazgos"])
        ca = collections.Counter(h["regla"] for d in ant.values() for h in d["sf_hallazgos"])
        for r in sorted(set(cr) | set(ca)):
            a, n = ca.get(r, 0), cr.get(r, 0)
            if a >= 5 and abs(n - a) > umbral * a:
                fallas.append(f"regla {r}: {a} → {n} (cambio mayor al {int(umbral * 100)} %): revisar si cambió la regla o los datos")
            elif a != n:
                notas.append(f"{r}: {a} → {n}")
    return _fin("cambios", fallas, notas[:15])


# ------------------------------------------------------------------ 5. determinismo entre procesos
def c_determinismo(src, hoy, auditor):
    huellas, fallas = {}, []
    tmp = tempfile.mkdtemp(prefix="sf_det_")
    try:
        # variante con las filas de r15 en orden inverso
        inv = os.path.join(tmp, "src_inv")
        shutil.copytree(src, inv)
        for f in glob.glob(os.path.join(inv, "reportes", "r15*.json")):
            d = json.load(open(f, encoding="utf-8"))
            tgt = d["data"] if isinstance(d.get("data"), dict) else d
            tgt["d"] = list(reversed(tgt["d"]))
            json.dump(d, open(f, "w", encoding="utf-8"), ensure_ascii=False)
        casos = [("semilla0", src, "0"), ("semilla1", src, "1"), ("semilla4242", src, "4242"), ("r15_invertido", inv, "7")]
        for nombre, s, seed in casos:
            o = os.path.join(tmp, "o_" + nombre)
            env = dict(os.environ, PYTHONHASHSEED=seed)
            r = subprocess.run([sys.executable, "-I", auditor, "correr", "--src", s, "--hoy", hoy, "--out", o],
                               capture_output=True, text=True, env=env)
            if r.returncode != 0:
                fallas.append(f"{nombre}: el auditor falló: {r.stderr[-200:]}"); continue
            huellas[nombre] = json.load(open(os.path.join(o, "resumen.json")))["sello"]["huellaSalida"]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if len(set(huellas.values())) > 1: fallas.append(f"huellas distintas: {huellas}")
    return _fin("determinismo", fallas, [f"huellas: {huellas}"])


# ------------------------------------------------------------------ 6. restricciones (Sales Engine v3)
def c_restricciones(out, reco_path):
    docs = _dir(os.path.join(out, "fichas"))
    reco = _load(reco_path)
    reco = reco.get("recomendaciones", reco) if isinstance(reco, dict) else reco
    fallas = []
    for r in reco:
        k = r["cuenta"] if isinstance(r, dict) else r
        d = docs.get(k)
        if d is None:
            fallas.append(f"{k}: recomendada pero no existe en stockfish_fichas"); continue
        res = [x for x in RESTRICCIONES if d.get(x)] + [x for x in RESTRICCIONES if (d.get("sf_restricciones") or {}).get(x)]
        if res: fallas.append(f"{k} ({d.get('empresa')}): recomendada pero tiene {sorted(set(res))}")
        if d.get("unificadaEn"): fallas.append(f"{k}: ficha unificada en {d['unificadaEn']}")
    return _fin("restricciones", fallas, [f"{len(reco)} recomendaciones revisadas"])


# ------------------------------------------------------------------ 7. escritura (lectura de vuelta)
def _huella(d):
    d = {k: v for k, v in d.items() if k not in ("version", "_version", "updatedAt")}
    return hashlib.sha256(json.dumps(d, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]


def c_escritura(out, leido):
    gen = _dir(os.path.join(out, "fichas"))
    esc = _dir(leido) if not os.path.isdir(os.path.join(leido, "stockfish_fichas")) else _dir(os.path.join(leido, "stockfish_fichas"))
    fallas = []
    faltan = sorted(set(gen) - set(esc)); sobran = sorted(set(esc) - set(gen))
    if faltan: fallas.append(f"{len(faltan)} fichas no se escribieron (ej. {faltan[0]})")
    if sobran: fallas.append(f"{len(sobran)} fichas leídas que no están en la corrida (ej. {sobran[0]})")
    dist = [k for k in set(gen) & set(esc) if _huella(gen[k]) != _huella(esc[k])]
    if dist: fallas.append(f"{len(dist)} fichas escritas distintas de lo generado (ej. {sorted(dist)[0]})")
    banc = [k for k, v in esc.items() if _tiene_bancarios(v)]
    if banc: fallas.append(f"{len(banc)} fichas escritas con datos bancarios (ej. {banc[0]})")
    return _fin("escritura", fallas, [f"generadas {len(gen)} · leídas {len(esc)}"])


# ------------------------------------------------------------------ 8. reloj: invariantes + mutaciones + localidad + tiempo (datos reales)
ESTADOS_REALES = {"archivada", "aceptada_facturada", "aceptada_sin_factura", "aceptada_dentro_corte", "rechazada",
                  "vigente", "vencida_sin_estado", "sin_estado", "perdida", "borrador"}


def _correr(auditor, src, hoy, out):
    r = subprocess.run([sys.executable, "-I", auditor, "correr", "--src", src, "--hoy", hoy, "--out", out], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-300:])
    return _dir(os.path.join(out, "fichas")), _load(os.path.join(out, "resumen.json"))


def invariantes(src, docs, resumen, valor=None):
    f = []
    if valor is not None:
        V = valor["cuentas"]
        if set(V) != set(docs): f.append(f"I13 valor: {len(set(docs) ^ set(V))} cuentas sin valor o de más")
        for k, v in V.items():
            d = docs.get(k) or {}
            r = any((d.get("sf_restricciones") or {}).get(x) for x in RESTRICCIONES)
            if r and v["valor"] is not None: f.append(f"I14 {k}: tiene restricción y lleva valor {v['valor']}")
            if not r and (v["valor"] is None or not 0 <= v["valor"] <= 100): f.append(f"I15 {k}: valor fuera de 0-100 ({v['valor']})")
            if v["valor"] is not None and abs(v["valor"] - sum(c["puntos"] for c in v["componentes"].values())) > 0.5:
                f.append(f"I16 {k}: el valor no es la suma de sus componentes")
    _, filas = _r15(src)
    clave = lambda fe, co, mo, br: (str(fe)[:10], co, mo, round(float(br or 0), 2))
    cruda = collections.Counter(clave(r["fecha"], r["comprobante"], r["moneda"], r["bruto"]) for r in filas)
    sal = collections.Counter()
    donde = collections.defaultdict(set)
    for k, d in docs.items():
        for x in d["sf_comprobantes"]:
            c = clave(x["fecha"], x["comp"], x["moneda"], x["bruto"]); sal[c] += 1; donde[c].add(k)
    if sum(sal.values()) + resumen["sinVinculoMonto"]["n"] != sum(cruda.values()):
        f.append(f"I1 filas: libro {sum(cruda.values())} vs cuentas {sum(sal.values())} + sin vínculo {resumen['sinVinculoMonto']['n']}")
    extra = [c for c in sal if sal[c] > cruda.get(c, 0)]
    if extra: f.append(f"I2 {len(extra)} comprobantes en la salida que no están (o están más veces) en el libro (ej. {extra[0]})")
    dos = [c for c, ks in donde.items() if len(ks) > 1]
    if dos: f.append(f"I3 {len(dos)} comprobantes asignados a más de una cuenta (ej. {dos[0]} en {sorted(donde[dos[0]])})")
    asign = collections.defaultdict(list)
    for k, d in docs.items():
        comps = {x["comp"] for x in d["sf_comprobantes"] if x["tipo"] in ("F", "ANT")}
        c = d["sf_compras"]
        if c["primera"] and c["ultima"] and c["primera"] > c["ultima"]: f.append(f"I4 {k}: primera compra posterior a la última")
        if c["nFacturas"] != len(comps): f.append(f"I5 {k}: nFacturas {c['nFacturas']} vs {len(comps)} facturas en comprobantes")
        for e in d["sf_cotizaciones"]:
            if e["estadoReal"] not in ESTADOS_REALES: f.append(f"I6 {k}: estadoReal desconocido '{e['estadoReal']}'")
            for fx in e["facturaR15"]:
                if fx not in comps: f.append(f"I7 {k}: {e['numero']} apunta a {fx}, que no es factura de la cuenta")
                asign[(k, fx)].append(e["numero"])
        base_r = {x: d.get(x) for x in RESTRICCIONES if d.get(x)}
        if any(d["sf_restricciones"].get(x) != v for x, v in base_r.items()): f.append(f"I8 {k}: sf_restricciones no refleja la ficha")
        for h in d["sf_hallazgos"]:
            if h["sev"] not in ("alta", "media", "baja") or not re.match(r"^R\d\d", h["regla"]): f.append(f"I9 {k}: hallazgo mal formado {h['regla']}")
        if _tiene_bancarios(d): f.append(f"I10 {k}: datos bancarios en la salida")
        s = dict(d); sello = s.pop("sf_sello", {})
        if sello.get("huellaDoc") != hashlib.sha256(json.dumps(s, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]:
            f.append(f"I11 {k}: huellaDoc no coincide con el contenido")
    dobles = {k: v for k, v in asign.items() if len(v) > 1}
    if dobles: f.append(f"I12 {len(dobles)} facturas asignadas a dos cotizaciones (ej. {next(iter(dobles.items()))})")
    return f


def c_reloj(src, hoy, auditor, n_local=3):
    fallas, notas = [], []
    tmp = tempfile.mkdtemp(prefix="sf_reloj_")
    try:
        base, res = _correr(auditor, src, hoy, os.path.join(tmp, "base"))
        f = invariantes(src, base, res, _load(os.path.join(tmp, "base", "valor.json"))); fallas += f
        notas.append(f"invariantes I1–I16 sobre {len(base)} cuentas: {'OK' if not f else str(len(f)) + ' fallas'}")
        # --- tiempo: un día después las compras no cambian y casi ninguna ficha cambia
        man = (_fecha(hoy) + datetime.timedelta(days=1)).isoformat()
        d1, _ = _correr(auditor, src, man, os.path.join(tmp, "manana"))
        comp_cambia = [k for k in base if base[k]["sf_compras"] != d1[k]["sf_compras"]]
        if comp_cambia: fallas.append(f"T1 {len(comp_cambia)} cuentas cambian sus compras de un día al otro sin datos nuevos (ej. {comp_cambia[0]})")
        cambian = [k for k in base if base[k] != d1[k]]
        notas.append(f"un día después cambian {len(cambian)} de {len(base)} fichas (solo vencimientos)")
        # --- localidad: sacar una cuenta no cambia ninguna otra
        cand = sorted(k for k, d in base.items() if not d["sf_sinFicha"] and len(d["sf_fichas"]) == 1 and d["sf_cuits"]
                      and d["sf_comprobantes"] and not d["sf_cotizaciones"] and not d["sf_pedidos"] and not d["sf_remitos"])
        paso = max(1, len(cand) // n_local)
        for k in cand[::paso][:n_local]:
            d = base[k]; cuits = set(d["sf_cuits"])
            s2 = os.path.join(tmp, "loc_" + k); shutil.copytree(src, s2)
            os.remove(os.path.join(s2, "oportunidades", k + ".json"))
            for c in cuits:
                p = os.path.join(s2, "facturacion", c + ".json")
                if os.path.exists(p): os.remove(p)
            for p, ci, _dic in _libros(s2):
                j = json.load(open(p, encoding="utf-8")); t = j["data"] if isinstance(j.get("data"), dict) else j
                i = ci.index("cuit"); t["d"] = [x for x in t["d"] if _digitos(x[i]) not in cuits]
                if "lineas" in t: t.pop("lineas")
                json.dump(j, open(p, "w", encoding="utf-8"), ensure_ascii=False)
            dl, _ = _correr(auditor, s2, hoy, os.path.join(tmp, "o_loc_" + k))
            otros = [x for x in base if x != k and (x not in dl or dl[x] != base[x])]
            if k in dl: fallas.append(f"L1 sacando {k}: la cuenta sigue apareciendo")
            if otros: fallas.append(f"L2 sacando {k} cambiaron {len(otros)} otras cuentas (ej. {otros[0]})")
            else: notas.append(f"localidad {k}: ninguna otra cuenta cambia")
        # --- mutaciones: cada error sembrado tiene que aparecer donde corresponde
        def mutar(nombre, fn, cuenta, espera):
            s3 = os.path.join(tmp, "mut_" + nombre); shutil.copytree(src, s3)
            fn(s3)
            dm, _ = _correr(auditor, s3, hoy, os.path.join(tmp, "o_mut_" + nombre))
            ok = espera(dm.get(cuenta))
            (notas if ok else fallas).append(f"M {nombre}: {'detectado' if ok else 'NO detectado'} en {cuenta}")
        regl = lambda d: {h["regla"] for h in (d or {}).get("sf_hallazgos", [])}
        # elegir víctimas reales del propio dataset
        acept = [(k, e) for k, d in sorted(base.items()) for e in d["sf_cotizaciones"] if e["estadoReal"] == "aceptada_facturada" and len(e["facturaR15"]) == 1]
        if acept:
            k, e = acept[0]; fx = e["facturaR15"][0]
            def borrar_factura(s3, fx=fx):
                for p, ci, dd in _libros(s3):
                    j = json.load(open(p, encoding="utf-8")); t = j["data"] if isinstance(j.get("data"), dict) else j
                    i = ci.index("comprobante"); it = ci.index("tipocomp")
                    dic = dd["tipocomp"]
                    t["d"] = [x for x in t["d"] if not (x[i] == fx and _signo(dic[x[it]] if isinstance(x[it], int) else x[it]) == 1 and "Débito" not in str(dic[x[it]] if isinstance(x[it], int) else x[it]))]
                    t.pop("lineas", None); json.dump(j, open(p, "w", encoding="utf-8"), ensure_ascii=False)
            mutar("factura_borrada", borrar_factura, k, lambda d, n=e["numero"]: d and any(c["numero"] == n and c["estadoReal"] in ("aceptada_sin_factura", "aceptada_dentro_corte") for c in d["sf_cotizaciones"]))
        abiertas = [(k, x) for k, d in sorted(base.items()) for x in d["sf_entregas"] if not x.get("entregado")]
        if abiertas:
            k, x = abiertas[0]
            def entregar(s3, comp=x["comp"]):
                p = os.path.join(s3, "config", "ventasEntregas.json"); j = json.load(open(p)); t = j["data"] if isinstance(j.get("data"), dict) else j
                t[comp] = hoy; json.dump(j, open(p, "w"))
            mutar("entrega_marcada", entregar, k, lambda d: d and "R07_ENTREGA_ABIERTA" not in regl(d))
        conf = sorted(k for k, d in base.items() if not d["sf_sinFicha"] and d.get("proximaFecha"))
        if conf:
            k = conf[0]
            def fecha_mala(s3, k=k):
                p = os.path.join(s3, "oportunidades", k + ".json"); j = json.load(open(p)); t = j["data"] if isinstance(j.get("data"), dict) else j
                t["proximaFecha"] = "31/12/2026"; json.dump(j, open(p, "w"))
            mutar("fecha_invalida", fecha_mala, k, lambda d: d and "R13_FECHA_INVALIDA" in regl(d) and "R09_PROMESA_VENCIDA" not in regl(d))
        cuenta_cuit = sorted(k for k, d in base.items() if not d["sf_sinFicha"] and len(d["sf_cuits"]) == 1 and d["sf_comprobantes"])
        if cuenta_cuit:
            k = cuenta_cuit[0]
            def banco(s3, k=k):
                p = os.path.join(s3, "oportunidades", k + ".json"); j = json.load(open(p)); t = j["data"] if isinstance(j.get("data"), dict) else j
                t["datosBancarios"] = {"cbu": "0000000000000000000000"}; json.dump(j, open(p, "w"))
            mutar("datos_bancarios", banco, k, lambda d: d is not None and not _tiene_bancarios(d))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return _fin("reloj", fallas, notas)


# ------------------------------------------------------------------ 9. fuentes: libro de ventas vs Reporte 4 (tercera fuente)
def _r4(src):
    s, hasta = "", None
    for n in ("r4", "r4_2", "r4_3"):
        p = os.path.join(src, "reportes", n + ".json")
        if os.path.exists(p):
            d = _load(p); s += d["filas"]
            if n == "r4": hasta = d.get("hasta")
    if not s:
        return [], None
    x = json.loads(s); D = x["d"]
    dec = lambda v: D[int(v[1:])] if isinstance(v, str) and v.startswith("s") and v[1:].isdigit() else v
    return [dict(zip(x["f"], [dec(v) for v in r])) for r in x["r"]], hasta


def c_fuentes(src, minimo=0.90):
    """Facturas y NC en USD del libro (r15) contra el Reporte 4, por (comprobante, CUIT, signo). Hasta el corte de r4."""
    filas4, hasta = _r4(src)
    if not filas4:
        return _fin("fuentes", [], ["sin Reporte 4: no se cruza"])
    pos, neg = collections.defaultdict(float), collections.defaultdict(float)
    for r in filas4:
        u = float(r["usd"] or 0)
        (pos if u > 0 else neg)[(r["comp"], _digitos(r.get("cuit")))] += u
    _, filas = _r15(src)
    n = ok = 0; ej = []
    for r in filas:
        t = str(r["tipocomp"])
        if r["moneda"] != "USD" or "Dif. Cambio" in t or "Débito" in t or str(r["fecha"])[:10] > (hasta or "9999"):
            continue
        k = (r["comprobante"], _digitos(r.get("cuit")))
        got = abs((neg if "Crédito" in t else pos).get(k, 0)); ref = abs(r["bruto"] or 0)
        n += 1
        if got and abs(got - ref) <= max(1.0, 0.02 * ref): ok += 1
        elif len(ej) < 5: ej.append(f"{r['comprobante']} {r['cliente'][:22]}: libro {ref:.0f} vs r4 {got:.0f}")
    tasa = ok / n if n else 1
    fallas = [] if tasa >= minimo else [f"solo {tasa:.1%} de los comprobantes USD coinciden con el Reporte 4 (mínimo {minimo:.0%})"]
    return _fin("fuentes", fallas, [f"{ok}/{n} comprobantes USD coinciden con r4 ({tasa:.1%}), corte r4 {hasta}"] + [f"no coincide: {e}" for e in ej])


# ------------------------------------------------------------------ tests de los controles
def test():
    ok = []
    def T(n, c):
        ok.append(bool(c)); print(("PASA " if c else "FALLA") + " · " + n)
    audit = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stockfish_auditor.py")
    sys.path.insert(0, os.path.dirname(audit))
    import importlib
    A = importlib.import_module("stockfish_auditor")
    tmp = tempfile.mkdtemp(prefix="sf_ctl_")
    cwd = os.getcwd()
    try:
        os.chdir(tmp)
        src = A._mini(os.path.join(tmp, "src"))
        out = os.path.join(tmp, "out")
        A.correr(src, "2026-11-09", out)
        import io, contextlib
        def silencio(f, *a, **k):
            b = io.StringIO()
            with contextlib.redirect_stdout(b):
                r = f(*a, **k)
            return r
        limpio = os.path.join(tmp, "limpio"); shutil.copytree(src, limpio)
        os.remove(os.path.join(limpio, "oportunidades", "e.json"))
        dj = json.load(open(os.path.join(limpio, "oportunidades", "d.json"))); dj.pop("datosBancarios"); dj["proximaFecha"] = "2026-11-09"
        json.dump(dj, open(os.path.join(limpio, "oportunidades", "d.json"), "w"))
        T("entrada: dataset limpio pasa", silencio(c_entrada, limpio, "2026-11-09", 60))
        T("entrada: dataset con CUIT de largo inválido y bancarios falla", not silencio(c_entrada, src, "2026-11-09"))
        # entrada: debe fallar con duplicado, bancarios, fecha inválida
        mal = os.path.join(tmp, "mal"); shutil.copytree(src, mal)
        json.dump({"empresa": "X", "datosBancarios": {"cbu": "1"}}, open(os.path.join(mal, "oportunidades", "x.json"), "w"))
        T("entrada: detecta datos bancarios", not silencio(c_entrada, mal, "2026-11-09"))
        mal2 = os.path.join(tmp, "mal2"); shutil.copytree(src, mal2)
        r = json.load(open(os.path.join(mal2, "reportes", "r15.json"))); r["d"].append(list(r["d"][0]))
        json.dump(r, open(os.path.join(mal2, "reportes", "r15.json"), "w"))
        T("entrada: detecta comprobante duplicado", not silencio(c_entrada, mal2, "2026-11-09"))
        T("cierre: recálculo independiente coincide", silencio(c_cierre, src, out, 1000))
        T("cierre: falla si el sin-vínculo supera el tope", not silencio(c_cierre, src, out, 5))
        # cierre: si el auditor sumara mal una cuenta, el control lo ve
        o2 = os.path.join(tmp, "out_roto"); shutil.copytree(out, o2)
        p = os.path.join(o2, "fichas", "a.json"); d = json.load(open(p))
        d["sf_compras"]["usdBrutoPorAnio"]["2026"] += 50; json.dump(d, open(p, "w"))
        T("cierre: detecta una cuenta mal sumada", not silencio(c_cierre, src, o2, 1000))
        oro = os.path.join(tmp, "oro.json")
        json.dump({"casos": [{"cuenta": "a", "debe_tener": ["R07_ENTREGA_ABIERTA"], "igual": {"sf_sinFicha": False}, "rango": {"sf_compras.usdBrutoNeto": [999, 1001]}},
                             {"cuenta": "d", "debe_tener": ["R07_ENTREGA_PARCIAL"], "no_debe_tener": ["R01_ACEPTADA_DENTRO_DE_OTRA"]},
                             {"cuenta": "zzz", "pendiente": True}]}, open(oro, "w"))
        T("oro: casos conocidos pasan", silencio(c_oro, out, oro))
        json.dump({"casos": [{"cuenta": "a", "debe_tener": ["R99_NO_EXISTE"]}]}, open(oro, "w"))
        T("oro: falla si falta un hallazgo esperado", not silencio(c_oro, out, oro))
        T("cambios: fidelidad de oportunidades + sin corrida previa", silencio(c_cambios, src, out))
        T("cambios: contra sí misma no hay saltos", silencio(c_cambios, src, out, out))
        o3 = os.path.join(tmp, "out_cambio"); shutil.copytree(out, o3)
        p = os.path.join(o3, "fichas", "a.json"); d = json.load(open(p)); d["etapa"] = "perdido"; json.dump(d, open(p, "w"))
        T("cambios: detecta una ficha canónica alterada", not silencio(c_cambios, src, o3))
        T("determinismo: 4 corridas, misma huella", silencio(c_determinismo, src, "2026-11-09", audit))
        reco = os.path.join(tmp, "reco.json")
        json.dump([{"cuenta": "d"}], open(reco, "w"))
        T("restricciones: cuenta sin restricción pasa", silencio(c_restricciones, out, reco))
        json.dump([{"cuenta": "a"}], open(reco, "w"))
        T("restricciones: noProspectar recomendada = FALLA", not silencio(c_restricciones, out, reco))
        T("escritura: lectura de vuelta idéntica", silencio(c_escritura, out, os.path.join(out, "fichas")))
        os.remove(os.path.join(out, "fichas", "b.json")) if False else None
        copia = os.path.join(tmp, "leido"); shutil.copytree(os.path.join(out, "fichas"), copia)
        p = os.path.join(copia, "b.json"); d = json.load(open(p)); d["etapa"] = "x"; json.dump(d, open(p, "w"))
        T("escritura: detecta una ficha distinta a la generada", not silencio(c_escritura, out, copia))
    finally:
        os.chdir(cwd); shutil.rmtree(tmp, ignore_errors=True)
    res = "PASA" if all(ok) else "FALLA"
    print(f"RESULTADO: {res} ({sum(ok)}/{len(ok)})")
    return res == "PASA"


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] == "test":
        sys.exit(0 if test() else 1)
    kv = dict(zip(a[1::2], a[2::2]))
    g = lambda k, d=None: kv.get("--" + k, d)
    f = {"entrada": lambda: c_entrada(g("src"), g("hoy")),
         "cierre": lambda: c_cierre(g("src"), g("out"), float(g("tope-usd-sin-vinculo", 1000))),
         "oro": lambda: c_oro(g("out"), g("oro")),
         "cambios": lambda: c_cambios(g("src"), g("out"), g("prev"), float(g("umbral", 0.25))),
         "determinismo": lambda: c_determinismo(g("src"), g("hoy"), g("auditor")),
         "restricciones": lambda: c_restricciones(g("out"), g("reco")),
         "escritura": lambda: c_escritura(g("out"), g("leido")),
         "fuentes": lambda: c_fuentes(g("src"), float(g("minimo", 0.90))),
         "reloj": lambda: c_reloj(g("src"), g("hoy"), g("auditor"), int(g("localidad", 3)))}.get(a[0])
    if not f:
        print("control desconocido:", a[0]); sys.exit(2)
    sys.exit(0 if f() else 1)

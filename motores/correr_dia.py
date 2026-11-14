#!/usr/bin/env python3
"""correr_dia v1.7 · 13/11/2026 · Claude CRM (Opus) · plan cerebro (decisión 107) + HIVE + mapa (decisión 110)

v1.7: el datacenter en 8 módulos (ruteo.modulos) y un selector. K15 (FALLA): cada documento en un solo módulo.
  python3 -I correr_dia.py selector --raiz R "pedido"   qué módulo actúa, qué leer, motor, skill y modelo
  python3 -I correr_dia.py desempacar --raiz R <doc>   devuelve un respaldo comprimido tal cual era
  desempacar queda para leer un respaldo comprimido viejo; escribir no comprime (la plataforma no quiere base64 en documentos).

v1.6: HIVE (Comb) como fuente de stock, solo lectura. «productos» lista qué consultar; Claude guarda R/hive_stock.json
  con consultar_stock y el día suma K14 (AVISO): cotizado + a entregar contra el stock de HIVE. Nunca se escribe en HIVE.
  python3 -I correr_dia.py productos --raiz R --hoy AAAA-MM-DD

v1.4: el datacenter decide, Claude no interpreta. Suma al día el bloque CEREBRO (FALLA = CADENA FALLA):
  K11 cada decisión desde decisiones.efectosDesde tiene su efecto estructurado (dato, ficha, cotización, código o
      procedimiento con motivo) y el efecto está en el dato;
  K12 todo SUPUESTO de reglas_motor y dictados está en datacenter/supuestos (y el resumen los lista siempre);
  K13 datacenter/definiciones existe y el Sales Engine da el mismo estado de cotización que la definición;
  K7  ningún texto de regla (índice, ruteo, reglas, reglas_motor, restricciones, dictados, supuestos, definiciones,
      protocolo) cita números de versión: AVISO.
  Envío tras pago lee el campo fijo cotizacion.hz_operacion (pago/pagoAt/despacho); el historial queda de respaldo.
  python3 -I correr_dia.py dictado  --raiz R --hoy AAAA-MM-DD "frase"   qué significa una frase de Nicolás (datacenter/dictados)
  python3 -I correr_dia.py escribir --raiz R --hoy AAAA-MM-DD --cambios cambios.json
      única puerta de escritura: valida (if_version, historial sin duplicar, hz_operacion, fechas ISO, sin versiones
      en textos) y deja R/salida/escritura_batch.json para UN ArtifactData batch.


v1.3: regla ENVÍO TRAS PAGO (reglas_motor.reglasVistas.envioTrasPagoHoras, 48 h): pago confirmado en la ficha + factura sin
despachar en el conciliador (no en depósito) + sin confirmación de envío posterior = pendiente en el resumen, con las
horas que corren; pasado el plazo, VENCIDO. Sale solo cuando Nicolás responde y se carga «Envío confirmado» (o retiro,
entrega, despacho) en la ficha. No cambia ninguna decisión del Sales Engine.

v1.2: una sola puerta (consulta y cierre también por acá), --skills se detecta solo (chat común /mnt/skills/plugins;
Claude Code /root/.claude/skills/synced/*/), y el día deja R/salida/resumen.txt: lo que va en la respuesta, en el
orden del protocolo (avisos → C1/C4 → empujes → RENOVAR → pendientes). inicio.txt queda completo en disco.

  python3 -I correr_dia.py consulta --raiz R "texto"              lo ya decidido o cargado (antes de preguntarle a Nicolás)
  python3 -I correr_dia.py cierre   --raiz R --hoy AAAA-MM-DD     errores de la bitácora de hoy → salida/aprendizajes_parche.json

Una sola orden para toda la cadena y los controles, con las entradas fijas (error del 12/11: pasé mal los archivos
de entrada del Sales Engine y salió otro resultado). El código de cada motor se toma de datacenter/<doc>.json (campo
«codigo»): la fuente única es el CRM, no una copia local.

  python3 -I correr_dia.py dia      --raiz R --hoy AAAA-MM-DD [--buzon para_CRM.md] [--skills /mnt/skills/plugins]   cadena conciliador → sales_engine → cinco_cosas → inicio_loki
  python3 -I correr_dia.py comparar --raiz R --hoy AAAA-MM-DD (--codigo-antes sales_viejo.py | --json-antes sales_viejo.json)
                                                                    cuentas que cambian entre un motor anterior y el vigente (sin modelo)
  python3 -I correr_dia.py oro                                    casos de oro: 10 cuentas reales (fotos del 12/11) con resultado verificado
  python3 -I correr_dia.py k10      --raiz R --hoy AAAA-MM-DD     el motor ve compras en un año donde Stockfish dice 0
  python3 -I correr_dia.py test                                   autotest

R es la carpeta exportada del CRM: stockfish_fichas/ oportunidades/ cotizaciones/ facturacion/ reportes/
config/continuidad.json datacenter/*.json. Las salidas van a R/salida/. Regla: el script decide, Claude explica.
"""
import argparse, datetime as dt, importlib.util, json, os, subprocess, sys, tempfile

VERSION = "1.7"
PASOS = ("conciliador", "sales_engine", "cinco_cosas", "script_inicio")


def doc(raiz, nombre):
    with open(os.path.join(raiz, "datacenter", nombre + ".json"), encoding="utf-8") as fh:
        d = json.load(fh)
    return d.get("data", d)


def extraer(raiz, nombre):
    """escribe el código del doc a R/.motores/<nombre>.py y devuelve la ruta"""
    d = os.path.join(raiz, ".motores")
    os.makedirs(d, exist_ok=True)
    c = doc(raiz, nombre).get("codigo")
    if not c:
        raise SystemExit(f"FALLA: datacenter/{nombre} no tiene código")
    p = os.path.join(d, nombre + ".py")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(c)
    return p


def correr(args, paso):
    r = subprocess.run([sys.executable, "-I"] + args, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"FALLA en {paso} (código {r.returncode}):\n{(r.stdout + r.stderr)[-1500:]}")
    return r.stdout


def cargar(ruta, nombre="m"):
    s = importlib.util.spec_from_file_location(nombre, ruta)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def rutas(raiz, hoy):
    j = lambda *p: os.path.join(raiz, *p)
    return dict(sf=j("stockfish_fichas"), crm=j("oportunidades"), cot=j("cotizaciones"), fact=j("facturacion"),
                rep=j("reportes"), dc=j("datacenter"), cont=j("config", "continuidad.json"), sal=j("salida"))


def sales(raiz, hoy, codigo, reglas, conc, salida):
    r = rutas(raiz, hoy)
    d = r["dc"]
    return correr([codigo, "dia", "--sf", r["sf"], "--crm", r["crm"], "--banco", os.path.join(d, "banco_manos.json"),
                   "--valor", os.path.join(d, "stockfish_valor.json"), "--restricciones", os.path.join(d, "restricciones.json"),
                   "--registro", os.path.join(d, "banco_registro.json"), "--conciliador", conc, "--reglas", reglas,
                   "--cot", r["cot"], "--hoy", hoy, "--json", salida], "sales_engine")


SKILLS_CANDIDATAS = ("/mnt/skills/plugins", "/root/.claude/skills/synced/*")


def buscar_skills(dada=None):
    """carpeta que tiene <skill>/SKILL.md (marca: loki-maestro). Devuelve (ruta o None, nota)."""
    import glob
    def ok(d):
        return d and os.path.isfile(os.path.join(d, "loki-maestro", "SKILL.md"))
    if ok(dada):
        return dada, ""
    for pat in SKILLS_CANDIDATAS:
        for d in sorted(glob.glob(pat)):
            if ok(d):
                return d, (f"--skills {dada} no tiene loki-maestro: se usó {d}" if dada else "")
    return dada, ("no se encontró la carpeta de skills: K7 sin controlar" if not dada else "")


def _leer(ruta, defecto=None):
    try:
        with open(ruta, encoding="utf-8") as fh:
            d = json.load(fh)
        return d.get("data", d) if isinstance(d, dict) else d
    except (OSError, ValueError):
        return defecto


def _bloque(txt, desde, hasta):
    i = txt.find(desde)
    if i < 0:
        return ""
    j = txt.find(hasta, i + len(desde)) if hasta else -1
    return txt[i:j if j > 0 else len(txt)].rstrip()


RX_PAGO = r"pago confirmado"
RX_ENVIO = r"env[ií]o confirmado|despacho confirmado|entregad|retir[oó]\b|retirado|recibi[oó]|lleg[oó]|en dep[oó]sito"


def pendientes_envio(raiz, hoy, conc, ahora=None):
    """v1.4: campo fijo cotizacion.hz_operacion (pago/pagoAt/despacho) primero; el historial de la ficha es respaldo."""
    r = rutas(raiz, hoy)
    reg = (_leer(os.path.join(r["dc"], "reglas_motor.json"), {}) or {}).get("reglasVistas") or {}
    horas = float(((reg.get("envioTrasPagoHoras") or {}).get("valor")) or 48)
    ventana = int(((reg.get("envioTrasPagoVentanaDias") or {}).get("valor")) or 30)
    dep = (_leer(os.path.join(r["dc"], "restricciones.json"), {}) or {}).get("enDeposito") or {}
    if ahora is None:
        ahora = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) if hoy == dt.date.today().isoformat() else dt.datetime.fromisoformat(hoy + "T23:59:00")
    lim = ahora - dt.timedelta(days=ventana)
    out, con_campo = [], set()
    for n in sorted(os.listdir(r["cot"])) if os.path.isdir(r["cot"]) else ():
        q = _leer(os.path.join(r["cot"], n), {}) or {}
        hz = q.get("hz_operacion") or {}
        fid = q.get("oportunidadId")
        if hz.get("pago") != "confirmado" or not hz.get("pagoAt") or not fid:
            continue
        con_campo.add(fid)
        tp = dt.datetime.fromisoformat(str(hz["pagoAt"])[:19])
        if tp < lim or fid in dep or hz.get("despacho") == "confirmado":
            continue
        h = (ahora - tp).total_seconds() / 3600
        vence = tp + dt.timedelta(hours=horas)
        estado = (f"VENCIDO hace {int(h - horas)} h" if h > horas else f"corre: {int(h)} de {int(horas)} h, vence {vence:%d/%m %H:%M} UTC")
        out.append({"ficha": fid, "empresa": q.get("cliente"), "pago": str(hz["pagoAt"])[:16], "horas": round(h, 1),
                    "vencido": h > horas, "estado": estado,
                    "factura": f"{q.get('numero')} · {hz.get('factura') or 'sin factura en el campo'} · despacho {hz.get('despacho') or 'sin dato'}"})
    for x in pendientes_envio_historial(raiz, hoy, conc, ahora):
        if x["ficha"] not in con_campo:
            x["factura"] += " · dato solo en el historial: cargar hz_operacion"
            out.append(x)
    return sorted(out, key=lambda x: (not x["vencido"], -x["horas"]))


def pendientes_envio_historial(raiz, hoy, conc, ahora=None):
    """decisión 106: después de confirmar el pago hay 48 h para confirmar el envío. Devuelve filas ordenadas."""
    import re
    r = rutas(raiz, hoy)
    reg = (_leer(os.path.join(r["dc"], "reglas_motor.json"), {}) or {}).get("reglasVistas") or {}   # fuera de «reglas»: no toca la huella del Sales Engine (K9)
    horas = float(((reg.get("envioTrasPagoHoras") or {}).get("valor")) or 48)
    ventana = int(((reg.get("envioTrasPagoVentanaDias") or {}).get("valor")) or 30)
    dep = (_leer(os.path.join(r["dc"], "restricciones.json"), {}) or {}).get("enDeposito") or {}
    c1 = {}
    for h in (conc or {}).get("hallazgos") or []:
        if h.get("ficha") and h.get("regla") == "C1" and h.get("informar", "si") == "si" and "En depósito" not in (h.get("hacer") or ""):
            c1.setdefault(h["ficha"], []).append(h)
    if ahora is None:
        ahora = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) if hoy == dt.date.today().isoformat() else dt.datetime.fromisoformat(hoy + "T23:59:00")
    lim = ahora - dt.timedelta(days=ventana)
    out = []
    for fid, hs in c1.items():
        if fid in dep:
            continue
        f = _leer(os.path.join(r["crm"], fid + ".json"), {}) or {}
        hist = sorted(f.get("historial") or [], key=lambda x: x.get("t") or "")
        pagos = [x for x in hist if re.search(RX_PAGO, x.get("txt") or "", re.I)]
        if not pagos:
            continue
        tp = dt.datetime.fromisoformat(pagos[-1]["t"][:19])
        if tp < lim:
            continue
        if any(re.search(RX_ENVIO, x.get("txt") or "", re.I) for x in hist if (x.get("t") or "") > pagos[-1]["t"]):
            continue
        h = (ahora - tp).total_seconds() / 3600
        vence = tp + dt.timedelta(hours=horas)
        estado = (f"VENCIDO hace {int(h - horas)} h" if h > horas else f"corre: {int(h)} de {int(horas)} h, vence {vence:%d/%m %H:%M} UTC")
        out.append({"ficha": fid, "empresa": f.get("empresa") or hs[0].get("empresa"), "pago": pagos[-1]["t"][:16],
                    "horas": round(h, 1), "vencido": h > horas, "estado": estado,
                    "factura": "; ".join(x["que"][:90] for x in hs)})
    return sorted(out, key=lambda x: (not x["vencido"], -x["horas"]))


def resumen(raiz, hoy, ini, conc_path, nota_skills=""):
    """lo que va en la respuesta, en el orden del protocolo; nada que no esté en las salidas de esta corrida"""
    r = rutas(raiz, hoy)
    L = [f"# RESUMEN · {hoy} (correr_dia v{VERSION}) · el detalle completo está en salida/inicio.txt", ""]
    lin = ini.splitlines()
    av = [l for l in lin if l.startswith("## Integridad") or l.startswith("## Coherencia") or l.startswith("## Skills K7")
          or l.startswith("- FALLA") or l.startswith("FRENO") or l.startswith("Control de cuentas")]
    L.append("## 1. Avisos y control")
    L += av + ([f"- AVISO skills: {nota_skills}"] if nota_skills else [])
    k6 = [l for l in lin if "AVISO K4" in l or "AVISO K5" in l or "Stockfish con foto vieja" in l]
    L += [l[:260] for l in k6]
    c = _leer(conc_path, {}) or {}
    hs = c.get("hallazgos") or []
    pe = pendientes_envio(raiz, hoy, c)
    L += [""] + list(CEREBRO_LINEAS)
    L += ["", f"## Pendientes de envío tras pago (decisión 106 · 48 h · sujeto a respuesta de Nicolás): {len(pe)}"]
    L += [f"- {x['empresa']} · pago confirmado {x['pago']} · {x['estado']} · {x['factura']} → preguntarle a Nicolás si salió; se cierra cuando lo confirma" for x in pe] or ["- ninguno"]
    alto = [h for h in hs if h.get("informar", "si" if not h.get("restringida") else "no") == "si" and h.get("regla") in ("C1", "C4") and h.get("nivel") == "alto"]
    sind = [h for h in hs if h.get("informar") == "si" and h.get("sinDato")]
    otros = [h for h in hs if h.get("informar", "si" if not h.get("restringida") else "no") == "si" and h.get("nivel") in ("alto", "medio") and h not in alto]
    avi = [h for h in hs if h.get("informar") == "aviso" and h.get("nivel") in ("alto", "medio") and (h.get("monto") or 0) > 0]   # archivada/compartida: solo con plata
    usd = lambda m: (" · USD " + format(m, ",.0f").replace(",", ".")) if m else ""
    L += ["", f"## 2. Conciliador v{c.get('version', '?')} {c.get('veredicto', '?')} · cortes {json.dumps(c.get('cortes', {}), ensure_ascii=False)}"]
    L += [f"- [{h['regla']}] {h['empresa']}{usd(h.get('monto'))} · {h['que'][:170]} → {h['hacer'][:140]}" for h in alto] or ["- C1/C4 para actuar: ninguno"]
    L += [f"- [sin dato] {h['empresa']} · {h['que'][:150]} → {h['hacer'][:150]}" for h in sind]
    L += [f"- [{h['regla']}·{h['nivel']}] {h['empresa']} · {h['que'][:150]} → {h['hacer'][:120]}" for h in otros]
    L += [f"- [aviso {h.get('restringida')}] {h['empresa']}{usd(h.get('monto'))} · {h['que'][:140]}" for h in avi]
    L += ["", "## 3. Orden del día (Sales Engine: el único que decide)"]
    L.append(_bloque(ini, "Empujes de hoy", "Fichas leídas") or "(sin orden del día)")
    ag = _bloque(ini, "## ENTREGA", "## COTIZACION")
    if ag:
        L += ["", "## 4. Entregas de la agenda", ag]
    bit = _leer(os.path.join(r["dc"], f"bitacora_{hoy}.json"), {}) or {}
    pend = bit.get("pendiente") or []
    if pend or bit.get("decisionesNicolas"):
        L += ["", f"## 5. Bitácora de hoy (ya decidido: no se pregunta) · pendientes {len(pend)}"]
        L += [f"- decidido: {str(x)[:200]}" for x in bit.get("decisionesNicolas") or []]
        L += [f"- pendiente: {str(x)[:200]}" for x in pend]
    L += [""] + supuestos_resumen(raiz)
    cont = _leer(r["cont"], {}) or {}
    if cont.get("ultimoChat"):
        L += ["", "## 6. Último chat", str(cont["ultimoChat"])[:400]]
    L += ["", "Regla: antes de preguntar algo, correr_dia.py consulta; lo estructural espera el «hacelo»."]
    txt = "\n".join(L)
    with open(os.path.join(r["sal"], "resumen.txt"), "w", encoding="utf-8") as fh:
        fh.write(txt + "\n")
    return txt


def cmd_consulta(a):
    r = rutas(a.raiz, None)
    print(correr([extraer(a.raiz, "script_inicio"), "--consulta", " ".join(a.texto), "--crm", r["crm"], "--docs", r["dc"],
                  "--continuidad", r["cont"]], "consulta"))
    return 0


def cmd_cierre(a):
    r = rutas(a.raiz, a.hoy)
    os.makedirs(r["sal"], exist_ok=True)
    bit = os.path.join(r["dc"], f"bitacora_{a.hoy}.json")
    if not os.path.exists(bit):
        raise SystemExit(f"FALLA: no está {bit}: escribir la bitácora de hoy y re-exportar el datacenter antes del cierre")
    print(correr([extraer(a.raiz, "script_inicio"), "--cierre", "--bitacora", bit, "--docs", r["dc"],
                  "--out", os.path.join(r["sal"], "aprendizajes_parche.json")], "cierre"))
    return 0


def cmd_dia(a):
    r = rutas(a.raiz, a.hoy)
    a.skills, nota_sk = buscar_skills(getattr(a, "skills", None))
    os.makedirs(r["sal"], exist_ok=True)
    cod = {p: extraer(a.raiz, p) for p in PASOS}
    conc, sj, cj = (os.path.join(r["sal"], n) for n in ("conciliador_hoy.json", "sales_hoy.json", "cinco_hoy.json"))
    correr([cod["conciliador"], "--crm", r["crm"], "--cot", r["cot"], "--fact", r["fact"], "--reportes", r["rep"], "--hoy", a.hoy,
            "--json", conc, "--restricciones", os.path.join(r["dc"], "restricciones.json")], "conciliador")
    sales(a.raiz, a.hoy, cod["sales_engine"], os.path.join(r["dc"], "reglas_motor.json"), conc, sj)
    correr([cod["cinco_cosas"], "dia", "--sales", sj, "--hoy", a.hoy, "--json", cj], "cinco_cosas")
    ini = correr([cod["script_inicio"], "--docs", r["dc"], "--crm", r["crm"], "--continuidad", r["cont"], "--hoy", a.hoy,
                  "--sf", r["sf"], "--cot", r["cot"], "--sales", sj, "--cinco", cj]
                 + (["--buzon"] + a.buzon if getattr(a, "buzon", None) else [])
                 + (["--skills", a.skills] if getattr(a, "skills", None) else []), "inicio_loki")
    with open(os.path.join(r["sal"], "inicio.txt"), "w", encoding="utf-8") as fh:
        fh.write(ini)
    ver_c, lin_c = cerebro(a.raiz, a.hoy, _leer(sj, {}))
    CEREBRO_LINEAS[:] = lin_c + [""] + k14_stock(a.raiz, a.hoy)
    print(resumen(a.raiz, a.hoy, ini, conc, nota_sk))
    mal = [l for l in ini.splitlines() if l.startswith("## Integridad") and "FALLA" in l or l.startswith("- FALLA")]
    import re as _re
    m = _re.search(r"Fichas leídas: (\d+)", ini)
    n_op = len([x for x in os.listdir(r["crm"]) if x.endswith(".json")])
    if ver_c == "FALLA":
        mal.append("CEREBRO FALLA (K11/K12/K13): ver el bloque en el resumen")
    if m and int(m.group(1)) == 0 and n_op:       # el 12/11 --crm apuntaba a la raíz y leía 0 fichas sin avisar
        mal.append("el inicio leyó 0 fichas de oportunidades (%d en la carpeta): revisar --crm" % n_op)
    print("\n" + "\n".join(l for l in _k10_resumen(a) if l))
    print("\nCADENA:", "FALLA · " + "; ".join(mal) if mal else "PASA (conciliador → sales_engine → cinco_cosas → inicio_loki, mismas entradas)")
    return 1 if mal else 0


# ---------------------------------------------------------------- v1.4 · plan cerebro (hacelo 13/11, decisión 107)
RX_VERSION = r"\bv\d+\.\d+\b"
DOCS_TEXTO = ("indice", "ruteo", "reglas", "reglas_motor", "restricciones", "dictados", "supuestos", "definiciones")


def _ruta(obj, ruta):
    """obj['a']['b'] con 'a.b'; 'a[].b' junta los valores de una lista."""
    vals = [obj]
    for p in ruta.split("."):
        nuevo = []
        lista = p.endswith("[]")
        p = p[:-2] if lista else p
        for v in vals:
            if isinstance(v, dict) and p in v:
                x = v[p]
                nuevo += (x if lista and isinstance(x, list) else [x])
        vals = nuevo
    return vals


def _cot_por_numero(cot_dir):
    out = {}
    for n in os.listdir(cot_dir) if os.path.isdir(cot_dir) else ():
        if n.endswith(".json"):
            q = _leer(os.path.join(cot_dir, n), {}) or {}
            if q.get("numero") and norm_estado(q.get("estado")) != "rechazada":
                out.setdefault(q["numero"], q)
    return out


def norm_estado(e):
    import unicodedata
    e = unicodedata.normalize("NFD", str(e or "")).encode("ascii", "ignore").decode().lower().strip()
    return "rechazada" if e in ("rechazada", "perdida", "perdido") else e


def k11_efectos(raiz, hoy):
    """K11: cada decisión desde efectosDesde tiene su efecto estructurado y el efecto está en el dato."""
    r = rutas(raiz, hoy)
    dec = doc(raiz, "decisiones")
    desde, ef = int(dec.get("efectosDesde") or 0), dec.get("efectos") or {}
    falla, aviso = [], []
    if not desde:
        return ["K11 decisiones sin efectosDesde/efectos (plan cerebro punto 1)"], aviso
    cots = _cot_por_numero(r["cot"])
    for n in range(desde, len(dec.get("lineas") or []) + 1):
        es = ef.get(str(n))
        if not es:
            falla.append(f"K11 decisión {n} sin efecto estructurado: cargarlo en decisiones.efectos")
            continue
        for e in es:
            t = e.get("tipo")
            if e.get("vigencia") and e["vigencia"] < hoy:
                aviso.append(f"K11 decisión {n}: efecto con vigencia {e['vigencia']} vencida: revisar")
                continue
            if t == "procedimiento":
                if not e.get("motivo"):
                    falla.append(f"K11 decisión {n}: procedimiento sin motivo")
                continue
            if t in ("dato", "codigo", "definicion"):
                d = os.path.join(r["dc"], (e.get("doc") or "definiciones") + ".json")
                v = _leer(d)
                if v is None:
                    falla.append(f"K11 decisión {n}: falta datacenter/{e.get('doc') or 'definiciones'}")
                elif t == "codigo" and e.get("contiene") not in (v.get("codigo") or ""):
                    falla.append(f"K11 decisión {n}: el código de {e['doc']} no tiene «{e['contiene']}»")
                elif t == "definicion" and e.get("clave") not in v:
                    falla.append(f"K11 decisión {n}: definiciones sin «{e.get('clave')}»")
                elif t == "dato" and e.get("ruta") and e.get("valor") not in _ruta(v, e["ruta"]):
                    falla.append(f"K11 decisión {n}: {e['doc']}.{e['ruta']} = {_ruta(v, e['ruta'])} y la decisión dice {e['valor']}")
                continue
            if t == "ficha":
                f = _leer(os.path.join(r["crm"], e["id"] + ".json"))
                if f is None:
                    falla.append(f"K11 decisión {n}: no está la ficha {e['id']}")
                elif e.get("contiene") and e["contiene"] not in json.dumps(f, ensure_ascii=False):
                    falla.append(f"K11 decisión {n}: la ficha {e['id']} no tiene «{e['contiene']}»")
                elif e.get("campo") and e.get("valor") not in _ruta(f, e["campo"]):
                    falla.append(f"K11 decisión {n}: ficha {e['id']}.{e['campo']} = {_ruta(f, e['campo'])} y la decisión dice {e['valor']}")
                continue
            if t == "cotizacion":
                q = cots.get(e["numero"])
                if q is None:
                    falla.append(f"K11 decisión {n}: no está la cotización {e['numero']}")
                elif e.get("valor") not in _ruta(q, e["campo"]):
                    falla.append(f"K11 decisión {n}: {e['numero']}.{e['campo']} = {_ruta(q, e['campo'])} y la decisión dice {e['valor']}")
                continue
            falla.append(f"K11 decisión {n}: tipo de efecto desconocido «{t}»")
    return falla, aviso


def k12_supuestos(raiz):
    """K12: todo SUPUESTO escrito en reglas_motor o dictados está en datacenter/supuestos."""
    sup = _leer(os.path.join(raiz, "datacenter", "supuestos.json"))
    if sup is None:
        return ["K12 falta datacenter/supuestos (plan cerebro punto 3)"], []
    refs = {s.get("ref") for s in sup.get("lista") or []}
    falla = []
    rm = _leer(os.path.join(raiz, "datacenter", "reglas_motor.json"), {}) or {}
    for grupo in ("reglas", "reglasVistas"):
        for k, v in (rm.get(grupo) or {}).items():
            if isinstance(v, dict) and "SUPUESTO" in str(v.get("fuente") or "") and f"reglas_motor:{k}" not in refs:
                falla.append(f"K12 reglas_motor.{k} es SUPUESTO y no está en datacenter/supuestos")
    dic = _leer(os.path.join(raiz, "datacenter", "dictados.json"), {}) or {}
    ids = {s.get("id") for s in sup.get("lista") or []}
    import re
    for fr in dic.get("frases") or []:
        for sid in re.findall(r"S-[\w-]+", str(fr.get("fuente") or "")):
            if sid not in ids:
                falla.append(f"K12 dictado «{fr.get('rx')}» cita {sid} y no está en supuestos")
        if "SUPUESTO" in str(fr.get("fuente")) and not re.search(r"S-[\w-]+", str(fr.get("fuente"))):
            falla.append(f"K12 dictado «{fr.get('rx')}» es SUPUESTO sin id en supuestos")
    return falla, []


def estado_definicion(q, hoy, de):
    e = norm_estado(q.get("estado"))
    c = de.get("cotizacion") or {}
    if e == "rechazada":
        return "rechazada"
    if e == "borrador":
        return "borrador"
    if e == "aceptada":
        return "aceptada"
    if e in (c.get("abiertos") or ()):
        lim = str(q.get("vence") or "")[:10]      # decisión 108: solo vence da vigencia; sin vence = vencida (RENOVAR)
        return "vencida_sin_estado" if not lim or lim < hoy else "vigente"
    return e


def k13_definiciones(raiz, hoy, sales):
    """K13: definiciones únicas presentes y el Sales Engine da el mismo estado que la definición."""
    de = _leer(os.path.join(raiz, "datacenter", "definiciones.json"))
    if de is None:
        return ["K13 falta datacenter/definiciones (plan cerebro punto 4)"], []
    falla, aviso = [], []
    for k in ("cotizacion", "operacion", "fuentes", "cortes"):
        if k not in de:
            falla.append(f"K13 definiciones sin «{k}»")
    r = rutas(raiz, hoy)
    for fila in (sales or {}).get("filas") or []:
        f = None
        for q in fila.get("cotizaciones") or []:
            if q.get("fuente") != "CRM vivo":
                continue
            v = _leer(os.path.join(r["cot"], q["id"] + ".json"))
            if v is None:
                continue
            esp = estado_definicion(v, hoy, de)
            got = q.get("estadoReal")
            if esp in ("vigente", "vencida_sin_estado") and got in ("vigente", "vencida_sin_estado") and esp != got:   # decisión 108
                falla.append(f"K13 {fila.get('empresa')} {q.get('numero')}: el Sales Engine dice {got} y la definición {esp}")
            if not v.get("vence"):
                aviso.append(f"K13 {fila.get('empresa')} {q.get('numero')}: cotización sin vence: cargarla (sin vence sale RENOVAR, decisión 108)")
    return falla, aviso


def k7_textos(raiz):
    """K7 ampliado: ningún texto que se lee como regla cita versiones (las versiones viven en el manifiesto)."""
    import re
    out = []
    def recorrer(o, ruta):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("version", "codigo", "huellaCodigo") or str(k).startswith("cambios"):
                    continue
                recorrer(v, f"{ruta}.{k}")
        elif isinstance(o, list):
            for i, v in enumerate(o):
                recorrer(v, f"{ruta}[{i}]")
        elif isinstance(o, str):
            m = re.search(RX_VERSION, o)
            if m:
                out.append(f"{ruta}: «…{o[max(0, m.start() - 30):m.end() + 10]}…»")
    for n in DOCS_TEXTO:
        d = _leer(os.path.join(raiz, "datacenter", n + ".json"))
        if d is not None:
            recorrer(d, n)
    si = _leer(os.path.join(raiz, "datacenter", "script_inicio.json"), {}) or {}
    recorrer({"protocolo": si.get("protocolo")}, "script_inicio")
    return out


def cerebro(raiz, hoy, sales):
    """Plan cerebro: K11 efectos, K12 supuestos, K13 definiciones, K7 textos. Devuelve (veredicto, líneas)."""
    falla, aviso = [], []
    for fn in (lambda: k11_efectos(raiz, hoy), lambda: k12_supuestos(raiz), lambda: k13_definiciones(raiz, hoy, sales), lambda: k15_mapa(raiz)):
        f, a = fn()
        falla += f
        aviso += a
    k7 = k7_textos(raiz)
    aviso += [f"K7 versión en texto: {x}" for x in k7[:8]] + ([f"K7 … y {len(k7) - 8} más"] if len(k7) > 8 else [])
    ver = "FALLA" if falla else "PASA"
    L = [f"## Cerebro (K11 efectos · K12 supuestos · K13 definiciones · K15 mapa · K7 textos): {ver}"]
    L += [f"- FALLA {x}" for x in falla[:20]] + [f"- AVISO {x}" for x in aviso]
    return ver, L


def supuestos_resumen(raiz):
    sup = _leer(os.path.join(raiz, "datacenter", "supuestos.json"), {}) or {}
    ls = sup.get("lista") or []
    return [f"## Supuestos vigentes (sin dictado de Nicolás): {len(ls)}"] + [f"- {s['id']}: {s['texto']}" for s in ls]


def resolver_dictado(raiz, frase, hoy):
    import re
    dic = _leer(os.path.join(raiz, "datacenter", "dictados.json"), {}) or {}
    d0 = dt.date.fromisoformat(hoy)
    out = []
    for f in dic.get("frases") or []:
        if re.search(f["rx"], frase, re.I):
            x = f"{f['tipo']}: {f['significado']}"
            rz = f.get("resolver")
            if rz == "lunes_siguiente":
                x += f" → {(d0 + dt.timedelta(days=7 - d0.weekday())).isoformat()}"
            elif rz == "dia_habil_siguiente":
                n = d0 + dt.timedelta(days=1)
                while n.weekday() >= 5:
                    n += dt.timedelta(days=1)
                x += f" → {n.isoformat()}"
            elif rz:
                x += f" → {rz}"
            out.append(x + f" · fuente: {f.get('fuente')}")
    return out


def cmd_dictado(a):
    res = resolver_dictado(a.raiz, " ".join(a.texto), a.hoy)
    print("\n".join(res) if res else "SIN DICTADO: preguntar una vez a Nicolás y sumarlo a datacenter/dictados con su fuente")
    return 0 if res else 2


# ---- escribir: una sola puerta de escritura (punto 6)
COLECCIONES_VIVAS = ("oportunidades", "cotizaciones")
OPS_HZ = {"pago": ("pendiente", "confirmado"), "despacho": ("pendiente", "confirmado", "parcial"),
          "entrega": ("pendiente", "confirmado", "parcial")}


def validar_cambios(raiz, cambios, hoy):
    """Devuelve (fallas, writes). cambios: [{op, collection, doc_id, data, if_version, historialNuevo?}]."""
    import re
    fallas, writes = [], []
    vistos = set()
    for i, c in enumerate(cambios):
        tag = f"#{i} {c.get('collection')}/{c.get('doc_id')}"
        if c.get("op") not in ("set", "update", "delete"):
            fallas.append(f"{tag}: op inválida")
            continue
        clave = (c.get("collection"), c.get("doc_id"))
        if clave in vistos:
            fallas.append(f"{tag}: el mismo documento dos veces en una escritura")
        vistos.add(clave)
        local = os.path.join(raiz, *str(c.get("collection")).split("/"), f"{c.get('doc_id')}.json")
        existe = os.path.exists(local)
        if existe and not isinstance(c.get("if_version"), int):
            fallas.append(f"{tag}: documento existente sin if_version")
        data = dict(c.get("data") or {})
        actual = _leer(local, {}) if existe else {}
        if "historial" in data and c.get("collection") in COLECCIONES_VIVAS:   # copias de motor (stockfish_fichas, manifiesto) se escriben enteras
            fallas.append(f"{tag}: historial no se escribe entero: usar historialNuevo (se suma sin duplicar)")
        if c.get("historialNuevo"):
            prev = list(actual.get("historial") or [])
            ya = {(x.get("t"), x.get("txt")) for x in prev}
            nuevos = []
            for x in c["historialNuevo"]:
                if not re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", str(x.get("t") or "")) or not x.get("txt"):
                    fallas.append(f"{tag}: entrada de historial sin t ISO o sin txt")
                elif (x.get("t"), x.get("txt")) in ya or any(x.get("txt") == y.get("txt") and str(y.get("t"))[:10] == str(x.get("t"))[:10] for y in prev):
                    fallas.append(f"{tag}: historial duplicado «{str(x.get('txt'))[:60]}»")
                else:
                    nuevos.append(x)
            data["historial"] = prev + nuevos
        hz = data.get("hz_operacion")
        if isinstance(hz, dict):
            hz = dict(actual.get("hz_operacion") or {}, **hz)
            data["hz_operacion"] = hz
            for k, vals in OPS_HZ.items():
                if k in hz and hz[k] not in vals:
                    fallas.append(f"{tag}: hz_operacion.{k} = {hz[k]} (vale: {', '.join(vals)})")
            if hz.get("pago") == "confirmado" and not hz.get("pagoAt"):
                fallas.append(f"{tag}: pago confirmado sin pagoAt")
            if hz.get("despacho") == "confirmado" and not hz.get("despachoAt"):
                fallas.append(f"{tag}: despacho confirmado sin despachoAt")
        for k, v in data.items():
            if re.search(r"(fecha|Fecha|vence|At)$", k) and v and not re.match(r"^\d{4}-\d{2}-\d{2}", str(v)):
                fallas.append(f"{tag}: {k} = {v} no es fecha ISO")
        if c.get("collection") == "datacenter" and c.get("doc_id") in DOCS_TEXTO:
            if re.search(RX_VERSION, json.dumps({k: v for k, v in data.items() if k not in ("version",) and not k.startswith("cambios")}, ensure_ascii=False)):
                fallas.append(f"{tag}: texto con número de versión (K7)")
        w = {"op": c["op"], "collection": c["collection"], "doc_id": c["doc_id"]}
        if isinstance(c.get("if_version"), int):
            w["if_version"] = c["if_version"]
        if c["op"] != "delete":
            w["data"] = data
        writes.append(w)
    return fallas, writes


def cmd_escribir(a):
    """Valida un archivo de cambios y deja R/salida/escritura_batch.json para UN ArtifactData batch (file_path por doc)."""
    r = rutas(a.raiz, a.hoy)
    os.makedirs(r["sal"], exist_ok=True)
    cambios = json.load(open(a.cambios, encoding="utf-8"))
    fallas, writes = validar_cambios(a.raiz, cambios, a.hoy)
    if len(writes) > 50:
        fallas.append(f"{len(writes)} escrituras: el batch admite 50")
    if fallas:
        print("ESCRITURA: FALLA (no se escribe nada)\n" + "\n".join("- " + f for f in fallas))
        return 1
    d = os.path.join(r["sal"], "escritura")
    os.makedirs(d, exist_ok=True)
    out = []
    for w in writes:
        if "data" in w:
            p = os.path.join(d, f"{w['collection'].replace('/', '_')}__{w['doc_id']}.json")
            json.dump(w.pop("data"), open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            w["file_path"] = p
        out.append(w)
    json.dump(out, open(os.path.join(r["sal"], "escritura_batch.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"ESCRITURA: PASA · {len(out)} documentos · mandar salida/escritura_batch.json como «writes» de un solo batch")
    return 0


# ---------------------------------------------------------------- v1.6 · HIVE como fuente de stock (solo lectura)
ABIERTOS_COT = ("enviada", "espera_decision", "espera_aprobacion")


def demanda_cotizada(raiz, hoy):
    """Productos de cotizaciones abiertas y de aceptadas sin despachar (no en depósito). -> {clave: {...}}"""
    import unicodedata
    r = rutas(raiz, hoy)
    dep = (_leer(os.path.join(r["dc"], "restricciones.json"), {}) or {}).get("enDeposito") or {}
    n = lambda s: unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode().lower().strip()
    out = {}
    for f in sorted(os.listdir(r["cot"])) if os.path.isdir(r["cot"]) else ():
        q = _leer(os.path.join(r["cot"], f), {}) or {}
        e, hz = norm_estado(q.get("estado")), q.get("hz_operacion") or {}
        abierta = e in ABIERTOS_COT
        entrega = e == "aceptada" and hz.get("despacho") not in ("confirmado",) and q.get("oportunidadId") not in dep \
            and str(q.get("fechaGanada") or q.get("fecha") or "") >= (dt.date.fromisoformat(hoy) - dt.timedelta(days=60)).isoformat()
        if not (abierta or entrega):
            continue
        for it in q.get("items") or []:
            k = str(it.get("codigo") or "").strip() or "n:" + n(it.get("articulo"))
            d = out.setdefault(k, {"codigo": str(it.get("codigo") or ""), "nombre": it.get("articulo"), "cotizado": 0, "aEntregar": 0, "donde": []})
            c = float(it.get("cantidad") or 0)
            d["aEntregar" if entrega else "cotizado"] += c
            d["donde"].append(f"{q.get('numero') or 's/N'} {str(q.get('cliente') or '')[:18]} {c:g}" + (" (a entregar)" if entrega else ""))
    # el mismo producto con código en una cotización y sin código en otra es uno solo (caso 48F: NM22 con 1349, NM48 sin código)
    cod_por_nombre = {n(v["nombre"]): k for k, v in out.items() if v["codigo"]}
    for k in [k for k in out if k.startswith("n:")]:
        dest = cod_por_nombre.get(k[2:])
        if dest:
            v = out.pop(k)
            out[dest]["cotizado"] += v["cotizado"]; out[dest]["aEntregar"] += v["aEntregar"]; out[dest]["donde"] += v["donde"]
    return out


def cmd_productos(a):
    """Lista lo que Claude tiene que consultar en HIVE (consultar_stock) para armar R/hive_stock.json."""
    d = demanda_cotizada(a.raiz, a.hoy)
    for k, v in sorted(d.items(), key=lambda x: str(x[1]["nombre"])):
        print(f"{v['codigo'] or '(sin código: buscar por nombre)'}\t{v['nombre']}")
    print(f"\n{len(d)} productos · guardar con correr_dia escribir en datacenter/hive_stock (desde {os.path.join(a.raiz, 'hive_stock.json')}) "
          '({"corte": <snapshot_fecha>, "bajado": <hoy>, "productos": {"<código>": {"nombre", "stock", "transito", "produccion", "eta"}}, "sinCatalogo": [<nombres>]})')
    return 0


def remitos_desde(raiz, corte, cod_por_nombre):
    """Lo despachado (remitos del reporte 21, netos de devoluciones) DESPUÉS de la foto de HIVE, por código. -> ({cod: cant}, hasta)"""
    import unicodedata
    rdir = os.path.join(raiz, "reportes")
    m = _leer(os.path.join(rdir, "r21.json"))
    if not m or not corte:
        return {}, None
    n = lambda s: unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode().lower().strip()
    f, dic = m["formato"]["f"], m.get("dic") or {}
    filas = list(m["d"])
    for i in range(2, int(m.get("partes", 1)) + 1):
        filas += (_leer(os.path.join(rdir, f"r21_{i}.json"), {}) or {}).get("d") or []
    out = {}
    for x in filas:
        r = dict(zip(f, x))
        for k in ("tipo", "producto"):
            if isinstance(r.get(k), int) and k in dic:
                r[k] = dic[k][r[k]]
        if str(r.get("fecha") or "") <= corte:
            continue
        cod = cod_por_nombre.get(n(r.get("producto")))
        if cod:
            signo = -1 if "devol" in n(r.get("tipo")) else 1
            out[cod] = out.get(cod, 0) + signo * float(r.get("cantidad") or 0)
    return out, m.get("hasta")


def k14_stock(raiz, hoy):
    """K14 (AVISO): lo cotizado + lo que falta entregar contra el stock de HIVE. Sin hive_stock.json: se dice y sigue."""
    import unicodedata
    h = _leer(os.path.join(raiz, "datacenter", "hive_stock.json")) or _leer(os.path.join(raiz, "hive_stock.json"))
    if h is None:
        return ["## Stock HIVE (K14): sin datos · falta datacenter/hive_stock (bajar la foto de HIVE)"]
    n = lambda s: unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode().lower().strip()
    prods = h.get("productos") or {}
    por_nombre = {n(v.get("nombre")): k for k, v in prods.items()}
    sin_cat = {n(x) for x in h.get("sinCatalogo") or []}
    edad = (dt.date.fromisoformat(hoy) - dt.date.fromisoformat(str(h.get("corte"))[:10])).days if h.get("corte") else None
    salio, rem_hasta = remitos_desde(raiz, str(h.get("corte") or "")[:10], {n(v.get("nombre")): k for k, v in prods.items()})
    L, ok, falta = [], 0, []
    for k, d in demanda_cotizada(raiz, hoy).items():
        cod = d["codigo"] or por_nombre.get(n(d["nombre"]))
        s = prods.get(cod) if cod else None
        pedido = d["cotizado"] + d["aEntregar"]
        if s is None:
            falta.append(f"{d['nombre']}: " + ("no está en el catálogo de HIVE" if n(d["nombre"]) in sin_cat else "sin consultar en HIVE") + f" · {'; '.join(d['donde'])}")
            continue
        st = float(s.get("stock") or 0) - salio.get(cod, 0)
        if pedido > st:
            extra = f" · tránsito {float(s.get('transito') or 0):g}" + (f" (llega {s['eta']})" if s.get("eta") else "") + (f" · producción {float(s.get('produccion') or 0):g}" if s.get("produccion") else "")
            L.append(f"- AVISO K14 {d['nombre']}: stock {st:g} y piden {pedido:g} (cotizado {d['cotizado']:g} + a entregar {d['aEntregar']:g}){extra} · {'; '.join(d['donde'])}")
        else:
            ok += 1
    cab = f"## Stock HIVE (K14): {'AVISO' if L else 'PASA'} · foto {h.get('corte')}" + (f" ({edad} días)" if edad is not None else "") \
        + f" menos remitos hasta {rem_hasta or 'sin remitos'} · {ok} alcanzan · {len(L)} no alcanzan · sin reservas (HIVE no las informa)"
    vieja = [f"- AVISO K14 la foto de HIVE tiene {edad} días: mirar si HIVE tiene una más nueva y re-bajarla"] if edad is not None and edad > 7 else []
    return [cab] + vieja + L + [f"- sin dato: {x}" for x in falta[:8]] + ([f"- … y {len(falta) - 8} sin dato más"] if len(falta) > 8 else [])


# ---------------------------------------------------------------- v1.7 · mapa del cerebro: módulos, selector, archivo comprimido
def _modulos(raiz):
    return ((_leer(os.path.join(raiz, "datacenter", "ruteo.json"), {}) or {}).get("modulos")) or {}


def modulo_de(doc_id, modulos):
    import fnmatch
    return [m for m, v in modulos.items() if any(not p.startswith("coleccion:") and fnmatch.fnmatchcase(doc_id, p) for p in v.get("docs") or [])]


def k15_mapa(raiz):
    """K15: cada documento del datacenter pertenece a un solo módulo y cada módulo dice qué es, qué lee y qué produce."""
    mods = _modulos(raiz)
    if not mods:
        return ["K15 ruteo sin modulos (mapa del cerebro)"], []
    falla = [f"K15 módulo {m} sin «{k}»" for m, v in mods.items() for k in ("que", "lee", "produce", "docs") if not v.get(k)]
    dc = os.path.join(raiz, "datacenter")
    for f in sorted(os.listdir(dc)) if os.path.isdir(dc) else ():
        if not f.endswith(".json"):
            continue
        d = f[:-5]
        ms = modulo_de(d, mods)
        if not ms:
            falla.append(f"K15 datacenter/{d} no pertenece a ningún módulo: sumarlo en ruteo.modulos")
        elif len(ms) > 1:
            falla.append(f"K15 datacenter/{d} está en {len(ms)} módulos ({', '.join(ms)}): uno solo")
    return falla, []


def selector(raiz, texto):
    import re, unicodedata
    n = lambda s: unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode().lower()
    r = _leer(os.path.join(raiz, "datacenter", "ruteo.json"), {}) or {}
    t = n(texto)
    return [p for p in r.get("pedidos") or [] if p.get("rx") and re.search(n(p["rx"]), t)]


def cmd_selector(a):
    ps = selector(a.raiz, " ".join(a.texto))
    if not ps:
        print("SIN MÓDULO: preguntarle una vez a Nicolás qué es y sumarlo a ruteo.pedidos (rx, módulo, leer, motor, skill, modelo)")
        return 2
    p = ps[0]
    print(f"PEDIDO: {p['pedido']} · módulo {p.get('modulo')}\nLEER: {'; '.join(p.get('leer') or [])}\nMOTOR: {p.get('motor')}\n"
          f"SKILL: {p.get('skill')} · MODELO: {p.get('modelo')}" + (f"\nFORMATO: {p['formato']}" if p.get("formato") else ""))
    if len(ps) > 1:
        print("También matchea (no actúa): " + ", ".join(x["pedido"] for x in ps[1:]))
    return 0


def empacar(doc):
    """respaldo comprimido: gzip + base64 del JSON canónico, con su huella; desempacar lo devuelve idéntico."""
    import gzip, base64, hashlib
    if isinstance(doc, dict) and doc.get("empaquetado"):
        return doc
    s = json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {"empaquetado": "gzip+base64", "sha256": hashlib.sha256(s).hexdigest(), "bytesOriginal": len(s),
            "nombre": (doc or {}).get("nombre") if isinstance(doc, dict) else None,
            "comoLeer": "python3 -I correr_dia.py desempacar --raiz R <doc_id>", "datos": base64.b64encode(gzip.compress(s, 9)).decode("ascii")}


def desempacar(p):
    import gzip, base64, hashlib
    if not (isinstance(p, dict) and p.get("empaquetado") == "gzip+base64"):
        return p
    s = gzip.decompress(base64.b64decode(p["datos"]))
    if hashlib.sha256(s).hexdigest() != p.get("sha256"):
        raise SystemExit("FALLA: el respaldo no coincide con su huella")
    return json.loads(s)


def cmd_desempacar(a):
    d = desempacar(_leer(os.path.join(a.raiz, "datacenter", a.doc + ".json")))
    out = os.path.join(rutas(a.raiz, None)["sal"], a.doc + ".json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(d, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"desempacado en {out}")
    return 0


CEREBRO_LINEAS = []


def filas(j):
    return {x["id"]: x for x in j["filas"]}


def cmd_comparar(a):
    r = rutas(a.raiz, a.hoy)
    os.makedirs(r["sal"], exist_ok=True)
    conc = os.path.join(r["sal"], "conciliador_hoy.json")
    if a.json_antes:
        antes = json.load(open(a.json_antes))
    else:
        tmp = os.path.join(r["sal"], "sales_antes.json")
        sales(a.raiz, a.hoy, a.codigo_antes, a.reglas_antes or os.path.join(r["dc"], "reglas_motor.json"), conc, tmp)
        antes = json.load(open(tmp))
    des = os.path.join(r["sal"], "sales_despues.json")
    sales(a.raiz, a.hoy, extraer(a.raiz, "sales_engine"), os.path.join(r["dc"], "reglas_motor.json"), conc, des)
    despues = json.load(open(des))
    A, B = filas(antes), filas(despues)
    n = 0
    for k in sorted(set(A) | set(B), key=lambda k: (A.get(k) or B.get(k))["empresa"]):
        x, y = A.get(k), B.get(k)
        if x is None or y is None:
            n += 1; print(f"- {(x or y)['empresa']}: {'nueva' if x is None else 'ya no está'}"); continue
        d = {f: (x.get(f), y.get(f)) for f in ("empujon", "usd", "esperado", "reactivar", "tambien") if x.get(f) != y.get(f)}
        if d:
            n += 1; print(f"- {x['empresa']}: " + json.dumps(d, ensure_ascii=False)[:360])
    ca, cb = antes["control"], despues["control"]
    print(f"\nCAMBIAN {n} de {len(A)} cuentas · elegibles {ca['elegibles']}→{cb['elegibles']} · bloqueadas {ca['bloqueadas']}→{cb['bloqueadas']} · cierra {ca['cierra']}→{cb['cierra']}")
    print("Regla: antes de escribir en el CRM cada cambio de esta lista debe tener explicación; si no, FALLA.")
    return 0


# ---- casos de oro: cuentas reales (comprobantes de la foto del 12/11) con resultado verificado a mano
ORO = json.loads(r'''{"infinitel":{"_id":"r016-infinitel","empresa":"Infinitel","sf_comprobantes":[{"comp":"A-00005-00000009","fecha":"2020-12-10","tipo":"F","bruto":25794,"total":28502.37,"moneda":"USD","anulada":false,"tc":95.233},{"comp":"A-00005-00000002","fecha":"2020-12-30","tipo":"ND","bruto":2192.49,"total":2422.7,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000011","fecha":"2020-12-30","tipo":"NC","bruto":-25794,"total":-28502.37,"moneda":"USD","anulada":false,"tc":95.233},{"comp":"A-00005-00000012","fecha":"2020-12-30","tipo":"NC","bruto":-4394,"total":-4855.37,"moneda":"USD","anulada":false,"tc":95.233},{"comp":"A-00005-00000038","fecha":"2020-12-30","tipo":"F","bruto":30188,"total":33357.74,"moneda":"USD","anulada":false,"tc":95.233},{"comp":"A-00005-00000018","fecha":"2021-01-14","tipo":"NC","bruto":-4200,"total":-4641,"moneda":"USD","anulada":false,"tc":91.03},{"comp":"A-00005-00000058","fecha":"2021-01-14","tipo":"F","bruto":8400,"total":9282,"moneda":"USD","anulada":false,"tc":91.03},{"comp":"A-00005-00000061","fecha":"2021-01-14","tipo":"F","bruto":15326,"total":16935.23,"moneda":"USD","anulada":false,"tc":91.19},{"comp":"A-00005-00000016","fecha":"2021-01-18","tipo":"NDC","bruto":2192.49,"total":2422.7,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000022","fecha":"2021-01-18","tipo":"NC","bruto":-2192.49,"total":-2422.7,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000027","fecha":"2021-01-20","tipo":"NCC","bruto":-304.3,"total":-336.25,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000028","fecha":"2021-01-25","tipo":"NC","bruto":-304.43,"total":-336.4,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000024","fecha":"2021-02-17","tipo":"NDC","bruto":20111.78,"total":22223.52,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000030","fecha":"2021-03-01","tipo":"ND","bruto":20111.78,"total":22223.52,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000033","fecha":"2021-03-01","tipo":"NCC","bruto":-20111.78,"total":-22223.52,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000036","fecha":"2021-03-23","tipo":"NDC","bruto":38791.66,"total":42864.78,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000056","fecha":"2021-04-19","tipo":"NDC","bruto":48033.96,"total":53077.53,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000064","fecha":"2021-05-04","tipo":"NDC","bruto":4490.98,"total":4962.53,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000054","fecha":"2021-06-04","tipo":"NC","bruto":-8788,"total":-9710.74,"moneda":"USD","anulada":false,"tc":95.233},{"comp":"A-00005-00000183","fecha":"2021-06-04","tipo":"F","bruto":8788,"total":9710.74,"moneda":"USD","anulada":true,"tc":95.233},{"comp":"A-00005-00000287","fecha":"2021-11-03","tipo":"F","bruto":2629,"total":2905.05,"moneda":"USD","anulada":true,"tc":105},{"comp":"A-00005-00000092","fecha":"2021-11-12","tipo":"NC","bruto":-2629,"total":-2905.05,"moneda":"USD","anulada":false,"tc":105},{"comp":"A-00005-00000467","fecha":"2022-06-15","tipo":"F","bruto":53.6,"total":59.23,"moneda":"USD","anulada":false,"tc":127.75},{"comp":"A-00005-00000469","fecha":"2022-06-15","tipo":"F","bruto":38,"total":41.99,"moneda":"USD","anulada":false,"tc":127.75},{"comp":"A-00005-00000482","fecha":"2022-06-24","tipo":"F","bruto":56,"total":61.88,"moneda":"USD","anulada":false,"tc":128.75},{"comp":"A-00005-00000126","fecha":"2022-06-29","tipo":"NC","bruto":-38,"total":-41.99,"moneda":"USD","anulada":false,"tc":127.75},{"comp":"A-00005-00000491","fecha":"2022-06-29","tipo":"F","bruto":38038,"total":42031.99,"moneda":"USD","anulada":false,"tc":129.75},{"comp":"A-00005-00000515","fecha":"2022-07-11","tipo":"F","bruto":760,"total":839.8,"moneda":"USD","anulada":false,"tc":134.25},{"comp":"A-00005-00000136","fecha":"2022-07-28","tipo":"NC","bruto":-28,"total":-30.94,"moneda":"USD","anulada":false,"tc":128.75},{"comp":"A-00005-00000137","fecha":"2022-07-28","tipo":"NC","bruto":-26.8,"total":-29.61,"moneda":"USD","anulada":false,"tc":127.75},{"comp":"A-00005-00000325","fecha":"2022-07-29","tipo":"NDC","bruto":57057,"total":63047.98,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000335","fecha":"2022-08-09","tipo":"NDC","bruto":19019,"total":21016,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000145","fecha":"2022-08-19","tipo":"NC","bruto":-53.6,"total":-59.23,"moneda":"USD","anulada":false,"tc":127.75},{"comp":"A-00005-00000146","fecha":"2022-08-19","tipo":"NC","bruto":-28,"total":-30.94,"moneda":"USD","anulada":false,"tc":128.75},{"comp":"A-00005-00000352","fecha":"2022-08-19","tipo":"ND","bruto":26.8,"total":29.61,"moneda":"USD","anulada":false,"tc":127.75},{"comp":"A-00005-00000357","fecha":"2022-08-25","tipo":"NDC","bruto":872.42,"total":964.02,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000366","fecha":"2022-08-29","tipo":"NDC","bruto":116015.9,"total":128197.57,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000385","fecha":"2022-09-19","tipo":"NDC","bruto":34234.2,"total":37828.79,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000391","fecha":"2022-09-27","tipo":"NDC","bruto":174974.8,"total":193347.15,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000394","fecha":"2022-10-03","tipo":"NDC","bruto":11411.4,"total":12609.6,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000407","fecha":"2022-10-12","tipo":"NDC","bruto":22822.8,"total":25219.19,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000417","fecha":"2022-10-28","tipo":"NDC","bruto":241541.3,"total":266903.14,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000440","fecha":"2022-11-23","tipo":"NDC","bruto":74174.1,"total":81962.38,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000715","fecha":"2022-11-23","tipo":"F","bruto":8488.48,"total":9379.77,"moneda":"USD","anulada":false,"tc":171.25},{"comp":"A-00005-00000843","fecha":"2023-03-10","tipo":"F","bruto":45875,"total":50691.88,"moneda":"USD","anulada":false,"tc":235.98},{"comp":"A-00005-00000515","fecha":"2023-03-16","tipo":"NDC","bruto":65371.87,"total":72235.92,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000872","fecha":"2023-03-21","tipo":"F","bruto":9000,"total":9945,"moneda":"USD","anulada":false,"tc":211.75},{"comp":"A-00005-00000875","fecha":"2023-03-23","tipo":"F","bruto":11380.2,"total":12575.12,"moneda":"USD","anulada":false,"tc":227.1075},{"comp":"A-00005-00000526","fecha":"2023-03-28","tipo":"NDC","bruto":15221.01,"total":16819.22,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000905","fecha":"2023-04-18","tipo":"F","bruto":9000,"total":9945,"moneda":"USD","anulada":false,"tc":223},{"comp":"A-00005-00000907","fecha":"2023-04-18","tipo":"F","bruto":5400,"total":5967,"moneda":"USD","anulada":false,"tc":223},{"comp":"A-00005-00000943","fecha":"2023-05-17","tipo":"F","bruto":19632,"total":21693.36,"moneda":"USD","anulada":false,"tc":241},{"comp":"A-00005-00001029","fecha":"2023-07-17","tipo":"F","bruto":27090,"total":29934.45,"moneda":"USD","anulada":false,"tc":315.53},{"comp":"A-00005-00001035","fecha":"2023-07-18","tipo":"F","bruto":9816,"total":10846.68,"moneda":"USD","anulada":false,"tc":279},{"comp":"A-00005-00001039","fecha":"2023-07-19","tipo":"F","bruto":151,"total":182.71,"moneda":"USD","anulada":false,"tc":279.5},{"comp":"A-00005-00001052","fecha":"2023-07-28","tipo":"F","bruto":14520,"total":16044.6,"moneda":"USD","anulada":false,"tc":310.65},{"comp":"A-00005-00001080","fecha":"2023-08-22","tipo":"F","bruto":36564,"total":40403.22,"moneda":"USD","anulada":false,"tc":419.1067},{"comp":"A-00005-00000259","fecha":"2023-08-31","tipo":"NCC","bruto":-709070,"total":-783522.35,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00001084","fecha":"2023-08-31","tipo":"F","bruto":11640,"total":12862.2,"moneda":"USD","anulada":false,"tc":475.15},{"comp":"A-00005-00001142","fecha":"2023-11-17","tipo":"F","bruto":6825.28,"total":7541.93,"moneda":"USD","anulada":false,"tc":369.5},{"comp":"A-00005-00000283","fecha":"2024-01-11","tipo":"NC","bruto":-147,"total":-162.44,"moneda":"USD","anulada":false,"tc":835},{"comp":"A-00005-00001160","fecha":"2024-01-11","tipo":"F","bruto":147,"total":162.44,"moneda":"USD","anulada":true,"tc":835},{"comp":"A-00005-00001185","fecha":"2024-04-09","tipo":"F","bruto":68,"total":75.14,"moneda":"USD","anulada":false,"tc":883.5},{"comp":"A-00005-00000307","fecha":"2024-07-22","tipo":"NCC","bruto":-18486.59,"total":-20427.68,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000376","fecha":"2026-02-05","tipo":"NC","bruto":-4179,"total":-4617.8,"moneda":"USD","anulada":false,"tc":1541.91},{"comp":"A-00005-00001546","fecha":"2026-02-05","tipo":"F","bruto":4179,"total":4617.8,"moneda":"USD","anulada":true,"tc":1541.91},{"comp":"A-00005-00001705","fecha":"2026-10-21","tipo":"F","bruto":8480,"total":9370.4,"moneda":"USD","anulada":false,"tc":1540}],"sf_lineas":[{"fecha":"2020-12-10","comp":"A-00005-00000009","tipo":"NC","items":["500 × Onu Gpon W85460HG 5DB [China Mobile]","100 × Onu Gpon WH81450V5EG [China Mobile]"]},{"fecha":"2020-12-30","comp":"A-00005-00000011","tipo":"NC","items":["-500 × Onu Gpon W85460HG 5DB [China Mobile]","-100 × Onu Gpon WH81450V5EG [China Mobile]"]},{"fecha":"2020-12-30","comp":"A-00005-00000038","tipo":"F","items":["500 × Onu Gpon W85460HG 5DB [China Mobile]","100 × Onu Gpon WH81450V5EG [China Mobile]"]},{"fecha":"2021-01-14","comp":"A-00005-00000061","tipo":"F","items":["970 × Onu Gpon B83100HG [China Mobile]"]},{"fecha":"2022-06-15","comp":"A-00005-00000467","tipo":"F","items":["2 × Onu Gpon F660 [Zte]"]},{"fecha":"2022-06-15","comp":"A-00005-00000469","tipo":"F","items":["1 × Onu Gpon F673A V6 [Zte]"]},{"fecha":"2022-06-21","comp":"A-00012-00000211","tipo":"F","items":["1 × Onu Gpon IC425ETB [I-con]"]},{"fecha":"2022-06-24","comp":"A-00005-00000482","tipo":"F","items":["2 × Onu Gpon F660 V8.0 [Zte]"]},{"fecha":"2022-06-29","comp":"A-00005-00000126","tipo":"NC","items":["-1 × Onu Gpon F673A V6 [Zte]"]},{"fecha":"2022-06-29","comp":"A-00005-00000491","tipo":"F","items":["1001 × Onu Gpon F673A V6 [Zte]"]},{"fecha":"2022-07-11","comp":"A-00005-00000515","tipo":"F","items":["20 × Onu Gpon F673A V6 [Zte]"]},{"fecha":"2022-07-28","comp":"A-00005-00000136","tipo":"NC","items":["-1 × Onu Gpon F660 V8.0 [Zte]"]},{"fecha":"2022-07-28","comp":"A-00005-00000137","tipo":"NC","items":["-1 × Onu Gpon F660 [Zte]"]},{"fecha":"2022-07-28","comp":"A-00012-00000044","tipo":"NC","items":["-1 × Onu Gpon IC425ETB [I-con]"]},{"fecha":"2022-08-19","comp":"A-00005-00000145","tipo":"NC","items":["-2 × Onu Gpon F660 [Zte]"]},{"fecha":"2022-08-19","comp":"A-00005-00000146","tipo":"NC","items":["-1 × Onu Gpon F660 V8.0 [Zte]"]},{"fecha":"2022-08-19","comp":"A-00005-00000352","tipo":"ND","items":["1 × Onu Gpon F660 [Zte]"]},{"fecha":"2022-11-23","comp":"A-00005-00000715","tipo":"F","items":["154 × Onu Gpon F673A V6 [Zte]"]},{"fecha":"2023-03-10","comp":"A-00005-00000843","tipo":"F","items":["750 × Onu Gpon F660 V6.0 [Zte]","200 × Onu Gpon F660 V8.0 [Zte]","200 × Onu Gpon F673A V9 [Zte]"]},{"fecha":"2023-03-21","comp":"A-00005-00000872","tipo":"F","items":["100 × Ont Gpon HG8245H5 [Huawei]"]},{"fecha":"2023-03-23","comp":"A-00005-00000875","tipo":"F","items":["390 × Onu Gpon IC435ETR [I-con]"]},{"fecha":"2023-04-18","comp":"A-00005-00000905","tipo":"F","items":["100 × Ont Gpon HG8245H5 [Huawei]"]},{"fecha":"2023-04-18","comp":"A-00005-00000907","tipo":"F","items":["60 × Ont Gpon HG8245H5 [Huawei]"]},{"fecha":"2023-05-17","comp":"A-00005-00000943","tipo":"F","items":["200 × Ont Gpon HG8245H5 [Huawei]"]},{"fecha":"2023-06-08","comp":"A-00012-00000470","tipo":"F","items":["700 × Onu Gpon F660 V6.0 [Zte]","300 × Onu Gpon F673A V9 [Zte]"]},{"fecha":"2023-07-17","comp":"A-00005-00001029","tipo":"F","items":["600 × Onu Gpon F660 V6.0 [Zte]"]},{"fecha":"2023-07-18","comp":"A-00005-00001035","tipo":"F","items":["100 × Ont Gpon HG8245H5 [Huawei]"]},{"fecha":"2024-04-09","comp":"A-00005-00001185","tipo":"F","items":["2 × Onu Gpon IC445ETRF [I-con]"]},{"fecha":"2026-02-05","comp":"A-00005-00000376","tipo":"NC","items":["-1194 × Onu Gpon IC435ETR [I-con]"]},{"fecha":"2026-02-05","comp":"A-00005-00001546","tipo":"F","items":["1194 × Onu Gpon IC435ETR [I-con]"]}],"sf_cotizaciones":[],"etapa":"ganado"},"monica":{"_id":"q-monica-beatriz-martinez","empresa":"Mónica Beatriz Martínez","sf_comprobantes":[{"comp":"A-00005-00000113","fecha":"2022-03-28","tipo":"NC","bruto":-879,"total":-971.3,"moneda":"USD","anulada":false,"tc":115.5},{"comp":"A-00005-00000390","fecha":"2022-03-28","tipo":"F","bruto":1030,"total":1138.15,"moneda":"USD","anulada":false,"tc":115.5},{"comp":"A-00005-00000443","fecha":"2022-05-17","tipo":"F","bruto":4600,"total":5083,"moneda":"USD","anulada":false,"tc":123},{"comp":"A-00005-00000474","fecha":"2022-06-22","tipo":"F","bruto":5600,"total":6188,"moneda":"USD","anulada":false,"tc":128.5},{"comp":"A-00005-00000293","fecha":"2022-06-28","tipo":"NDC","bruto":7000,"total":7735,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000514","fecha":"2022-07-08","tipo":"F","bruto":1030,"total":1138.15,"moneda":"USD","anulada":false,"tc":133.25},{"comp":"A-00005-00000540","fecha":"2022-07-28","tipo":"F","bruto":990,"total":1093.95,"moneda":"USD","anulada":false,"tc":137.25},{"comp":"A-00005-00000543","fecha":"2022-07-29","tipo":"F","bruto":6508,"total":7191.34,"moneda":"USD","anulada":false,"tc":137.25},{"comp":"A-00005-00000572","fecha":"2022-08-17","tipo":"F","bruto":1479,"total":1634.3,"moneda":"USD","anulada":false,"tc":141.75},{"comp":"A-00005-00000365","fecha":"2022-08-29","tipo":"NDC","bruto":16812.33,"total":18577.63,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000384","fecha":"2022-09-19","tipo":"NDC","bruto":9762,"total":10787.01,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000390","fecha":"2022-09-27","tipo":"NDC","bruto":33624.67,"total":37155.26,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000395","fecha":"2022-10-03","tipo":"NDC","bruto":3254,"total":3595.67,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000418","fecha":"2022-10-28","tipo":"NDC","bruto":52606.33,"total":58130,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000169","fecha":"2022-10-31","tipo":"NC","bruto":-6508,"total":-7191.34,"moneda":"USD","anulada":false,"tc":137.25},{"comp":"A-00005-00000677","fecha":"2022-10-31","tipo":"F","bruto":4160,"total":4596.8,"moneda":"USD","anulada":false,"tc":161.5},{"comp":"A-00005-00000728","fecha":"2022-11-30","tipo":"F","bruto":1260,"total":1392.3,"moneda":"USD","anulada":false,"tc":174.25},{"comp":"A-00005-00000185","fecha":"2022-12-05","tipo":"NCC","bruto":-173547.67,"total":-191770.18,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00001010","fecha":"2023-06-29","tipo":"F","bruto":1724,"total":1905.02,"moneda":"USD","anulada":false,"tc":267},{"comp":"A-00005-00000584","fecha":"2023-07-07","tipo":"NDC","bruto":48004.78,"total":53045.28,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00001026","fecha":"2023-07-11","tipo":"F","bruto":8697,"total":9610.19,"moneda":"USD","anulada":false,"tc":306.2048},{"comp":"A-00005-00001085","fecha":"2023-09-05","tipo":"F","bruto":2742,"total":3029.91,"moneda":"USD","anulada":false,"tc":411.1875},{"comp":"A-00005-00000649","fecha":"2023-12-01","tipo":"NDC","bruto":18394.25,"total":20325.65,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000650","fecha":"2023-12-01","tipo":"NDC","bruto":159352.59,"total":176084.61,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00001188","fecha":"2024-04-17","tipo":"F","bruto":2280,"total":2519.4,"moneda":"USD","anulada":false,"tc":1030.08},{"comp":"A-00005-00000308","fecha":"2024-07-26","tipo":"NC","bruto":-281.41,"total":-310.96,"moneda":"USD","anulada":false,"tc":949.5},{"comp":"A-00005-00000702","fecha":"2024-07-26","tipo":"NDC","bruto":72254.42,"total":79841.13,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00001248","fecha":"2024-07-26","tipo":"F","bruto":12480,"total":13790.4,"moneda":"USD","anulada":false,"tc":949.5},{"comp":"A-00005-00000703","fecha":"2024-07-30","tipo":"NDC","bruto":106468.86,"total":117648.09,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00001274","fecha":"2024-09-13","tipo":"F","bruto":3907.2,"total":4317.46,"moneda":"USD","anulada":false,"tc":980.5},{"comp":"A-00005-00001285","fecha":"2024-09-25","tipo":"F","bruto":680,"total":751.4,"moneda":"USD","anulada":false,"tc":986.5},{"comp":"A-00005-00000313","fecha":"2024-09-26","tipo":"NC","bruto":-3069,"total":-3391.25,"moneda":"USD","anulada":false,"tc":988.5},{"comp":"A-00005-00000719","fecha":"2024-10-03","tipo":"NDC","bruto":189611.45,"total":209520.65,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00001313","fecha":"2024-12-16","tipo":"F","bruto":490,"total":541.45,"moneda":"USD","anulada":false,"tc":1040.5},{"comp":"A-00005-00001318","fecha":"2024-12-20","tipo":"F","bruto":2040,"total":2254.2,"moneda":"USD","anulada":false,"tc":1105},{"comp":"A-00005-00001319","fecha":"2024-12-20","tipo":"F","bruto":171,"total":206.91,"moneda":"USD","anulada":false,"tc":1044.5},{"comp":"A-00005-00000348","fecha":"2025-08-08","tipo":"NC","bruto":-490,"total":-541.45,"moneda":"USD","anulada":false,"tc":1040.5},{"comp":"A-00005-00001663","fecha":"2026-08-27","tipo":"F","bruto":3000,"total":3315,"moneda":"USD","anulada":false,"tc":1580.63},{"comp":"A-00005-00001668","fecha":"2026-09-03","tipo":"F","bruto":1275,"total":1408.88,"moneda":"USD","anulada":false,"tc":1535},{"comp":"A-00005-00001674","fecha":"2026-09-09","tipo":"F","bruto":114.52,"total":138.57,"moneda":"USD","anulada":false,"tc":1530.0152},{"comp":"A-00005-00001680","fecha":"2026-09-18","tipo":"F","bruto":123.62,"total":149.58,"moneda":"USD","anulada":false,"tc":1535}],"sf_lineas":[{"fecha":"2022-11-30","comp":"A-00005-00000728","tipo":"F","items":["30 × Onu Gpon IC405WSG [I-con]"]},{"fecha":"2024-07-26","comp":"A-00005-00001248","tipo":"F","items":["100 × Onu Gpon HG8245H5 [Huawei]"]},{"fecha":"2024-09-13","comp":"A-00005-00001274","tipo":"F","items":["60 × Onu Gpon EG8145V5 [Huawei]"]},{"fecha":"2024-09-26","comp":"A-00005-00000313","tipo":"NC","items":["-99 × Onu Gpon HG8245H5 [Huawei]"]},{"fecha":"2024-12-16","comp":"A-00005-00001313","tipo":"F","items":["35 × Onu Xpon WK-3801-D [Wolk]"]},{"fecha":"2025-08-08","comp":"A-00005-00000348","tipo":"NC","items":["-35 × Onu Xpon WK-3801-D [Wolk]"]},{"fecha":"2026-09-03","comp":"A-00005-00001668","tipo":"F","items":["50 × Ont Gpon HG6543D [FiberHome]"]}],"sf_cotizaciones":[],"etapa":"ganado"},"sol":{"_id":"w-sol-informaticas","empresa":"Sol-Informaticas","sf_comprobantes":[{"comp":"A-00005-00001334","fecha":"2025-02-04","tipo":"F","bruto":980,"total":1082.9,"moneda":"USD","anulada":false,"tc":1106.22},{"comp":"A-00005-00001356","fecha":"2025-03-21","tipo":"F","bruto":490,"total":541.45,"moneda":"USD","anulada":false,"tc":1127.63},{"comp":"A-00005-00001369","fecha":"2025-04-10","tipo":"F","bruto":490,"total":541.45,"moneda":"USD","anulada":false,"tc":1139.84},{"comp":"A-00005-00001383","fecha":"2025-05-06","tipo":"F","bruto":490,"total":541.45,"moneda":"USD","anulada":false,"tc":1293.2},{"comp":"A-00005-00001404","fecha":"2025-06-24","tipo":"F","bruto":350,"total":386.75,"moneda":"USD","anulada":false,"tc":1273.3},{"comp":"A-00005-00001427","fecha":"2025-07-22","tipo":"F","bruto":350,"total":386.75,"moneda":"USD","anulada":false,"tc":1391},{"comp":"A-00005-00001438","fecha":"2025-08-14","tipo":"F","bruto":350,"total":386.75,"moneda":"USD","anulada":false,"tc":1325},{"comp":"A-00005-00000761","fecha":"2025-08-25","tipo":"NDC","bruto":32462.49,"total":35871.05,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00001457","fecha":"2025-09-09","tipo":"F","bruto":350,"total":386.75,"moneda":"USD","anulada":false,"tc":1464.13},{"comp":"A-00005-00000351","fecha":"2025-09-15","tipo":"NCC","bruto":-5185.76,"total":-5730.27,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000358","fecha":"2025-10-14","tipo":"NC","bruto":-350,"total":-386.75,"moneda":"USD","anulada":false,"tc":1375.78},{"comp":"A-00005-00001478","fecha":"2025-10-14","tipo":"F","bruto":350,"total":386.75,"moneda":"USD","anulada":true,"tc":1532.78},{"comp":"A-00005-00001481","fecha":"2025-10-16","tipo":"F","bruto":350,"total":386.75,"moneda":"USD","anulada":false,"tc":1532.78},{"comp":"A-00005-00001485","fecha":"2025-11-05","tipo":"F","bruto":350,"total":386.75,"moneda":"USD","anulada":false,"tc":1663.2},{"comp":"A-00005-00001507","fecha":"2025-11-27","tipo":"F","bruto":560,"total":618.8,"moneda":"USD","anulada":false,"tc":1519.25},{"comp":"A-00005-00000364","fecha":"2025-12-23","tipo":"NC","bruto":-560,"total":-618.8,"moneda":"USD","anulada":false,"tc":1475},{"comp":"A-00005-00001520","fecha":"2025-12-23","tipo":"F","bruto":560,"total":618.8,"moneda":"USD","anulada":true,"tc":1475},{"comp":"A-00005-00001521","fecha":"2025-12-23","tipo":"F","bruto":560,"total":618.8,"moneda":"USD","anulada":false,"tc":1519.25},{"comp":"A-00005-00001551","fecha":"2026-02-24","tipo":"F","bruto":560,"total":618.8,"moneda":"USD","anulada":false,"tc":1418.5},{"comp":"A-00005-00001576","fecha":"2026-04-06","tipo":"F","bruto":560,"total":618.8,"moneda":"USD","anulada":false,"tc":1415},{"comp":"A-00005-00001604","fecha":"2026-05-19","tipo":"F","bruto":560,"total":618.8,"moneda":"USD","anulada":false,"tc":1420},{"comp":"A-00005-00001640","fecha":"2026-07-23","tipo":"F","bruto":560,"total":618.8,"moneda":"USD","anulada":false,"tc":1510},{"comp":"A-00005-00001699","fecha":"2026-10-19","tipo":"F","bruto":560,"total":618.8,"moneda":"USD","anulada":false,"tc":1540}],"sf_lineas":[{"fecha":"2025-02-04","comp":"A-00005-00001334","tipo":"F","items":["20 × Ont Gpon HG6145F3 [FiberHome]"]},{"fecha":"2025-03-21","comp":"A-00005-00001356","tipo":"F","items":["10 × Ont Gpon HG6145F3 [FiberHome]"]},{"fecha":"2025-04-10","comp":"A-00005-00001369","tipo":"F","items":["10 × Ont Gpon HG6145F3 [FiberHome]"]},{"fecha":"2025-05-06","comp":"A-00005-00001383","tipo":"F","items":["10 × Ont Gpon HG6145F3 [FiberHome]"]},{"fecha":"2025-06-24","comp":"A-00005-00001404","tipo":"F","items":["10 × Ont Gpon HG6543D [FiberHome]"]},{"fecha":"2025-07-22","comp":"A-00005-00001427","tipo":"F","items":["10 × Ont Gpon HG6543D [FiberHome]"]},{"fecha":"2025-08-14","comp":"A-00005-00001438","tipo":"F","items":["10 × Ont Gpon HG6543D [FiberHome]"]},{"fecha":"2025-09-09","comp":"A-00005-00001457","tipo":"F","items":["10 × Ont Gpon HG6543D [FiberHome]"]},{"fecha":"2025-10-16","comp":"A-00005-00001481","tipo":"F","items":["10 × Ont Gpon HG6543D [FiberHome]"]},{"fecha":"2025-11-05","comp":"A-00005-00001485","tipo":"F","items":["10 × Ont Gpon HG6543D [FiberHome]"]},{"fecha":"2025-11-27","comp":"A-00005-00001507","tipo":"F","items":["20 × Ont Gpon HG6543D [FiberHome]"]},{"fecha":"2025-12-23","comp":"A-00005-00001521","tipo":"F","items":["20 × Ont Gpon HG6543D [FiberHome]"]},{"fecha":"2026-02-24","comp":"A-00005-00001551","tipo":"F","items":["20 × Ont Gpon HG6145F3 [FiberHome]"]},{"fecha":"2026-04-06","comp":"A-00005-00001576","tipo":"F","items":["20 × Ont Gpon HG6543D [FiberHome]"]},{"fecha":"2026-05-19","comp":"A-00005-00001604","tipo":"F","items":["20 × Ont Gpon HG6543D [FiberHome]"]},{"fecha":"2026-07-23","comp":"A-00005-00001640","tipo":"F","items":["20 × Ont Gpon HG6543D [FiberHome]"]},{"fecha":"2026-10-19","comp":"A-00005-00001699","tipo":"F","items":["20 × Ont Gpon HG6543D [FiberHome]"]}],"sf_cotizaciones":[],"etapa":"ganado"},"fullsat":{"_id":"r088-fullsat-internet","empresa":"Fullsat Internet","sf_comprobantes":[{"comp":"A-00005-00001470","fecha":"2025-09-25","tipo":"F","bruto":4850,"total":5359.25,"moneda":"USD","anulada":false,"tc":1360},{"comp":"A-00005-00001482","fecha":"2025-10-21","tipo":"F","bruto":4850,"total":5359.25,"moneda":"USD","anulada":false,"tc":1495},{"comp":"A-00005-00000769","fecha":"2025-10-23","tipo":"NDC","bruto":97000,"total":107185,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00001505","fecha":"2025-11-21","tipo":"F","bruto":4850,"total":5359.25,"moneda":"USD","anulada":false,"tc":1450},{"comp":"A-00005-00001695","fecha":"2026-10-15","tipo":"F","bruto":10950,"total":12099.75,"moneda":"USD","anulada":true,"tc":1535},{"comp":"A-00005-00000406","fecha":"2026-10-20","tipo":"NC","bruto":-10950,"total":-12099.75,"moneda":"USD","anulada":false,"tc":1535},{"comp":"A-00005-00001702","fecha":"2026-10-20","tipo":"F","bruto":10950,"total":12099.75,"moneda":"USD","anulada":false,"tc":1535}],"sf_lineas":[{"fecha":"2025-09-25","comp":"A-00005-00001470","tipo":"F","items":["200 × Ont Gpon HG6543D [FiberHome]"]},{"fecha":"2025-10-21","comp":"A-00005-00001482","tipo":"F","items":["200 × Ont Gpon HG6543D [FiberHome]"]},{"fecha":"2025-11-21","comp":"A-00005-00001505","tipo":"AJ","items":["0 × Descuento Contado (Iva 10,5%) [-]","200 × Ont Gpon HG6543D [FiberHome]"]},{"fecha":"2026-10-15","comp":"A-00005-00001695","tipo":"F","items":["300 × Ont Gpon HG6145F3 [FiberHome]"]},{"fecha":"2026-10-20","comp":"A-00005-00000406","tipo":"NC","items":["-300 × Ont Gpon HG6145F3 [FiberHome]"]},{"fecha":"2026-10-20","comp":"A-00005-00001702","tipo":"F","items":["300 × Ont Gpon HG6145F3 [FiberHome]"]}],"sf_cotizaciones":[],"etapa":"cotizado"},"frappa":{"_id":"w-frappa-gretix","empresa":"Frappa Gretix","sf_comprobantes":[{"comp":"A-00005-00000104","fecha":"2021-03-04","tipo":"F","bruto":3290,"total":3635.45,"moneda":"USD","anulada":false,"tc":95.75},{"comp":"A-00005-00000170","fecha":"2021-05-26","tipo":"F","bruto":3318,"total":3666.39,"moneda":"USD","anulada":false,"tc":105.1023},{"comp":"A-00005-00000202","fecha":"2021-07-02","tipo":"F","bruto":3318,"total":3666.39,"moneda":"USD","anulada":false,"tc":100.75},{"comp":"A-00005-00000204","fecha":"2021-07-07","tipo":"F","bruto":6400,"total":7072,"moneda":"USD","anulada":false,"tc":101},{"comp":"A-00005-00000095","fecha":"2021-07-08","tipo":"NDC","bruto":829.5,"total":916.6,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000071","fecha":"2021-08-06","tipo":"NCC","bruto":-187.31,"total":-206.98,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000112","fecha":"2021-08-06","tipo":"NDC","bruto":6400,"total":7072,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000080","fecha":"2021-09-29","tipo":"NC","bruto":-3318,"total":-3666.39,"moneda":"USD","anulada":false,"tc":103.75},{"comp":"A-00005-00000081","fecha":"2021-09-29","tipo":"NC","bruto":-6400,"total":-7072,"moneda":"USD","anulada":false,"tc":103.75},{"comp":"A-00005-00000241","fecha":"2021-09-29","tipo":"F","bruto":5850,"total":6464.25,"moneda":"USD","anulada":false,"tc":103.75},{"comp":"A-00005-00000242","fecha":"2021-09-29","tipo":"F","bruto":3318,"total":3666.39,"moneda":"USD","anulada":true,"tc":103.75},{"comp":"A-00005-00000243","fecha":"2021-09-29","tipo":"F","bruto":6400,"total":7072,"moneda":"USD","anulada":true,"tc":103.75},{"comp":"A-00005-00000252","fecha":"2021-10-06","tipo":"F","bruto":2310,"total":2552.55,"moneda":"USD","anulada":false,"tc":104.25},{"comp":"A-00005-00000156","fecha":"2021-10-29","tipo":"NDC","bruto":2437.5,"total":2693.44,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000284","fecha":"2021-10-29","tipo":"F","bruto":27960,"total":30895.8,"moneda":"USD","anulada":false,"tc":105},{"comp":"A-00005-00000158","fecha":"2021-11-03","tipo":"NDC","bruto":205506,"total":227084.13,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000163","fecha":"2021-11-05","tipo":"NDC","bruto":770,"total":850.85,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000173","fecha":"2021-11-29","tipo":"NDC","bruto":3900,"total":4309.5,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000176","fecha":"2021-12-02","tipo":"NDC","bruto":890.4,"total":1077.38,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000180","fecha":"2021-12-07","tipo":"NDC","bruto":962.5,"total":1063.56,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000181","fecha":"2021-12-07","tipo":"NDC","bruto":770,"total":850.85,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000312","fecha":"2021-12-14","tipo":"F","bruto":4172.4,"total":4610.5,"moneda":"USD","anulada":false,"tc":106.75},{"comp":"A-00005-00000201","fecha":"2022-01-14","tipo":"NDC","bruto":2781.6,"total":3073.67,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000206","fecha":"2022-01-26","tipo":"NDC","bruto":125.71,"total":138.91,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000104","fecha":"2022-02-01","tipo":"NCC","bruto":-890.4,"total":-1077.38,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000212","fecha":"2022-02-01","tipo":"NDC","bruto":975,"total":1077.38,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000217","fecha":"2022-02-14","tipo":"NDC","bruto":6954,"total":7684.17,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000355","fecha":"2022-02-22","tipo":"F","bruto":2692,"total":2974.66,"moneda":"USD","anulada":false,"tc":112.5},{"comp":"A-00005-00000370","fecha":"2022-03-10","tipo":"F","bruto":8076,"total":8923.98,"moneda":"USD","anulada":false,"tc":125.4},{"comp":"A-00005-00000377","fecha":"2022-03-14","tipo":"F","bruto":7593.64,"total":8390.97,"moneda":"USD","anulada":true,"tc":114},{"comp":"A-00005-00000230","fecha":"2022-03-15","tipo":"NDC","bruto":10431,"total":11526.26,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000111","fecha":"2022-03-16","tipo":"NC","bruto":-7593.64,"total":-8390.97,"moneda":"USD","anulada":false,"tc":114},{"comp":"A-00005-00000392","fecha":"2022-03-31","tipo":"F","bruto":105.91,"total":117.03,"moneda":"USD","anulada":false,"tc":116},{"comp":"A-00005-00000428","fecha":"2022-05-06","tipo":"F","bruto":11855.64,"total":13100.48,"moneda":"USD","anulada":false,"tc":121.25},{"comp":"A-00005-00000444","fecha":"2022-05-20","tipo":"F","bruto":760,"total":839.8,"moneda":"USD","anulada":false,"tc":123.75},{"comp":"A-00005-00000449","fecha":"2022-05-26","tipo":"F","bruto":4295,"total":4745.98,"moneda":"USD","anulada":false,"tc":136.675},{"comp":"A-00005-00000454","fecha":"2022-05-31","tipo":"F","bruto":2334,"total":2579.07,"moneda":"USD","anulada":false,"tc":125.25},{"comp":"A-00005-00000287","fecha":"2022-06-14","tipo":"NDC","bruto":2334,"total":2579.07,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000468","fecha":"2022-06-15","tipo":"F","bruto":2723,"total":3008.92,"moneda":"USD","anulada":false,"tc":141.8025},{"comp":"A-00005-00000475","fecha":"2022-06-22","tipo":"F","bruto":1520,"total":1679.6,"moneda":"USD","anulada":false,"tc":128.5},{"comp":"A-00005-00000125","fecha":"2022-06-23","tipo":"NC","bruto":-1166.4,"total":-1288.87,"moneda":"USD","anulada":false,"tc":128.5},{"comp":"A-00005-00000476","fecha":"2022-06-23","tipo":"F","bruto":1166.4,"total":1288.87,"moneda":"USD","anulada":true,"tc":128.5},{"comp":"A-00005-00000477","fecha":"2022-06-23","tipo":"F","bruto":1166.4,"total":1288.87,"moneda":"USD","anulada":false,"tc":142.635},{"comp":"A-00005-00000297","fecha":"2022-06-28","tipo":"NDC","bruto":0.24,"total":0.26,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000298","fecha":"2022-06-28","tipo":"NDC","bruto":1900,"total":2099.5,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000505","fecha":"2022-07-05","tipo":"F","bruto":5236,"total":5785.78,"moneda":"USD","anulada":false,"tc":151.5125},{"comp":"A-00005-00000534","fecha":"2022-07-20","tipo":"F","bruto":804,"total":888.42,"moneda":"USD","anulada":false,"tc":135.75},{"comp":"A-00005-00000542","fecha":"2022-07-28","tipo":"F","bruto":2664,"total":2943.72,"moneda":"USD","anulada":false,"tc":150.975},{"comp":"A-00005-00000555","fecha":"2022-08-09","tipo":"F","bruto":550,"total":607.75,"moneda":"USD","anulada":false,"tc":140},{"comp":"A-00005-00000337","fecha":"2022-08-10","tipo":"NDC","bruto":8058.61,"total":8904.76,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000596","fecha":"2022-08-25","tipo":"F","bruto":4673.64,"total":5164.37,"moneda":"USD","anulada":false,"tc":149.76},{"comp":"A-00005-00000597","fecha":"2022-08-25","tipo":"F","bruto":629.8,"total":695.93,"moneda":"USD","anulada":false,"tc":144},{"comp":"A-00005-00000361","fecha":"2022-08-26","tipo":"NDC","bruto":927.29,"total":1024.66,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000598","fecha":"2022-08-26","tipo":"F","bruto":4275.6,"total":4724.54,"moneda":"USD","anulada":false,"tc":150.02},{"comp":"A-00005-00000370","fecha":"2022-08-31","tipo":"NDC","bruto":3335.07,"total":3685.25,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000609","fecha":"2022-09-01","tipo":"F","bruto":596,"total":658.58,"moneda":"USD","anulada":false,"tc":145},{"comp":"A-00005-00000375","fecha":"2022-09-08","tipo":"NDC","bruto":894,"total":987.87,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000635","fecha":"2022-09-22","tipo":"F","bruto":345.16,"total":381.4,"moneda":"USD","anulada":false,"tc":150.75},{"comp":"A-00005-00000637","fecha":"2022-09-22","tipo":"F","bruto":13417.6,"total":14826.45,"moneda":"USD","anulada":true,"tc":150.75},{"comp":"A-00005-00000640","fecha":"2022-09-22","tipo":"F","bruto":9524.8,"total":10524.9,"moneda":"USD","anulada":false,"tc":171.385},{"comp":"A-00005-00000641","fecha":"2022-09-22","tipo":"F","bruto":4800,"total":5304,"moneda":"USD","anulada":false,"tc":163.08},{"comp":"A-00005-00000160","fecha":"2022-09-23","tipo":"NC","bruto":-13417.6,"total":-14826.45,"moneda":"USD","anulada":false,"tc":150.75},{"comp":"A-00005-00000699","fecha":"2022-11-08","tipo":"F","bruto":2028.07,"total":2241.02,"moneda":"USD","anulada":false,"tc":166},{"comp":"A-00005-00000749","fecha":"2022-12-22","tipo":"F","bruto":3422.4,"total":3781.75,"moneda":"USD","anulada":false,"tc":180.5},{"comp":"A-00005-00000464","fecha":"2022-12-23","tipo":"NDC","bruto":30887.48,"total":34130.66,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000767","fecha":"2023-01-16","tipo":"F","bruto":7973,"total":8810.17,"moneda":"USD","anulada":false,"tc":201.9625},{"comp":"A-00005-00000479","fecha":"2023-01-24","tipo":"NDC","bruto":4228.27,"total":4672.24,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000781","fecha":"2023-01-26","tipo":"F","bruto":3455.8,"total":3818.66,"moneda":"USD","anulada":false,"tc":191.5},{"comp":"A-00005-00000783","fecha":"2023-01-30","tipo":"F","bruto":5335.05,"total":5895.23,"moneda":"USD","anulada":false,"tc":205.7075},{"comp":"A-00005-00000201","fecha":"2023-02-03","tipo":"NC","bruto":-345.16,"total":-381.4,"moneda":"USD","anulada":false,"tc":195},{"comp":"A-00005-00000796","fecha":"2023-02-03","tipo":"F","bruto":2970,"total":3281.85,"moneda":"USD","anulada":false,"tc":195},{"comp":"A-00005-00000484","fecha":"2023-02-07","tipo":"NDC","bruto":35891.61,"total":39660.23,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000848","fecha":"2023-03-13","tipo":"F","bruto":4720,"total":5215.6,"moneda":"USD","anulada":false,"tc":207},{"comp":"A-00005-00000859","fecha":"2023-03-14","tipo":"F","bruto":764,"total":844.22,"moneda":"USD","anulada":false,"tc":208.25},{"comp":"A-00005-00000523","fecha":"2023-03-22","tipo":"NDC","bruto":2674,"total":2954.77,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000934","fecha":"2023-05-10","tipo":"F","bruto":1548,"total":1710.54,"moneda":"USD","anulada":false,"tc":237},{"comp":"A-00005-00000989","fecha":"2023-06-15","tipo":"F","bruto":2820,"total":3116.1,"moneda":"USD","anulada":false,"tc":257},{"comp":"A-00005-00000576","fecha":"2023-06-28","tipo":"NDC","bruto":25380,"total":28044.9,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00001008","fecha":"2023-06-29","tipo":"F","bruto":2155,"total":2381.28,"moneda":"USD","anulada":false,"tc":267},{"comp":"A-00005-00000247","fecha":"2023-07-25","tipo":"NC","bruto":-2155,"total":-2381.28,"moneda":"USD","anulada":false,"tc":267},{"comp":"A-00005-00000602","fecha":"2023-07-27","tipo":"NDC","bruto":25380,"total":28044.9,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000629","fecha":"2023-09-13","tipo":"NDC","bruto":6218.1,"total":6871,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00001204","fecha":"2024-05-17","tipo":"F","bruto":9116,"total":10073.18,"moneda":"USD","anulada":false,"tc":905.5},{"comp":"A-00005-00001222","fecha":"2024-06-11","tipo":"F","bruto":479,"total":529.3,"moneda":"USD","anulada":false,"tc":921},{"comp":"A-00005-00001223","fecha":"2024-06-12","tipo":"F","bruto":5000,"total":6050,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00001238","fecha":"2024-07-10","tipo":"F","bruto":548,"total":605.54,"moneda":"USD","anulada":false,"tc":937.5},{"comp":"A-00005-00001291","fecha":"2024-10-10","tipo":"F","bruto":1644,"total":1816.62,"moneda":"USD","anulada":false,"tc":997.5},{"comp":"A-00005-00001311","fecha":"2024-12-12","tipo":"F","bruto":82,"total":90.61,"moneda":"USD","anulada":false,"tc":1037.5},{"comp":"A-00005-00001314","fecha":"2024-12-16","tipo":"F","bruto":986,"total":1089.53,"moneda":"USD","anulada":false,"tc":1040.5},{"comp":"A-00005-00001379","fecha":"2025-04-28","tipo":"F","bruto":119.28,"total":144.33,"moneda":"USD","anulada":false,"tc":1170},{"comp":"A-00005-00001382","fecha":"2025-05-06","tipo":"F","bruto":119.28,"total":144.33,"moneda":"USD","anulada":false,"tc":1220},{"comp":"A-00005-00001394","fecha":"2025-05-29","tipo":"F","bruto":149.1,"total":180.41,"moneda":"USD","anulada":false,"tc":1185},{"comp":"A-00005-00000346","fecha":"2025-07-31","tipo":"NC","bruto":-82,"total":-90.61,"moneda":"USD","anulada":false,"tc":1037.5},{"comp":"A-00005-00000390","fecha":"2026-06-22","tipo":"NC","bruto":-3944,"total":-4358.12,"moneda":"USD","anulada":false,"tc":1531.8},{"comp":"A-00005-00001619","fecha":"2026-06-22","tipo":"F","bruto":3944,"total":4358.12,"moneda":"USD","anulada":true,"tc":1531.8},{"comp":"A-00005-00001620","fecha":"2026-06-22","tipo":"F","bruto":3944,"total":4358.12,"moneda":"USD","anulada":false,"tc":1557.7},{"comp":"A-00005-00000394","fecha":"2026-07-03","tipo":"NC","bruto":-3944,"total":-4358.12,"moneda":"USD","anulada":false,"tc":1531.8},{"comp":"A-00005-00001628","fecha":"2026-07-03","tipo":"F","bruto":3944,"total":4358.12,"moneda":"USD","anulada":true,"tc":1531.8},{"comp":"A-00005-00001657","fecha":"2026-08-25","tipo":"F","bruto":2776,"total":3067.48,"moneda":"USD","anulada":false,"tc":1530}],"sf_lineas":[{"fecha":"2022-03-31","comp":"A-00005-00000392","tipo":"F","items":["1 × Onu Gpon NT570W-RF [Netconn]"]},{"fecha":"2022-05-05","comp":"A-00012-00000169","tipo":"F","items":["40 × Onu Gpon IC425ETB [I-con]"]},{"fecha":"2022-05-20","comp":"A-00005-00000444","tipo":"F","items":["20 × Onu Gpon F673A V6 [Zte]"]},{"fecha":"2022-05-20","comp":"A-00012-00000180","tipo":"F","items":["120 × Onu Gpon IC410WSG [I-con]"]},{"fecha":"2022-06-22","comp":"A-00005-00000475","tipo":"F","items":["40 × Onu Gpon F673A V6 [Zte]"]},{"fecha":"2022-07-20","comp":"A-00005-00000534","tipo":"F","items":["30 × Onu Gpon F660 [Zte]"]},{"fecha":"2022-09-01","comp":"A-00005-00000609","tipo":"F","items":["20 × Onu Gpon F660 [Zte]"]},{"fecha":"2022-12-22","comp":"A-00005-00000749","tipo":"F","items":["40 × Onu Gpon EG8141H5 [Huawei]"]},{"fecha":"2023-01-26","comp":"A-00005-00000781","tipo":"F","items":["20 × Onu Gpon HG8247H5 [Huawei]"]},{"fecha":"2023-03-13","comp":"A-00005-00000848","tipo":"F","items":["160 × Onu Gpon IC435ETR [I-con]"]},{"fecha":"2023-03-14","comp":"A-00005-00000859","tipo":"F","items":["20 × Onu Gpon F660 V6.0 [Zte]"]},{"fecha":"2023-05-10","comp":"A-00005-00000934","tipo":"F","items":["60 × Onu Gpon IC425ETB [I-con]"]},{"fecha":"2024-05-21","comp":"A-00012-00000540","tipo":"F","items":["120 × Onu Gpon IC435ETR [I-con]"]},{"fecha":"2024-12-12","comp":"A-00005-00001311","tipo":"F","items":["1 × Ont Gpon HG6144F [FiberHome]"]},{"fecha":"2024-12-16","comp":"A-00005-00001314","tipo":"F","items":["1 × Placa Controladora SCM [-]"]}],"sf_cotizaciones":[],"etapa":"pausa"},"buenaonda":{"_id":"w-buena-onda-televisora-color","empresa":"BUENA ONDA TELEVISORA COLOR","sf_comprobantes":[{"comp":"A-00005-00000471","fecha":"2022-06-16","tipo":"F","bruto":13237.18,"total":14627.08,"moneda":"USD","anulada":false,"tc":141.8025},{"comp":"A-00005-00000124","fecha":"2022-06-21","tipo":"NCC","bruto":-179396.84,"total":-198233.51,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000133","fecha":"2022-07-05","tipo":"NC","bruto":-550,"total":-607.75,"moneda":"USD","anulada":false,"tc":131.75},{"comp":"A-00005-00000504","fecha":"2022-07-05","tipo":"F","bruto":550,"total":607.75,"moneda":"USD","anulada":true,"tc":131.75},{"comp":"A-00005-00000178","fecha":"2022-11-16","tipo":"NC","bruto":-84119,"total":-92951.5,"moneda":"USD","anulada":false,"tc":168.5},{"comp":"A-00005-00000709","fecha":"2022-11-16","tipo":"F","bruto":84119,"total":92951.5,"moneda":"USD","anulada":true,"tc":168.5},{"comp":"A-00005-00000710","fecha":"2022-11-16","tipo":"F","bruto":83990,"total":92808.95,"moneda":"USD","anulada":true,"tc":169},{"comp":"A-00005-00000180","fecha":"2022-11-17","tipo":"NC","bruto":-83990,"total":-92808.95,"moneda":"USD","anulada":false,"tc":169},{"comp":"A-00005-00000436","fecha":"2022-11-17","tipo":"ND","bruto":84119,"total":92951.5,"moneda":"USD","anulada":false,"tc":168.5},{"comp":"A-00005-00000449","fecha":"2022-11-28","tipo":"NDC","bruto":231327.27,"total":255616.63,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000822","fecha":"2023-02-27","tipo":"F","bruto":6545.88,"total":7233.2,"moneda":"USD","anulada":false,"tc":231.99},{"comp":"A-00005-00000926","fecha":"2023-05-03","tipo":"F","bruto":7800,"total":8619,"moneda":"USD","anulada":false,"tc":231},{"comp":"A-00005-00000930","fecha":"2023-05-08","tipo":"F","bruto":6240,"total":6895.2,"moneda":"USD","anulada":false,"tc":235},{"comp":"A-00005-00000965","fecha":"2023-06-01","tipo":"F","bruto":6291.6,"total":6952.22,"moneda":"USD","anulada":false,"tc":249.5},{"comp":"A-00005-00000979","fecha":"2023-06-09","tipo":"F","bruto":14156.1,"total":15642.49,"moneda":"USD","anulada":false,"tc":254.5},{"comp":"A-00005-00000569","fecha":"2023-06-22","tipo":"NDC","bruto":113248.78,"total":125139.9,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00001509","fecha":"2025-12-03","tipo":"F","bruto":10200,"total":11271,"moneda":"USD","anulada":false,"tc":1622.5},{"comp":"A-00005-00001578","fecha":"2026-04-06","tipo":"F","bruto":1462,"total":1615.51,"moneda":"USD","anulada":false,"tc":1514.05},{"comp":"A-00005-00000385","fecha":"2026-04-30","tipo":"NC","bruto":-1462,"total":-1615.51,"moneda":"USD","anulada":false,"tc":1514.05}],"sf_lineas":[{"fecha":"2022-03-15","comp":"A-00012-00000122","tipo":"F","items":["2 × Onu Gpon IC410WSG [I-con]"]},{"fecha":"2022-06-09","comp":"A-00012-00000205","tipo":"F","items":["2 × Onu Gpon IC445ETRF [I-con]"]},{"fecha":"2022-07-21","comp":"A-00012-00000251","tipo":"F","items":["200 × Onu Gpon IC410WSG [I-con]"]},{"fecha":"2022-09-23","comp":"A-00012-00000321","tipo":"F","items":["210 × Onu Gpon IC405WSG [I-con]"]},{"fecha":"2023-05-03","comp":"A-00005-00000926","tipo":"F","items":["150 × Onu Gpon IC405WSG [I-con]"]},{"fecha":"2023-05-08","comp":"A-00005-00000930","tipo":"F","items":["120 × Onu Gpon IC405WSG [I-con]"]},{"fecha":"2023-06-01","comp":"A-00005-00000965","tipo":"F","items":["120 × Onu Gpon IC405WSG [I-con]"]},{"fecha":"2023-06-09","comp":"A-00005-00000979","tipo":"F","items":["270 × Onu Gpon IC405WSG [I-con]"]},{"fecha":"2023-10-12","comp":"A-00012-00000107","tipo":"NC","items":["-2 × Onu Gpon IC445ETRF [I-con]"]},{"fecha":"2023-10-12","comp":"A-00012-00000108","tipo":"NC","items":["-2 × Onu Gpon IC410WSG [I-con]"]},{"fecha":"2024-06-13","comp":"A-00012-00000549","tipo":"F","items":["600 × Onu Xpon ZC-521T [Zikun]"]},{"fecha":"2024-07-15","comp":"A-00012-00000558","tipo":"F","items":["1251 × Onu Xpon ZC-521T [Zikun]"]},{"fecha":"2024-07-31","comp":"A-00012-00000566","tipo":"F","items":["200 × Onu Xpon ZC-521-4 [Zikun]"]}],"sf_cotizaciones":[],"etapa":"contactado"},"souto":{"_id":"w-ssservicios-souto","empresa":"SSSERVICIOS SOUTO","sf_comprobantes":[{"comp":"A-00005-00000050","fecha":"2021-01-08","tipo":"F","bruto":7204,"total":7960.42,"moneda":"USD","anulada":false,"tc":89.75},{"comp":"A-00005-00000078","fecha":"2021-01-28","tipo":"F","bruto":21507,"total":23765.24,"moneda":"USD","anulada":false,"tc":92},{"comp":"A-00005-00000698","fecha":"2022-11-08","tipo":"F","bruto":2500,"total":2762.5,"moneda":"USD","anulada":false,"tc":166},{"comp":"A-00005-00000437","fecha":"2022-11-18","tipo":"NDC","bruto":2500,"total":2762.5,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000184","fecha":"2022-12-02","tipo":"NC","bruto":-47443.44,"total":-52425,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000452","fecha":"2022-12-02","tipo":"ND","bruto":47443.44,"total":52425,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000199","fecha":"2023-01-30","tipo":"NC","bruto":-247.95,"total":-273.98,"moneda":"USD","anulada":false,"tc":192.25},{"comp":"A-00005-00000784","fecha":"2023-01-30","tipo":"F","bruto":5206.95,"total":5753.68,"moneda":"USD","anulada":false,"tc":192.25},{"comp":"A-00005-00000498","fecha":"2023-03-01","tipo":"NDC","bruto":11653.65,"total":12877.28,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000834","fecha":"2023-03-07","tipo":"F","bruto":42780,"total":47271.9,"moneda":"USD","anulada":false,"tc":239.25},{"comp":"A-00005-00000506","fecha":"2023-03-09","tipo":"NDC","bruto":2231.55,"total":2465.86,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000839","fecha":"2023-03-10","tipo":"F","bruto":5200,"total":6292,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000535","fecha":"2023-04-03","tipo":"NDC","bruto":23059.35,"total":25480.58,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000553","fecha":"2023-05-02","tipo":"NDC","bruto":36448.65,"total":40275.76,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000939","fecha":"2023-05-12","tipo":"F","bruto":85.5,"total":94.48,"moneda":"USD","anulada":false,"tc":238},{"comp":"A-00005-00000561","fecha":"2023-05-31","tipo":"NDC","bruto":55788.75,"total":61646.57,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000564","fecha":"2023-06-07","tipo":"NDC","bruto":3967.2,"total":4383.76,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000568","fecha":"2023-06-15","tipo":"NDC","bruto":1581.79,"total":1747.88,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00001030","fecha":"2023-07-17","tipo":"F","bruto":11550,"total":12762.75,"moneda":"USD","anulada":false,"tc":296.9357},{"comp":"A-00005-00001032","fecha":"2023-07-17","tipo":"F","bruto":5200,"total":6292,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00001156","fecha":"2023-12-06","tipo":"F","bruto":3400,"total":3757,"moneda":"USD","anulada":false,"tc":379},{"comp":"A-00005-00000651","fecha":"2023-12-07","tipo":"NDC","bruto":1698.84,"total":1877.22,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00001510","fecha":"2025-12-05","tipo":"F","bruto":101,"total":122.21,"moneda":"USD","anulada":false,"tc":1470}],"sf_lineas":[{"fecha":"2022-04-20","comp":"A-00012-00000147","tipo":"F","items":["40 × Onu Gpon IC410WSG [I-con]"]},{"fecha":"2022-05-23","comp":"A-00012-00000181","tipo":"F","items":["400 × Onu Gpon IC410WSG [I-con]"]},{"fecha":"2022-06-07","comp":"A-00012-00000203","tipo":"F","items":["520 × Onu Gpon IC410WSG [I-con]"]},{"fecha":"2022-06-28","comp":"A-00012-00000214","tipo":"F","items":["520 × Onu Gpon IC410WSG [I-con]"]},{"fecha":"2022-07-18","comp":"A-00012-00000248","tipo":"F","items":["520 × Onu Gpon IC410WSG [I-con]"]},{"fecha":"2022-08-01","comp":"A-00012-00000260","tipo":"F","items":["1000 × Onu Gpon IC405WSG [I-con]","1000 × Onu Gpon IC405WSG [I-con]","1000 × Onu Gpon IC405WSG [I-con]"]},{"fecha":"2023-03-07","comp":"A-00005-00000834","tipo":"NC","items":["930 × Onu Gpon IC405WSG [I-con]"]},{"fecha":"2023-03-07","comp":"A-00012-00000437","tipo":"NC","items":["1080 × Onu Gpon IC405WSG [I-con]"]},{"fecha":"2023-05-12","comp":"A-00005-00000939","tipo":"F","items":["3 × Onu Gpon IC425ETB [I-con]"]},{"fecha":"2023-07-17","comp":"A-00005-00001030","tipo":"F","items":["60 × Onu Gpon IC405WSG [I-con]","150 × Onu Gpon IC405WSG [I-con]"]},{"fecha":"2024-05-24","comp":"A-00012-00000542","tipo":"NC","items":["5 × Onu Gpon IC455WDB [I-con]"]},{"fecha":"2024-05-24","comp":"A-00012-00000543","tipo":"F","items":["5 × Onu Xpon ZC-521-4 [Zikun]"]},{"fecha":"2024-10-15","comp":"A-00012-00000131","tipo":"NC","items":["-5 × Onu Gpon IC455WDB [I-con]","-5 × Onu Xpon ZC-521-4 [Zikun]"]}],"sf_cotizaciones":[],"etapa":"contactado"},"fournet":{"_id":"r050-fournet","empresa":"Fournet","sf_comprobantes":[{"comp":"A-00005-00000501","fecha":"2022-07-05","tipo":"F","bruto":4159.45,"total":4596.19,"moneda":"USD","anulada":false,"tc":131.75},{"comp":"A-00005-00000509","fecha":"2022-07-08","tipo":"F","bruto":51,"total":56.36,"moneda":"USD","anulada":false,"tc":132.25},{"comp":"A-00005-00000549","fecha":"2022-08-02","tipo":"F","bruto":1927.8,"total":2130.22,"moneda":"USD","anulada":false,"tc":138.5},{"comp":"A-00005-00000566","fecha":"2022-08-11","tipo":"F","bruto":550,"total":607.75,"moneda":"USD","anulada":false,"tc":140},{"comp":"A-00005-00000567","fecha":"2022-08-12","tipo":"F","bruto":5207.4,"total":5754.18,"moneda":"USD","anulada":false,"tc":141},{"comp":"A-00005-00000346","fecha":"2022-08-18","tipo":"NDC","bruto":63.48,"total":70.14,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000606","fecha":"2022-08-30","tipo":"F","bruto":750,"total":828.75,"moneda":"USD","anulada":false,"tc":145},{"comp":"A-00005-00000670","fecha":"2022-10-25","tipo":"F","bruto":2104,"total":2324.92,"moneda":"USD","anulada":false,"tc":161.5},{"comp":"A-00005-00000766","fecha":"2023-01-13","tipo":"F","bruto":20110,"total":22221.55,"moneda":"USD","anulada":false,"tc":187.75},{"comp":"A-00005-00000477","fecha":"2023-01-18","tipo":"NDC","bruto":127832.56,"total":141254.98,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000774","fecha":"2023-01-19","tipo":"F","bruto":7973,"total":8810.17,"moneda":"USD","anulada":false,"tc":189.25},{"comp":"A-00005-00000778","fecha":"2023-01-20","tipo":"F","bruto":2128,"total":2351.44,"moneda":"USD","anulada":false,"tc":189.75},{"comp":"A-00005-00000480","fecha":"2023-01-24","tipo":"NDC","bruto":3192,"total":3527.16,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000802","fecha":"2023-02-09","tipo":"F","bruto":935,"total":1033.18,"moneda":"USD","anulada":false,"tc":196.25},{"comp":"A-00005-00000806","fecha":"2023-02-14","tipo":"F","bruto":935,"total":1033.18,"moneda":"USD","anulada":false,"tc":198},{"comp":"A-00005-00000832","fecha":"2023-03-07","tipo":"F","bruto":935,"total":1033.18,"moneda":"USD","anulada":false,"tc":206.25},{"comp":"A-00005-00000854","fecha":"2023-03-13","tipo":"F","bruto":4440,"total":4906.2,"moneda":"USD","anulada":false,"tc":208.25},{"comp":"A-00005-00000858","fecha":"2023-03-14","tipo":"F","bruto":2700,"total":2983.5,"moneda":"USD","anulada":false,"tc":208.25},{"comp":"A-00005-00000881","fecha":"2023-03-29","tipo":"F","bruto":1350,"total":1491.75,"moneda":"USD","anulada":false,"tc":214.5},{"comp":"A-00005-00000909","fecha":"2023-04-19","tipo":"F","bruto":1470,"total":1624.35,"moneda":"USD","anulada":false,"tc":223.5},{"comp":"A-00005-00000923","fecha":"2023-05-02","tipo":"F","bruto":935,"total":1033.18,"moneda":"USD","anulada":false,"tc":230.5},{"comp":"A-00005-00000925","fecha":"2023-05-03","tipo":"F","bruto":2940,"total":3248.7,"moneda":"USD","anulada":false,"tc":231},{"comp":"A-00005-00000942","fecha":"2023-05-17","tipo":"F","bruto":1992,"total":2201.16,"moneda":"USD","anulada":false,"tc":240.5},{"comp":"A-00005-00000951","fecha":"2023-05-24","tipo":"F","bruto":6720.01,"total":7425.61,"moneda":"USD","anulada":false,"tc":245},{"comp":"A-00005-00000957","fecha":"2023-05-30","tipo":"F","bruto":22170,"total":24497.85,"moneda":"USD","anulada":false,"tc":248.5},{"comp":"A-00005-00000960","fecha":"2023-05-31","tipo":"F","bruto":2940,"total":3248.7,"moneda":"USD","anulada":false,"tc":249},{"comp":"A-00005-00000978","fecha":"2023-06-09","tipo":"F","bruto":24300,"total":26851.5,"moneda":"USD","anulada":false,"tc":254},{"comp":"A-00005-00000566","fecha":"2023-06-13","tipo":"NDC","bruto":12150,"total":13425.75,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000986","fecha":"2023-06-14","tipo":"F","bruto":22923,"total":25329.92,"moneda":"USD","anulada":false,"tc":256.5},{"comp":"A-00005-00001006","fecha":"2023-06-28","tipo":"F","bruto":1470,"total":1624.35,"moneda":"USD","anulada":false,"tc":266},{"comp":"A-00005-00000589","fecha":"2023-07-13","tipo":"NDC","bruto":204960.31,"total":226481.14,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00001051","fecha":"2023-07-28","tipo":"F","bruto":1299.68,"total":1436.15,"moneda":"USD","anulada":false,"tc":285},{"comp":"A-00005-00000606","fecha":"2023-08-01","tipo":"NDC","bruto":1949.53,"total":2154.23,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00000279","fecha":"2023-11-28","tipo":"NC","bruto":-260,"total":-287.3,"moneda":"USD","anulada":false,"tc":375},{"comp":"A-00005-00000287","fecha":"2024-02-22","tipo":"NC","bruto":-700,"total":-773.5,"moneda":"USD","anulada":false,"tc":857},{"comp":"A-00005-00000297","fecha":"2024-04-09","tipo":"NCC","bruto":-150287.76,"total":-166067.98,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00001184","fecha":"2024-04-09","tipo":"F","bruto":1096,"total":1211.08,"moneda":"USD","anulada":false,"tc":883},{"comp":"A-00005-00001191","fecha":"2024-04-22","tipo":"F","bruto":805,"total":889.53,"moneda":"USD","anulada":false,"tc":892},{"comp":"A-00005-00001196","fecha":"2024-04-30","tipo":"F","bruto":805,"total":889.53,"moneda":"USD","anulada":false,"tc":895.5},{"comp":"A-00005-00001348","fecha":"2025-03-12","tipo":"F","bruto":805,"total":889.53,"moneda":"USD","anulada":false,"tc":1086.25},{"comp":"A-00005-00000745","fecha":"2025-03-17","tipo":"NDC","bruto":1408.76,"total":1556.68,"moneda":"ARS","anulada":false,"tc":1},{"comp":"A-00005-00001358","fecha":"2025-03-27","tipo":"F","bruto":1610,"total":1779.05,"moneda":"USD","anulada":false,"tc":1091.5},{"comp":"A-00005-00001361","fecha":"2025-03-28","tipo":"F","bruto":805,"total":889.53,"moneda":"USD","anulada":false,"tc":1092.5},{"comp":"A-00005-00001437","fecha":"2025-08-14","tipo":"F","bruto":4000,"total":4420,"moneda":"USD","anulada":false,"tc":1325},{"comp":"A-00005-00001443","fecha":"2025-08-22","tipo":"F","bruto":560,"total":618.8,"moneda":"USD","anulada":false,"tc":1335},{"comp":"A-00005-00001452","fecha":"2025-09-05","tipo":"F","bruto":1400,"total":1547,"moneda":"USD","anulada":false,"tc":1375},{"comp":"A-00005-00001512","fecha":"2025-12-10","tipo":"F","bruto":800,"total":884,"moneda":"USD","anulada":false,"tc":1465}],"sf_lineas":[{"fecha":"2022-07-08","comp":"A-00005-00000509","tipo":"F","items":["1 × Onu Gpon NT570W-RF [Netconn]"]},{"fecha":"2022-07-08","comp":"A-00012-00000236","tipo":"F","items":["1 × Onu Gpon IC410WSG [I-con]","1 × Onu Gpon IC435ETR [I-con]"]},{"fecha":"2022-07-26","comp":"A-00012-00000255","tipo":"F","items":["120 × Onu Gpon IC455WDB [I-con]"]},{"fecha":"2022-08-02","comp":"A-00005-00000549","tipo":"F","items":["1 × Placa Controladora SMM [-]"]},{"fecha":"2022-08-12","comp":"A-00005-00000567","tipo":"F","items":["99 × Onu Gpon NT570W-RF [Netconn]"]},{"fecha":"2022-08-12","comp":"A-00012-00000269","tipo":"F","items":["99 × Onu Gpon IC410WSG [I-con]"]},{"fecha":"2022-08-23","comp":"A-00012-00000282","tipo":"F","items":["2 × Onu Gpon IC485WRF [I-con]"]},{"fecha":"2022-08-23","comp":"A-00012-00000283","tipo":"F","items":["2 × Onu Gpon IC405WSG [I-con]"]},{"fecha":"2022-09-01","comp":"A-00012-00000295","tipo":"F","items":["300 × Onu Gpon IC405WSG [I-con]"]},{"fecha":"2022-10-25","comp":"A-00005-00000670","tipo":"F","items":["40 × Onu Gpon NT570W-RF [Netconn]"]},{"fecha":"2022-10-25","comp":"A-00012-00000345","tipo":"F","items":["80 × Onu Gpon IC405WSG [I-con]","30 × Onu Gpon IC455WDB [I-con]"]},{"fecha":"2022-10-28","comp":"A-00012-00000349","tipo":"F","items":["10 × Onu Gpon IC405WSG [I-con]"]},{"fecha":"2022-11-15","comp":"A-00012-00000371","tipo":"F","items":["60 × Onu Gpon IC405WSG [I-con]"]},{"fecha":"2022-12-19","comp":"A-00012-00000383","tipo":"F","items":["90 × Onu Gpon IC405WSG [I-con]"]},{"fecha":"2023-01-16","comp":"A-00012-00000400","tipo":"F","items":["30 × Onu Gpon IC405WSG [I-con]"]},{"fecha":"2023-02-16","comp":"A-00012-00000427","tipo":"F","items":["40 × Onu Gpon IC425ETB [I-con]"]},{"fecha":"2023-03-13","comp":"A-00005-00000854","tipo":"F","items":["60 × Onu Gpon IC485WRF [I-con]"]},{"fecha":"2023-03-14","comp":"A-00005-00000858","tipo":"F","items":["60 × Onu Gpon IC405WSG [I-con]"]},{"fecha":"2023-03-29","comp":"A-00005-00000881","tipo":"F","items":["30 × Onu Gpon IC405WSG [I-con]"]},{"fecha":"2023-03-29","comp":"A-00012-00000448","tipo":"F","items":["40 × Onu Gpon IC425ETB [I-con]"]},{"fecha":"2023-04-19","comp":"A-00005-00000909","tipo":"F","items":["30 × Onu Gpon IC405WSG [I-con]"]},{"fecha":"2023-05-03","comp":"A-00005-00000925","tipo":"F","items":["60 × Onu Gpon IC405WSG [I-con]"]},{"fecha":"2023-05-16","comp":"A-00012-00000460","tipo":"F","items":["1 × Onu Gpon IC405WSG [I-con]"]},{"fecha":"2023-05-17","comp":"A-00005-00000942","tipo":"F","items":["80 × Onu Gpon IC425ETB [I-con]"]},{"fecha":"2023-05-17","comp":"A-00012-00000462","tipo":"F","items":["1 × Onu Gpon IC425ETB [I-con]"]},{"fecha":"2023-05-30","comp":"A-00005-00000957","tipo":"F","items":["300 × Onu Gpon IC405WSG [I-con]","300 × Onu Gpon IC425ETB [I-con]"]},{"fecha":"2023-05-31","comp":"A-00005-00000960","tipo":"F","items":["60 × Onu Gpon IC405WSG [I-con]"]},{"fecha":"2023-06-09","comp":"A-00005-00000978","tipo":"F","items":["300 × Onu Gpon IC485WRF [I-con]"]},{"fecha":"2023-06-14","comp":"A-00005-00000986","tipo":"F","items":["283 × Onu Gpon IC485WRF [I-con]"]},{"fecha":"2023-06-28","comp":"A-00005-00001006","tipo":"F","items":["30 × Onu Gpon IC405WSG [I-con]"]},{"fecha":"2023-11-28","comp":"A-00005-00000279","tipo":"NC","items":["-2 × Onu Gpon IC405WSG [I-con]","-2 × Onu Gpon IC485WRF [I-con]"]},{"fecha":"2024-04-30","comp":"A-00012-00000534","tipo":"F","items":["30 × Onu Gpon IC405WSG [I-con]"]},{"fecha":"2024-07-03","comp":"A-00012-00000554","tipo":"F","items":["30 × Onu Gpon IC405WSG [I-con]"]},{"fecha":"2024-09-04","comp":"A-00012-00000577","tipo":"NC","items":["30 × Onu Gpon IC405WSG [I-con]"]},{"fecha":"2025-08-14","comp":"A-00005-00001437","tipo":"F","items":["400 × Onu Gpon HG8245H5 [Huawei]"]},{"fecha":"2025-08-22","comp":"A-00005-00001443","tipo":"F","items":["40 × Onu Gpon HG8245H5 [Huawei]"]},{"fecha":"2025-09-05","comp":"A-00005-00001452","tipo":"F","items":["100 × Onu Gpon HG8245H5 [Huawei]"]},{"fecha":"2025-12-10","comp":"A-00005-00001512","tipo":"F","items":["100 × Onu Gpon IC405WSG [I-con]"]}],"sf_cotizaciones":[],"etapa":"negociacion"},"interflash":{"_id":"f-interflash","empresa":"Interflash","sf_comprobantes":[{"comp":"A-00005-00001495","fecha":"2025-11-18","tipo":"F","bruto":631.46,"total":764.07,"moneda":"USD","anulada":false,"tc":1415},{"comp":"A-00005-00001587","fecha":"2026-04-23","tipo":"F","bruto":951.8,"total":1151.68,"moneda":"USD","anulada":false,"tc":1405},{"comp":"A-00005-00000388","fecha":"2026-05-05","tipo":"NC","bruto":-951.8,"total":-1151.68,"moneda":"USD","anulada":false,"tc":1405},{"comp":"A-00005-00001595","fecha":"2026-05-05","tipo":"F","bruto":1428,"total":1727.88,"moneda":"USD","anulada":false,"tc":1405},{"comp":"A-00005-00000396","fecha":"2026-07-28","tipo":"NC","bruto":-1428,"total":-1727.88,"moneda":"USD","anulada":false,"tc":1405},{"comp":"A-00005-00001648","fecha":"2026-07-28","tipo":"F","bruto":1428,"total":1727.88,"moneda":"USD","anulada":true,"tc":1599.8},{"comp":"A-00005-00000400","fecha":"2026-08-28","tipo":"NC","bruto":-1428,"total":-1727.88,"moneda":"USD","anulada":false,"tc":1599.8}],"sf_lineas":[],"sf_cotizaciones":[],"etapa":"contactado"},"luna":{"_id":"h-luna-net","empresa":"Luna Net","sf_comprobantes":[{"comp":"A-00005-00001503","fecha":"2025-11-21","tipo":"F","bruto":3492,"total":3858.66,"moneda":"USD","anulada":false,"tc":1450},{"comp":"A-00005-00001504","fecha":"2025-11-21","tipo":"F","bruto":3492,"total":3858.66,"moneda":"USD","anulada":false,"tc":1450},{"comp":"A-00005-00001524","fecha":"2026-01-13","tipo":"F","bruto":1850,"total":2044.25,"moneda":"USD","anulada":false,"tc":1490},{"comp":"A-00005-00000374","fecha":"2026-01-26","tipo":"NC","bruto":-281.25,"total":-310.78,"moneda":"USD","anulada":false,"tc":1460},{"comp":"A-00005-00001541","fecha":"2026-01-26","tipo":"F","bruto":9375,"total":10359.38,"moneda":"USD","anulada":false,"tc":1460},{"comp":"A-00005-00001575","fecha":"2026-03-31","tipo":"F","bruto":10912.5,"total":12058.31,"moneda":"USD","anulada":false,"tc":1415},{"comp":"A-00005-00001642","fecha":"2026-07-23","tipo":"F","bruto":7275,"total":8038.88,"moneda":"USD","anulada":false,"tc":1510},{"comp":"A-00005-00001643","fecha":"2026-07-23","tipo":"F","bruto":3637.5,"total":4019.44,"moneda":"USD","anulada":false,"tc":1510},{"comp":"A-00005-00001670","fecha":"2026-09-07","tipo":"F","bruto":7125,"total":7873.13,"moneda":"USD","anulada":false,"tc":1530}],"sf_lineas":[{"fecha":"2025-11-21","comp":"A-00005-00001503","tipo":"AJ","items":["0 × Descuento Contado (Iva 10,5%) [-]","150 × Ont Gpon HG6543D [FiberHome]"]},{"fecha":"2025-11-21","comp":"A-00005-00001504","tipo":"AJ","items":["0 × Descuento Contado (Iva 10,5%) [-]","150 × Ont Gpon HG6543D [FiberHome]"]},{"fecha":"2026-01-26","comp":"A-00005-00001541","tipo":"F","items":["100 × Ont Gpon HG6145F3 [FiberHome]","150 × Ont Gpon HG6145F3 [FiberHome]"]},{"fecha":"2026-03-31","comp":"A-00005-00001575","tipo":"AJ","items":["300 × Ont Gpon HG6145F3 [FiberHome]"]},{"fecha":"2026-07-23","comp":"A-00005-00001642","tipo":"AJ","items":["200 × Ont Gpon HG6145F3 [FiberHome]"]},{"fecha":"2026-07-23","comp":"A-00005-00001643","tipo":"AJ","items":["100 × Ont Gpon HG6145F3 [FiberHome]"]},{"fecha":"2026-09-07","comp":"A-00005-00001670","tipo":"AJ","items":["200 × Ont Gpon HG6145F3 [FiberHome]"]}],"sf_cotizaciones":[],"etapa":"ganado"}}''')
HOY_ORO = dt.date(2026, 11, 12)


def casos_oro(se):
    """se = módulo sales_engine ya con reglas cargadas. Devuelve [(ok, texto)]."""
    out = []
    t = lambda ok, txt: out.append((bool(ok), txt))
    comp = lambda k: se.componentes(ORO[k], HOY_ORO)
    anul = lambda k: se.comps_anuladas(ORO[k])
    c = comp("infinitel")
    t("A-00005-00001546" in anul("infinitel") and "REPONER" not in c and "REEMPLAZAR" not in c,
      "Infinitel: FA 1546 anulada por NC, sin reponer 9.945 ni ONU 4.618 (error 12/11)")
    c = comp("monica")
    t("REPONER" not in c and "_REACTIVAR" in c, "Mónica: ráfaga reciente de 7 d y 55 d sin comprar = reactivar, no sin acción")
    t("REPONER" not in comp("sol"), "Sol-Informáticas: sin reposición este mes")
    t("REPONER" not in comp("fullsat"), "Fullsat: sin reposición (2 compras separadas por 11 meses)")
    fa = {x[-4:] for x in anul("fullsat")}
    t("1695" in fa and "1702" not in fa, "Fullsat: la NC 406 anula la FA 1695 (marcada) y la gemela FA 1702 cuenta una vez")
    t("_REACTIVAR" in comp("frappa"), "Frappa: sigue en reactivar")
    c = comp("buenaonda")
    t("_REACTIVAR" in c and "03/12/2025" in c["_REACTIVAR"][2][0], "Buena Onda: reactivar con última compra 03/12/2025 (FA 1578 anulada por NC 385)")
    t("_REACTIVAR" in comp("souto"), "Souto: dormido (5x), reactivar")
    t("_REACTIVAR" in comp("fournet"), "Fournet: dormida con ONU discontinuada = reactivación (decisión 82)")
    t({x[-4:] for x in anul("interflash")} >= {"1595", "1648"},
      "Interflash: cada NC anula una factura (la marcada no roba la NC de la anterior)")
    t("REPONER" in comp("luna"), "Luna Net: le toca reponer")
    return out


def cmd_oro(a, se=None):
    if se is None:
        raise SystemExit("FALLA: oro necesita --raiz para cargar sales_engine y reglas")
    res = casos_oro(se)
    for ok, txt in res:
        print(("PASA  · " if ok else "FALLA · ") + txt)
    ok = all(x[0] for x in res)
    print("ORO:", "PASA" if ok else "FALLA", f"({sum(x[0] for x in res)}/{len(res)})")
    return 0 if ok else 1


def modulo_con_reglas(raiz):
    se = cargar(extraer(raiz, "sales_engine"), "se")
    f = se.cargar_reglas(doc(raiz, "reglas_motor"))
    if f:
        raise SystemExit(f"FALLA: reglas_motor incompleto: {f}")
    return se


def _k10_resumen(a):
    import contextlib, io
    b = io.StringIO()
    with contextlib.redirect_stdout(b):
        cmd_k10(a)
    return b.getvalue().splitlines()[-6:]


def cmd_k10(a):
    """K10: el motor ve compras netas en un año donde Stockfish dice USD 0 (anulaciones que el motor no detecta)."""
    se = modulo_con_reglas(a.raiz)
    hoy = dt.date.fromisoformat(a.hoy)
    r = rutas(a.raiz, a.hoy)
    av = []
    for n in sorted(os.listdir(r["sf"])):
        if not n.endswith(".json"):
            continue
        f = json.load(open(os.path.join(r["sf"], n)))
        f = f.get("data", f)
        por = ((f.get("sf_compras") or {}).get("usdBrutoPorAnio")) or {}
        if not por:
            continue
        net = {}
        for fe, usd, comp in se.facturas_netas(f, hoy):
            net.setdefault(str(fe.year), []).append((fe, usd, comp))
        for anio, lst in net.items():
            if (por.get(anio) or 0) <= 0 < sum(x[1] for x in lst):
                av.append((sum(x[1] for x in lst), f.get("empresa") or n[:-5], anio, max(x[0] for x in lst)))
    for usd, e, anio, ult in sorted(av, reverse=True)[:15]:
        print(f"AVISO K10 {e}: el motor cuenta USD {usd:,.0f} netos en {anio} (última {ult:%d/%m/%Y}) y Stockfish dice 0".replace(",", "."))
    print(f"K10: {len(av)} aviso(s)" if av else "K10: PASA · el motor y Stockfish coinciden por año")
    return 0


def cmd_test(a):
    ok = True
    def t(c, txt):
        nonlocal ok
        ok &= bool(c); print(("PASA  · " if c else "FALLA · ") + txt)
    t(isinstance(ORO, dict) and len(ORO) == 10, "oro: 10 cuentas reales cargadas")
    t(all(ORO[k]["sf_comprobantes"] for k in ORO), "oro: todas con comprobantes")
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, "datacenter"))
    json.dump({"codigo": "print('hola')"}, open(os.path.join(d, "datacenter", "x.json"), "w"))
    p = extraer(d, "x")
    t(os.path.exists(p) and open(p).read() == "print('hola')", "extraer escribe el código del doc")
    try:
        correr(["-c", "raise SystemExit(3)"], "falso"); t(False, "un paso que falla frena la cadena")
    except SystemExit as e:
        t("FALLA en falso" in str(e), "un paso que falla frena la cadena")
    tmp = tempfile.mkdtemp()
    os.makedirs(os.path.join(tmp, "x", "loki-maestro")); open(os.path.join(tmp, "x", "loki-maestro", "SKILL.md"), "w").close()
    t(buscar_skills(os.path.join(tmp, "x"))[0] == os.path.join(tmp, "x"), "v1.2: --skills válido se respeta")
    t(buscar_skills(os.path.join(tmp, "nada"))[0] != os.path.join(tmp, "nada") or not any(
        os.path.isdir(g) for g in ("/mnt/skills/plugins",)), "v1.2: --skills sin loki-maestro busca la carpeta real")
    for sub_ in ("salida", "datacenter", "config"):
        os.makedirs(os.path.join(tmp, sub_), exist_ok=True)
    cj = os.path.join(tmp, "c.json")
    json.dump({"version": "1.3", "veredicto": "PASA", "hallazgos": [
        {"regla": "C1", "empresa": "Propia", "monto": 10, "que": "FA 1", "hacer": "Asegurar entrega", "nivel": "alto", "restringida": None, "informar": "si"},
        {"regla": "C1", "empresa": "NoProsp", "monto": 99, "que": "FA 2", "hacer": "x", "nivel": "alto", "restringida": "noProspectar", "informar": "no"},
        {"regla": "C1", "empresa": "Archi", "monto": 50, "que": "FA 3", "hacer": "x", "nivel": "alto", "restringida": "archivada", "informar": "aviso"},
        {"regla": "C1", "empresa": "Nueva", "monto": 0, "que": "FA 4", "hacer": "Sin dato", "nivel": "info", "restringida": None, "informar": "si", "sinDato": True}]}, open(cj, "w"))
    rs = resumen(tmp, "2026-11-13", "## Integridad x: PASA\nEmpujes de hoy: 1\n- A\nFichas leídas: 1\nControl de cuentas: 1 (cierra)", cj)
    t("Propia" in rs and "NoProsp" not in rs and "[aviso archivada] Archi" in rs and "[sin dato] Nueva" in rs,
      "v1.2: resumen informa la propia, avisa la archivada, marca sin dato y no informa no prospectar (decisión 105)")
    t("Empujes de hoy: 1" in rs and os.path.exists(os.path.join(tmp, "salida", "resumen.txt")), "v1.2: resumen trae el orden del día y queda en salida/")
    # v1.3: envío tras pago (decisión 106)
    os.makedirs(os.path.join(tmp, "oportunidades"), exist_ok=True)
    json.dump({"reglasVistas": {"envioTrasPagoHoras": {"valor": 48}}}, open(os.path.join(tmp, "datacenter", "reglas_motor.json"), "w"))
    json.dump({"enDeposito": {"dep": "x"}}, open(os.path.join(tmp, "datacenter", "restricciones.json"), "w"))
    mk = lambda fid, hist: json.dump({"empresa": fid, "historial": hist}, open(os.path.join(tmp, "oportunidades", fid + ".json"), "w"))
    mk("a", [{"t": "2026-11-12T10:00:00.000Z", "txt": "Pago confirmado · NM1"}])
    mk("b", [{"t": "2026-11-10T10:00:00.000Z", "txt": "Pago confirmado · NM2"}])
    mk("c", [{"t": "2026-11-10T10:00:00.000Z", "txt": "Pago confirmado · NM3"}, {"t": "2026-11-11T10:00:00.000Z", "txt": "Envío confirmado (Nicolás)"}])
    mk("d", [{"t": "2026-11-12T10:00:00.000Z", "txt": "Facturada"}])
    mk("dep", [{"t": "2026-11-12T10:00:00.000Z", "txt": "Pago confirmado"}])
    cc = {"hallazgos": [{"regla": "C1", "ficha": k, "empresa": k, "que": "FA x", "hacer": "Asegurar entrega", "informar": "si"} for k in ("a", "b", "c", "d", "dep")]}
    pe = {x["ficha"]: x for x in pendientes_envio(tmp, "2026-11-13", cc, dt.datetime(2026, 11, 13, 12, 0))}
    t(set(pe) == {"a", "b"}, "v1.3: pago confirmado + sin despachar = pendiente; con envío confirmado, sin pago o en depósito no")
    t(not pe["a"]["vencido"] and pe["b"]["vencido"] and "VENCIDO" in pe["b"]["estado"], "v1.3: a las 26 h corre, a las 74 h está VENCIDO (48 h)")
    # v1.4: plan cerebro
    os.makedirs(os.path.join(tmp, "cotizaciones"), exist_ok=True)
    json.dump({"numero": "NM9", "cliente": "Campo", "oportunidadId": "e", "estado": "aceptada",
               "hz_operacion": {"pago": "confirmado", "pagoAt": "2026-11-12T12:00:00Z", "despacho": "pendiente"}},
              open(os.path.join(tmp, "cotizaciones", "q9.json"), "w"))
    mk("e", [])
    pe = {x["ficha"]: x for x in pendientes_envio(tmp, "2026-11-13", cc, dt.datetime(2026, 11, 13, 12, 0))}
    t("e" in pe and "hz_operacion" not in pe["e"]["factura"] and "cargar hz_operacion" in pe["a"]["factura"],
      "v1.4: envío tras pago lee hz_operacion; lo que está solo en el historial pide cargar el campo")
    json.dump({"frases": [{"rx": "semana que viene", "tipo": "fecha", "resolver": "lunes_siguiente", "significado": "lunes", "fuente": "x"},
                          {"rx": "mañana", "tipo": "fecha", "resolver": "dia_habil_siguiente", "significado": "hábil", "fuente": "S-m"}]},
              open(os.path.join(tmp, "datacenter", "dictados.json"), "w"))
    t(resolver_dictado(tmp, "la semana que viene", "2026-11-13")[0].endswith("→ 2026-11-16 · fuente: x"), "v1.4: «semana que viene» un viernes = lunes 16/11")
    t("→ 2026-11-16" in resolver_dictado(tmp, "mañana", "2026-11-13")[0], "v1.4: «mañana» un viernes = lunes (día hábil)")
    t(resolver_dictado(tmp, "cualquier cosa", "2026-11-13") == [], "v1.4: frase sin dictado no se interpreta")
    t(any("S-m" in x for x in k12_supuestos(tmp)[0]) or k12_supuestos(tmp)[0][0].startswith("K12 falta"), "v1.4: K12 sin supuestos o con id que falta = FALLA")
    json.dump({"lista": [{"id": "S-m", "ref": "dictados:mañana", "texto": "x"}]}, open(os.path.join(tmp, "datacenter", "supuestos.json"), "w"))
    t(k12_supuestos(tmp)[0] == [], "v1.4: K12 PASA con el supuesto registrado")
    json.dump({"reglasVistas": {"envioTrasPagoHoras": {"valor": 48}, "z": {"valor": 1, "fuente": "SUPUESTO de Claude"}}},
              open(os.path.join(tmp, "datacenter", "reglas_motor.json"), "w"))
    t(any("reglas_motor.z" in x for x in k12_supuestos(tmp)[0]), "v1.4: K12 SUPUESTO de reglas_motor fuera de la lista = FALLA")
    json.dump({"lineas": ["a", "b", "c"], "efectosDesde": 2, "efectos": {
        "2": [{"tipo": "dato", "doc": "reglas_motor", "ruta": "reglasVistas.envioTrasPagoHoras.valor", "valor": 48}]}},
              open(os.path.join(tmp, "datacenter", "decisiones.json"), "w"))
    f11 = k11_efectos(tmp, "2026-11-13")[0]
    t(f11 == ["K11 decisión 3 sin efecto estructurado: cargarlo en decisiones.efectos"], "v1.4: K11 decisión sin efecto = FALLA; efecto en el dato = PASA")
    json.dump({"lineas": ["a"], "efectosDesde": 1, "efectos": {"1": [{"tipo": "cotizacion", "numero": "NM9", "campo": "estado", "valor": "rechazada"}]}},
              open(os.path.join(tmp, "datacenter", "decisiones.json"), "w"))
    t(any("NM9.estado" in x for x in k11_efectos(tmp, "2026-11-13")[0]), "v1.4: K11 efecto distinto del dato = FALLA")
    de = {"cotizacion": {"abiertos": ["enviada"]}}
    t(estado_definicion({"estado": "enviada", "revisionFecha": "2026-11-16"}, "2026-11-13", de) == "vencida_sin_estado",
      "decisión 108: sin vence la cotización está vencida (RENOVAR) aunque tenga revisión pactada")
    t(estado_definicion({"estado": "enviada", "vence": "2026-11-20"}, "2026-11-13", de) == "vigente"
      and estado_definicion({"estado": "enviada", "vence": "2026-11-10", "revisionFecha": "2026-11-16"}, "2026-11-13", de) == "vencida_sin_estado",
      "v1.4: vigente/vencida con vence; la revisión pactada no da vigencia (como el Sales Engine)")
    json.dump({"empresa": "x", "historial": [{"t": "2026-11-12T10:00:00Z", "txt": "hola"}]}, open(os.path.join(tmp, "oportunidades", "h.json"), "w"))
    fa, _ = validar_cambios(tmp, [{"op": "update", "collection": "oportunidades", "doc_id": "h", "data": {"etapa": "x"}}], "2026-11-13")
    t(any("sin if_version" in x for x in fa), "v1.4: escribir sin if_version = FALLA")
    fa, _ = validar_cambios(tmp, [{"op": "update", "collection": "oportunidades", "doc_id": "h", "if_version": 3,
                                   "historialNuevo": [{"t": "2026-11-12T18:00:00Z", "txt": "hola"}]}], "2026-11-13")
    t(any("duplicado" in x for x in fa), "v1.4: escribir historial repetido el mismo día = FALLA")
    fa, _ = validar_cambios(tmp, [{"op": "set", "collection": "stockfish_fichas", "doc_id": "nuevo", "data": {"historial": [{"t": "x", "txt": "y"}]}}], "2026-11-13")
    t(not fa, "v1.4: una copia de motor (stockfish_fichas) se escribe entera, con su historial")
    fa, _ = validar_cambios(tmp, [{"op": "update", "collection": "oportunidades", "doc_id": "h", "if_version": 3, "data": {"historial": []}}], "2026-11-13")
    t(any("historialNuevo" in x for x in fa), "v1.4: en la ficha viva el historial no se pisa entero")
    fa, w = validar_cambios(tmp, [{"op": "update", "collection": "oportunidades", "doc_id": "h", "if_version": 3,
                                   "historialNuevo": [{"t": "2026-11-13T18:00:00Z", "txt": "nuevo"}]}], "2026-11-13")
    t(not fa and len(w[0]["data"]["historial"]) == 2, "v1.4: escribir suma el historial sin duplicar")
    fa, _ = validar_cambios(tmp, [{"op": "update", "collection": "cotizaciones", "doc_id": "q9", "if_version": 2,
                                   "data": {"hz_operacion": {"despacho": "confirmado"}}}], "2026-11-13")
    t(any("despachoAt" in x for x in fa), "v1.4: despacho confirmado sin despachoAt = FALLA")
    json.dump({"que": "lo dice el Sales Engine v4.6"}, open(os.path.join(tmp, "datacenter", "ruteo.json"), "w"))
    t(any("ruteo" in x for x in k7_textos(tmp)), "v1.4: K7 encuentra versiones en textos del datacenter")
    # v1.6: HIVE stock (K14)
    t(k14_stock(tmp, "2026-11-13")[0].startswith("## Stock HIVE (K14): sin datos"), "v1.6: sin hive_stock.json K14 lo dice y sigue")
    json.dump({"numero": "NMs", "cliente": "Cli", "estado": "enviada", "items": [{"codigo": "1349", "articulo": "Cable 48F", "cantidad": 100000},
               {"codigo": "", "articulo": "OLT X7", "cantidad": 1}]}, open(os.path.join(tmp, "cotizaciones", "qs.json"), "w"))
    json.dump({"numero": "NMt", "cliente": "Otro", "estado": "enviada", "items": [{"codigo": "", "articulo": "Cable 48F", "cantidad": 1}]},
              open(os.path.join(tmp, "cotizaciones", "qt.json"), "w"))
    t(demanda_cotizada(tmp, "2026-11-13")["1349"]["cotizado"] == 100001, "v1.6: el mismo producto con y sin código se suma una sola vez")
    json.dump({"corte": "2026-11-06", "productos": {"1349": {"nombre": "Cable 48F", "stock": 72000, "transito": 0}}, "sinCatalogo": ["OLT X7"]},
              open(os.path.join(tmp, "hive_stock.json"), "w"))
    os.makedirs(os.path.join(tmp, "reportes"), exist_ok=True)
    json.dump({"formato": {"f": ["fecha", "tipo", "producto", "cantidad"]}, "dic": {}, "hasta": "2026-11-10",
               "d": [["2026-11-05", "Remito de Venta", "Cable 48F", 5000], ["2026-11-08", "Remito de Venta", "Cable 48F", 2000]]},
              open(os.path.join(tmp, "reportes", "r21.json"), "w"))
    t(remitos_desde(tmp, "2026-11-06", {"cable 48f": "1349"})[0] == {"1349": 2000}, "v1.6: solo resta los remitos posteriores a la foto de HIVE")
    k = "\n".join(k14_stock(tmp, "2026-11-13"))
    t("AVISO K14 Cable 48F: stock 70000 y piden 100001" in k and "OLT X7: no está en el catálogo" in k and "(7 días)" in k,
      "v1.6: K14 avisa lo que no alcanza, lo que no está en el catálogo y la edad de la foto")
    # v1.7: mapa, selector, archivo comprimido
    json.dump({"modulos": {"a": {"que": "x", "lee": "y", "produce": "z", "docs": ["reglas_motor", "respaldo_*"]},
                           "b": {"que": "x", "lee": "y", "produce": "z", "docs": ["respaldo_2*"]}},
               "pedidos": [{"pedido": "Loki (arranque)", "rx": "^\\s*loki\\b", "modulo": "a", "leer": ["a"], "motor": "m", "skill": "s", "modelo": "M"}]},
              open(os.path.join(tmp, "datacenter", "ruteo.json"), "w"))
    json.dump({}, open(os.path.join(tmp, "datacenter", "respaldo_2026.json"), "w"))
    f15 = k15_mapa(tmp)[0]
    t(any("respaldo_2026 está en 2" in x for x in f15) and any("decisiones no pertenece" in x for x in f15), "v1.7: K15 marca documentos sin módulo y en dos módulos")
    t(selector(tmp, "Loki")[0]["pedido"] == "Loki (arranque)" and selector(tmp, "cualquier cosa") == [], "v1.7: el selector elige por el pedido y sin match no inventa")
    orig = {"nombre": "x", "v": [1, 2.0, "ñ"], "z": {"a": None}}
    pk = empacar(orig)
    t(pk["empaquetado"] == "gzip+base64" and desempacar(pk) == orig and empacar(pk) is pk, "v1.7: empacar y desempacar devuelven el original; no se empaca dos veces")
    fa, w = validar_cambios(tmp, [{"op": "set", "collection": "datacenter", "doc_id": "respaldo_nuevo", "data": orig}], "2026-11-13")
    t(not fa and not w[0]["data"].get("empaquetado"), "v1.7: escribir NO comprime (la plataforma pide datos, no archivos en base64)")
    print("RESULTADO:", "PASA" if ok else "FALLA")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    pc = sub.add_parser("consulta")
    pc.add_argument("--raiz", required=True); pc.add_argument("texto", nargs="+")
    pz = sub.add_parser("cierre")
    pz.add_argument("--raiz", required=True); pz.add_argument("--hoy", default=dt.date.today().isoformat())
    for n in ("dia", "comparar", "oro", "k10"):
        p = sub.add_parser(n)
        p.add_argument("--raiz", required=True)
        p.add_argument("--hoy", default=dt.date.today().isoformat())
        if n == "dia":
            p.add_argument("--buzon", nargs="*"); p.add_argument("--skills")
        if n == "comparar":
            p.add_argument("--codigo-antes"); p.add_argument("--json-antes"); p.add_argument("--reglas-antes")
    ps_ = sub.add_parser("selector")
    ps_.add_argument("--raiz", required=True); ps_.add_argument("texto", nargs="+")
    pz_ = sub.add_parser("desempacar")
    pz_.add_argument("--raiz", required=True); pz_.add_argument("doc")
    pp = sub.add_parser("productos")
    pp.add_argument("--raiz", required=True); pp.add_argument("--hoy", default=dt.date.today().isoformat())
    pd = sub.add_parser("dictado")
    pd.add_argument("--raiz", required=True); pd.add_argument("--hoy", default=dt.date.today().isoformat()); pd.add_argument("texto", nargs="+")
    pe_ = sub.add_parser("escribir")
    pe_.add_argument("--raiz", required=True); pe_.add_argument("--hoy", default=dt.date.today().isoformat()); pe_.add_argument("--cambios", required=True)
    sub.add_parser("test")
    a = ap.parse_args()
    if a.cmd == "dia":
        return cmd_dia(a)
    if a.cmd == "consulta":
        return cmd_consulta(a)
    if a.cmd == "cierre":
        return cmd_cierre(a)
    if a.cmd == "comparar":
        if not (a.codigo_antes or a.json_antes):
            raise SystemExit("FALLA: comparar necesita --codigo-antes o --json-antes")
        return cmd_comparar(a)
    if a.cmd == "oro":
        return cmd_oro(a, modulo_con_reglas(a.raiz))
    if a.cmd == "k10":
        return cmd_k10(a)
    if a.cmd == "selector":
        return cmd_selector(a)
    if a.cmd == "desempacar":
        return cmd_desempacar(a)
    if a.cmd == "productos":
        return cmd_productos(a)
    if a.cmd == "dictado":
        return cmd_dictado(a)
    if a.cmd == "escribir":
        return cmd_escribir(a)
    if a.cmd == "test":
        return cmd_test(a)
    ap.print_help()


if __name__ == "__main__":
    sys.exit(main())

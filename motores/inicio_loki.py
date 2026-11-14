#!/usr/bin/env python3
"""
inicio_loki.py · Horizon CRM · script de inicio de chat (v1.7, 11/11/2026)

Lee SIEMPRE igual lo que Claude ya exportó a disco y devuelve el resumen del día en ~80 líneas.
No escribe nada en el CRM ni en Drive. El script ordena con reglas fijas; Claude lee y explica.
Solo biblioteca estándar de Python (sin instalar nada).

Uso:
  python3 -I inicio_loki.py --crm CARPETA_oportunidades [--continuidad continuidad.json]
        [--buzon para_CRM_*.md ...] [--hoy AAAA-MM-DD] [--top 5]
        [--docs CARPETA_datacenter]            (v1.1: chequeo de integridad contra datacenter/manifiesto)
  python3 -I inicio_loki.py --sellar --docs CARPETA_datacenter --continuidad continuidad.json
        --hoy AAAA-MM-DD --version X.Y --nota "qué cambió" --out manifiesto_nuevo.json   (solo con hacelo)
  python3 -I inicio_loki.py --consulta "texto" --crm CARPETA_oportunidades --docs CARPETA_datacenter
        [--continuidad continuidad.json]   (v1.3: chequeo ANTES de preguntarle algo a Nicolás)
  python3 -I inicio_loki.py --test

Reglas vigentes (v1.3). Con --docs, el resumen del día termina con TODAS las decisiones de
datacenter/decisiones (una línea cada una, el núcleo de la regla). Claude no elige qué leer: el script lo imprime.
Consulta (v1.3). Antes de preguntarle algo a Nicolás sobre una cuenta, un vínculo o un pendiente, Claude corre
--consulta con el nombre o el tema: busca en la ficha viva (empresa, id, CUIT, próxima acción, notas, historial),
en decisiones, en todas las bitácoras/cierres y en la continuidad. Si aparece la respuesta, no se pregunta
(regla 10/11). Busca todas las palabras (sin acentos ni mayúsculas) en el mismo texto.

Notas vs ficha (v1.4). Cada frase de la nota de continuidad que tiene una duda («verificar», «confirmar», «¿…?»,
«pendiente», «consultar», «ver si», «de quién») y nombra una cuenta (nombre único en las fichas) se cruza con la
ficha viva: si la ficha tiene un dictado de Nicolás de los últimos 7 días, se avisa «REVISAR NOTA» con la cita.
Manda la ficha (caso Tecnet 10/11: la nota decía «verificar vendedor» y la ficha ya tenía «Tecnet sumala»).
Restricciones (v1.4): datacenter/restricciones es dato fijo del manifiesto (lista única de cinco_cosas y Sales Engine).
v1.6 (11/11, L0, hacelo 14:31): las excepciones (Fullsat/Telviso) y las cuentas fuera / de Nicolás salen de
datacenter/restricciones, no del código. Suma el CONTROL DE COHERENCIA (con --sf y --cot), que va antes del día:
  K1 restricciones tiene las claves L0 (excepcionesNicolas, cuentasFuera, enDeposito, cuentasDeNicolas)   -> si no, FALLA
  K2 decisión sobre una cuenta (fuera / de Nicolás / en depósito) sin reflejo en restricciones o ficha    -> FALLA
  K3 cuenta fuera que igual sale en un carril del día                                                    -> FALLA
  K4 cotización: número o estado del CRM distinto de la copia de Stockfish                                -> FALLA (re-correr Stockfish)
  K5 ficha del CRM que Stockfish no tiene                                                                 -> FALLA (re-correr Stockfish)
  K6 comprador sin ficha ni restricción (Stockfish sin ficha con compras): lista a resolver una vez       -> AVISO
Una FALLA de coherencia no frena el día: se dice primero y el motor que usa ese dato se toma con pinzas.
v1.8 (11/11 15:49, «terminemos el datacenter»):
  - datacenter/ruteo (vivo): capas L0-L3 y despachador pedido -> motor, capas, skill, modelo.
  - K7 skills (con --skills CARPETA): cada skill del ruteo existe y no cita versiones de motor viejas -> AVISO.
  - --cierre --bitacora ARCHIVO --out PARCHE: errores de Claude de la bitácora que no están en aprendizajes
    -> parche para sumarlos (error -> regla -> test); Claude completa regla y test y escribe con el resto del cierre.
v1.7 (11/11 15:15, hacelo de Nicolás: «todo en módulos, sin conflictos»): el arranque es VISTA del Sales Engine v4.4.
  Con --sales (salida --json del Sales Engine) y --cinco (salida --json de cinco_cosas v2):
  - imprime primero el ORDEN DEL DÍA del Sales Engine (empujes de hoy, RENOVAR obligatorio, cinco cosas);
  - la agenda por fecha (motor de Seguimiento: mover la base) no repite cuentas que el Sales Engine ya empuja con
    plata ni muestra frenadas (una cuenta, un lugar; caso TPP en «Responder» del 11/11);
  - el umbral «por vencer» sale de datacenter/reglas_motor (antes 3 días acá y 2 en el Sales Engine);
  - K4/K5 pasan a AVISO cuando el Sales Engine lee el CRM vivo (Stockfish queda como historial: re-correrlo igual);
  K9 coherencia de motores -> FALLA si: la salida del Sales Engine no es de hoy o no lee el CRM vivo; sus reglas no
     son las de reglas_motor; cinco_cosas no es vista de esa misma salida; una cuenta de las cinco cosas está frenada,
     en cadencia o con otro monto; un número de cotización del Sales Engine no es el del CRM; una frenada sale en la agenda.
v1.5 (11/11): suma datacenter/conciliador (código) y las copias del PM pm_* (fijo: solo cambian al recargar el export
del PM, con respaldo y sello). pm_control_* se reconoce como control (no avisa).

Integridad (v1.1). El manifiesto guarda la huella (sha256, 12 caracteres) de cada documento clave:
  codigo  scripts: la huella del código tiene que coincidir con el manifiesto y con su huellaCodigo  -> si no, FALLA
  fijo    datos que solo cambian al re-correr un motor: si cambió sin sellar                          -> FALLA
  vivo    índice, continuidad, decisiones, registros: tienen que existir; si cambiaron es normal     -> se informa
  dependencias: stockfish_valor = versión del auditor; Monte Carlo corrido sobre el banco actual;
                el último Monte Carlo tiene sus predicciones en banco_registro                       -> si no, FALLA
  documentos nuevos que no están en el manifiesto ni son bitácora/cierre/respaldo                   -> AVISO
Si falla la huella del propio inicio_loki: se frena (no se lista el día). Una FALLA en otro documento
no frena el día: marca qué motor no se usa hasta resolverlo. Sellar solo con todo en PASA.

Reglas fijas (cambiarlas solo con "hacelo" de Nicolás). Se mira una ficha solo si tiene
proximaFecha vencida o de hoy (o una cotización que vence en los próximos 3 días según su texto).
Quedan afuera: archivadas, noProspectar, otroVendedor (Full Sat y Telviso son de Nicolás: no se excluyen)
y las fichas con recompra en espera hasta una fecha futura.
Cada ficha cae en el PRIMER carril que cumple, en este orden:
  1 ENTREGA       etapa ganado y la próxima acción es confirmar entrega / pedir despacho / confirmar pago
  2 COTIZACION    etapa cotizado o negociacion con monto > 0 (o que vence en <= 3 días)
  3 RESPONDER     la próxima acción dice "responder"
  4 RECOMPRA      cliente Horizon y la próxima acción empieza con recompra / reactivar
  5 SEGUIMIENTO   contactado / calificado / ganado con contacto previo
  6 AGENDA VIEJA  el resto (prospecto, pausa, sin contacto): solo se cuenta
Dentro de cada carril: monto mayor primero, después más días vencida.
"""
import argparse, datetime as dt, glob, hashlib, json, os, re, sys
from collections import Counter, defaultdict

VERSION = "1.11"

# ------------------------------------------------------------------ integridad (manifiesto)
CLASES = {
    "codigo": ["script_inicio", "script_control_reportes", "stockfish", "stockfish_auditor",
               "stockfish_controles", "banco_script", "banco_montecarlo", "cinco_cosas", "sales_engine", "conciliador", "script_correr_dia"],
    "fijo": ["reglas", "reglas_motor", "stockfish_oro", "stockfish_valor", "banco_manos", "restricciones",
             "dictados", "supuestos", "definiciones",
             "pm_aprendizajes", "pm_cotizador", "pm_listaVigente", "pm_motorV8", "pm_motorV8_plantilla", "pm_numeracion",
             "pm_plantillaPedido", "pm_preciosEspeciales", "pm_productos", "pm_stock", "pm_vocabulario"],
    "vivo": ["indice", "decisiones", "mercado", "controles", "fundetec", "clientes_resumen",
             "banco_registro", "stockfish_registro", "config/continuidad", "aprendizajes", "ruteo", "hive_stock"],
}
MOTOR = {"script_control_reportes": "control de reportes", "stockfish": "Stockfish v1",
         "stockfish_auditor": "Stockfish auditor", "stockfish_controles": "Stockfish controles",
         "stockfish_valor": "Stockfish valor", "banco_script": "banco de manos", "banco_manos": "banco de manos",
         "banco_montecarlo": "Monte Carlo", "banco_registro": "registro del banco", "reglas": "reglas del datacenter",
         "stockfish_oro": "cuentas de oro", "cinco_cosas": "cinco cosas del día",
         "sales_engine": "Sales Engine v4", "restricciones": "cinco cosas, Sales Engine y conciliador (lista única)",
         "conciliador": "conciliador (factura · remito · ficha · dictado)",
         "script_correr_dia": "correr_dia (cadena, comparador, casos de oro, K10)",
         "reglas_motor": "Sales Engine y vistas (reglas únicas)",
         "dictados": "diccionario de frases de Nicolás (correr_dia dictado)",
         "supuestos": "supuestos vigentes (resumen del día, K12)",
         "definiciones": "definiciones y fuentes únicas (K13)",
         "aprendizajes": "aprendizajes de Claude (error → regla → test)",
         "pm_listaVigente": "precios (copia del PM)", "pm_stock": "stock (copia del PM)", "pm_productos": "fichas de producto (copia del PM)",
         "pm_preciosEspeciales": "precios especiales (copia del PM)", "pm_numeracion": "numeración (copia del PM)"}
PATRONES_CONOCIDOS = (r"^bitacora_", r"^cierre_", r"^respaldo_", r"^skills_copia_", r"^indice_respaldo_", r"^pm_control_",
                      r"_borrador$", r"^manifiesto$")
MAX_HISTORIAL = 10


def h12(texto):
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:12]


def huella_doc(d):
    return h12(json.dumps(d, sort_keys=True, ensure_ascii=False))


def leer_doc(ruta):
    d = json.load(open(ruta, encoding="utf-8"))
    return d.get("data", d) if isinstance(d, dict) and set(d) <= {"data", "id", "version"} and "data" in d else d


def cargar_docs(carpeta, continuidad):
    docs = {}
    for ruta in sorted(glob.glob(os.path.join(carpeta, "*.json"))):
        docs[os.path.splitext(os.path.basename(ruta))[0]] = leer_doc(ruta)
    if continuidad and os.path.exists(continuidad):
        docs["config/continuidad"] = leer_doc(continuidad)
    return docs


def huella_actual(clase, doc):
    if clase == "codigo":
        return h12(doc.get("codigo") or "")
    return huella_doc(doc)


def huella_mc(banco):
    # misma función que banco_montecarlo.py v1.0: huella({"m": manos, "r": recomendadas})
    return h12(json.dumps({"m": banco["manos"]["manos"], "r": banco["recomendadas"]}, sort_keys=True, ensure_ascii=False))


def dependencias(docs):
    fallas = []
    for k in CLASES["codigo"]:
        d = docs.get(k)
        if d and d.get("huellaCodigo"):
            declarada = str(d["huellaCodigo"])[:12]
            if declarada != h12(d.get("codigo") or ""):
                fallas.append((k, f"huellaCodigo declarada {declarada} no coincide con su código"))
    au, va = docs.get("stockfish_auditor"), docs.get("stockfish_valor")
    if au and va and str(au.get("version")) != str(va.get("version")):
        fallas.append(("stockfish_valor", f"generado con auditor v{va.get('version')}, el auditor está en v{au.get('version')}: re-correr"))
    bm, mc, rg = docs.get("banco_manos"), docs.get("banco_montecarlo"), docs.get("banco_registro")
    if bm and mc:
        hm = (mc.get("resultado") or {}).get("huellaEntrada")
        if hm != huella_mc(bm):
            fallas.append(("banco_montecarlo", "el Monte Carlo no se corrió sobre el banco actual: re-correr"))
    if mc and rg:
        hoy_mc = (mc.get("resultado") or {}).get("hoy")
        n_mc = len((mc.get("resultado") or {}).get("porCuenta") or {})
        n_rg = sum(1 for p in rg.get("predicciones") or [] if p.get("fechaPrediccion") == hoy_mc)
        if n_mc != n_rg:
            fallas.append(("banco_registro", f"Monte Carlo del {hoy_mc} tiene {n_mc} cuentas y el registro {n_rg} predicciones"))
    return fallas


def verificar(man, docs, propio_codigo):
    """Devuelve (estado, frenar, lineas). estado: PASA / AVISO / FALLA."""
    fallas, avisos, cambiados = [], [], []
    ent = man.get("entradas") or {}
    frenar = False
    if h12(propio_codigo) != (ent.get("script_inicio") or {}).get("huella"):
        frenar = True
        fallas.append(("script_inicio", "el inicio_loki que corre no es el sellado en el manifiesto"))
    for k, e in sorted(ent.items()):
        d = docs.get(k)
        if d is None:
            if e.get("requerido", True):
                fallas.append((k, "falta (no vino en la exportación o se borró)"))
            continue
        if huella_actual(e["clase"], d) != e["huella"]:
            if e["clase"] in ("codigo", "fijo"):
                if k != "script_inicio" or not frenar:
                    fallas.append((k, "cambió sin sellar el manifiesto"))
            else:
                cambiados.append(k)
    fallas += dependencias(docs)
    for k in sorted(docs):
        if k not in ent and not any(re.search(p, k) for p in PATRONES_CONOCIDOS):
            avisos.append((k, "documento nuevo fuera del manifiesto: clasificarlo al sellar"))
    estado = "FALLA" if fallas else ("AVISO" if avisos else "PASA")
    lineas = [f"## Integridad · manifiesto v{man.get('version')} sellado {man.get('sellado')}: {estado}"
              + (f" · {len(ent)} documentos" if estado == "PASA" else "")]
    vistos = set()
    for k, m in fallas:
        afecta = MOTOR.get(k)
        lineas.append(f"- FALLA {k}: {m}" + (f" → no usar {afecta} hasta resolver" if afecta and afecta not in vistos else ""))
        if afecta: vistos.add(afecta)
    for k, m in avisos:
        lineas.append(f"- AVISO {k}: {m}")
    if cambiados:
        lineas.append(f"- vivos que cambiaron desde el sello (normal): {', '.join(cambiados)}")
    if frenar:
        lineas.append("FRENO: no se lista el día. Volver a extraer el script desde datacenter/script_inicio.")
    return estado, frenar, lineas


def sellar(docs, anterior, hoy, version, nota):
    falt = [k for c in CLASES.values() for k in c if k not in docs]
    dep = dependencias(docs)
    if falt or dep:
        return None, [f"faltan: {falt}"] * bool(falt) + [f"{k}: {m}" for k, m in dep]
    ent = {}
    for clase, ks in CLASES.items():
        for k in ks:
            d = docs[k]
            e = {"clase": clase, "huella": huella_actual(clase, d), "requerido": True}
            if d.get("version") is not None:
                e["versionDoc"] = str(d["version"])
            ent[k] = e
    hist = list((anterior or {}).get("historial") or [])
    if anterior and anterior.get("entradas"):
        prev = anterior["entradas"]
        cambios = sorted(k for k in set(prev) | set(ent) if (prev.get(k) or {}).get("huella") != (ent.get(k) or {}).get("huella"))
        hist.append({"version": anterior.get("version"), "sellado": anterior.get("sellado"), "nota": anterior.get("nota"),
                     "entradas": prev, "cambiosAlSiguiente": cambios})
    man = {"nombre": "Manifiesto del datacenter · Horizon CRM", "version": version, "sellado": hoy,
           "selladoCon": f"inicio_loki.py v{VERSION}", "nota": nota, "entradas": ent,
           "historial": hist[-MAX_HISTORIAL:],
           "reglas": "Se sella solo con todo en PASA y con hacelo de Nicolás. Cada sello nuevo guarda el anterior completo "
                     "en historial (últimos 10). Nunca se edita a mano: se regenera con --sellar."}
    return man, []

EXCEPCIONES_NICOLAS = ()           # v1.6: sale de restricciones.excepcionesNicolas (L0)
L0_CLAVES = ("excepcionesNicolas", "cuentasFuera", "enDeposito", "cuentasDeNicolas")
FUERA, NICOLAS = {}, {}
RE_ENTREGA = re.compile(r"^\s*(confirmar (la )?(entrega|sucursal|pago)|pedir despacho|entrega parcial)", re.I)
RE_VENCE = re.compile(r"vence[a-z ]{0,12}(\d{1,2})/(\d{1,2})", re.I)
POR_VENCER = [None]                # v1.7: datacenter/reglas_motor.porVencerDias (sin el documento: K9 FALLA y vale 2)


def huella_reglas(doc):
    """La misma huella que calcula el Sales Engine v4.4 sobre {clave: valor} de reglas_motor."""
    reg = (doc or {}).get("reglas") or {}
    vals = {k: v.get("valor") for k, v in reg.items() if isinstance(v, dict) and "valor" in v}
    return hashlib.sha256(json.dumps(vals, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12] if vals else ""
ORDEN = ["ENTREGA", "COTIZACION", "RESPONDER", "RECOMPRA", "SEGUIMIENTO"]


def norm(s):
    import unicodedata
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)


def fecha(v):
    try:
        return dt.date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def fmt(d):
    return d.strftime("%d/%m") if d else "—"


def usd(x):
    return "USD " + f"{x:,.0f}".replace(",", ".") if x else ""


def cargar_fichas(carpeta):
    fichas = []
    for ruta in sorted(glob.glob(os.path.join(carpeta, "*.json"))):
        d = json.load(open(ruta, encoding="utf-8"))
        data = d.get("data", d)
        data["_id"] = d.get("id") or os.path.splitext(os.path.basename(ruta))[0]
        fichas.append(data)
    return fichas


def vence_en(txt, hoy):
    m = RE_VENCE.search(txt or "")
    if not m:
        return None
    try:
        return dt.date(hoy.year, int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def _dig(x):
    return re.sub(r"\D", "", str(x or ""))


def cuits_ficha(f):
    s = {_dig(f.get("cuit")), _dig(f.get("facturacionId"))} | {_dig(c) for c in (f.get("sf_cuits") or [])}
    ca = f.get("cuitsAdicionales") or []
    if isinstance(ca, str):
        ca = re.split(r"[,;\s]+", ca)
    s |= {_dig(c) for c in ca}
    return {c for c in s if len(c) >= 8}


def en_lista(f, mapa):
    if not mapa:
        return None
    if f.get("_id") in mapa:
        return f["_id"]
    cs = cuits_ficha(f)
    for k, v in mapa.items():
        if isinstance(v, dict) and _dig(v.get("cuit")) in cs and _dig(v.get("cuit")):
            return k
    return None


def cargar_l0(restr):
    global EXCEPCIONES_NICOLAS
    restr = restr or {}
    EXCEPCIONES_NICOLAS = tuple(norm(e) for e in restr.get("excepcionesNicolas") or ())
    FUERA.clear(); FUERA.update(restr.get("cuentasFuera") or {})
    NICOLAS.clear(); NICOLAS.update(restr.get("cuentasDeNicolas") or {})
    return [k for k in L0_CLAVES if k not in restr]


LEGAL = {"s", "r", "l", "a", "srl", "sa", "sas", "sapem", "ltda", "coop", "cooperativa", "de", "la", "el", "del", "y",
         "internet", "telecomunicaciones"}


def clave_nombre(nombre):
    """Nombre distintivo para buscar una cuenta en un texto (sin sufijos legales); '' si es muy corto."""
    k = " ".join(w for w in norm_txt(nombre).split() if w not in LEGAL)
    return k if len(k) >= 4 else ""


K2_TIPOS = (("fuera", re.compile(r"cuentas? fuera", re.I)),
            ("nicolas", re.compile(r"es cuenta de nicol|son cuentas de nicol|es de nicol", re.I)),
            ("deposito", re.compile(r"en dep[oó]sito", re.I)))


def coherencia(fichas, docs, sf, cots, carriles, restr, sales=None, cinco=None, hoy=None, frenadas_en_agenda=()):
    """Control de coherencia L0 (K1-K6) + K9 motores (v1.7). Devuelve (veredicto, líneas)."""
    falla, aviso = [], []
    vivo = bool(sales and sales.get("lector") == "crm_vivo")
    faltan = [k for k in L0_CLAVES if k not in (restr or {})]
    if faltan:
        falla.append(f"K1 restricciones sin claves L0: {', '.join(faltan)}")
    restr = restr or {}
    dep = restr.get("enDeposito") or {}
    # K2: decisiones sobre cuentas con reflejo en restricciones o ficha
    cuentas = []   # (clave, ficha|None, tipo de lista)
    for f in fichas:
        k = clave_nombre(f.get("empresa"))
        if k:
            cuentas.append((k, f))
    lista_k = {"fuera": {clave_nombre((v or {}).get("empresa")) for v in FUERA.values() if isinstance(v, dict)},
               "nicolas": {clave_nombre((v or {}).get("empresa")) for v in NICOLAS.values() if isinstance(v, dict)}
                          | {e for e in EXCEPCIONES_NICOLAS}}
    lineas = (docs.get("decisiones") or {}).get("lineas") or []
    for n, ln in enumerate(lineas, 1):
        txt = norm_txt(ln)
        for tipo, rx in K2_TIPOS:
            if not rx.search(ln):
                continue
            nombradas = [(k, f) for k, f in cuentas if re.search(r"\b" + re.escape(k) + r"\b", txt)]
            en_lista_txt = [k for k in lista_k.get(tipo, ()) if k and re.search(r"\b" + re.escape(k) + r"\b", txt)]
            sin = []
            for k, f in nombradas:
                if tipo != "fuera" and f.get("archivada"):   # duplicado archivado: no cuenta (caso San Luis CTV r020)
                    continue
                if tipo == "fuera":
                    ok = k in lista_k["fuera"] or en_lista(f, FUERA) or f.get("otroVendedor") or f.get("noProspectar") or f.get("archivada")
                elif tipo == "nicolas":
                    ok = en_lista(f, NICOLAS) or any(e in norm(f.get("empresa")) for e in EXCEPCIONES_NICOLAS) or not (
                        f.get("otroVendedor") or f.get("noProspectar") or f.get("archivada"))
                else:
                    ok = f.get("_id") in dep
                if not ok:
                    sin.append(f.get("empresa"))
            if sin:
                falla.append(f"K2 decisión {n} ({tipo}) sin reflejo: {', '.join(sorted(set(sin)))}")
            elif not nombradas and not en_lista_txt:
                aviso.append(f"K2 decisión {n} ({tipo}): no se identificó la cuenta en fichas ni restricciones")
    # K3: cuenta fuera en un carril del día
    for c, lista in carriles.items():
        for f in lista:
            if en_lista(f, FUERA):
                falla.append(f"K3 cuenta fuera en el carril {c}: {f.get('empresa')}")
    # K4 / K5 / K6 con la copia de Stockfish
    if sf is not None:
        cubiertas = set(sf)
        for i, d in sf.items():
            cubiertas |= set(d.get("sf_fichas") or [])
        for f in fichas:
            if f["_id"] not in cubiertas:
                (aviso if vivo else falla).append(f"K5 ficha sin Stockfish: {f.get('empresa')} ({f['_id']})"
                                                  + (" · el Sales Engine la lee del CRM vivo; re-correr Stockfish" if vivo else ""))
        sfq = {q.get("id"): (q, d.get("empresa")) for d in sf.values() for q in d.get("sf_cotizaciones") or [] if q.get("id")}
        for cid, q in sorted((cots or {}).items()):
            if cid not in sfq:
                continue
            s, emp = sfq[cid]
            k4 = aviso if vivo else falla
            nota = " · los motores usan el CRM vivo; re-correr Stockfish" if vivo else ""
            if (q.get("numero") or "") != (s.get("numero") or ""):
                k4.append(f"K4 {emp}: cotización {cid} es {q.get('numero')} en el CRM y {s.get('numero')} en Stockfish{nota}")
            if norm(q.get("estado")) in ("perdida", "perdido") and s.get("estadoReal") in ("vigente", "vencida_sin_estado"):
                k4.append(f"K4 {emp}: cotización {q.get('numero') or cid} perdida en el CRM y {s.get('estadoReal')} en Stockfish{nota}")
        sueltas = []
        for i, d in sf.items():
            if not d.get("sf_sinFicha"):
                continue
            f = dict(d, _id=i)
            if en_lista(f, FUERA) or en_lista(f, NICOLAS):
                continue
            u = ((d.get("sf_compras") or {}).get("usdBrutoNeto") or 0)
            if u > 0:
                sueltas.append((u, d.get("empresa") or i))
        if sueltas:
            sueltas.sort(reverse=True)
            aviso.append(f"K6 compradores sin ficha ni restricción: {len(sueltas)} (a resolver una vez) · mayores: "
                         + ", ".join(f"{e} {usd(u)}" for u, e in sueltas[:5]))
    if sales is not None:
        falla += k9_motores(docs, sales, cinco, cots, hoy, frenadas_en_agenda)
    ver = "FALLA" if falla else "PASA"
    out = [f"## Coherencia L0: {ver}" + (f" · {len(falla)} para corregir" if falla else "")]
    out += [f"- {x}" for x in falla[:15]] + ([f"- … y {len(falla) - 15} más"] if len(falla) > 15 else [])
    k45 = [x for x in aviso if x.startswith(("K4", "K5"))]
    otros = [x for x in aviso if not x.startswith(("K4", "K5"))]
    out += [f"- AVISO {x}" for x in otros[:6]]
    if k45:
        out.append(f"- AVISO Stockfish con foto vieja ({len(k45)}): " + "; ".join(x.split(" · ")[0] for x in k45[:4])
                   + " · no cambia las decisiones (el Sales Engine lee el CRM vivo); re-correr Stockfish")
    return ver, out


def k9_motores(docs, sales, cinco, cots, hoy, frenadas_en_agenda):
    """K9 (v1.7): los motores deciden con el mismo dato y las mismas reglas. Devuelve las FALLAS."""
    f = []
    v = str(sales.get("version") or "0.0").split(".")
    try:
        v_ok = (int(v[0]), int(v[1])) >= (4, 4)
    except ValueError:
        v_ok = False
    if not v_ok or sales.get("lector") != "crm_vivo":
        f.append(f"K9 el Sales Engine v{sales.get('version')} no lee el CRM vivo (hace falta v4.4)")
    if hoy and sales.get("hoy") != hoy.isoformat():
        f.append(f"K9 la salida del Sales Engine es del {sales.get('hoy')}, no de hoy: re-correrlo")
    hr = huella_reglas(docs.get("reglas_motor"))
    if not hr:
        f.append("K9 falta datacenter/reglas_motor (reglas únicas de los motores)")
    elif sales.get("reglasHuella") != hr:
        f.append(f"K9 el Sales Engine decidió con reglas {sales.get('reglasHuella')} y reglas_motor es {hr}: re-correrlo")
    filas = {r["id"]: r for r in sales.get("filas") or []}
    fren = set(sales.get("bloqueadas") or {})
    if cinco is not None and cinco.get("vistaDe") != sales.get("huella"):
        f.append(f"K9 cinco_cosas es vista de la salida {cinco.get('vistaDe')} y el Sales Engine dio {sales.get('huella')}: re-correr")
    for lugar, it in ((cinco or {}).get("items") or sales.get("cinco") or {}).items():
        c, r = it.get("cuenta"), filas.get(it.get("cuenta"))
        if c in fren or r is None:
            f.append(f"K9 {lugar}: {it.get('empresa')} está frenada o fuera del Sales Engine")
            continue
        if lugar in ("COTIZACION", "REPOSICION") and (not r.get("hoy") or abs((it.get("monto") or 0) - (r.get("usd") or 0)) > 0.5):
            f.append(f"K9 {lugar}: {it.get('empresa')} con {it.get('monto')} y el Sales Engine dice {r.get('usd')} (hoy={r.get('hoy')})")
        if r.get("enCadenciaHasta") and lugar != "RESPONDER":
            f.append(f"K9 {lugar}: {it.get('empresa')} está en cadencia hasta {r['enCadenciaHasta']}")
    for r in filas.values():
        for q in r.get("cotizaciones") or []:
            c = (cots or {}).get(q.get("id"))
            if c and (c.get("numero") or "") != (q.get("numero") or ""):
                f.append(f"K9 {r.get('empresa')}: el Sales Engine dice {q.get('numero')} y el CRM {c.get('numero')}")
    for e in frenadas_en_agenda:
        f.append(f"K9 frenada en la agenda del día: {e}")
    return f


def clasificar(f, hoy):
    """Devuelve (carril|None, motivo_exclusion|None)."""
    nombre = norm(f.get("empresa"))
    es_nicolas = any(e and e in nombre for e in EXCEPCIONES_NICOLAS) or bool(en_lista(f, NICOLAS))
    if en_lista(f, FUERA):
        return None, "cuenta fuera"
    if f.get("archivada"):
        return None, "archivada"
    if not es_nicolas and f.get("noProspectar"):
        return None, "noProspectar"
    if not es_nicolas and f.get("otroVendedor"):
        return None, "otroVendedor"
    rec = f.get("hz_recompra") or {}
    if rec.get("estado") == "espera" and (fecha(rec.get("hasta")) or hoy) > hoy:
        return None, "recompra en espera"
    accion = f.get("proximaAccion") or ""
    pf = fecha(f.get("proximaFecha"))
    etapa = f.get("etapa")
    monto = f.get("monto") or 0
    ve = vence_en(accion, hoy) if etapa in ("cotizado", "negociacion") else None
    por_vencer = ve is not None and 0 <= (ve - hoy).days <= (POR_VENCER[0] if POR_VENCER[0] is not None else 2)
    vencida = pf is not None and pf <= hoy
    if not (vencida or por_vencer):
        return None, "sin fecha o a futuro"
    if etapa == "ganado" and RE_ENTREGA.search(accion):
        return "ENTREGA", None
    if etapa in ("cotizado", "negociacion") and (monto > 0 or por_vencer):
        return "COTIZACION", None
    if "respond" in accion.lower():
        return "RESPONDER", None
    if f.get("clienteHorizon") == "si" and re.match(r"\s*(recompra|reactivar)", accion, re.I):
        return "RECOMPRA", None
    if etapa in ("contactado", "calificado", "ganado") and f.get("ultimoContacto"):
        return "SEGUIMIENTO", None
    return "AGENDA VIEJA", None


def linea(f, hoy):
    pf = fecha(f.get("proximaFecha"))
    uc = fecha(f.get("ultimoContacto"))
    ve = vence_en(f.get("proximaAccion"), hoy) if f.get("etapa") in ("cotizado", "negociacion") else None
    partes = [f"{f.get('empresa', f['_id'])}", f.get("etapa", "")]
    if f.get("monto"):
        partes.append(usd(f["monto"]))
    if pf:
        estado = f" (vencida {(hoy - pf).days} d)" if pf < hoy else " (hoy)" if pf == hoy else f" (en {(pf - hoy).days} d)"
        partes.append(f"fecha {fmt(pf)}{estado}")
    if ve:
        partes.append(("venció " if ve < hoy else "vence ") + fmt(ve))
    if uc:
        partes.append(f"último contacto hace {(hoy - uc).days} d")
    if f.get("cuentaCompartida"):
        partes.append("COMPARTIDA")
    accion = (f.get("proximaAccion") or "").replace("\n", " ")
    return "- " + " · ".join(p for p in partes if p) + f"\n    → {accion[:130]}"


# ---------------- v1.8 · K7 skills y ruteo ----------------
RX_VER = re.compile(r"(sales[ _]engine|inicio[_ ]loki|cinco[_ ]cosas|conciliador)`?\s*v?(\d+\.\d+)", re.I)
RX_CRM = re.compile(r"\bCRM\s+v(\d{3})\b")


def versiones_vigentes(docs):
    v = {}
    for doc, clave in (("sales_engine", "sales engine"), ("script_inicio", "inicio loki"),
                       ("cinco_cosas", "cinco cosas"), ("conciliador", "conciliador")):
        if docs.get(doc, {}).get("version"):
            v[clave] = str(docs[doc]["version"])
    crm = (docs.get("ruteo") or {}).get("crmVersion")
    if crm:
        v["crm"] = str(crm)
    return v


def k7_skills(docs, skills_dir):
    """AVISO por skill del ruteo que falta o cita una versión de motor que no es la vigente."""
    ruteo = docs.get("ruteo") or {}
    vig = versiones_vigentes(docs)
    avisos = []
    if not ruteo:
        return ["K7 falta datacenter/ruteo (capas y despachador)"]
    for sk in sorted({x.get("skill") for x in ruteo.get("pedidos") or [] if x.get("skill")}):
        ruta = os.path.join(skills_dir, sk, "SKILL.md")
        if not os.path.exists(ruta):
            avisos.append(f"K7 skill {sk} del ruteo no está instalada"); continue
        txt = open(ruta, encoding="utf-8", errors="replace").read()
        viejas = set()
        for m in RX_VER.finditer(txt):
            k = re.sub(r"[_ ]+", " ", m.group(1).lower())
            if k in vig and m.group(2) != vig[k]:
                viejas.add(f"{k} v{m.group(2)} (vigente v{vig[k]})")
        for m in RX_CRM.finditer(txt):
            if "crm" in vig and m.group(1) != vig["crm"]:
                viejas.add(f"CRM v{m.group(1)} (vigente v{vig['crm']})")
        if viejas:
            avisos.append(f"K7 skill {sk} cita " + ", ".join(sorted(viejas)) + ": manda el manifiesto, actualizar la skill")
    return avisos


# ---------------- v1.8 · cierre: errores de la bitácora -> aprendizajes ----------------
def errores_bitacora(bit):
    out = []
    def visitar(o, ruta):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "erroresClaude" and isinstance(v, list):
                    out.extend((ruta or "bitacora", str(e)) for e in v if str(e).strip())
                else:
                    visitar(v, k if not ruta else ruta)
    visitar(bit, "")
    return out


def ya_aprendido(err, aprend_txt):
    w = [x for x in palabras(err).split() if len(x) > 4]
    if not w:
        return True
    return sum(1 for x in set(w) if x in aprend_txt) / len(set(w)) >= 0.6


def cierre(bit, aprend):
    lista = (aprend or {}).get("aprendizajes") or []
    txt = palabras(json.dumps(lista, ensure_ascii=False))
    n = max([int(re.sub(r"\D", "", x.get("id", "A0")) or 0) for x in lista] or [0])
    nuevos = []
    for chat, e in errores_bitacora(bit):
        if not ya_aprendido(e, txt) and not any(palabras(e) == palabras(x["error"]) for x in nuevos):
            n += 1
            nuevos.append({"id": f"A{n:02d}", "error": e, "fuente": f"bitácora {bit.get('fecha', '')} · {chat}",
                           "patron": "", "regla": "", "test": "", "estado": "a completar por Claude en el cierre"})
    return nuevos


def palabras(s):
    import unicodedata
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def nucleo(ln):
    """'10/11 · Nicolás · regla · porqué · quién' -> '10/11 · regla'."""
    p = [x.strip() for x in str(ln).split(" · ")]
    if len(p) >= 3 and palabras(p[1]).startswith("nicolas"):
        cuerpo = p[2:]
        if len(cuerpo) > 1 and re.match(r"(claude|aplic)", palabras(cuerpo[-1])):
            cuerpo = cuerpo[:-1]                      # quién lo aplicó no es parte de la regla
        return " · ".join([p[0]] + cuerpo)
    return str(ln)


def reglas_vigentes(docs, ancho=2000, ultimas=None):
    """v1.9: ultimas=N imprime solo las N decisiones más nuevas (las anteriores ya viven en restricciones y reglas_motor,
    que los motores aplican, y se leen con --consulta); sin ultimas (o --reglas-todas) imprime todas."""
    lin = ((docs or {}).get("decisiones") or {}).get("lineas") or []
    desde = max(0, len(lin) - ultimas) if ultimas else 0
    out = [f"## Reglas vigentes · datacenter/decisiones ({len(lin)}"
           + (f", últimas {len(lin) - desde}" if desde else "") + ") · antes de preguntar: --consulta"
           + (" · todas: --reglas-todas" if desde else "")]
    for i, ln in enumerate(lin, 1):
        if i <= desde:
            continue
        t = nucleo(ln)
        out.append(f"{i:>2}. " + (t if len(t) <= ancho else t[:ancho - 1] + "…"))
    return out


def textos(o, ruta=""):
    """Todos los strings de un documento con su ruta (para la consulta)."""
    if isinstance(o, dict):
        for k, v in o.items():
            yield from textos(v, f"{ruta}.{k}" if ruta else str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from textos(v, f"{ruta}[{i}]")
    elif isinstance(o, str):
        yield ruta, o


def consulta(q, fichas, docs, maximo=40):
    ws = palabras(q).split()
    if not ws:
        return ["CONSULTA: texto vacío"]
    def ok(t):
        t = palabras(t)
        return all(w in t for w in ws)
    hits = []
    for f in fichas or []:
        campos = ("empresa", "_id", "cuit", "contacto", "proximaAccion", "proximaFecha", "etapa", "notas",
                  "otroVendedor", "noProspectar", "cuentaCompartida", "archivada")
        cab = " ".join(str(f.get(k) or "") for k in campos)
        cuits = " ".join(str(c.get("cuit") or "") for c in f.get("cuitsAdicionales") or [] if isinstance(c, dict))
        if ok(cab + " " + cuits):
            marcas = [k for k in ("otroVendedor", "noProspectar", "cuentaCompartida", "archivada") if f.get(k)]
            hits.append(("ficha", f"{f.get('empresa')} ({f['_id']}) · etapa {f.get('etapa')} · próx {f.get('proximaFecha') or '—'}: "
                         f"{(f.get('proximaAccion') or '')[:140]}" + (f" · MARCAS {marcas}" if marcas else "")))
        for h in f.get("historial") or []:
            if isinstance(h, dict) and ok(h.get("txt")) :
                hits.append(("historial", f"{f.get('empresa')} {str(h.get('t'))[:10]}: {h.get('txt')[:200]}"))
    for i, ln in enumerate(((docs or {}).get("decisiones") or {}).get("lineas") or [], 1):
        if ok(ln):
            hits.append(("decisión", f"{i}. {ln[:260]}"))
    for k in sorted(docs or {}):
        if re.match(r"^(bitacora_|cierre_)", k) or k == "config/continuidad":
            for ruta, t in textos(docs[k]):
                if ok(t):
                    hits.append((k, f"{ruta}: {t[:220]}"))
    orden = {"decisión": 0, "ficha": 1, "historial": 2}
    hits.sort(key=lambda x: (orden.get(x[0], 3), x[0]))
    out = [f"## Consulta «{q}»: {len(hits)} coincidencias" + (f" (se muestran {maximo})" if len(hits) > maximo else "")]
    out += [f"- [{f}] {t}" for f, t in hits[:maximo]]
    if not hits:
        out.append("- sin coincidencias: recién ahí se le puede preguntar a Nicolás")
    return out


RX_DUDA = re.compile(r"verificar|confirmar|¿|\?|pendiente|consultar|ver si|chequear|de qui[eé]n|si es suy", re.I)
STOP_NOMBRE = {"cooperativa", "cable", "internet", "video", "telecom", "telecomunicaciones", "servicios", "comunicaciones",
               "grupo", "digital", "sistemas", "soluciones", "fibra", "redes", "electrica", "television", "telefonica",
               "group", "network", "online", "sapem", "televisora", "color", "argentina", "informatica", "informaticas"}


def norm_txt(s):
    import unicodedata
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def notas_vs_ficha(cont, fichas, hoy, dias=7):
    """Frases con duda de la continuidad que nombran una cuenta cuya ficha tiene dictado de Nicolás reciente."""
    claves = defaultdict(list)
    for f in fichas:
        if f.get("archivada"):
            continue
        toks = [w for w in re.findall(r"[a-z0-9]+", norm_txt(f.get("empresa"))) if len(w) >= 5 and w not in STOP_NOMBRE]
        if toks:
            claves[toks[0]].append(f)
    out, vistos = [], set()
    for t in (cont or {}).get("abiertos") or []:
        for frag in re.split(r"\s·\s|;|\.\s", t.get("linea") or ""):
            if not RX_DUDA.search(frag):
                continue
            nf = norm_txt(frag)
            for k, fs in sorted(claves.items()):
                if len(fs) != 1 or not re.search(rf"\b{re.escape(k)}\b", nf):
                    continue
                f = fs[0]
                dict_ = [(fecha(h.get("t")), h.get("txt") or "") for h in f.get("historial") or []
                         if "nicol" in norm_txt(h.get("txt")) and fecha(h.get("t")) and 0 <= (hoy - fecha(h.get("t"))).days <= dias]
                if not dict_ or (t.get("tema"), f["_id"]) in vistos:
                    continue
                vistos.add((t.get("tema"), f["_id"]))
                d, txt = sorted(dict_, key=lambda x: x[0])[-1]
                out.append(f"- REVISAR NOTA · {t.get('tema')}: «{frag.strip()[:90]}» · la ficha {f.get('empresa')} tiene "
                           f"dictado de Nicolás del {d:%d/%m}: {txt[:150]} → manda la ficha")
    return out


def leer_buzon(rutas):
    abiertos = []
    for r in rutas:
        try:
            texto = open(r, encoding="utf-8").read()
        except OSError:
            continue
        texto = texto.replace("\\", "")
        for ln in texto.splitlines():
            ln = ln.strip()
            if ln.startswith("- [") and "estado: abierto" in ln:
                abiertos.append((os.path.basename(r), ln))
    return abiertos


def main():
    ap = argparse.ArgumentParser(description="Resumen de inicio de chat del Horizon CRM")
    ap.add_argument("--crm")
    ap.add_argument("--continuidad")
    ap.add_argument("--buzon", nargs="*", default=[])
    ap.add_argument("--hoy")
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--docs")
    ap.add_argument("--sellar", action="store_true")
    ap.add_argument("--version")
    ap.add_argument("--nota", default="")
    ap.add_argument("--out")
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--consulta")
    ap.add_argument("--reglas-todas", action="store_true")
    ap.add_argument("--sf")       # v1.6: carpeta stockfish_fichas (coherencia K4-K6)
    ap.add_argument("--cot")      # v1.6: carpeta cotizaciones del CRM (coherencia K4)
    ap.add_argument("--sales")    # v1.7: salida --json del Sales Engine v4.4 (orden del día + K9)
    ap.add_argument("--cinco")    # v1.7: salida --json de cinco_cosas v2 (K9)
    ap.add_argument("--skills")   # v1.8: carpeta de skills instaladas (K7)
    ap.add_argument("--cierre", action="store_true")   # v1.8: errores de la bitácora -> aprendizajes
    ap.add_argument("--bitacora")
    a = ap.parse_args()
    if a.test:
        return test()
    hoy = dt.date.fromisoformat(a.hoy) if a.hoy else dt.date.today()
    propio = open(os.path.abspath(__file__), encoding="utf-8").read()

    if a.sellar:
        if not (a.docs and a.version and a.out and a.hoy):
            print("SELLAR: faltan --docs, --version, --out o --hoy"); return 1
        docs = cargar_docs(a.docs, a.continuidad)
        if "script_inicio" in docs and h12(docs["script_inicio"].get("codigo") or "") != h12(propio):
            print("SELLAR: FALLA · el script que corre no es el que está en datacenter/script_inicio"); return 1
        anterior = docs.get("manifiesto")
        man, err = sellar(docs, anterior, a.hoy, a.version, a.nota)
        if err:
            print("SELLAR: FALLA"); [print(" ·", e) for e in err]; return 1
        json.dump(man, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
        print(f"SELLAR: PASA · manifiesto v{a.version} · {len(man['entradas'])} documentos · historial {len(man['historial'])}")
        return 0

    if a.cierre:
        if not (a.bitacora and a.docs and a.out):
            print("CIERRE: faltan --bitacora, --docs o --out"); return 1
        docs = cargar_docs(a.docs, a.continuidad)
        bit = leer_doc(a.bitacora)
        nuevos = cierre(bit, docs.get("aprendizajes"))
        json.dump({"agregar": nuevos}, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"CIERRE: {len(errores_bitacora(bit))} errores en la bitácora · {len(nuevos)} nuevos para aprendizajes")
        for x in nuevos:
            print(f"- {x['id']} · {x['error'][:160]} ({x['fuente']})")
        return 0

    if a.consulta is not None:
        docs = cargar_docs(a.docs, a.continuidad) if a.docs else {}
        print("\n".join(consulta(a.consulta, cargar_fichas(a.crm) if a.crm else [], docs))); return 0

    integ, docs = [], {}
    if a.docs:
        docs = cargar_docs(a.docs, a.continuidad)
        man = docs.get("manifiesto")
        if not man:
            integ = ["## Integridad: FALLA · no hay datacenter/manifiesto en la exportación"]
        else:
            _, frenar, integ = verificar(man, docs, propio)
            if frenar:
                print("\n".join(integ)); return 2
    if not a.crm:
        print("\n".join(integ) if integ else "falta --crm"); return 0 if integ else 1

    restr = docs.get("restricciones") or {}
    restr = restr.get("data", restr)
    cargar_l0(restr)
    rm = ((docs.get("reglas_motor") or {}).get("reglas") or {}).get("porVencerDias") or {}
    POR_VENCER[0] = rm.get("valor")
    sales = json.load(open(a.sales, encoding="utf-8")) if a.sales else None
    cinco_v = json.load(open(a.cinco, encoding="utf-8")) if a.cinco else None
    fren = set((sales or {}).get("bloqueadas") or {})
    con_plata = {r["id"] for r in (sales or {}).get("filas") or [] if (r.get("usd") or 0) > 0}
    con_plata |= {it.get("cuenta") for it in ((sales or {}).get("cinco") or {}).values()}   # una cuenta, un lugar (Algitech)
    fichas = cargar_fichas(a.crm)
    carriles, excluidas = defaultdict(list), Counter()
    for f in fichas:
        c, motivo = clasificar(f, hoy)
        if c and f["_id"] in fren:
            c, motivo = None, "frenada (Sales Engine)"
        elif c and f["_id"] in con_plata:
            c, motivo = None, "en el orden del Sales Engine"
        if c:
            carriles[c].append(f)
        else:
            excluidas[motivo] += 1

    def clave(f):
        pf = fecha(f.get("proximaFecha")) or hoy
        return (-(f.get("monto") or 0), pf)
    for c in carriles:
        carriles[c].sort(key=clave)

    sf = {os.path.splitext(os.path.basename(p))[0]: leer_doc(p) for p in sorted(glob.glob(os.path.join(a.sf, "*.json")))} if a.sf else None
    cots = {os.path.splitext(os.path.basename(p))[0]: leer_doc(p) for p in sorted(glob.glob(os.path.join(a.cot, "*.json")))} if a.cot else None
    fae = [f.get("empresa") for lst in carriles.values() for f in lst if f["_id"] in fren]
    _, coh = coherencia(fichas, docs, sf, cots, carriles, restr, sales, cinco_v, hoy, fae) if a.docs else ("", [])
    if a.skills and a.docs:
        k7 = k7_skills(docs, a.skills)
        coh = coh + ([f"## Skills K7: {'AVISO' if k7 else 'PASA'}"] + [f"- AVISO {x}" for x in k7])
    out = [f"# Inicio Loki v{VERSION} · {hoy:%d/%m/%Y}", ""] + integ + ([""] if integ else []) + coh + ([""] if coh else [])
    if sales:
        out += orden_del_dia(sales, a.top + 5) + [""]
    n_trab = sum(len(v) for v in carriles.values())
    out.append(f"Fichas leídas: {len(fichas)} · para mirar hoy: {n_trab} · "
               f"afuera: " + ", ".join(f"{n} {m}" for m, n in excluidas.most_common()))
    chequeo = n_trab + sum(excluidas.values())
    out.append(f"Control de cuentas: {n_trab} + {sum(excluidas.values())} = {chequeo} "
               + ("(cierra)" if chequeo == len(fichas) else f"(NO cierra: faltan {len(fichas) - chequeo})"))
    out.append("")
    if sales:
        out.append("# AGENDA DE SEGUIMIENTO (mover la base · sin las cuentas que el Sales Engine ya empuja ni las frenadas)")
    for c in ORDEN:
        lista = carriles.get(c, [])
        if not lista:
            continue
        out.append(f"## {c} ({len(lista)})")
        out += [linea(f, hoy) for f in lista[:a.top]]
        if len(lista) > a.top:
            out.append(f"- … y {len(lista) - a.top} más: " + ", ".join(f.get("empresa", f["_id"]) for f in lista[a.top:a.top + 8]))
        out.append("")
    viejas = carriles.get("AGENDA VIEJA", [])
    if viejas:
        por_etapa = Counter(f.get("etapa") for f in viejas)
        out.append(f"## AGENDA VIEJA ({len(viejas)}): " + ", ".join(f"{n} {e}" for e, n in por_etapa.most_common()) + " · no se listan")
        out.append("")

    if a.continuidad and os.path.exists(a.continuidad):
        d = json.load(open(a.continuidad, encoding="utf-8"))
        d = d.get("data", d)
        out.append("## Nota de continuidad")
        out.append(f"Actualizada: {str(d.get('actualizado'))[:10]} · último chat: {(d.get('ultimoChat') or '')[:260]}")
        for t in d.get("abiertos", []):
            out.append(f"- {t.get('tema')}: {(t.get('linea') or '')[:90]}")
        nv = notas_vs_ficha(d, fichas, hoy)
        out.append(f"## Notas vs ficha: {len(nv)} para revisar" + ("" if nv else " · la nota no contradice dictados recientes"))
        out += nv
        out.append("")
    if a.buzon:
        ab = leer_buzon(a.buzon)
        out.append(f"## Buzón del PM: {len(ab)} avisos abiertos")
        for arch, ln in ab[:a.top + 3]:
            out.append("- " + ln[2:170])
        if len(ab) > a.top + 3:
            out.append(f"- … y {len(ab) - a.top - 3} más")
        out.append("")
    if docs.get("decisiones"):
        out += reglas_vigentes(docs, 300 if not a.reglas_todas else 2000, None if a.reglas_todas else 12) + [""]
    out.append("Regla: esto ordena, no decide. Claude explica y propone; lo estructural espera el «hacelo» de Nicolás.")
    print("\n".join(out))


def orden_del_dia(sales, top):
    """v1.7: lo que decidió el Sales Engine, tal cual (el arranque no recalcula)."""
    filas = sales.get("filas") or []
    hoy_ = [r for r in filas if r.get("hoy")]
    obl = [r for r in filas if r.get("obligatorio")]
    L = [f"# ORDEN DEL DÍA · Sales Engine v{sales.get('version')} (salida {sales.get('huella')})",
         f"Empujes de hoy: {len(hoy_)} · bruto {usd(sum((r.get('usd') or 0) for r in hoy_))} · esperado {usd(sum((r.get('esperado') or 0) for r in hoy_))}"]
    L += [f"- {r['empresa']} · {(r.get('palabras') or '')} · {usd((r.get('usd') or 0))}" + (" · POR VENCER" if r.get("porVencer") else "")
          + (f" · + {r['tambien']}" if r.get("tambien") else "") for r in hoy_[:top]]
    L.append(f"RENOVAR obligatorio ({len(obl)}): " + "; ".join(
        f"{r['empresa']} {(r.get('palabras') or '').split(' · ')[0].replace('Renovar ', '')} {usd((r.get('usd') or 0))}"
        + (f" (agendada {fmt(fecha(r['agendada']))})" if r.get("agendada") else "")
        + (f" (cadencia hasta {fmt(fecha(r['enCadenciaHasta']))})" if r.get("enCadenciaHasta") else "") for r in obl))
    cinco = sales.get("cinco") or {}
    L.append("Cinco cosas: " + " · ".join(f"{k.lower()} {v['empresa']}" for k, v in cinco.items()) if cinco else "Cinco cosas: nada")
    fr = sales.get("bloqueadas") or {}
    if fr:
        L.append("Frenadas: " + ", ".join(v["empresa"] for v in fr.values()))
    return L


def test():
    ok = True
    def t(c, m):
        nonlocal ok
        print(("PASA " if c else "FALLA") + " · " + m); ok &= bool(c)
    propio = "print('hola')"
    banco = {"manos": {"manos": [["a", "2026-11-01", "SG", 0, ""]]}, "recomendadas": {"a": {"jugada": "SG"}}}
    docs = {k: {"x": 1} for c in ("fijo", "vivo") for k in CLASES[c]}
    for k in CLASES["codigo"]:
        docs[k] = {"codigo": f"# {k}"}
    docs["script_inicio"] = {"codigo": propio}
    docs["banco_manos"] = banco
    docs["stockfish_auditor"]["version"] = "2.4"; docs["stockfish_valor"]["version"] = "2.4"
    docs["banco_montecarlo"]["resultado"] = {"huellaEntrada": huella_mc(banco), "hoy": "2026-11-10", "porCuenta": {"a": {}}}
    docs["banco_registro"] = {"predicciones": [{"fechaPrediccion": "2026-11-10"}]}
    man, err = sellar(docs, None, "2026-11-10", "1.0", "prueba")
    t(man is not None and not err, "sella un estado consistente")
    e, fr, _ = verificar(man, docs, propio)
    t(e == "PASA" and not fr, "verifica PASA recién sellado")
    d2 = json.loads(json.dumps(docs)); d2["banco_script"]["codigo"] += "x"
    e, fr, l = verificar(man, d2, propio)
    t(e == "FALLA" and not fr and any("banco_script" in x for x in l), "código cambiado sin sellar = FALLA, no frena")
    e, fr, _ = verificar(man, docs, propio + " ")
    t(fr, "script de inicio distinto al sellado = FRENA")
    d3 = json.loads(json.dumps(docs)); d3["decisiones"]["y"] = 2
    e, _, l = verificar(man, d3, propio)
    t(e == "PASA" and any("decisiones" in x for x in l), "vivo cambiado = PASA e informa")
    d4 = json.loads(json.dumps(docs)); d4["banco_manos"]["manos"]["manos"].append(["a", "2026-11-02", "AD", 2, ""])
    e, _, l = verificar(man, d4, propio)
    t(e == "FALLA" and any("Monte Carlo no se corrió" in x for x in l), "banco cambiado sin re-correr Monte Carlo = FALLA")
    t(sellar(d4, man, "2026-11-11", "1.1", "")[0] is None, "no sella si una dependencia falla")
    d5 = json.loads(json.dumps(docs)); d5["informe_nuevo"] = {}; d5["bitacora_2026-11-11"] = {}
    e, _, l = verificar(man, d5, propio)
    t(e == "AVISO" and sum(x.startswith("- AVISO") for x in l) == 1, "doc nuevo = AVISO; bitácora no avisa")
    d6 = json.loads(json.dumps(docs)); del d6["reglas"]
    t(verificar(man, d6, propio)[0] == "FALLA", "documento requerido faltante = FALLA")
    d7 = json.loads(json.dumps(docs)); d7["stockfish_valor"]["version"] = "2.3"
    t(any("re-correr" in x for x in verificar(man, d7, propio)[2]), "stockfish_valor de otra versión del auditor = FALLA")
    d8 = json.loads(json.dumps(docs)); d8["banco_script"]["huellaCodigo"] = "000000000000"
    t(any("huellaCodigo declarada" in x for x in verificar(man, d8, propio)[2]), "huellaCodigo declarada falsa = FALLA")
    m2, _ = sellar(d3, man, "2026-11-11", "1.1", "otra")
    t(m2["historial"][-1]["version"] == "1.0" and m2["historial"][-1]["cambiosAlSiguiente"] == ["decisiones"]
      and m2["historial"][-1]["entradas"] == man["entradas"], "sello nuevo guarda el anterior completo y qué cambió")
    t(json.dumps(sellar(docs, None, "2026-11-10", "1.0", "prueba")[0], sort_keys=True) == json.dumps(man, sort_keys=True), "determinismo")
    dd = {"decisiones": {"lineas": ["10/11 · Nicolás · San Luis CTV es cuenta de Nicolás · motivo · Claude CRM",
                                    "09/11 · Nicolás · Toda cotización no perdida se renueva · x · y"]},
          "bitacora_2026-11-10": {"hechos": ["Swissnet: renovar la 0000-00018"]},
          "config/continuidad": {"abiertos": [{"tema": "Esperando", "linea": "Telviso NM33/NM46 vigentes"}]}}
    ff = [{"_id": "r017-ctv", "empresa": "San Luis CTV", "etapa": "cotizado", "proximaAccion": "Seguimiento NM22",
           "historial": [{"t": "2026-11-02", "txt": "NM22 clasificada"}]}]
    r = consulta("san luis", ff, dd)
    t(any("[decisión]" in x for x in r) and any("[ficha]" in x for x in r), "consulta encuentra decisión y ficha")
    t(any("[bitacora_2026-11-10]" in x for x in consulta("SWISSNET 0000-00018", [], dd)), "consulta busca en bitácoras sin mayúsculas")
    t(any("[config/continuidad]" in x for x in consulta("telviso", [], dd)), "consulta busca en continuidad")
    t(any("sin coincidencias" in x for x in consulta("pepe inexistente", ff, dd)), "sin coincidencias lo dice")
    cn = {"abiertos": [{"tema": "Dormidos", "linea": "Tecnet 379k, Algitech 275k. Verificar vendedor: pone Tecnet 1º"},
                       {"tema": "Otro", "linea": "Algitech sin dudas"}]}
    fn = [{"_id": "w-tecnet", "empresa": "TECNET BACKBONE", "historial": [{"t": "2026-11-10", "txt": "Nicolás 10/11: Tecnet sumala"}]},
          {"_id": "w-algitech", "empresa": "Algitech", "historial": [{"t": "2026-11-09", "txt": "Nicolás 09/11: algo"}]},
          {"_id": "x", "empresa": "Cooperativa Viejo", "historial": [{"t": "2026-10-01", "txt": "Nicolás 01/10"}]}]
    nv = notas_vs_ficha(cn, fn, dt.date(2026, 11, 10))
    t(len(nv) == 1 and "TECNET" in nv[0] and "sumala" in nv[0], "nota con duda vs dictado reciente = REVISAR NOTA (caso Tecnet)")
    t(notas_vs_ficha(cn, fn, dt.date(2026, 12, 30)) == [], "dictado viejo (>7 d) no avisa")
    rv = reglas_vigentes(dd)
    t(len(rv) == 3 and rv[1].endswith("San Luis CTV es cuenta de Nicolás · motivo"), "reglas vigentes: todas, con el núcleo")
    # v1.9 · arranque corto: solo las últimas N decisiones; --reglas-todas las imprime todas
    dd3 = {"decisiones": {"lineas": [f"{i}. x · y · z · w" for i in range(30)]}}
    rv3 = reglas_vigentes(dd3, 300, 12)
    t(len(rv3) == 13 and "últimas 12" in rv3[0] and rv3[1].startswith("19."), "v1.9: el arranque imprime solo las últimas 12 decisiones")
    t(len(reglas_vigentes(dd3)) == 31 and "últimas" not in reglas_vigentes(dd3)[0], "v1.9: sin recorte imprime todas")
    t("script_correr_dia" in CLASES["codigo"], "v1.9: correr_dia está en el manifiesto como código")
    # v1.6 · coherencia L0 (casos fijos Comworks, Fiberland, Meditel, Nodo Net NM50/NM51, Wisp NM41)
    rs = {"excepcionesNicolas": ["fullsat", "telviso"], "enDeposito": {"w-meditel": "FA 1704 en depósito"},
          "cuentasFuera": {"sf-c30715548999": {"cuit": "30715548999", "empresa": "Comworks SA"}},
          "cuentasDeNicolas": {"sf-c30716386194": {"cuit": "30716386194", "empresa": "Fiberland S.R.L."}}}
    t(cargar_l0(rs) == [], "v1.6: L0 completo")
    fc = [{"_id": "w-meditel", "empresa": "Meditel", "etapa": "ganado"},
          {"_id": "w-fiberland", "empresa": "Fiberland S.R.L.", "cuit": "30716386194", "otroVendedor": "Taddei"},
          {"_id": "w-comworks", "empresa": "Comworks SA", "cuit": "30-71554899-9", "etapa": "ganado",
           "proximaFecha": "2026-11-01", "ultimoContacto": "2026-10-01", "proximaAccion": "seguimiento"},
          {"_id": "h-nodo-net", "empresa": "Nodo Net", "etapa": "cotizado"},
          {"_id": "r128-soluciones-wisp", "empresa": "Soluciones Wisp", "etapa": "ganado"}]
    t(clasificar(fc[2], dt.date(2026, 11, 11)) == (None, "cuenta fuera"), "v1.6: cuenta fuera por CUIT no entra al día (Comworks)")
    t(clasificar(fc[1], dt.date(2026, 11, 11))[1] != "otroVendedor", "v1.6: cuenta de Nicolás no se excluye por otroVendedor (Fiberland)")
    dk = {"decisiones": {"lineas": ["11/11 · Nicolás · Comworks SA, Pogliotti y Generación WiFi son cuentas fuera · x",
                                    "11/11 · Nicolás · Fiberland S.R.L. es cuenta de Nicolás: crear ficha · x",
                                    "11/11 · Nicolás · Meditel FA 1704 queda en depósito a pedido del cliente · x"]}}
    sfk = {"w-meditel": {"empresa": "Meditel"}, "w-comworks": {"empresa": "Comworks SA"}, "w-fiberland": {"empresa": "Fiberland"},
           "r128-soluciones-wisp": {"empresa": "Soluciones Wisp", "sf_cotizaciones": [{"id": "q41", "numero": "NM41", "estadoReal": "vencida_sin_estado"}]},
           "h-nodo-net": {"empresa": "Nodo Net", "sf_cotizaciones": [{"id": "q50", "numero": "NM50", "estadoReal": "vigente"}]},
           "sf-c1": {"empresa": "Suelta SA", "sf_sinFicha": True, "sf_compras": {"usdBrutoNeto": 900}}}
    ck = {"q50": {"numero": "NM50"}, "q41": {"numero": "NM41", "estado": "perdida"}}
    v, L = coherencia(fc, dk, sfk, ck, {}, rs)
    t(v == "FALLA" and any("K4" in x and "perdida" in x and "NM41" in x for x in L), "v1.6: K4 cotización perdida en CRM y viva en Stockfish (Wisp NM41)")
    t(not any("K2" in x and "FALLA" in x for x in L) and not any(x.startswith("- K2") for x in L), "v1.6: K2 decisiones con reflejo no fallan")
    t(any("K6" in x and "Suelta SA" in x for x in L), "v1.6: K6 lista compradores sin ficha ni restricción")
    ck["q50"]["numero"] = "NM51"
    v2, L2 = coherencia(fc, dk, sfk, ck, {}, rs)
    t(any("K4" in x and "NM51" in x and "NM50" in x for x in L2), "v1.6: K4 número distinto CRM/Stockfish (Nodo Net NM51)")
    dep0 = dict(rs, enDeposito={})
    v3, L3 = coherencia(fc, dk, sfk, {}, {}, dep0)
    t(any("K2" in x and "deposito" in x and "Meditel" in x for x in L3), "v1.6: K2 depósito decidido sin reflejo = FALLA")
    v4, L4 = coherencia(fc, dk, {k: v for k, v in sfk.items() if k != "w-fiberland"}, {}, {}, rs)
    t(any("K5" in x and "Fiberland" in x for x in L4), "v1.6: K5 ficha sin Stockfish (Fiberland)")
    v5, L5 = coherencia(fc, dk, None, None, {"SEGUIMIENTO": [fc[2]]}, rs)
    t(any("K3" in x and "Comworks" in x for x in L5), "v1.6: K3 cuenta fuera en un carril = FALLA")
    t(coherencia([], {}, None, None, {}, {})[0] == "FALLA", "v1.6: K1 restricciones sin L0 = FALLA")
    cargar_l0(rs)
    dup = [{"_id": "a", "empresa": "San Luis CTV"}, {"_id": "b", "empresa": "San Luis CTV", "archivada": True, "otroVendedor": "x"}]
    t(coherencia(dup, {"decisiones": {"lineas": ["10/11 · Nicolás · San Luis CTV es cuenta de Nicolás · x"]}}, None, None, {}, rs)[0] == "PASA",
      "v1.6: duplicado archivado no hace fallar K2 (San Luis CTV)")
    # ---- v1.7 · K9 coherencia de motores y K4/K5 a aviso con el Sales Engine vivo
    rmd = {"reglas": {"porVencerDias": {"valor": 2}, "repoAtrasoMax": {"valor": 2.5}}}
    dk9 = dict(dk, reglas_motor=rmd)
    H = dt.date(2026, 11, 11)
    fil = [{"id": "h-nodo-net", "empresa": "Nodo Net", "usd": 20097, "hoy": True, "enCadenciaHasta": "",
            "cotizaciones": [{"id": "q50", "numero": "NM51"}]},
           {"id": "cablenet", "empresa": "Cablenet", "usd": 2897, "hoy": False, "enCadenciaHasta": "2026-11-12", "cotizaciones": []}]
    sal = {"version": "4.4", "lector": "crm_vivo", "hoy": "2026-11-11", "reglasHuella": huella_reglas(rmd), "huella": "h1",
           "filas": fil, "bloqueadas": {"h-tpp": {"empresa": "TPP"}},
           "cinco": {"COTIZACION": {"cuenta": "h-nodo-net", "empresa": "Nodo Net", "monto": 20097}}}
    cv = {"vistaDe": "h1", "items": sal["cinco"]}
    ck2 = {"q50": {"numero": "NM51"}}
    v9, L9 = coherencia(fc, dk9, sfk, ck2, {}, rs, sal, cv, H)
    t(not any("K9" in x for x in L9), "v1.7: K9 PASA con Sales Engine de hoy, mismas reglas y cinco como vista")
    t(any("K4" in x and "AVISO" in x for x in L9) and not any(x.startswith("- K4") for x in L9),
      "v1.7: K4 pasa a AVISO cuando el Sales Engine lee el CRM vivo (Nodo Net NM50/NM51)")
    v9b, L9b = coherencia(fc, dk9, sfk, ck2, {}, rs, dict(sal, reglasHuella="otra"), cv, H)
    t(any("K9" in x and "reglas" in x for x in L9b), "v1.7: K9 FALLA si el Sales Engine decidió con otras reglas")
    malo = dict(sal, cinco={"COTIZACION": {"cuenta": "cablenet", "empresa": "Cablenet", "monto": 2897}})
    v9c, L9c = coherencia(fc, dk9, sfk, ck2, {}, rs, malo, {"vistaDe": "h1", "items": malo["cinco"]}, H)
    t(any("K9" in x and "Cablenet" in x and "cadencia" in x for x in L9c), "v1.7: K9 FALLA si una vista empuja una cuenta en cadencia (Cablenet)")
    v9d, L9d = coherencia(fc, dk9, sfk, ck2, {}, rs, sal, {"vistaDe": "otra", "items": sal["cinco"]}, H)
    t(any("K9" in x and "vista" in x for x in L9d), "v1.7: K9 FALLA si cinco_cosas no es vista de esta salida")
    v9e, L9e = coherencia(fc, dk9, sfk, {"q50": {"numero": "NM52"}}, {}, rs, sal, cv, H)
    t(any("K9" in x and "NM52" in x for x in L9e), "v1.7: K9 FALLA si el número del Sales Engine no es el del CRM")
    v9f, L9f = coherencia(fc, dk9, sfk, ck2, {}, rs, sal, cv, H, ["TPP"])
    t(any("K9" in x and "TPP" in x for x in L9f), "v1.7: K9 FALLA si una frenada sale en la agenda (TPP)")
    v9g, L9g = coherencia(fc, dk, sfk, ck2, {}, rs, sal, cv, H)
    t(any("K9" in x and "reglas_motor" in x for x in L9g), "v1.7: K9 FALLA sin datacenter/reglas_motor")
    v9h, L9h = coherencia(fc, dk9, sfk, ck2, {}, rs, dict(sal, hoy="2026-11-10"), cv, H)
    t(any("K9" in x and "no de hoy" in x for x in L9h), "v1.7: K9 FALLA con salida de otro día")
    POR_VENCER[0] = 2
    t(clasificar({"_id": "x", "empresa": "X", "etapa": "cotizado", "monto": 0, "proximaAccion": "vence el 14/11"}, H)[0] is None,
      "v1.7: por vencer usa reglas_motor (2 días): a 3 días no entra")
    POR_VENCER[0] = None
    o = orden_del_dia(sal, 5)
    t(o[0].startswith("# ORDEN DEL DÍA") and any("Nodo Net" in x for x in o) and any("TPP" in x for x in o),
      "v1.7: orden del día = salida del Sales Engine, con frenadas a la vista")
    # ---- v1.8
    import tempfile
    tmp = tempfile.mkdtemp()
    os.makedirs(os.path.join(tmp, "horizon-crm")); os.makedirs(os.path.join(tmp, "loki-maestro"))
    open(os.path.join(tmp, "horizon-crm", "SKILL.md"), "w").write("usa el CRM v181 y el Sales Engine v4.5")
    open(os.path.join(tmp, "loki-maestro", "SKILL.md"), "w").write("corre inicio_loki v1.8 y sales_engine v4.5")
    d8 = {"sales_engine": {"version": "4.5"}, "script_inicio": {"version": "1.8"}, "cinco_cosas": {"version": "2.0"},
          "ruteo": {"crmVersion": 190, "pedidos": [{"skill": "horizon-crm"}, {"skill": "loki-maestro"}, {"skill": "no-existe"}]}}
    k7 = k7_skills(d8, tmp)
    t(any("horizon-crm" in x and "CRM v181" in x for x in k7), "v1.8: K7 avisa skill que cita una versión vieja del CRM")
    t(not any("loki-maestro" in x for x in k7), "v1.8: K7 no avisa la skill al día")
    t(any("no-existe" in x and "no está instalada" in x for x in k7), "v1.8: K7 avisa skill del ruteo que no está")
    t(k7_skills({}, tmp) == ["K7 falta datacenter/ruteo (capas y despachador)"], "v1.8: K7 sin ruteo = aviso")
    bit = {"fecha": "2026-11-11", "chatA": {"erroresClaude": ["Dijo que Villa del Rosario era venta nueva y era una refacturación"]},
           "chatB": {"erroresClaude": ["En la apertura dijo que Fibernext FA 1715 era la única entrega sin decisión"]}}
    ap8 = {"aprendizajes": [{"id": "A13", "casos": "Fibernext FA 1715 entrega sin decisión apertura dijo única", "patron": "x"}]}
    nv = cierre(bit, ap8)
    t(len(nv) == 1 and nv[0]["id"] == "A14" and "Villa del Rosario" in nv[0]["error"], "v1.8: cierre suma solo el error nuevo, con id siguiente")
    t(cierre(bit, {"aprendizajes": ap8["aprendizajes"] + [{"id": "A14", "casos": "Villa del Rosario venta nueva refacturación dijo"}]}) == [],
      "v1.8: cierre no duplica lo ya aprendido")
    cargar_l0({})
    print("RESULTADO:", "PASA" if ok else "FALLA"); return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

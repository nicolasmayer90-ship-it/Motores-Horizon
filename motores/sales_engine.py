#!/usr/bin/env python3
"""Sales Engine v4.6 · Horizon CRM · empuja las cuentas con UN solo criterio (10/11/2026, hacelo de Nicolás)
Reglas fijas: misma entrada -> misma salida. El script decide; Claude explica. No escribe nada.

Uso:
  python3 -I sales_engine.py dia --sf <dir stockfish_fichas> --crm <dir oportunidades> --banco <banco_manos.json>
        --valor <stockfish_valor.json> --restricciones <restricciones.json> --registro <banco_registro.json>
        --conciliador <salida --json del conciliador> --hoy AAAA-MM-DD [--top 15] [--json salida.json]
  python3 -I sales_engine.py test

Stockfish revisa el pasado (decisión 20, 09/11); el Sales Engine decide qué hacer ahora. La ficha viva es la
entrada: pisa a la copia de Stockfish en lo comercial (próxima acción, etapa, monto, marcas).

CRITERIO ÚNICO (Nicolás 10/11): USD con evidencia que pueden entrar este mes. Cada cuenta tiene un número:
  COTIZACION  suma de sus cotizaciones abiertas (estadoReal vigente o vencida sin estado; total con IVA).
              Toda cotización no marcada perdida sigue viva (decisión 44): si su validez («vence», o el
              límite si no tiene) ya pasó, el empujón es RENOVAR y es OBLIGATORIO (no se saltea ni se saca).
              Si no venció, el empujón es CERRAR.
  ENTREGA     total de las facturas con entrega o despacho pendiente (R07 de Stockfish): ASEGURAR.
  REPOSICION  3+ facturas, la última hace <= 365 d y el ciclo típico (mediana entre compras) se cumple antes
              de fin de mes: la compra típica (mediana del total por factura).
  REEMPLAZO   compró ONU de marca discontinuada en los últimos 365 d y ninguna ONU FiberHome en ese lapso:
              mediana del total de esas facturas.
  resto       0.
  El número de la cuenta es el MAYOR de sus componentes (no se suman tipos: no contar dos veces).
  Orden: USD mayor primero; empate: valor Stockfish (stockfish_valor), después id.
DICTADO MANDA: si la próxima acción de la ficha dice «<número> nunca enviada», esa cotización no suma;
  si además dice «renovar», el empujón es RENOVAR por el monto de la ficha (caso Swissnet 0000-00018 / NM48).
v4.2 (11/11, hacelo de Nicolás tras la auditoría de motores):
  CONCILIADOR  ASEGURAR toma los C1 del conciliador (factura vs remitos, más nuevo que la foto de Stockfish).
               Sin C1 pero con R07 de Stockfish se mantiene, marcado «solo Stockfish». Sin --conciliador: AVISO.
  ENTREGA NUNCA TAPADA  si la cuenta tiene entrega pendiente y gana otro empujón, la entrega se muestra al lado
               («+ Asegurar ...») y el total por asegurar suma TODAS las entregas pendientes.
  TOPE DE ATRASO  reposición solo si última compra / ciclo <= 2,5 (SUPUESTO de Claude, el mismo del motor R6.5).
               Más atraso = cliente dormido: no suma plata este mes y se lista en «Pasaron a reactivar».
  PISO REEMPLAZO  menos de USD 300 no se empuja (SUPUESTO de Claude).
  DOS NÚMEROS  bruto (como antes) y esperado = bruto x P. P: ASEGURAR 1,0 (ya facturado); el resto P(pedido) del
               registro del banco (Monte Carlo) si la cuenta está medida; si no, SUPUESTO = mediana del registro
               (igual que cinco_cosas). En cada cuenta gana el componente de mayor ESPERADO (antes: mayor
               bruto); los demás se muestran al lado («+ ...»). Orden: por vencer (CERRAR que vence en 0..2 d) primero, después esperado,
               bruto, valor Stockfish, id. RENOVAR sigue obligatorio y se lista siempre.
  CADENCIA     si el último contacto fue hace menos de CADENCIA[tipo] días (SUPUESTO de Claude; por cuenta manda
               restricciones.cadencia), la cuenta no sale en los empujes de hoy: figura «en cadencia hasta dd/mm».
               No aplica a lo que vence en 0..2 d. RENOVAR en cadencia sigue en la lista obligatoria con la nota.
Excluidas (mismas reglas que cinco_cosas): sin ficha, archivada, noProspectar, otroVendedor (salvo Fullsat y
  Telviso), cuentaCompartida, recompra en espera, solo HFC. Bloqueo comercial (esperar dictado, pide Huawei,
  BLOQUEOS_DICTADOS con su fuente):
  no se empuja y se informa. Etapa perdido no suma cotizaciones.
v4.6 (12/11, Nicolás 08:19: «anotá ese error y corregí esa acción en general: precisión y velocidad, con coherencia»;
  caso Infinitel: USD 9.945 «reponer» y USD 4.618 «reemplazar ONU» sin base):
  FACTURAS NETAS  una sola función (facturas_netas) decide qué factura es compra de verdad: se descartan las que
               Stockfish marca anuladas y las que una NC comercial anula por el mismo importe (misma moneda, hasta
               ncAnulaDias después; una NC anula una factura; las NCC y ND por diferencia de cambio no anulan). La usan
               REPOSICION, REEMPLAZO ONU e historia (última compra y días): ninguna cuenta vuelve a contar una
               factura anulada como compra.
  RITMO RECIENTE  el ciclo y la compra típica de REPOSICION se calculan solo con las compras netas del último año de
               actividad: repoVentanaDias (365 d, el mismo plazo de repoMaxDias) hacia atrás desde la última compra.
               Reponer es plata de ESTE mes y necesita ritmo reciente (repoMinFacturas dentro de esa ventana); un
               ritmo de años anteriores no cuenta (caso Infinitel: ciclo de 2023). DORMIDA (reactivar) se mide con
               todo el historial neto (caso Fournet, Souto) y también contra el ritmo reciente: atrasada más de
               repoAtrasoMax contra cualquiera de los dos = reactivación (caso Mónica). Sin ritmo reciente no se
               promete reposición: sin evidencia no hay USD.
               NC: cada NC anula UNA factura, la más vieja que cumpla (caso Interflash, auditoría Opus 12/11).
  REEMPLAZO   solo con líneas de facturas netas (no cuentan las anuladas ni las líneas de NC).
v4.5 (11/11 15:49, «terminemos el datacenter»): cuenta dormida (atraso > repoAtrasoMax) con ONU
  discontinuada pasa a REACTIVACIÓN y no a REEMPLAZAR; el dato de la ONU queda en la evidencia (decisión 82, caso Fournet).
v4.4 (11/11 15:15, hacelo de Nicolás: «todo en módulos, sin conflictos, bajar la tasa de error»):
  REGLAS ÚNICAS  todos los umbrales salen de datacenter/reglas_motor (--reglas). Sin ese documento, o con una
               clave faltante, el día no se calcula (FRENO). El código no tiene números de negocio.
  CRM VIVO     el lector arma cada cuenta con la ficha viva (oportunidades) + las cotizaciones vivas del CRM
               (--cot) + Stockfish solo como historial (facturas, compras, hallazgos). La cotización viva pisa
               número, total, vence, revisionFecha y estado de la copia de Stockfish (caso NM50/NM51 Nodo Net).
               Una cotización del CRM que Stockfish no tiene se suma a su cuenta; una ficha del CRM que Stockfish
               no tiene entra igual, marcada «sin Stockfish» (caso Fiberland). Borradores no cuentan.
  RENOVACIÓN PACTADA  si la cotización tiene revisionFecha (Nicolás: «renovar hasta X»), el límite efectivo es esa
               fecha; si el documento enviado ya venció, sigue siendo RENOVAR obligatorio con «renovación hasta dd/mm».
  AGENDADA     si Nicolás puso próxima fecha a futuro, la cuenta no sale en los empujes de hoy (salvo por vencer);
               figura en «Agendadas». RENOVAR obligatorio la sigue listando con su fecha (decisión 40).
  ÚNICO DECISOR  el Sales Engine calcula también las cinco cosas del día (entrega, cotización, responder,
               reposición, reactivación) con sus mismas reglas y las deja en la salida --json. cinco_cosas y
               el arranque de Loki solo muestran esa salida (una cuenta, un lugar; frenada = en ninguna vista).
"""
import argparse, datetime as dt, glob, hashlib, json, os, re, statistics, sys, unicodedata

VERSION = "4.7"
EXCEPCIONES_NICOLAS = ()           # v4.3: sale de restricciones.excepcionesNicolas (L0)
R07 = ("R07_ENTREGA_ABIERTA", "R07_ENTREGA_PARCIAL", "R07_DESPACHO_PENDIENTE")
RX_ONU = re.compile(r"\b(onu|ont)\b", re.I)
# v4.1: los bloqueos dictados por Nicolás viven en UNA sola lista, datacenter/restricciones (la misma de
# cinco_cosas). Se cargan con --restricciones; sin ella el día no se calcula (FRENO). Cambiar solo con «hacelo».
BLOQUEOS_DICTADOS = {}
# v4.4: los umbrales salen de datacenter/reglas_motor (cargar_reglas). Estos valores vacíos no se usan nunca:
# si falta una clave, el día frena.
REGLAS_CLAVES = ("porVencerDias", "repoMinFacturas", "repoMaxDias", "repoAtrasoMin", "repoAtrasoMax", "reemplazoDias",
                 "reemplazoMinUsd", "reactMinDias", "cadenciaDias", "pSinBancoDefecto", "yaHechaDias",
                 "marcasOnuDiscontinuadas", "rxEsperarDictado", "repoVentanaDias", "ncAnulaDias")
R = {}                         # reglas cargadas: clave -> valor
REGLAS_HUELLA = ""
RX_ESPERAR = re.compile(r"(?!)")
C1 = {}                        # ficha -> [hallazgos C1 del conciliador]; None = no se pasó --conciliador
CADENCIA_CUENTA = {}           # restricciones.cadencia
REACT_PRIMERO = []             # restricciones.reactivacionPrimero
ORDEN_TIPO = {"RENOVAR": 0, "CERRAR": 1, "ASEGURAR": 2, "REPONER": 3, "REEMPLAZAR": 4, "—": 9}
ABIERTA = ("vigente", "vencida_sin_estado")
LUGARES = ["ENTREGA", "COTIZACION", "RESPONDER", "REPOSICION", "REACTIVACION"]
JUGADA_TXT = {
    "PP": "próximo paso con fecha", "CP": "cierre de prueba", "PF": "pregunta de freno", "ES": "escalar al que decide",
    "AD": "apertura con dato", "MU": "muestra", "SG": "seguimiento", "OF": "oferta", "AG": "agradecer/cortesía",
    "EP": "esperar", "RT": "retomar", "CC": "cierre directo", "PV": "posventa", "RF": "referido", "ER": "error/aclaración",
}
JUGADA_DEFECTO = {"ENTREGA": "PP", "COTIZACION": "PP", "RESPONDER": "PP", "REPOSICION": "AD", "REACTIVACION": "AD"}
YA_HECHA = {   # jugada -> evidencia en la ficha de que ya se hizo; reemplazo (igual que cinco_cosas v1.2)
    "ES": (re.compile(r"(pas[oó]|pasad[ao]|envi[oó]|enviad[ao]|mand[oó]|derivad[ao]|elev[oó]|llev[oó])\b.{0,40}"
                      r"\b(due[nñ]o|gerente|decisor|directorio|presidente|socio|jefe|consejo)", re.I),
           "SG", "ya escalado según la ficha: seguimiento con el contacto (¿el que decide ya la vio? ¿qué falta para cerrar?)"),
    "MU": (re.compile(r"muestra.{0,30}(enviada|entregada|recibi|despach)", re.I),
           "SG", "muestra ya enviada según la ficha: seguimiento de la prueba"),
}


def cargar_reglas(doc):
    """Carga datacenter/reglas_motor. Devuelve la lista de claves que faltan (vacía = PASA)."""
    global REGLAS_HUELLA, RX_ESPERAR
    reg = ((doc or {}).get("reglas") or {})
    falta = [k for k in REGLAS_CLAVES if k not in reg or "valor" not in (reg.get(k) or {})]
    R.clear()
    if falta:
        return falta
    R.update({k: reg[k]["valor"] for k in REGLAS_CLAVES})
    RX_ESPERAR = re.compile(R["rxEsperarDictado"], re.I)
    REGLAS_HUELLA = hashlib.sha256(json.dumps(R, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]
    return []


def norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", s).strip()


def fecha(v):
    try:
        return dt.date.fromisoformat(str(v)[:10]) if v else None
    except ValueError:
        return None


def usd(x):
    return "USD " + f"{x:,.0f}".replace(",", ".")


def tot(c):
    t = c.get("total") or c.get("bruto") or 0
    if c.get("moneda") == "USD":
        return t
    tc = c.get("tc") or 0
    return t / tc if tc and tc > 1 else 0.0


def comps_anuladas(f):
    """v4.6 · comprobantes F anulados: marcados por Stockfish o anulados por una NC comercial (tipo NC) del mismo
    importe y moneda, hasta ncAnulaDias después. Una NC anula una sola factura: las NC en orden de fecha, cada una a la
    factura MÁS VIEJA sin NC que cumpla (la marcada anulada no tiene límite de días). NCC y ND no anulan."""
    comps = f.get("sf_comprobantes") or []
    ncs = sorted(((fecha(c.get("fecha")), abs(c.get("bruto") or c.get("total") or 0), c.get("moneda"))
                  for c in comps
                  if c.get("tipo") == "NC" and (c.get("bruto") or c.get("total") or 0) < 0 and fecha(c.get("fecha"))),
                 key=lambda x: (x[0], x[1]))
    fs = sorted((c for c in comps if c.get("tipo") == "F"), key=lambda c: (c.get("fecha") or "", c.get("comp") or ""))
    anul = {c.get("comp") for c in fs if c.get("anulada")}          # las marcadas por Stockfish ya están anuladas
    tomadas = set()
    for nf, nb, nm in ncs:
        for c in fs:
            fe = fecha(c.get("fecha"))
            b = abs(c.get("bruto") or c.get("total") or 0)
            if c.get("comp") in tomadas or not fe or not b or c.get("moneda") != nm or abs(nb - b) > 0.01 or nf < fe:
                continue
            if not c.get("anulada") and (nf - fe).days > R["ncAnulaDias"]:
                continue
            tomadas.add(c.get("comp")); anul.add(c.get("comp"))
            break
    return anul

def facturas_netas(f, hoy):
    """v4.6 · [(fecha, total, comp)] de las facturas que son compra de verdad hasta hoy, ordenadas."""
    anul = comps_anuladas(f)
    return sorted((fecha(c["fecha"]), tot(c), c.get("comp")) for c in f.get("sf_comprobantes") or []
                  if c.get("tipo") == "F" and c.get("comp") not in anul and fecha(c.get("fecha")) and fecha(c["fecha"]) <= hoy)


def leer_dir(carpeta):
    out = {}
    for p in sorted(glob.glob(os.path.join(carpeta, "*.json"))):
        d = json.load(open(p, encoding="utf-8"))
        out[os.path.splitext(os.path.basename(p))[0]] = d.get("data", d)
    return out


def leer(p):
    d = json.load(open(p, encoding="utf-8"))
    return d.get("data", d)


CAMPOS_VIVOS = ("proximaAccion", "proximaFecha", "etapa", "monto", "ultimoContacto", "empresa", "archivada",
                "noProspectar", "otroVendedor", "cuentaCompartida", "hz_recompra", "historial", "cuit", "clienteHorizon")
LECTOR = {}                    # control del lector (cotizaciones pisadas, agregadas, fichas sin Stockfish)


def estado_vivo(q, hoy):
    """estadoReal de una cotización con el estado del CRM vivo (la copia de Stockfish puede estar vieja)."""
    e = norm(q.get("estado"))
    if e in ("rechazada", "perdida", "perdido"):
        return "rechazada"
    if e == "borrador":
        return "borrador"
    if e == "aceptada":
        return q.get("estadoReal") if str(q.get("estadoReal") or "").startswith("aceptada") else "aceptada_sin_factura"
    if q.get("estadoReal") and q.get("estadoReal") not in ABIERTA:
        return q["estadoReal"]                      # archivada / facturada según Stockfish: no se reabre
    v = fecha(q.get("vence")) or fecha(q.get("limite"))
    return "vencida_sin_estado" if not v or v < hoy else "vigente"     # decisión 108: sin vence = vencida (RENOVAR)


def limite_efectivo(q):
    """Fecha hasta la que vale la cotización: la renovación pactada (revisionFecha) si es posterior."""
    v = fecha(q.get("vence")) or fecha(q.get("limite"))
    r = fecha(q.get("revisionFecha"))
    return max(d for d in (v, r) if d) if (v or r) else None


def fusionar(sf, vivas, cots=None, hoy=None):
    """Lector común v4.4: ficha viva + cotizaciones vivas + Stockfish como historial."""
    hoy = hoy or dt.date.today()
    cots = cots or {}
    LECTOR.clear()
    LECTOR.update({"cotizacionesPisadas": 0, "cotizacionesAgregadas": 0, "fichasSinStockfish": [], "numerosCorregidos": []})
    cuentas, cubiertas = {}, set()
    for i, d in sf.items():
        f = dict(d)
        f["_id"] = d.get("sf_cuenta") or i
        cubiertas.add(f["_id"])
        cubiertas.update(d.get("sf_fichas") or [])
        v = vivas.get(f["_id"])
        if v:
            for k in CAMPOS_VIVOS:
                if k in v:
                    f[k] = v[k]
        cuentas[f["_id"]] = f
    for vid in sorted(vivas):                      # ficha del CRM que Stockfish no tiene: entra igual
        if vid in cubiertas:
            continue
        v = vivas[vid]
        f = {k: v[k] for k in CAMPOS_VIVOS if k in v}
        f.update(_id=vid, sf_cuenta=vid, sf_comprobantes=[], sf_cotizaciones=[], sf_lineas=[], _sinStockfish=True)
        cuentas[vid] = f
        LECTOR["fichasSinStockfish"].append(vid)
    if cots:
        vistos = set()
        for cid in sorted(cuentas):
            f = cuentas[cid]
            nuevas = []
            for q in f.get("sf_cotizaciones") or []:
                c = cots.get(q.get("id"))
                if c is None:
                    nuevas.append(q)
                    continue
                vistos.add(q["id"])
                q2 = dict(q)
                for k in ("numero", "total", "vence", "revisionFecha", "estado"):
                    if c.get(k) not in (None, ""):
                        q2[k] = c[k]
                if (q.get("numero") or "") != (q2.get("numero") or ""):
                    LECTOR["numerosCorregidos"].append(f"{f.get('empresa') or cid}: {q.get('numero')} → {q2.get('numero')}")
                q2["estadoReal"] = estado_vivo(q2, hoy)
                q2["_fuente"] = "CRM vivo"
                nuevas.append(q2)
                LECTOR["cotizacionesPisadas"] += 1
            f["sf_cotizaciones"] = nuevas
        for qid in sorted(cots):                   # cotización del CRM que Stockfish no tiene
            c = cots[qid]
            dueno = c.get("oportunidadId")
            if qid in vistos or dueno not in cuentas:
                continue
            q = {"id": qid, "numero": c.get("numero"), "total": c.get("total") or 0, "vence": c.get("vence"),
                 "limite": c.get("vence"), "revisionFecha": c.get("revisionFecha"), "estado": c.get("estado"), "_fuente": "CRM vivo"}
            q["estadoReal"] = estado_vivo(q, hoy)
            if q["estadoReal"] == "borrador":
                continue
            cuentas[dueno].setdefault("sf_cotizaciones", []).append(q)
            LECTOR["cotizacionesAgregadas"] += 1
    return cuentas


# L0 (hacelo 11/11 14:31): excepciones, cuentas fuera, cuentas de Nicolás y entregas en depósito salen de
# datacenter/restricciones (lista única), no del código. Sin alguna de esas claves el día no se calcula (FRENO).
L0_CLAVES = ("excepcionesNicolas", "cuentasFuera", "enDeposito", "cuentasDeNicolas")
FUERA, NICOLAS, DEPOSITO = {}, {}, {}


def _cuits(f):
    s = {re.sub(r"\D", "", str(f.get("cuit") or ""))} | {re.sub(r"\D", "", str(c)) for c in f.get("sf_cuits") or []}
    s.discard("")
    return s


def en_lista(f, mapa):
    """Clave de la lista que corresponde a la cuenta (por id o por CUIT), o None."""
    if not mapa:
        return None
    if f.get("_id") in mapa:
        return f["_id"]
    cs = _cuits(f)
    for k, v in mapa.items():
        c = re.sub(r"\D", "", str(v.get("cuit") or "")) if isinstance(v, dict) else ""
        if c and c in cs:
            return k
    return None


def cargar_l0(restr):
    """Carga las claves L0 de restricciones; devuelve las que faltan."""
    global EXCEPCIONES_NICOLAS
    restr = restr or {}
    EXCEPCIONES_NICOLAS = tuple(norm(e) for e in restr.get("excepcionesNicolas") or ())
    for g, k in ((FUERA, "cuentasFuera"), (NICOLAS, "cuentasDeNicolas"), (DEPOSITO, "enDeposito")):
        g.clear()
        g.update(restr.get(k) or {})
    return [k for k in L0_CLAVES if k not in restr]


def es_de_nicolas(f):
    return any(e and e in norm(f.get("empresa")) for e in EXCEPCIONES_NICOLAS) or bool(en_lista(f, NICOLAS))


def excluida(f, hoy):
    if en_lista(f, FUERA):          # v4.3: cuenta fuera (restricciones.cuentasFuera), por id o CUIT
        return "cuenta fuera"
    if f.get("sf_sinFicha"):
        return "sin ficha"
    es_n = es_de_nicolas(f)
    r = f.get("sf_restricciones") or {}
    if f.get("archivada") or r.get("archivada"):
        return "archivada"
    if not es_n and (f.get("noProspectar") or r.get("noProspectar")):
        return "noProspectar"
    if not es_n and (f.get("otroVendedor") or r.get("otroVendedor")):
        return "otroVendedor"
    if f.get("cuentaCompartida") or r.get("cuentaCompartida"):
        return "cuentaCompartida"
    rec = f.get("hz_recompra") or {}
    if rec.get("estado") == "espera" and (fecha(rec.get("hasta")) or hoy) > hoy:
        return "recompra en espera"
    fam = set(((f.get("sf_compras") or {}).get("familias") or {}).keys()) - {"-"}
    if fam and fam <= {"HFC"}:
        return "solo HFC"
    return None


def bloqueo(f, banco):
    if f["_id"] in BLOQUEOS_DICTADOS:
        return BLOQUEOS_DICTADOS[f["_id"]]
    rec = (banco.get("recomendadas") or {}).get(f["_id"]) or {}
    if rec.get("jugada") == "EP" or RX_ESPERAR.search(f.get("proximaAccion") or ""):
        return "esperar dictado"
    if ((banco.get("senales") or {}).get(f["_id"]) or {}).get("pideHuawei"):
        return "pide Huawei"
    return None


def componentes(f, hoy):
    fin_mes = (hoy.replace(day=28) + dt.timedelta(days=4)).replace(day=1) - dt.timedelta(days=1)
    acc = f.get("proximaAccion") or ""
    nunca = {norm(m) for m in re.findall(r"([A-Z]{0,3}\d[\w-]*)\s+nunca enviada", acc, re.I)}
    comp = {}
    # COTIZACION (RENOVAR / CERRAR)
    if f.get("etapa") != "perdido":
        ab = [q for q in f.get("sf_cotizaciones") or [] if q.get("estadoReal") in ABIERTA
              and norm(q.get("numero")) not in nunca]
        if ab:
            def doc_v(q):
                return fecha(q.get("vence")) or fecha(q.get("limite"))

            def ev_q(q):
                v, r = doc_v(q), fecha(q.get("revisionFecha"))
                s = f"{q.get('numero') or 's/N'} {usd(q.get('total') or 0)} ("
                s += (f"{'venció' if v < hoy else 'vence'} {v:%d/%m}" if v else "sin vence")
                if r and (not v or r > v):
                    s += f"; renovación pactada hasta {r:%d/%m}"
                return s + ")" + (" [CRM vivo]" if q.get("_fuente") else "")
            venc = [q for q in ab if q.get("estadoReal") == "vencida_sin_estado" or (doc_v(q) or hoy) < hoy]   # decisión 108: sin vence = vencida
            vig = [q for q in ab if q not in venc]
            total = sum(q.get("total") or 0 for q in ab)
            if venc:
                q0 = sorted(venc, key=lambda q: -(q.get("total") or 0))[0]
                pal = f"Renovar {q0.get('numero') or 's/N'} · " + (f"venció {doc_v(q0):%d/%m}" if doc_v(q0) else "sin vence: cargarlo")
                r0 = fecha(q0.get("revisionFecha"))
                if r0 and r0 >= hoy:
                    pal += f" · renovación pactada hasta {r0:%d/%m}: enviar la renovada"
                if len(ab) > 1:
                    pal += f" · {len(ab)} abiertas"
                comp["RENOVAR"] = (total, pal, [ev_q(q) for q in ab])
            else:
                q0 = sorted(vig, key=lambda q: (limite_efectivo(q) or dt.date.max))[0]
                comp["CERRAR"] = (total, f"Cerrar {q0.get('numero') or 's/N'} · vale hasta {(limite_efectivo(q0) or hoy):%d/%m}",
                                  [ev_q(q) for q in ab])
        elif nunca and re.search(r"renovar", acc, re.I) and (f.get("monto") or 0) > 0:
            m = re.search(r"renovar (?:la )?([\w-]+)", acc, re.I)
            comp["RENOVAR"] = (f.get("monto"), f"Renovar {m.group(1) if m else ''} · dictado".strip(),
                               [f"dictado en la ficha: {acc[:120]}", f"monto de la ficha {usd(f.get('monto'))}",
                                "DATO A CORREGIR: Stockfish tiene como vigente una cotización que la ficha dice nunca enviada"])
    # ENTREGA
    hs = [h for h in f.get("sf_hallazgos") or [] if h.get("regla") in R07]
    c1 = (C1 or {}).get(f["_id"]) or []
    if c1:
        mt = sum(h.get("monto") or 0 for h in c1)
        m = re.search(r"FA (?:\d+-)?0*(\d+)", c1[0].get("que") or "")
        if mt:
            comp["ASEGURAR"] = (mt, f"Asegurar entrega {('FA ' + m.group(1)) if m else ''}".strip(),
                                [f"{(h.get('que') or '')[:150]} · {h.get('fuenteB') or ''} [conciliador]" for h in c1])
    elif hs:
        ev = sorted({e for h in hs for e in (h.get("evidencia") or [])})
        fac = [e for e in ev if re.match(r"^[A-Z]-\d", e)]
        mt = sum(tot(c) for c in f.get("sf_comprobantes") or [] if c.get("comp") in set(ev))
        if mt:
            comp["ASEGURAR"] = (mt, f"Asegurar entrega {('FA ' + fac[0].split('-')[-1].lstrip('0')) if fac else ''}".strip(),
                                [h.get("txt", "")[:140] for h in hs]
                                + (["solo Stockfish: el conciliador no lo marca (puede estar despachado)"] if C1 is not None else []))
    # REPOSICION
    # v4.6: facturas netas (sin anuladas por NC). DORMIDA (reactivar) se mide con todo el historial neto: un cliente
    # que dejó de comprar sigue dormido (decisión 82). REPONER («le toca») usa solo el último año de actividad
    # (repoVentanaDias hacia atrás desde la última compra): un ritmo de años anteriores no prueba que reponga este mes.
    fs_all = [(x[0], x[1]) for x in facturas_netas(f, hoy)]
    def _ritmo(fs_):
        fe = sorted({x[0] for x in fs_})
        return fe, [(b_ - a_).days for a_, b_ in zip(fe, fe[1:])]
    if fs_all:
        fechas, gaps = _ritmo(fs_all)
        dias = (hoy - fechas[-1]).days
        if len(fechas) >= R["repoMinFacturas"] and dias <= R["repoMaxDias"] and gaps:
            ciclo = statistics.median(gaps)
            if ciclo > 0 and dias / ciclo > R["repoAtrasoMax"]:
                comp["_REACTIVAR"] = (0, f"reposición vencida {dias / ciclo:.1f}x · reactivar".replace(".", ","),
                                      [f"{len(fechas)} compras · ciclo {ciclo:.0f} d · última {fechas[-1]:%d/%m/%Y} (hace {dias} d)"])
            else:
                fs = [x for x in fs_all if (fs_all[-1][0] - x[0]).days <= R["repoVentanaDias"]]
                fechas, gaps = _ritmo(fs)
                if len(fechas) >= R["repoMinFacturas"] and gaps:
                    ciclo = statistics.median(gaps)
                    if ciclo > 0 and dias / ciclo > R["repoAtrasoMax"]:     # atrasada contra su ritmo reciente: dormida
                        comp["_REACTIVAR"] = (0, f"reposición vencida {dias / ciclo:.1f}x (último año) · reactivar".replace(".", ","),
                                              [f"{len(fechas)} compras en el último año · ciclo {ciclo:.0f} d · última {fechas[-1]:%d/%m/%Y} (hace {dias} d)"])
                    elif ciclo > 0 and (fin_mes - fechas[-1]).days >= ciclo:
                        tip = statistics.median([x[1] for x in fs if x[1] > 0] or [0])
                        if tip > 0:
                            comp["REPONER"] = (tip, "Reponer · " + ("le toca" if dias >= ciclo else f"le toca el {fechas[-1] + dt.timedelta(days=int(ciclo)):%d/%m}"),
                                               [f"{len(fechas)} compras · ciclo {ciclo:.0f} d · última {fechas[-1]:%d/%m/%Y} (hace {dias} d)",
                                                f"compra típica {usd(tip)}"])
                            comp["_ATRASO"] = round(dias / ciclo, 2)
    # REEMPLAZO ONU
    disc, fh = set(), False
    anul = comps_anuladas(f)       # v4.6: ni las facturas anuladas ni las líneas de una NC/NCC son compra
    de_nc = {c.get("comp") for c in f.get("sf_comprobantes") or [] if c.get("tipo") in ("NC", "NCC")}
    for ln in f.get("sf_lineas") or []:
        fl = fecha(ln.get("fecha"))
        if not fl or (hoy - fl).days > R["reemplazoDias"]:
            continue
        if ln.get("comp") in de_nc or ln.get("comp") in anul:
            continue
        for it in ln.get("items") or []:
            if not RX_ONU.search(it):
                continue
            low = it.lower()
            if "[fiberhome]" in low:
                fh = True
            if any(d in low for d in R["marcasOnuDiscontinuadas"]):
                disc.add(ln.get("comp"))
    if disc and not fh and "_REACTIVAR" in comp:
        # v4.5 (decisión 82): dormida con ONU discontinuada = REACTIVACIÓN, no reemplazo (no suma plata del mes)
        comp["_REACTIVAR"][2].append(f"{len(disc)} facturas con ONU discontinuada en 12 m: al reactivar, ofrecer ONU FiberHome")
    elif disc and not fh:
        mts = [tot(c) for c in f.get("sf_comprobantes") or [] if c.get("comp") in disc and tot(c) > 0]
        if mts and statistics.median(mts) >= R["reemplazoMinUsd"]:
            comp["REEMPLAZAR"] = (statistics.median(mts), "Reemplazar ONU · pasar a FiberHome",
                                  [f"{len(disc)} facturas con ONU discontinuada en 12 m", "sin ONU FiberHome en 12 m"])
    return comp


def p_registro(registro):
    pped = {}
    for p in (registro or {}).get("predicciones") or []:   # la más nueva por cuenta
        if p.get("cuenta") and (p["cuenta"] not in pped or (p.get("fechaPrediccion") or "") >= pped[p["cuenta"]][1]):
            pped[p["cuenta"]] = (p.get("pPedido"), p.get("fechaPrediccion") or "")
    med = sorted(v[0] for v in pped.values() if v[0] is not None)
    return {k: v[0] for k, v in pped.items() if v[0] is not None}, (statistics.median(med) if med else R["pSinBancoDefecto"])


def historia(f, hoy):
    """(días desde la última factura, USD histórico, última fecha) con las facturas de Stockfish."""
    fs = [(x[0], x[1]) for x in facturas_netas(f, hoy)]      # v4.6: sin facturas anuladas por NC
    if not fs:
        return None, 0.0, None
    hist = (f.get("sf_compras") or {}).get("usdBrutoNeto") or sum(x[1] for x in fs)
    return (hoy - fs[-1][0]).days, hist, fs[-1][0]


def ya_hecha(f, j, hoy):
    """(jugada nueva, porqué, cita) si la ficha viva prueba que la jugada j ya se hizo; si no, None."""
    if j not in YA_HECHA:
        return None
    rx, nueva, txt = YA_HECHA[j]
    citas = []
    for h in f.get("historial") or []:
        t = fecha(h.get("t"))
        if t and 0 <= (hoy - t).days <= R["yaHechaDias"] and rx.search(h.get("txt") or ""):
            citas.append((t, h.get("txt")))
    if rx.search(f.get("proximaAccion") or ""):
        citas.append((hoy, "próxima acción: " + f["proximaAccion"]))
    if not citas:
        return None
    t, c = sorted(citas, key=lambda x: x[0])[-1]
    return nueva, txt, f"{t:%d/%m}: {c[:160]}"


def calcular(sf, vivas, banco, valor, hoy, registro=None, cots=None):
    cuentas = fusionar(sf, vivas, cots, hoy)
    pped, p_med = p_registro(registro)
    excl, bloq, filas, dep = {}, {}, [], {}
    for cid in sorted(cuentas):
        f = cuentas[cid]
        m = excluida(f, hoy)
        if m:
            excl[m] = excl.get(m, 0) + 1
            continue
        comp = componentes(f, hoy)
        react = comp.pop("_REACTIVAR", None)
        atraso = comp.pop("_ATRASO", None)
        dk = en_lista(f, DEPOSITO)      # v4.3: entrega en depósito por decisión de Nicolás: no se empuja ni suma
        if dk and "ASEGURAR" in comp:
            dep[cid] = {"empresa": f.get("empresa"), "usd": round(comp.pop("ASEGURAR")[0], 2), "motivo": str(DEPOSITO[dk])}
        b = bloqueo(f, banco)
        if b:                           # v4.4: frenada = en ninguna vista, tenga plata o no (caso TPP)
            bloq[cid] = {"empresa": f.get("empresa"), "motivo": b, "usd": round(max([v[0] for v in comp.values()] or [0]), 2)}
            continue
        p_cta, p_cta_or = (pped[cid], "banco (Monte Carlo)") if cid in pped else (p_med, "SUPUESTO: mediana del banco")
        pt = lambda k: 1.0 if k == "ASEGURAR" else p_cta
        if comp:   # v4.2: gana el componente de mayor ESPERADO (una entrega facturada pesa más que una reposición probable)
            tipo, (u, pal, ev) = max(comp.items(), key=lambda kv: (kv[1][0] * pt(kv[0]), kv[1][0], -ORDEN_TIPO[kv[0]]))
            if "RENOVAR" in comp and tipo != "RENOVAR":       # renovar es obligatorio: si hay vencida, va primero
                tipo, (u, pal, ev) = "RENOVAR", comp["RENOVAR"]
        else:
            tipo, u, pal, ev = "—", 0, "", []
        p, p_or = (1.0, "ya facturado") if tipo == "ASEGURAR" else (p_cta, p_cta_or)
        # por vencer: CERRAR cuya cotización más próxima vale hasta 0..N d (N = reglas_motor.porVencerDias)
        pv = False
        abiertas = [q for q in f.get("sf_cotizaciones") or [] if q.get("estadoReal") in ABIERTA]
        if tipo == "CERRAR":
            ds = [(limite_efectivo(q) - hoy).days for q in abiertas if q.get("estadoReal") == "vigente" and limite_efectivo(q)]
            pv = bool(ds) and 0 <= min(ds) <= R["porVencerDias"]
        # cadencia
        cad_hasta = ""
        uc = fecha(f.get("ultimoContacto"))
        cad = CADENCIA_CUENTA.get(cid, R["cadenciaDias"].get(tipo))
        if tipo != "—" and not pv and uc and cad and (hoy - uc).days < cad:
            cad_hasta = (uc + dt.timedelta(days=cad)).isoformat()
        dias_ult, hist, ult = historia(f, hoy)
        tambien = " | ".join(f"{v[1]} · {usd(v[0])}" for k, v in sorted(comp.items(), key=lambda kv: ORDEN_TIPO[kv[0]]) if k != tipo)
        filas.append({"id": cid, "empresa": f.get("empresa"), "etapa": f.get("etapa"), "usd": round(u, 2), "empujon": tipo,
                      "palabras": pal, "evidencia": ev, "obligatorio": tipo == "RENOVAR",
                      "p": round(p, 3) if u else 0, "pOrigen": p_or if u else "", "esperado": round(u * p, 2),
                      "porVencer": pv, "enCadenciaHasta": cad_hasta, "tambien": tambien,
                      "asegurar": round(comp["ASEGURAR"][0], 2) if "ASEGURAR" in comp else 0,
                      "reactivar": (react[1] + " · " + " | ".join(react[2])) if react else "",
                      "valorSF": ((valor.get(cid) or {}).get("valor") or 0),
                      "otros": {k: round(v[0], 2) for k, v in comp.items() if k != tipo},
                      "agendada": f.get("proximaFecha") if (fecha(f.get("proximaFecha")) or hoy) > hoy else "",
                      "atraso": atraso if tipo == "REPONER" else None,
                      "diasUltimaCompra": dias_ult, "usdHistorico": round(hist, 2), "ultimaCompra": ult.isoformat() if ult else "",
                      "sinStockfish": bool(f.get("_sinStockfish")),
                      "cotizaciones": [{"id": q.get("id"), "numero": q.get("numero"), "total": q.get("total") or 0,
                                        "vence": q.get("vence") or q.get("limite") or "", "revisionFecha": q.get("revisionFecha") or "",
                                        "estadoReal": q.get("estadoReal"), "fuente": q.get("_fuente") or "Stockfish"} for q in abiertas],
                      "proximaAccion": (f.get("proximaAccion") or "")[:200], "proximaFecha": f.get("proximaFecha") or ""})
    filas.sort(key=lambda r: (0 if r["porVencer"] else 1, -r["esperado"], -r["usd"], -r["valorSF"], r["id"]))
    for n, r in enumerate(filas, 1):
        r["puesto"] = n
        r["hoy"] = bool(r["usd"] > 0 and not r["enCadenciaHasta"] and (not r["agendada"] or r["porVencer"]))
    cinco_, cctl = cinco(filas, cuentas, banco, hoy)
    control = {"stockfish": len(cuentas), "cuentas": len(cuentas), "elegibles": len(filas), "excluidas": sum(excl.values()),
               "bloqueadas": len(bloq), "cierra": len(filas) + sum(excl.values()) + len(bloq) == len(cuentas),
               "pSinBanco": round(p_med, 3), "conciliador": C1 is not None, "enDeposito": dep,
               "lector": dict(LECTOR), "cinco": cctl}
    control["lector"]["fichasSinStockfish"] = list(LECTOR.get("fichasSinStockfish") or [])
    return filas, excl, bloq, control, cinco_


def cinco(filas, cuentas, banco, hoy):
    """Las cinco cosas del día con el mismo cálculo (v4.4). Una cuenta, un lugar; frenadas y excluidas nunca entran."""
    rec = (banco or {}).get("recomendadas") or {}
    hoy_ = [r for r in filas if r["hoy"]]           # mismo orden del Sales Engine
    usados, items, cand = set(), {}, {}

    def poner(lugar, lista, dato, monto):
        lista = [r for r in lista if r["id"] not in usados]
        cand[lugar] = len(lista)
        if not lista:
            return
        r = lista[0]
        items[lugar] = {"cuenta": r["id"], "empresa": r["empresa"], "monto": round(monto(r), 2), "dato": dato(r),
                        "puesto": r.get("puesto"), "esperado": r.get("esperado"), "p": r.get("p"), "pOrigen": r.get("pOrigen"),
                        "porVencer": r.get("porVencer"), "candidatos": len(lista),
                        "segundo": lista[1]["empresa"] if len(lista) > 1 else None}
        usados.add(r["id"])
    # 1 ENTREGA: toda entrega facturada pendiente que no está en depósito (aunque gane otro empujón)
    ent = sorted([r for r in filas if r["asegurar"] > 0 and not r["enCadenciaHasta"] and (not r["agendada"] or r["porVencer"])],
                 key=lambda r: (-r["asegurar"], r["id"]))
    poner("ENTREGA", ent, lambda r: f"entrega facturada pendiente {usd(r['asegurar'])}"
          + (f" · {r['palabras']}" if r["empujon"] == "ASEGURAR" else ""), lambda r: r["asegurar"])
    # 2 COTIZACION: renovar o cerrar, en el orden del Sales Engine
    poner("COTIZACION", [r for r in hoy_ if r["empujon"] in ("RENOVAR", "CERRAR")],
          lambda r: f"{r['palabras']} · " + " | ".join(r["evidencia"][:3]), lambda r: r["usd"])
    # 3 RESPONDER: el cliente espera respuesta nuestra (próxima acción «respond» vencida); sin cadencia
    resp = [r for r in filas if "respond" in norm(r["proximaAccion"]) and (fecha(r["proximaFecha"]) or dt.date.max) <= hoy
            and r["etapa"] != "perdido"]
    resp.sort(key=lambda r: (fecha(r["proximaFecha"]), -((cuentas.get(r["id"]) or {}).get("monto") or 0), r["id"]))
    poner("RESPONDER", resp, lambda r: f"espera respuesta desde {fecha(r['proximaFecha']):%d/%m}: {r['proximaAccion'][:140]}",
          lambda r: (cuentas.get(r["id"]) or {}).get("monto") or 0)
    # 4 REPOSICION: reponer que ya le toca (atraso entre repoAtrasoMin y repoAtrasoMax) o reemplazo de ONU
    poner("REPOSICION", [r for r in hoy_ if (r["empujon"] == "REPONER" and (r["atraso"] or 0) >= R["repoAtrasoMin"])
                         or r["empujon"] == "REEMPLAZAR"],
          lambda r: f"{r['palabras']} · " + " | ".join(r["evidencia"][:2]), lambda r: r["usd"])
    # 5 REACTIVACION: dormidas (atraso mayor a repoAtrasoMax) o sin compras hace más de reactMinDias
    rea = [r for r in filas if not r["agendada"] and r["usdHistorico"] > 0
           and (r["reactivar"] or (r["diasUltimaCompra"] or 0) > R["reactMinDias"])]
    rea.sort(key=lambda r: (REACT_PRIMERO.index(r["id"]) if r["id"] in REACT_PRIMERO else len(REACT_PRIMERO),
                            -r["usdHistorico"], r["id"]))
    poner("REACTIVACION", rea, lambda r: f"{usd(r['usdHistorico'])} comprados en total, última compra "
          f"{fecha(r['ultimaCompra']):%m/%Y} (hace {r['diasUltimaCompra']} d)"
          + (f" · {r['reactivar']}" if r["reactivar"] else ""), lambda r: r["usdHistorico"])
    for lugar, it in items.items():
        rr = rec.get(it["cuenta"]) or {}
        j, pq, org = (rr["jugada"], rr.get("porQue") or "", "banco") if rr.get("jugada") else (JUGADA_DEFECTO[lugar], "", "defecto")
        yh = ya_hecha(cuentas.get(it["cuenta"]) or {}, j, hoy)
        if yh:
            j0 = j
            j, pq, cita = yh
            org = f"ficha viva ({j0} ya hecha · {cita})"
        it.update(jugada=j, jugadaTxt=JUGADA_TXT.get(j, j), porQue=pq, jugadaOrigen=org)
    ctl = {"candidatos": cand, "sinRepetir": len({it["cuenta"] for it in items.values()}) == len(items)}
    return items, ctl


def huella(o):
    return hashlib.sha256(json.dumps(o, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]


def render(filas, excl, bloq, control, hoy, top):
    con = [r for r in filas if r["usd"] > 0]
    out = [f"# Sales Engine v{VERSION} · {hoy:%d/%m/%Y} · USD con evidencia este mes: bruto y esperado", ""]
    out.append(f"Control: {control['elegibles']} elegibles + {control['excluidas']} excluidas + {control['bloqueadas']} bloqueadas"
               f" = {control['elegibles'] + control['excluidas'] + control['bloqueadas']} de {control['cuentas']} "
               + ("(cierra)" if control["cierra"] else "(NO CIERRA)"))
    lec = control.get("lector") or {}
    out.append(f"Lector: CRM vivo · reglas {REGLAS_HUELLA} · cotizaciones pisadas por el CRM {lec.get('cotizacionesPisadas', 0)}"
               f" · agregadas {lec.get('cotizacionesAgregadas', 0)} · fichas sin Stockfish {len(lec.get('fichasSinStockfish') or [])}"
               + (f" · números corregidos: {', '.join(lec['numerosCorregidos'])}" if lec.get("numerosCorregidos") else ""))
    out.append(f"Excluidas: {excl}")
    if not control.get("conciliador"):
        out.append("AVISO: sin --conciliador. ASEGURAR sale de la foto de Stockfish (puede faltar o sobrar una entrega).")
    if bloq:
        out.append("Frenadas (no salen en ninguna vista): " + ", ".join(f"{v['empresa']} ({v['motivo']}, {usd(v['usd'])})" for v in bloq.values()))
    por = {}
    for r in con:
        p = por.setdefault(r["empujon"], [0, 0.0, 0.0]); p[0] += 1; p[1] += r["usd"]; p[2] += r["esperado"]
    out.append(f"Con plata este mes: {len(con)} cuentas · bruto {usd(sum(r['usd'] for r in con))} · esperado {usd(sum(r['esperado'] for r in con))}")
    out += [f"  {k} {n} · bruto {usd(u)} · esperado {usd(e)}" for k, (n, u, e) in sorted(por.items(), key=lambda kv: ORDEN_TIPO[kv[0]])]
    aseg = [r for r in filas if r["asegurar"] > 0]
    out.append(f"Por asegurar (todas las entregas pendientes): {len(aseg)} cuentas · {usd(sum(r['asegurar'] for r in aseg))}")
    dep = control.get("enDeposito") or {}
    if dep:
        out.append(f"En depósito por decisión de Nicolás (no se empuja ni suma): {len(dep)} cuentas · {usd(sum(v['usd'] for v in dep.values()))} · "
                   + ", ".join(f"{v['empresa']} {usd(v['usd'])}" for v in dep.values()))
    out.append(f"P sin banco (SUPUESTO, mediana del registro): {control['pSinBanco']:.0%}")
    obl = [r for r in filas if r["obligatorio"]]
    out.append(f"\n## RENOVAR obligatorio ({len(obl)})")
    out += [f"- {r['empresa']} · {r['palabras']} · {usd(r['usd'])}"
            + (f" · agendada {fecha(r['agendada']):%d/%m}" if r["agendada"] else "")
            + (f" · en cadencia hasta {fecha(r['enCadenciaHasta']):%d/%m}" if r["enCadenciaHasta"] else "") for r in obl]
    hoy_ = [r for r in con if r["hoy"]]
    out.append(f"\n## Empujes del día (top {top} de {len(hoy_)})")
    for r in hoy_[:top]:
        out.append(f"{r['puesto']:>2}. {r['empresa']} · {r['palabras']} · bruto {usd(r['usd'])} · esperado {usd(r['esperado'])} (P {r['p']:.0%}, {r['pOrigen']})"
                   + (" · POR VENCER" if r["porVencer"] else "")
                   + (f" · agendada {fecha(r['agendada']):%d/%m}" if r["agendada"] else ""))
        if r["tambien"]:
            out.append(f"     + {r['tambien']}")
        out.append(f"     ▸ " + " | ".join(r["evidencia"][:3]))
    ag = [r for r in con if r["agendada"] and not r["hoy"] and not r["enCadenciaHasta"]]
    out.append(f"\n## Agendadas por Nicolás, no salen hoy ({len(ag)})")
    out += [f"- {r['empresa']} · {r['palabras']} · {usd(r['usd'])} · vuelve el {fecha(r['agendada']):%d/%m}" for r in ag]
    cad = [r for r in con if r["enCadenciaHasta"]]
    out.append(f"\n## En cadencia, no se tocan hoy ({len(cad)})")
    out += [f"- {r['empresa']} · {r['palabras']} · {usd(r['usd'])} · vuelve el {fecha(r['enCadenciaHasta']):%d/%m}"
            + (f" · + {r['tambien']}" if r["tambien"] else "") for r in cad]
    rea = [r for r in filas if r["reactivar"]]
    out.append(f"\n## Pasaron a reactivar: atraso mayor a {str(R['repoAtrasoMax']).replace('.', ',')}x, no suman este mes ({len(rea)})")
    out += [f"- {r['empresa']} · {r['reactivar']}" for r in sorted(rea, key=lambda r: (-r['valorSF'], r['id']))]
    cero = [r for r in filas if r["usd"] == 0][:5]
    out.append(f"\nEn 0: {len(filas) - len(con)} cuentas (siembra; desempate valor Stockfish): "
               + ", ".join(f"{r['empresa']} {r['valorSF']}" for r in cero))
    out.append(f"Huella salida: {huella(filas)}")
    out.append("Regla: el script decide; Claude explica. Cambiar reglas solo con «hacelo».")
    return "\n".join(out)


def cargar_restr(restr):
    """Claves L0 + bloqueos + cadencia por cuenta + reactivacionPrimero. Devuelve las claves L0 que faltan."""
    falta = cargar_l0(restr)
    BLOQUEOS_DICTADOS.clear()
    BLOQUEOS_DICTADOS.update((restr or {}).get("bloqueosDictados") or {})
    CADENCIA_CUENTA.clear()
    CADENCIA_CUENTA.update((restr or {}).get("cadencia") or {})
    REACT_PRIMERO[:] = list((restr or {}).get("reactivacionPrimero") or [])
    return falta


def cmd_dia(a):
    hoy = dt.date.fromisoformat(a.hoy)
    sf, vivas = leer_dir(a.sf), leer_dir(a.crm) if a.crm else {}
    banco, valor = leer(a.banco), leer(a.valor).get("cuentas") or {}
    if not a.reglas or not os.path.exists(a.reglas):
        print("FRENO: falta --reglas (datacenter/reglas_motor). Sin las reglas únicas no se calcula el día.")
        return 3
    falta = cargar_reglas(leer(a.reglas))
    if falta:
        print(f"FRENO: a datacenter/reglas_motor le faltan reglas: {', '.join(falta)}.")
        return 3
    if not a.cot or not os.path.isdir(a.cot) or not a.crm:
        print("FRENO: faltan --crm o --cot (CRM vivo). Sin la ficha y las cotizaciones vivas no se decide (caso NM50/NM51).")
        return 3
    if not a.restricciones or not os.path.exists(a.restricciones):
        print("FRENO: falta --restricciones (datacenter/restricciones). Sin la lista única no se calcula el día.")
        return 3
    global C1
    falta = cargar_restr(leer(a.restricciones))
    if falta:
        print(f"FRENO: a datacenter/restricciones le faltan claves L0: {', '.join(falta)}.")
        return 3
    C1 = None
    if a.conciliador and os.path.exists(a.conciliador):
        cj = json.load(open(a.conciliador, encoding="utf-8"))
        if cj.get("veredicto") != "PASA" or cj.get("hoy") != a.hoy:
            print(f"FRENO: el conciliador no es PASA de hoy (veredicto {cj.get('veredicto')}, fecha {cj.get('hoy')}). Re-correrlo.")
            return 3
        C1 = {}
        for h in cj.get("hallazgos") or []:
            if h.get("regla") == "C1" and not h.get("restringida"):
                C1.setdefault(h["ficha"], []).append(h)
    registro = leer(a.registro) if a.registro and os.path.exists(a.registro) else {}
    cots = leer_dir(a.cot)
    filas, excl, bloq, control, items = calcular(sf, vivas, banco, valor, hoy, registro, cots)
    print(render(filas, excl, bloq, control, hoy, a.top))
    if a.json:
        sal = {"version": VERSION, "hoy": a.hoy, "lector": "crm_vivo", "reglasHuella": REGLAS_HUELLA, "control": control,
               "excluidas": excl, "bloqueadas": bloq, "filas": filas, "cinco": items}
        sal["huella"] = huella({"filas": filas, "cinco": items})
        json.dump(sal, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return 0 if control["cierra"] and control["cinco"]["sinRepetir"] else 1


REGLAS_PRUEBA = {"reglas": {k: {"valor": v} for k, v in {
    "porVencerDias": 2, "repoMinFacturas": 3, "repoMaxDias": 365, "repoAtrasoMin": 1.0, "repoAtrasoMax": 2.5,
    "reemplazoDias": 365, "reemplazoMinUsd": 300, "reactMinDias": 365,
    "cadenciaDias": {"RENOVAR": 7, "CERRAR": 7, "ASEGURAR": 2, "REPONER": 14, "REEMPLAZAR": 14},
    "pSinBancoDefecto": 0.10, "yaHechaDias": 21,
    "marcasOnuDiscontinuadas": ["i-con", "icon", "zte", "netconn", "intelbras", "china mobile", "zikun", "wolk", "compal", "arris"],
    "rxEsperarDictado": "esperar \\(nicol|no insistir", "repoVentanaDias": 365, "ncAnulaDias": 90}.items()}}   # igual que datacenter/reglas_motor v1.1


def cmd_test(_):
    global C1
    hoy = dt.date(2026, 11, 10)
    C1 = {}
    cargar_reglas(REGLAS_PRUEBA)
    REACT_PRIMERO[:] = []
    CADENCIA_CUENTA.clear()
    cargar_l0({"excepcionesNicolas": ["fullsat", "telviso"]})   # fijo de prueba, como datacenter/restricciones
    ok = True

    def t(c, m):
        nonlocal ok
        print(("PASA " if c else "FALLA") + " · " + m); ok &= bool(c)

    def F(fe, total, comp=None, items=None):
        return {"fecha": fe, "total": total, "bruto": total, "moneda": "USD", "tipo": "F", "comp": comp or f"A-1-{fe}"}

    def cta(i, **k):
        d = {"sf_cuenta": i, "empresa": i, "etapa": "cotizado", "sf_comprobantes": [], "sf_cotizaciones": [], "sf_lineas": []}
        d.update(k); return d

    def Q(num, total, vence, est="vigente"):
        return {"numero": num, "total": total, "vence": vence, "limite": vence, "estadoReal": est}
    sf = {
        "vencida": cta("vencida", sf_cotizaciones=[Q("NM1", 5000, "2026-11-01", "vencida_sin_estado")]),
        "vigente": cta("vigente", sf_cotizaciones=[Q("NM2", 8000, "2026-11-20")]),
        "grande-repo": cta("grande-repo", etapa="ganado", sf_comprobantes=[F("2026-05-01", 9000), F("2026-07-01", 9000), F("2026-09-01", 9000)],
                           sf_cotizaciones=[Q("NM3", 1000, "2026-10-01", "vencida_sin_estado")]),
        "repo": cta("repo", etapa="ganado", sf_comprobantes=[F("2026-05-01", 3000), F("2026-07-01", 3000), F("2026-09-01", 3000)]),
        "noprosp": cta("noprosp", noProspectar="si", sf_cotizaciones=[Q("NM4", 99000, "2026-11-20")]),
        "telviso": cta("Telviso", otroVendedor="x", sf_cotizaciones=[Q("NM5", 100, "2026-11-20")]),
        "perdido": cta("perdido", etapa="perdido", sf_cotizaciones=[Q("NM6", 7000, "2026-11-20")]),
        "huawei": cta("huawei", sf_cotizaciones=[Q("NM7", 7000, "2026-11-20")]),
        "dictado": cta("dictado", monto=70000, proximaAccion="0000-00018 vencida; NM48 nunca enviada. Renovar la 0000-00018",
                       sf_cotizaciones=[Q("NM48", 70000, "2026-11-18")]),
        "entrega": cta("entrega", etapa="ganado", sf_comprobantes=[F("2026-11-03", 15000, "A-00005-00001713")],
                       sf_hallazgos=[{"regla": "R07_ENTREGA_ABIERTA", "evidencia": ["A-00005-00001713"], "txt": "sin entregar"}]),
        "cero-a": cta("cero-a", etapa="prospecto"), "cero-b": cta("cero-b", etapa="prospecto"),
        "sinficha": cta("sinficha", sf_sinFicha=True),
    }
    sf["y81m4dlhqd81su9nsdfr"] = cta("y81m4dlhqd81su9nsdfr", sf_cotizaciones=[Q("0000-00026", 2394, "2026-11-03")])
    banco = {"senales": {"huawei": {"pideHuawei": True}}}
    valor = {"cero-a": {"valor": 10}, "cero-b": {"valor": 50}}
    BLOQUEOS_DICTADOS.clear()
    BLOQUEOS_DICTADOS.update({"y81m4dlhqd81su9nsdfr": "no tocar: Nicolás le debe info (UNLaR, cierre 08/11)"})  # como datacenter/restricciones
    filas, excl, bloq, control, _c = calcular(sf, {}, banco, valor, hoy)
    R = {r["id"]: r for r in filas}
    t(control["cierra"] and control["stockfish"] == len(sf), "control de cuentas cierra")
    t(R["vencida"]["empujon"] == "RENOVAR" and R["vencida"]["obligatorio"], "cotización vencida sin estado = RENOVAR obligatorio")
    _sv = {"sinvence": cta("sinvence", sf_cotizaciones=[{"id": "q", "numero": "NMx", "total": 500, "vence": "", "revisionFecha": "2026-11-20", "estadoReal": "vencida_sin_estado"}])}
    Rsv = {r["id"]: r for r in calcular(_sv, {}, banco, valor, hoy)[0]}
    t(Rsv["sinvence"]["empujon"] == "RENOVAR" and Rsv["sinvence"]["obligatorio"] and "sin vence" in Rsv["sinvence"]["palabras"],
      "decisión 108: cotización sin vence = RENOVAR obligatorio aunque tenga revisión pactada (caso Pampacom NM47)")
    t(R["vigente"]["empujon"] == "CERRAR", "cotización vigente = CERRAR")
    t(R["grande-repo"]["empujon"] == "RENOVAR" and R["grande-repo"]["usd"] == 1000, "renovar va primero aunque la reposición valga más")
    t(R["repo"]["empujon"] == "REPONER" and R["repo"]["usd"] == 3000, "reposición con ciclo cumplido = compra típica")
    t("noprosp" not in R and excl.get("noProspectar") == 1, "no prospectar nunca se empuja")
    t(R["Telviso"]["usd"] == 100, "Telviso es de Nicolás aunque tenga otroVendedor")
    t(R["perdido"]["usd"] == 0, "etapa perdido no suma cotizaciones")
    t("huawei" in bloq and "huawei" not in R, "pide Huawei = bloqueada e informada")
    t(R["dictado"]["empujon"] == "RENOVAR" and "dictado" in R["dictado"]["palabras"] and R["dictado"]["usd"] == 70000,
      "dictado manda: «nunca enviada» no suma; renovar por el monto de la ficha")
    t(R["entrega"]["empujon"] == "ASEGURAR" and R["entrega"]["usd"] == 15000, "entrega pendiente = ASEGURAR por la factura")
    t(R["cero-b"]["puesto"] < R["cero-a"]["puesto"], "empate en 0 se ordena por valor Stockfish")
    t([r["id"] for r in filas][:3] == ["dictado", "entrega", "grande-repo"] or filas[0]["esperado"] >= filas[1]["esperado"], "orden por esperado")
    t("y81m4dlhqd81su9nsdfr" in bloq and "no tocar" in bloq["y81m4dlhqd81su9nsdfr"]["motivo"], "bloqueo dictado (UNLaR) no se empuja")
    t(huella(calcular(sf, {}, banco, valor, hoy)[0]) == huella(filas), "determinismo")
    # ---- v4.2
    f3 = [F("2026-05-01", 4000), F("2026-07-01", 4000), F("2026-09-01", 4000)]             # ciclo 61 d, hace 70 d = 1,1x
    dorm = [F("2025-11-20", 4000), F("2025-12-20", 4000), F("2026-01-20", 4000)]            # ciclo 30 d, hace 294 d = 9,8x
    sf2 = {
        "tapada": cta("tapada", etapa="ganado", sf_cotizaciones=[Q("NM12", 1000, "2026-10-25", "vencida_sin_estado")]),
        "gana-entrega": cta("gana-entrega", etapa="ganado", sf_comprobantes=f3),
        "nueva": cta("nueva", etapa="ganado"),
        "dormida": cta("dormida", etapa="ganado", sf_comprobantes=dorm),
        "dormida-bloq": cta("dormida-bloq", etapa="ganado", sf_comprobantes=dorm),
        "chico": cta("chico", etapa="ganado", sf_comprobantes=[F("2026-09-01", 88, "A-1")],
                     sf_lineas=[{"fecha": "2026-09-01", "comp": "A-1", "items": ["10 ONU ZTE F660"]}]),
        "medida": cta("medida", sf_cotizaciones=[Q("NM8", 100000, "2026-11-01", "vencida_sin_estado")]),
        "sinmedir": cta("sinmedir", sf_cotizaciones=[Q("NM9", 30000, "2026-11-01", "vencida_sin_estado")]),
        "vencehoy": cta("vencehoy", sf_cotizaciones=[Q("NM10", 500, "2026-11-10")], ultimoContacto="2026-11-09"),
        "ayer": cta("ayer", sf_cotizaciones=[Q("NM11", 9000, "2026-11-01", "vencida_sin_estado")], ultimoContacto="2026-11-09"),
        "sfsolo": cta("sfsolo", etapa="ganado", sf_comprobantes=[F("2026-11-03", 700, "A-00005-00001000")],
                      sf_hallazgos=[{"regla": "R07_ENTREGA_ABIERTA", "evidencia": ["A-00005-00001000"], "txt": "sin entregar"}]),
    }
    C1 = {"tapada": [{"regla": "C1", "monto": 3000, "que": "FA 00005-00009999: sin despachar 10 de 10", "fuenteB": "remitos"}],
          "gana-entrega": [{"regla": "C1", "monto": 3500, "que": "FA 00005-00001705 (parcial): sin despachar", "fuenteB": "remitos"}],
          "nueva": [{"regla": "C1", "monto": 2378, "que": "FA 00005-00001715: sin despachar", "fuenteB": "remitos"}]}
    BLOQUEOS_DICTADOS["dormida-bloq"] = "no contactar (prueba)"
    reg = {"predicciones": [{"cuenta": "medida", "pPedido": 0.1, "fechaPrediccion": "2026-11-10"},
                            {"cuenta": "otra", "pPedido": 0.2, "fechaPrediccion": "2026-11-10"},
                            {"cuenta": "otra2", "pPedido": 0.5, "fechaPrediccion": "2026-11-10"}]}
    f2, e2, b2, c2, _c2 = calcular(sf2, {}, {}, {}, hoy, reg)
    R2 = {r["id"]: r for r in f2}
    t(c2["cierra"], "v4.2: control de cuentas cierra")
    t(R2["tapada"]["empujon"] == "RENOVAR" and "FA 9999" in R2["tapada"]["tambien"] and R2["tapada"]["asegurar"] == 3000,
      "v4.2: entrega pendiente nunca queda tapada (caso Infinitel)")
    t(R2["nueva"]["empujon"] == "ASEGURAR" and R2["nueva"]["usd"] == 2378 and R2["nueva"]["p"] == 1.0,
      "v4.2: C1 del conciliador sin foto en Stockfish = ASEGURAR (caso Fibernext)")
    t(R2["gana-entrega"]["empujon"] == "ASEGURAR" and R2["gana-entrega"]["usd"] == 3500 and "Reponer" in R2["gana-entrega"]["tambien"]
      and "FA 1705" in R2["gana-entrega"]["palabras"], "v4.2: entrega facturada le gana a una reposición más grande (esperado) y la reposición va al lado")
    t(sum(r["asegurar"] for r in f2) == 3000 + 3500 + 2378 + 700, "v4.2: el total por asegurar suma todas las entregas")
    t("solo Stockfish" in " ".join(R2["sfsolo"]["evidencia"]), "v4.2: R07 sin C1 se mantiene, marcado solo Stockfish")
    t(R2["dormida"]["usd"] == 0 and "reactivar" in R2["dormida"]["reactivar"], "v4.2: atraso mayor a 2,5x no es reposición: pasa a reactivar")
    t("dormida-bloq" in b2 and "dormida-bloq" not in R2, "v4.2: cuenta bloqueada no sale ni como reactivar (caso TPP)")
    t(R2["chico"]["usd"] == 0, "v4.2: reemplazo de menos de USD 300 no se empuja")
    t(R2["medida"]["esperado"] == 10000 and "banco" in R2["medida"]["pOrigen"], "v4.2: esperado = bruto x P del banco")
    t(R2["sinmedir"]["esperado"] == 6000 and "SUPUESTO" in R2["sinmedir"]["pOrigen"], "v4.2: sin medir usa la mediana del registro, marcada SUPUESTO")
    t(R2["vencehoy"]["puesto"] == 1 and R2["vencehoy"]["porVencer"] and not R2["vencehoy"]["enCadenciaHasta"],
      "v4.2: lo que vence en 0..2 d va primero y no entra en cadencia (caso Nodo Net)")
    t(R2["medida"]["puesto"] < R2["sinmedir"]["puesto"], "v4.2: orden por esperado")
    t(R2["ayer"]["enCadenciaHasta"] == "2026-11-16" and R2["ayer"]["obligatorio"], "v4.2: contactada ayer queda en cadencia y RENOVAR sigue obligatorio")
    CADENCIA_CUENTA["ayer"] = 1
    t(not {r["id"]: r for r in calcular(sf2, {}, {}, {}, hoy, reg)[0]}["ayer"]["enCadenciaHasta"], "v4.2: la cadencia por cuenta de restricciones manda")
    CADENCIA_CUENTA.clear()
    C1 = None
    t("solo Stockfish" not in " ".join({r["id"]: r for r in calcular(sf2, {}, {}, {}, hoy, reg)[0]}["sfsolo"]["evidencia"]),
      "v4.2: sin conciliador funciona con la foto de Stockfish")
    t(huella(calcular(sf2, {}, {}, {}, hoy, reg)[0]) == huella(calcular(sf2, {}, {}, {}, hoy, reg)[0]), "v4.2: determinismo")
    # v4.3 · L0: casos fijos (Comworks, Fiberland, Meditel en depósito)
    C1 = {"meditel": [{"regla": "C1", "monto": 32347, "que": "FA 00005-00001704: sin despachar", "fuenteB": "remitos"}]}
    sf3 = {"comworks": cta("comworks", empresa="Comworks SA", cuit="30-71554899-9", sf_cuits=["30715548999"], sf_cotizaciones=[Q("NMx", 9000, "2026-11-20")]),
           "fiberland": cta("fiberland", empresa="Fiberland S.R.L.", cuit="30716386194", otroVendedor="Taddei", sf_cotizaciones=[Q("NMy", 500, "2026-11-20")]),
           "meditel": cta("meditel", empresa="Meditel", etapa="ganado", sf_cotizaciones=[Q("NMz", 800, "2026-11-20")])}
    falta = cargar_l0({"excepcionesNicolas": ["fullsat", "telviso"],
                       "cuentasFuera": {"sf-c30715548999": {"cuit": "30715548999", "empresa": "Comworks SA"}},
                       "cuentasDeNicolas": {"sf-c30716386194": {"cuit": "30716386194", "empresa": "Fiberland S.R.L."}},
                       "enDeposito": {"meditel": "FA 1704 en depósito a pedido del cliente"}})
    f3, e3, b3, c3, _c3 = calcular(sf3, {}, {}, {}, hoy, reg)
    R3 = {r["id"]: r for r in f3}
    t(not falta and c3["cierra"], "v4.3: L0 completo y el control cierra")
    t("comworks" not in R3 and e3.get("cuenta fuera") == 1, "v4.3: cuenta fuera (por CUIT) nunca se empuja (caso Comworks)")
    t(R3["fiberland"]["usd"] == 500, "v4.3: cuenta de Nicolás no se excluye por otroVendedor (caso Fiberland)")
    t(R3["meditel"]["empujon"] == "CERRAR" and R3["meditel"]["asegurar"] == 0 and c3["enDeposito"]["meditel"]["usd"] == 32347,
      "v4.3: entrega en depósito no se empuja ni suma; queda informada (caso Meditel)")
    t(cargar_l0({"bloqueosDictados": {}}) == list(L0_CLAVES), "v4.3: sin claves L0 el día frena")
    # ---- v4.4 · reglas únicas, CRM vivo, agenda y cinco cosas en el mismo cálculo (casos del 11/11)
    C1 = {}
    cargar_l0({"excepcionesNicolas": ["fullsat", "telviso"], "cuentasFuera": {}, "cuentasDeNicolas": {}, "enDeposito": {}})
    BLOQUEOS_DICTADOS.clear()
    BLOQUEOS_DICTADOS.update({"tpp": "no contactar hasta revisar el remito (prueba)"})
    REACT_PRIMERO[:] = ["algitech"]
    H = dt.date(2026, 11, 11)
    cada20 = [F(d, 9945) for d in ("2026-08-01", "2026-08-21", "2026-09-10", "2026-09-30", "2026-10-20")]   # ciclo 20 d, hace 22 d
    sf4 = {
        "nodo": cta("nodo", sf_cotizaciones=[{"id": "q-nodo", "numero": "NM50", "total": 20097.19, "vence": "2026-11-11",
                                              "limite": "2026-11-11", "estadoReal": "vigente"}], ultimoContacto="2026-11-04"),
        "wisp": cta("wisp", sf_cotizaciones=[{"id": "q-wisp", "numero": "NM41", "total": 17371, "vence": "2026-11-20",
                                              "limite": "2026-11-20", "estadoReal": "vigente"}]),
        "telv": cta("telv", sf_cotizaciones=[{"id": "q-telv", "numero": "NM29", "total": 6979, "vence": "2026-10-17",
                                              "limite": "2026-10-17", "estadoReal": "vencida_sin_estado"}],
                    proximaFecha="2026-11-16", ultimoContacto="2026-11-01"),
        "cablenet": cta("cablenet", sf_cotizaciones=[{"id": "q-cn", "numero": "NMc", "total": 2897, "vence": "2026-11-06",
                                                      "limite": "2026-11-06", "estadoReal": "vencida_sin_estado"}], ultimoContacto="2026-11-05"),
        "infinitel": cta("infinitel", etapa="ganado", sf_comprobantes=cada20),
        "buenaonda": cta("buenaonda", etapa="ganado", sf_comprobantes=[F("2025-10-01", 3000), F("2025-12-05", 3000), F("2026-02-08", 3000), F("2026-04-06", 3000)]),
        "algitech": cta("algitech", etapa="calificado", sf_comprobantes=[F("2023-01-01", 200000), F("2024-03-01", 75000)]),
        "grande-dormida": cta("grande-dormida", sf_comprobantes=[F("2022-01-01", 900000)]),
        "tpp": cta("tpp", proximaAccion="responder a Lepore", proximaFecha="2026-11-11", sf_comprobantes=[F("2026-10-01", 500)]),
        "resp": cta("resp", etapa="contactado", proximaAccion="Responder consulta de precios", proximaFecha="2026-11-09"),
    }
    vivas4 = {"nodo": {"proximaFecha": "2026-11-13", "proximaAccion": "Renovar NM51 hasta el viernes 13/11", "ultimoContacto": "2026-11-04"},
              "fiberland": {"empresa": "Fiberland S.R.L.", "etapa": "prospecto", "proximaFecha": "2026-11-11"}}
    cots4 = {"q-nodo": {"numero": "NM51", "total": 20097.19, "vence": "2026-11-11", "revisionFecha": "2026-11-13", "estado": "enviada",
                        "oportunidadId": "nodo"},
             "q-wisp": {"numero": "NM41", "total": 17371, "vence": "2026-11-20", "estado": "rechazada", "oportunidadId": "wisp"},
             "q-telv": {"numero": "NM29", "total": 6979, "vence": "2026-10-17", "revisionFecha": "2026-11-16", "estado": "enviada", "oportunidadId": "telv"},
             "q-fl": {"numero": "NM60", "total": 1500, "vence": "2026-11-30", "estado": "enviada", "oportunidadId": "fiberland"},
             "q-borr": {"numero": "", "total": 999, "vence": "2026-11-30", "estado": "borrador", "oportunidadId": "fiberland"}}
    f4, e4, b4, c4, k4 = calcular(sf4, vivas4, {}, {}, H, reg, cots4)
    R4 = {r["id"]: r for r in f4}
    t(c4["cierra"] and c4["cuentas"] == len(sf4) + 1, "v4.4: control cierra con la ficha del CRM que Stockfish no tiene")
    t(R4["nodo"]["cotizaciones"][0]["numero"] == "NM51" and "NM51" in R4["nodo"]["palabras"],
      "v4.4: la cotización viva pisa el número de Stockfish (caso Nodo Net NM50 → NM51)")
    t(R4["nodo"]["empujon"] == "CERRAR" and "13/11" in R4["nodo"]["palabras"] and R4["nodo"]["porVencer"] and R4["nodo"]["hoy"],
      "v4.4: renovación pactada (revisionFecha) es el límite efectivo; por vencer sale aunque esté agendada")
    t(R4["wisp"]["usd"] == 0, "v4.4: cotización rechazada en el CRM no suma aunque Stockfish la tenga vigente (caso Wisp NM41)")
    t(R4["telv"]["empujon"] == "RENOVAR" and R4["telv"]["obligatorio"] and not R4["telv"]["hoy"] and "16/11" in R4["telv"]["palabras"],
      "v4.4: agendada a futuro no sale hoy, pero RENOVAR sigue obligatorio con la renovación pactada (caso Telviso)")
    t("fiberland" in R4 and R4["fiberland"]["sinStockfish"] and R4["fiberland"]["usd"] == 1500,
      "v4.4: ficha sin Stockfish entra con su cotización viva y el borrador no suma (caso Fiberland)")
    t("tpp" in b4 and "tpp" not in R4, "v4.4: frenada sin plata tampoco sale (caso TPP)")
    ids5 = {it["cuenta"] for it in k4.values()}
    t(k4["COTIZACION"]["cuenta"] == "nodo", "v4.4: cinco · COTIZACION = la primera del Sales Engine")
    t("cablenet" not in ids5 and R4["cablenet"]["enCadenciaHasta"], "v4.4: cinco · cuenta en cadencia no ocupa lugar (caso Cablenet)")
    t(k4["REPOSICION"]["cuenta"] == "infinitel" and k4["REPOSICION"]["monto"] == R4["infinitel"]["usd"],
      "v4.4: cinco · la compra típica es el mismo número del Sales Engine (caso Infinitel 9.945)")
    t(R4["buenaonda"]["reactivar"] and k4.get("REPOSICION", {}).get("cuenta") != "buenaonda",
      "v4.4: cinco · atraso mayor a 2,5x no es reposición (caso Buena Onda)")
    t(k4["REACTIVACION"]["cuenta"] == "algitech", "v4.4: cinco · reactivacionPrimero manda sobre el USD histórico (Algitech)")
    t(k4["RESPONDER"]["cuenta"] == "resp" and "tpp" not in ids5, "v4.4: cinco · RESPONDER no muestra frenadas (caso TPP)")
    t(c4["cinco"]["sinRepetir"], "v4.4: cinco · una cuenta, un lugar")
    t(not any(it["cuenta"] in b4 for it in k4.values()), "v4.4: ninguna frenada en las cinco cosas")
    t(huella(calcular(sf4, vivas4, {}, {}, H, reg, cots4)[4]) == huella(k4), "v4.4: determinismo de las cinco cosas")
    # ---- v4.5 · dormida con ONU discontinuada (decisión 82, caso Fournet)
    onu = lambda fe, c: {"fecha": fe, "comp": c, "items": ["50 × ONU ZTE F660 [ZTE]"]}
    dorm5 = [F("2025-11-10", 900, "A-9-1"), F("2025-11-24", 900, "A-9-2"), F("2025-12-10", 900, "A-9-3")]  # ciclo 15 d, hace 335 d
    viva5 = [F("2026-09-10", 900, "A-8-1"), F("2026-09-25", 900, "A-8-2"), F("2026-10-10", 900, "A-8-3")]  # ciclo 15 d, hace 31 d = 2,1x
    sf5 = {"fournet": cta("fournet", etapa="ganado", sf_comprobantes=dorm5, sf_lineas=[onu("2025-12-10", "A-9-3")]),
           "activa": cta("activa", etapa="ganado", sf_comprobantes=viva5, sf_lineas=[onu("2026-10-10", "A-8-3")])}
    f5, e5, b5, c5, k5 = calcular(sf5, {}, {}, {}, H, reg)
    R5 = {r["id"]: r for r in f5}
    t(R5["fournet"]["empujon"] != "REEMPLAZAR" and R5["fournet"]["usd"] == 0 and R5["fournet"]["reactivar"],
      "v4.5: dormida (>2,5x) con ONU discontinuada = reactivación, no reemplazo ni plata del mes (caso Fournet)")
    t(any("ONU discontinuada" in e for e in R5["fournet"]["evidencia"]) or "ONU" in R5["fournet"]["reactivar"],
      "v4.5: el dato de la ONU discontinuada queda en la evidencia de la reactivación")
    t("REEMPLAZAR" in (R5["activa"]["empujon"], R5["activa"]["tambien"]) or "Reemplazar" in R5["activa"]["tambien"],
      "v4.5: cuenta activa (<=2,5x) con ONU discontinuada sigue con reemplazo")
    # ---- v4.6 · facturas netas y ritmo reciente (caso Infinitel 12/11: ciclo de un año viejo + facturas anuladas por NC)
    NC = lambda fe, total, comp: {"fecha": fe, "total": -total, "bruto": -total, "moneda": "USD", "tipo": "NC", "comp": comp}
    NCC = lambda fe, total, comp: {"fecha": fe, "total": -total * 1500, "bruto": -total * 1500, "moneda": "ARS", "tipo": "NCC", "comp": comp, "tc": 1}
    lin6 = lambda fe, comp, tipo: {"fecha": fe, "comp": comp, "tipo": tipo, "items": ["1194 × Onu Gpon IC435ETR [I-con]"]}
    ritmo_viejo = [F(d, 9000, "A-V-" + d) for d in ("2025-01-10", "2025-01-20", "2025-02-01", "2025-02-10", "2025-02-20")]
    anuladas6 = [F("2026-07-01", 4000, "A-N-1"), NC("2026-07-02", 4000, "A-N-1c"), F("2026-08-01", 4000, "A-N-2"),
                 NC("2026-08-01", 4000, "A-N-2c"), F("2026-09-01", 4000, "A-N-3")]
    parcial6 = [F("2026-05-01", 3000, "A-P-1"), F("2026-07-01", 3000, "A-P-2"), F("2026-09-01", 3000, "A-P-3"), NC("2026-07-05", 500, "A-P-2c")]
    ncc6 = [F("2026-05-01", 3000, "A-C-1"), F("2026-07-01", 3000, "A-C-2"), F("2026-09-01", 3000, "A-C-3"), NCC("2026-07-02", 3000, "A-C-2c")]
    sf6 = {"viejo": cta("viejo", etapa="ganado", sf_comprobantes=ritmo_viejo + [F("2026-10-21", 9370, "A-V-9")]),
           "anuladas": cta("anuladas", etapa="ganado", sf_comprobantes=anuladas6),
           "parcial": cta("parcial", etapa="ganado", sf_comprobantes=parcial6),
           "ncc": cta("ncc", etapa="ganado", sf_comprobantes=ncc6),
           "onuanul": cta("onuanul", etapa="ganado", sf_comprobantes=[F("2026-02-05", 4617, "A-O-1"), NC("2026-02-05", 4617, "A-O-1c")],
                          sf_lineas=[lin6("2026-02-05", "A-O-1", "F"), lin6("2026-02-05", "A-O-1c", "NC")]),
           "onuflag": cta("onuflag", etapa="ganado", sf_comprobantes=[dict(F("2026-02-05", 4617, "A-O-3"), anulada=True)],
                          sf_lineas=[lin6("2026-02-05", "A-O-3", "F")]),
           "onuvalida": cta("onuvalida", etapa="ganado", sf_comprobantes=[F("2026-06-05", 4617, "A-O-2")],
                            sf_lineas=[lin6("2026-06-05", "A-O-2", "F")])}
    f6, e6, b6, c6, k6 = calcular(sf6, {}, {}, {}, H, reg)
    R6 = {r["id"]: r for r in f6}
    t(R6["viejo"]["usd"] == 0 and R6["viejo"]["empujon"] != "REPONER",
      "v4.6: ciclo de hace más de un año + una sola compra reciente = sin reposición (caso Infinitel)")
    t(R6["anuladas"]["usd"] == 0 and R6["anuladas"]["empujon"] != "REPONER",
      "v4.6: facturas anuladas por NC del mismo importe no cuentan como compras")
    t(R6["parcial"]["empujon"] == "REPONER" and R6["parcial"]["usd"] == 3000,
      "v4.6: una NC parcial no anula la factura: la reposición sigue")
    t(R6["ncc"]["empujon"] == "REPONER" and R6["ncc"]["usd"] == 3000,
      "v4.6: una NCC en pesos (diferencia de cambio) no anula nada")
    t(R6["onuanul"]["empujon"] != "REEMPLAZAR" and R6["onuanul"]["usd"] == 0,
      "v4.6: ONU de una factura anulada por NC no es reemplazo (caso Infinitel USD 4.618)")
    t(R6["onuflag"]["empujon"] != "REEMPLAZAR" and R6["onuflag"]["usd"] == 0,
      "v4.6: ONU de una factura marcada anulada por Stockfish no es reemplazo")
    t(R6["onuvalida"]["empujon"] == "REEMPLAZAR" and R6["onuvalida"]["usd"] == 4617,
      "v4.6: ONU de una factura vigente sigue con reemplazo")
    t(comps_anuladas(sf6["anuladas"]) == {"A-N-1", "A-N-2"}, "v4.6: comps_anuladas devuelve solo las anuladas")
    dos = cta("dos", sf_comprobantes=[F("2026-06-01", 4000, "A-D-1"), F("2026-06-01", 4000, "A-D-2"), NC("2026-06-02", 4000, "A-D-1c")])
    t(len(comps_anuladas(dos)) == 1, "v4.6: una NC anula una sola factura")
    gemelas = cta("gemelas", sf_comprobantes=[dict(F("2026-10-15", 10950, "A-G-1"), anulada=True), F("2026-10-20", 10950, "A-G-2"),
                                              NC("2026-10-20", 10950, "A-G-1c")])
    t(comps_anuladas(gemelas) == {"A-G-1"} and [x[2] for x in facturas_netas(gemelas, H)] == ["A-G-2"],
      "v4.6: factura marcada anulada + gemela + una sola NC = la NC anula una sola, la gemela cuenta una vez (caso Fullsat 1695/1702, Frappa 1619/1620)")
    antes = cta("antes", sf_comprobantes=[NC("2026-05-01", 4000, "A-Y-1c"), F("2026-06-01", 4000, "A-Y-1")])
    t(comps_anuladas(antes) == set(), "v4.6: una NC anterior a la factura no la anula")
    lejos = cta("lejos", sf_comprobantes=[F("2026-01-01", 4000, "A-X-1"), NC("2026-06-01", 4000, "A-X-1c")])
    t(comps_anuladas(lejos) == set(), "v4.6: una NC de más de ncAnulaDias después no anula")
    # auditoría Opus 12/11: A (sin acción) · B (NC a la factura equivocada) · C (línea de factura con renglón negativo)
    base_m = dt.date(2024, 9, 1)
    monica = [F((base_m + dt.timedelta(days=30 * i)).isoformat(), 1900, f"A-M-{i}") for i in range(11)] \
        + [F(d, 1900, "A-M-" + d) for d in ("2026-08-27", "2026-09-03", "2026-09-09", "2026-09-18")]
    mon = calcular({"monica": cta("monica", etapa="ganado", sf_comprobantes=monica)}, {}, {}, {}, H, reg)[0][0]
    t(mon["empujon"] != "REPONER" and "reactivar" in mon["reactivar"],
      "v4.6: ritmo histórico 30 d pero ráfaga reciente de 7 d y atrasada 7,9x = reactivar, no queda sin acción (caso Mónica)")
    inter = cta("inter", sf_comprobantes=[F("2026-05-05", 1428, "A-I-1595"), NC("2026-07-28", 1428, "A-I-396"),
                                          dict(F("2026-07-28", 1428, "A-I-1648"), anulada=True), NC("2026-08-28", 1428, "A-I-400")])
    t(comps_anuladas(inter) == {"A-I-1595", "A-I-1648"} and facturas_netas(inter, H) == [],
      "v4.6: cada NC anula la factura más vieja que cumple; la marcada anulada no le roba la NC a la anterior (caso Interflash)")
    negat = cta("negat", etapa="ganado", sf_comprobantes=[F("2026-06-05", 4617, "A-Z-1")],
                sf_lineas=[lin6("2026-06-05", "A-Z-1", "NC")])
    rz = calcular({"negat": negat}, {}, {}, {}, H, reg)[0][0]
    t("Reemplazar" in (rz["empujon"] + " " + rz["tambien"]) or rz["empujon"] == "REEMPLAZAR",
      "v4.6: una línea de FACTURA con renglón negativo (tipo NC en la línea) no se descarta; solo las líneas de comprobantes NC/NCC")
    t(historia(sf6["onuanul"], H)[0] is None, "v4.6: la historia no toma como última compra una factura anulada")
    t(huella(calcular(sf6, {}, {}, {}, H, reg)[0]) == huella(f6), "v4.6: determinismo")
    t(any(k in cargar_reglas({"reglas": {k2: v for k2, v in REGLAS_PRUEBA["reglas"].items() if k2 != "repoVentanaDias"}}) for k in ("repoVentanaDias",)),
      "v4.6: sin repoVentanaDias el día frena")
    cargar_reglas(REGLAS_PRUEBA)
    t(cargar_reglas({"reglas": {"porVencerDias": {"valor": 2}}}) != [], "v4.4: reglas incompletas = FRENO")
    t(cargar_reglas({}) == list(REGLAS_CLAVES), "v4.4: sin reglas_motor = FRENO")
    cargar_reglas(REGLAS_PRUEBA)
    BLOQUEOS_DICTADOS.clear()
    REACT_PRIMERO[:] = []
    cargar_l0({"excepcionesNicolas": ["fullsat", "telviso"]})
    C1 = None
    print("RESULTADO:", "PASA" if ok else "FALLA"); return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    d = sub.add_parser("dia")
    for k in ("--sf", "--crm", "--banco", "--valor", "--hoy", "--json", "--restricciones", "--registro", "--conciliador",
              "--reglas", "--cot"):
        d.add_argument(k)
    d.add_argument("--top", type=int, default=15)
    sub.add_parser("test")
    a = ap.parse_args()
    return cmd_dia(a) if a.cmd == "dia" else cmd_test(a) if a.cmd == "test" else ap.print_help()


if __name__ == "__main__":
    sys.exit(main())

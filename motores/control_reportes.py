#!/usr/bin/env python3
"""
control_reportes.py · Horizon CRM · control de calidad y auditoria de reportes (v1.1, 08/11/2026)

Lee cualquier Excel/CSV que suba Nicolas (Finnegans u otros), lo valida SIEMPRE con las mismas
reglas fijas y devuelve PASA o FALLA. No escribe nada en el CRM: solo deja archivos de salida.
El script decide; Claude lee el informe y lo explica. Se carga al datacenter solo con PASA + "hacelo".

Uso:
  python3 control_reportes.py ARCHIVO [ARCHIVO ...]
        [--crm clientes_resumen.json]   # datacenter/clientes_resumen exportado del CRM
        [--anterior resultado.json]     # resultado.json del control anterior del mismo reporte
        [--salida carpeta]              # por defecto ./control
        [--hoy AAAA-MM-DD]              # por defecto la fecha del sistema

Salida por archivo/hoja en <salida>/<nombre>/:
  informe.md      lectura corta para Nicolas
  resultado.json  veredicto, corte, conteos, totales por moneda y por mes (sirve de --anterior)
  limpio.json     filas que pasaron, normalizadas, listas para el datacenter
  cuarentena.csv  filas apartadas con el motivo
Codigo de salida: 0 todo PASA · 1 alguna FALLA · 2 no se pudo leer
"""
import argparse, csv, datetime as dt, hashlib, io, json, os, re, sys, unicodedata
from collections import Counter, defaultdict

import pandas as pd

VERSION = "1.1"

# ---------------- reglas fijas (cambiarlas solo con "hacelo" de Nicolas) ----------------
UMBRAL = {
    "fecha_invalida": 0.02,   # mas del 2 % de filas con fecha ilegible -> FALLA
    "fecha_futura": 0.02,     # mas del 2 % con fecha posterior a hoy -> FALLA
    "cuit_invalido": 0.05,    # mas del 5 % con CUIT que no cumple el digito verificador -> FALLA
    "sin_cuit": 0.20,         # mas del 20 % sin CUIT (no se pueden unir) -> FALLA
    "numero_invalido": 0.01,  # mas del 1 % de importes ilegibles -> FALLA
    "saldo_descuadre": 0.01,  # saldo acumulado que no cierra con Debe-Haber en mas del 1 % -> FALLA
    "tolerancia": 0.01,       # diferencia de redondeo aceptada en importes
    "cambio_mes": 0.01,       # variacion de importe de un mes ya cargado que se avisa
}
# Clientes de Nicolas aunque otro reporte diga lo contrario (08/11/2026)
EXCEPCIONES_NICOLAS = ["fullsat", "telviso"]

SINONIMOS = {  # nombre de columna normalizado -> campo canonico (el orden importa)
    "fecha": ["fecha", "fechacomprobante", "fechaemision", "fechadeemision", "fec", "fechapedido",
              "fechafactura", "fechamovimiento", "fechaentrega"],
    "cuit": ["cuit", "cuitcliente", "cuitdni", "nrodoc", "nrodocumento",
             "identificacionfiscal", "nroidentificacion", "cuitcuil"],
    "cliente": ["cliente", "razonsocial", "nombrecliente", "descripcioncliente", "organizacion",
                "denominacion", "nombre", "clienteproveedor"],
    "comprobante": ["comprobante", "nrocomprobante", "numerocomprobante", "nrodecomprobante",
                    "nrocomp", "transaccion", "nropedido", "pedido", "factura", "numero", "nro"],
    "tipocomp": ["tipocomprobante", "documento", "tipo", "tipodecomprobante", "tipotransaccion"],
    "moneda": ["moneda", "mon", "divisa", "monedacomprobante"],
    "importe": ["importe", "total", "monto", "totalcomprobante", "importetotal"],
    "bruto": ["bruto", "importebruto", "neto", "importeneto", "subtotal", "totalbruto", "netogravado"],
    "otros": ["otros", "impuestos", "iva", "totalimpuestos"],
    "tc": ["cotizacion", "tipodecambio", "tc", "cambio"],
    "usd": ["usd", "importeusd", "totalusd", "montousd", "dolares", "importeendolares", "brutousd"],
    "debe": ["debe", "debito", "debitos"],
    "haber": ["haber", "credito", "creditos"],
    "saldo": ["saldo", "saldoacumulado", "saldofinal", "saldoactual"],
    "vendedor": ["vendedor", "vendedora", "ejecutivo", "comercial", "vendedorasignado"],
    "producto": ["producto", "articulo", "descripcionproducto", "descripcionarticulo", "item",
                 "codigoproducto"],
    "detalle": ["descripcion", "detalle", "observaciones", "concepto"],
    "marca": ["marca"],
    "familia": ["familia"],
    "subfamilia": ["subfamilia"],
    "cantidad": ["cantidad", "cant", "unidades", "cantidadpedida"],
    "pendiente": ["pendiente", "ptedest", "pendientedestino", "pendientededestino",
                  "pendienteentrega", "pendientedeentrega"],
    "limite": ["limitecredito", "creditomaximo", "limitedecredito"],
}
MONTOS = ["importe", "bruto", "otros", "tc", "usd", "debe", "haber", "saldo", "limite"]
MONEDAS = {"usd": "USD", "us": "USD", "u$s": "USD", "us$": "USD", "dolar": "USD", "dolares": "USD",
           "dol": "USD", "dolarestadounidense": "USD",
           "ars": "ARS", "$": "ARS", "pes": "ARS", "peso": "ARS", "pesos": "ARS",
           "pesosargentinos": "ARS", "$ar": "ARS"}


# ---------------- utilidades ----------------
def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9$]", "", s)


def vacio(v):
    return v is None or (isinstance(v, float) and v != v) or str(v).strip() in ("", "nan", "NaT", "None")


def cuit_valido(d):
    if len(d) != 11:
        return False
    w = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    r = 11 - sum(int(a) * b for a, b in zip(d[:10], w)) % 11
    r = 0 if r == 11 else r
    return r != 10 and r == int(d[10])


def leer_numero(v):
    """Devuelve (float|None, ok). Acepta formato argentino 1.234,56 y (123) negativo."""
    if vacio(v):
        return None, True
    if isinstance(v, (int, float)):
        return float(v), True
    s = str(v).strip()
    neg = s.startswith("(") and s.endswith(")") or s.endswith("-")
    s = re.sub(r"(?i)u\$s|us\$|usd|ars|\$|\s|\(|\)", "", s).rstrip("-")
    if s.startswith("-"):
        neg, s = True, s[1:]
    if s in ("", "-"):
        return None, True
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
        s = s.replace(".", "")
    try:
        x = float(s)
    except ValueError:
        return None, False
    return (-x if neg else x), True


def leer_fecha(v):
    """Devuelve (date|None, ok)."""
    if vacio(v):
        return None, True
    if isinstance(v, (pd.Timestamp, dt.datetime)):
        return v.date(), True
    if isinstance(v, dt.date):
        return v, True
    if isinstance(v, (int, float)) and 20000 < v < 80000:  # serial de Excel
        return (dt.date(1899, 12, 30) + dt.timedelta(days=int(v))), True
    s = str(v).strip().split(" ")[0].split("T")[0]
    for f in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d"):
        try:
            return dt.datetime.strptime(s, f).date(), True
        except ValueError:
            pass
    return None, False


def leer_moneda(v):
    if vacio(v):
        return None
    n = norm(v)
    if n in MONEDAS:
        return MONEDAS[n]
    if "dol" in n or "usd" in n or "u$s" in n:
        return "USD"
    if "peso" in n or n.startswith("ar"):
        return "ARS"
    return "OTRA:" + str(v).strip()


# ---------------- lectura ----------------
def leer_tablas(ruta):
    """Lista de (nombre_hoja, DataFrame sin cabecera). Lanza ValueError si no se puede leer."""
    ext = os.path.splitext(ruta)[1].lower()
    crudo = open(ruta, "rb").read()
    if ext in (".xlsx", ".xlsm"):
        hojas = pd.read_excel(ruta, sheet_name=None, header=None, dtype=object, engine="openpyxl")
        return [(h, df) for h, df in hojas.items() if not df.dropna(how="all").empty]
    if ext == ".xls":
        if crudo[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
            raise ValueError("Excel 97 (.xls binario): abrilo y guardalo como .xlsx o .csv y volvé a subirlo")
        texto = decodificar(crudo)
        if "<table" in texto.lower():  # Finnegans y otros exportan HTML con extension .xls
            tablas = pd.read_html(io.StringIO(texto), header=None)
            return [(f"tabla{i+1}", t.astype(object)) for i, t in enumerate(tablas)]
        return [("csv", leer_csv_texto(texto))]
    if ext in (".csv", ".txt", ".tsv"):
        return [("csv", leer_csv_texto(decodificar(crudo)))]
    raise ValueError(f"formato {ext} no soportado (usar .xlsx, .xls, .csv o .txt)")


def decodificar(b):
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode("latin-1", errors="replace")


def leer_csv_texto(t):
    muestra = "\n".join(t.splitlines()[:30])
    sep = max([";", ",", "\t", "|"], key=lambda c: muestra.count(c))
    filas = list(csv.reader(io.StringIO(t), delimiter=sep))
    ancho = max((len(f) for f in filas), default=0)
    return pd.DataFrame([f + [None] * (ancho - len(f)) for f in filas], dtype=object)


def mapear_columnas(cabecera):
    usados, mapa = set(), {}
    nombres = [norm(c) for c in cabecera]
    for canon, sins in SINONIMOS.items():
        for s in sins:
            for i, n in enumerate(nombres):
                if i not in usados and n == s:
                    mapa[canon] = i
                    usados.add(i)
                    break
            if canon in mapa:
                break
    return mapa


def detectar_cabecera(df):
    mejor, fila = 0, None
    for i in range(min(25, len(df))):
        celdas = [c for c in df.iloc[i].tolist() if not vacio(c)]
        m = len(mapear_columnas(celdas)) if celdas else 0
        if m > mejor:
            mejor, fila = m, i
    return fila if mejor >= 2 else None


def tipo_reporte(m):
    if "debe" in m and "haber" in m:
        return "cuenta_corriente"
    if "limite" in m:
        return "credito"
    if "saldo" in m:
        return "saldos"
    if "producto" in m and ("cantidad" in m or "familia" in m or "marca" in m):
        return "ventas_lineas"
    if "comprobante" in m and ("importe" in m or "usd" in m or "bruto" in m):
        return "comprobantes"
    if "cuit" in m and "cliente" in m:
        return "clientes"
    return "desconocido"


# ---------------- control ----------------
def controlar(ruta, hoja, df, crm, anterior, hoy, hash_archivo):
    hallazgos = []  # (nivel, codigo, texto)
    def H(nivel, cod, txt):
        hallazgos.append((nivel, cod, txt))

    fila_cab = detectar_cabecera(df)
    if fila_cab is None:
        H("ERROR", "sin_cabecera", "No encontré una fila de títulos reconocible (fecha, CUIT, cliente, importe...).")
        return armar_resultado(ruta, hoja, "desconocido", {}, [], [], hallazgos, None, hash_archivo, {})
    cab = [str(c).strip() if not vacio(c) else f"col{j+1}" for j, c in enumerate(df.iloc[fila_cab].tolist())]
    m = mapear_columnas(cab)
    tipo = tipo_reporte(m)
    if fila_cab > 0:
        H("INFO", "titulos", f"Los títulos están en la fila {fila_cab+1}; lo de arriba se ignoró.")
    if tipo == "desconocido":
        H("AVISO", "tipo", "No reconozco el tipo de reporte; se controló solo lo que se pudo mapear.")
    no_mapeadas = [c for j, c in enumerate(cab) if j not in m.values()]

    cuerpo = df.iloc[fila_cab + 1:].reset_index(drop=True)
    filas, cuarentena = [], []
    vistos = set()
    cont = Counter()
    nombres_por_cuit, cuits_por_nombre = defaultdict(set), defaultdict(set)

    for i, r in cuerpo.iterrows():
        nro = fila_cab + 2 + i  # numero de fila como lo ve Nicolas en Excel
        valores = r.tolist()
        if all(vacio(v) for v in valores):
            cont["vacias"] += 1
            continue
        get = lambda k: valores[m[k]] if k in m and m[k] < len(valores) else None
        motivos = []
        # filas de total/subtotal
        textos = [norm(v) for v in valores if isinstance(v, str)]
        if any(t.startswith(("total", "subtotal", "saldoanterior", "transporte")) for t in textos) and vacio(get("cuit")):
            cuarentena.append((nro, "fila de total o subtotal", valores))
            cont["totales"] += 1
            continue
        clave = tuple("" if vacio(v) else str(v).strip() for v in valores)
        if clave in vistos:
            cuarentena.append((nro, "duplicado exacto de otra fila", valores))
            cont["duplicados"] += 1
            continue
        vistos.add(clave)

        reg = {"_fila": nro}
        if "fecha" in m:
            f, ok = leer_fecha(get("fecha"))
            if not ok or f is None:
                motivos.append("fecha ilegible o vacía")
                cont["fecha_invalida"] += 1
            elif f > hoy:
                motivos.append(f"fecha futura {f:%d/%m/%Y}")
                cont["fecha_futura"] += 1
            reg["fecha"] = f.isoformat() if f else None
        if "cuit" in m:
            d = re.sub(r"\D", "", "" if vacio(get("cuit")) else str(get("cuit")).split(".")[0])
            if not d:
                motivos.append("sin CUIT")
                cont["sin_cuit"] += 1
            elif len(d) == 11 and not cuit_valido(d):
                motivos.append(f"CUIT {d} no cumple el dígito verificador")
                cont["cuit_invalido"] += 1
            elif len(d) not in (7, 8, 11):
                motivos.append(f"CUIT/DNI {d} con largo inválido")
                cont["cuit_invalido"] += 1
            elif len(d) in (7, 8):
                cont["dni"] += 1
            reg["cuit"] = d or None
        for k in ("cliente", "comprobante", "tipocomp", "vendedor", "producto", "marca", "familia", "subfamilia", "detalle"):
            if k in m and not vacio(get(k)):
                reg[k] = str(get(k)).strip()
        if "moneda" in m:
            reg["moneda"] = leer_moneda(get("moneda"))
            if reg["moneda"] and reg["moneda"].startswith("OTRA:"):
                cont["moneda_rara"] += 1
        elif "usd" in m:
            reg["moneda"] = "USD"
        for k in MONTOS + ["cantidad", "pendiente"]:
            if k in m:
                x, ok = leer_numero(get(k))
                if not ok:
                    motivos.append(f"{k} ilegible: {get(k)!r}")
                    cont["numero_invalido"] += 1
                reg[k] = x
        if reg.get("cantidad") is not None and reg["cantidad"] < 0:
            cont["cantidad_negativa"] += 1
        if reg.get("importe") is not None and reg["importe"] < 0 or reg.get("usd") is not None and reg["usd"] < 0:
            cont["importe_negativo"] += 1
        extra = {cab[j]: (None if vacio(v) else str(v).strip()) for j, v in enumerate(valores)
                 if j not in m.values() and j < len(cab) and not vacio(v)}
        if extra:
            reg["extra"] = extra
        if motivos:
            cuarentena.append((nro, "; ".join(motivos), valores))
            continue
        if reg.get("cuit") and reg.get("cliente"):
            nombres_por_cuit[reg["cuit"]].add(reg["cliente"])
            cuits_por_nombre[norm(reg["cliente"])].add(reg["cuit"])
        filas.append(reg)

    n_datos = len(filas) + sum(1 for c in cuarentena if not c[1].startswith(("fila de total", "duplicado")))
    base = max(n_datos, 1)

    def umbral(cod, txt):
        if cont[cod]:
            nivel = "ERROR" if cont[cod] / base > UMBRAL[cod] else "AVISO"
            H(nivel, cod, f"{cont[cod]} filas con {txt} ({cont[cod]/base:.1%}; tope {UMBRAL[cod]:.0%}). Van a cuarentena.")
    umbral("fecha_invalida", "fecha ilegible")
    umbral("fecha_futura", "fecha posterior a hoy")
    umbral("cuit_invalido", "CUIT inválido")
    umbral("sin_cuit", "CUIT vacío (no se pueden unir con el CRM)")
    umbral("numero_invalido", "importes ilegibles")
    if not filas:
        H("ERROR", "sin_filas", "No quedó ninguna fila válida.")
    if cont["duplicados"]:
        H("AVISO", "duplicados", f"{cont['duplicados']} filas idénticas a otra: quedan en cuarentena para no contar doble. Si son líneas legítimas repetidas, avisame.")
    if cont["totales"]:
        H("INFO", "totales", f"{cont['totales']} filas de total/subtotal apartadas (no son datos).")
    if cont["dni"]:
        H("INFO", "dni", f"{cont['dni']} filas con DNI en lugar de CUIT (consumidor final o monotributo).")
    if cont["moneda_rara"]:
        H("AVISO", "moneda", f"{cont['moneda_rara']} filas con moneda no reconocida.")
    if any(k in m for k in ("importe", "debe", "haber", "saldo")) and "moneda" not in m and "usd" not in m:
        H("AVISO", "moneda", "El reporte trae importes pero no dice la moneda: no se suman ni se comparan entre clientes.")
    if cont["importe_negativo"]:
        H("INFO", "negativos", f"{cont['importe_negativo']} filas con importe negativo (notas de crédito o anulaciones).")
    if cont["cantidad_negativa"]:
        H("AVISO", "cantidad_negativa", f"{cont['cantidad_negativa']} filas con cantidad negativa (devoluciones).")
    if "fecha" not in m:
        H("AVISO", "sin_fecha", "El reporte no tiene fecha: no se puede saber hasta cuándo llega.")
    if "cuit" not in m and ("cliente" not in m or crm is None):
        H("AVISO", "sin_columna_cuit", "El reporte no tiene CUIT: no se puede unir con el CRM.")

    multi = {c: n for c, n in nombres_por_cuit.items() if len(n) > 1}
    if multi:
        ej = "; ".join(f"{c}: {' / '.join(sorted(n))}" for c, n in list(multi.items())[:5])
        H("INFO", "cuit_varios_nombres", f"{len(multi)} CUIT con más de un nombre (normal en Finnegans, se une por CUIT). Ej.: {ej}")
    multi_n = {n: c for n, c in cuits_por_nombre.items() if len(c) > 1}
    if multi_n:
        ej = "; ".join(f"{n}: {', '.join(sorted(c))}" for n, c in list(multi_n.items())[:5])
        H("AVISO", "nombre_varios_cuit", f"{len(multi_n)} nombres con más de un CUIT (grupo o error de carga): revisar antes de unificar fichas. Ej.: {ej}")

    # integridad de comprobantes (libro de ventas: facturas, NC, ND)
    if "bruto" in m and "otros" in m and "importe" in m:
        mal = [r for r in filas if None not in (r.get("bruto"), r.get("otros"), r.get("importe"))
               and abs(r["bruto"] + r["otros"] - r["importe"]) > max(UMBRAL["tolerancia"], abs(r["importe"]) * 1e-6)]
        if mal:
            nivel = "ERROR" if len(mal) / max(len(filas), 1) > UMBRAL["numero_invalido"] else "AVISO"
            H(nivel, "bruto_otros_total", f"{len(mal)} comprobantes donde Bruto + Otros ≠ Total. Ej.: filas {', '.join(str(r['_fila']) for r in mal[:5])}")
        else:
            H("INFO", "bruto_otros_ok", f"Bruto + Otros = Total en las {len(filas)} filas.")
    if "tipocomp" in m:
        campo_signo = "importe" if "importe" in m else ("bruto" if "bruto" in m else None)
        signo_mal = []
        for r in filas:
            t, v = norm(r.get("tipocomp", "")), r.get(campo_signo) if campo_signo else None
            if v is None or v == 0:
                continue
            if "credito" in t and v > 0 or ("factura" in t or "debito" in t) and "credito" not in t and v < 0:
                signo_mal.append(r)
        if signo_mal:
            H("AVISO", "signo", f"{len(signo_mal)} comprobantes con el signo cambiado (NC positiva o factura/ND negativa). Ej.: filas {', '.join(str(r['_fila']) for r in signo_mal[:5])}")
        tipos = Counter(r.get("tipocomp", "(vacío)") for r in filas)
        H("INFO", "tipos", "Comprobantes: " + ", ".join(f"{t} ({n})" for t, n in tipos.most_common(10)) + ".")
        campo_v = "bruto" if "bruto" in m else ("importe" if "importe" in m else None)
        if campo_v:
            grupo = defaultdict(float)
            for r in filas:
                t = norm(r.get("tipocomp", ""))
                g = ("dif. de cambio" if "cambio" in t else "notas de crédito" if "credito" in t
                     else "notas de débito" if "debito" in t else "facturas")
                grupo[(g, r.get("moneda") or "SIN_MONEDA")] += r.get(campo_v) or 0
            H("INFO", "totales_por_tipo", f"Totales {campo_v} por tipo (las diferencias de cambio no son venta): "
              + " · ".join(f"{g} {mon} {ar(v)}" for (g, mon), v in sorted(grupo.items())))
        if "comprobante" in m:
            claves = Counter((r.get("tipocomp"), r.get("comprobante")) for r in filas if r.get("comprobante"))
            rep = [k for k, n in claves.items() if n > 1]
            if rep:
                H("AVISO", "comprobante_repetido", f"{len(rep)} comprobantes (tipo + número) aparecen más de una vez con datos distintos. Ej.: {'; '.join(f'{a} {b}' for a, b in rep[:4])}")
    if "tc" in m and "moneda" in m:
        raro = [r for r in filas if r.get("tc") is not None and (r.get("moneda") == "ARS" and abs(r["tc"] - 1) > 1e-6
                or r.get("moneda") == "USD" and r["tc"] <= 1)]
        if raro:
            H("AVISO", "tc", f"{len(raro)} filas con tipo de cambio que no corresponde a la moneda (pesos ≠ 1 o dólares ≤ 1). Ej.: filas {', '.join(str(r['_fila']) for r in raro[:5])}")

    # saldo acumulado = saldo anterior + Debe - Haber (por cliente y moneda, en el orden del reporte)
    if tipo == "cuenta_corriente" and "saldo" in m:
        grupos, chequeadas, mal, ejemplos = {}, 0, 0, []
        for reg in filas:
            g = (reg.get("cuit") or reg.get("cliente"), reg.get("moneda"))
            esperado = None
            if g in grupos and grupos[g] is not None:
                esperado = grupos[g] + (reg.get("debe") or 0) - (reg.get("haber") or 0)
            if esperado is not None and reg.get("saldo") is not None:
                chequeadas += 1
                if abs(esperado - reg["saldo"]) > UMBRAL["tolerancia"]:
                    mal += 1
                    if len(ejemplos) < 5:
                        ejemplos.append(f"fila {reg['_fila']}: esperado {ar(esperado)}, dice {ar(reg['saldo'])}")
            grupos[g] = reg.get("saldo")
        if chequeadas:
            tasa = mal / chequeadas
            if tasa > 0.5:
                H("AVISO", "saldo_no_acumulado", "La columna Saldo no es acumulada fila a fila: no se valida contra Debe−Haber. Usar Debe−Haber, nunca sumar saldos.")
            elif tasa > UMBRAL["saldo_descuadre"]:
                H("ERROR", "saldo_descuadre", f"{mal} de {chequeadas} saldos no cierran con Debe−Haber ({tasa:.1%}). Ej.: {'; '.join(ejemplos)}")
            elif mal:
                H("AVISO", "saldo_descuadre", f"{mal} saldos no cierran con Debe−Haber (dentro de tolerancia general). Ej.: {'; '.join(ejemplos)}")
            else:
                H("INFO", "saldo_ok", f"Saldo acumulado verificado en {chequeadas} filas: cierra con Debe−Haber.")

    resumen = resumir(filas, m)

    # comparacion con la carga anterior
    if anterior:
        if anterior.get("hash") == hash_archivo:
            H("AVISO", "ya_controlado", "Es exactamente el mismo archivo que el control anterior: no hay nada nuevo.")
        if anterior.get("tipo") and anterior["tipo"] != tipo:
            H("AVISO", "tipo_distinto", f"El control anterior era '{anterior['tipo']}' y este es '{tipo}': la comparación puede no servir.")
        c_ant, c_nue = anterior.get("corte"), resumen.get("corte")
        if c_ant and c_nue and c_nue < c_ant:
            H("ERROR", "corte_viejo", f"Este reporte llega al {fmt(c_nue)} y lo ya cargado llega al {fmt(c_ant)}: es más viejo, no pisa lo cargado.")
        mes_corte_ant = (c_ant or "")[:7]
        for mes, v in (anterior.get("porMes") or {}).items():
            if mes >= mes_corte_ant:
                continue
            nv = resumen["porMes"].get(mes)
            if not nv:
                H("AVISO", "mes_faltante", f"El mes {mes} estaba en la carga anterior ({v['filas']} filas) y no está en esta (¿filtro de fechas distinto?).")
                continue
            if nv["filas"] < v["filas"]:
                H("AVISO", "mes_menos_filas", f"{mes}: antes {v['filas']} filas, ahora {nv['filas']} (faltan filas de un período ya cargado).")
            for mon, tot in (v.get("totales") or {}).items():
                t2 = nv.get("totales", {}).get(mon, 0.0)
                if tot and abs(t2 - tot) / abs(tot) > UMBRAL["cambio_mes"]:
                    H("AVISO", "mes_cambio_importe", f"{mes} {mon}: antes {ar(tot)}, ahora {ar(t2)} (NC o refacturación en un mes cerrado).")
        ant_cuits = set(anterior.get("cuits") or [])
        if ant_cuits and resumen["cuits"]:
            nuevos = set(resumen["cuits"]) - ant_cuits
            if nuevos:
                H("INFO", "cuits_nuevos", f"{len(nuevos)} CUIT que no estaban en la carga anterior.")

    # cruce con el CRM (solo por CUIT) y reglas comerciales
    flags = {}
    if crm is not None:
        por_cuit = {re.sub(r"\D", "", str(c.get("cuit", ""))): c for c in crm if c.get("cuit")}
        fuera, sin_crm, excep = defaultdict(int), Counter(), set()
        if "cuit" not in m and "cliente" in m:
            # sin columna CUIT: se busca el CUIT por nombre EXACTO (normalizado, sin forma societaria).
            # Nombre que no coincide exacto o que coincide con dos CUIT -> queda sin CUIT. Nunca aproximado.
            por_nombre = defaultdict(set)
            for c in crm:
                for n in (c.get("cliente"), c.get("ficha")):
                    if n and c.get("cuit"):
                        por_nombre[nombre_base(n)].add(re.sub(r"\D", "", str(c["cuit"])))
            sin_match, ambiguos = Counter(), set()
            for reg in filas:
                cands = por_nombre.get(nombre_base(reg.get("cliente", "")), set())
                if len(cands) == 1:
                    reg["cuit"] = next(iter(cands))
                    reg["cuitPorNombre"] = True
                elif len(cands) > 1:
                    ambiguos.add(reg.get("cliente"))
                else:
                    sin_match[reg.get("cliente", "(vacío)")] += 1
            con = sum(1 for r in filas if r.get("cuitPorNombre"))
            H("AVISO" if sin_match else "INFO", "cuit_por_nombre",
              f"El reporte no trae CUIT: se asignó por nombre exacto en {con} de {len(filas)} filas "
              f"({len({r['cliente'] for r in filas if r.get('cuitPorNombre')})} clientes). "
              + (f"Sin coincidencia exacta: {len(sin_match)} clientes, ej.: {', '.join(n for n, _ in sin_match.most_common(6))}. " if sin_match else "")
              + (f"Nombre con más de un CUIT (no se asigna): {', '.join(sorted(ambiguos)[:5])}." if ambiguos else ""))
            resumen["clientesSinCUIT"] = [n for n, _ in sin_match.most_common()]
        for reg in filas:
            c = reg.get("cuit")
            if not c:
                continue
            ficha = por_cuit.get(c)
            if not ficha:
                sin_crm[c] += 1
                continue
            nombre = norm(ficha.get("cliente", "") + " " + ficha.get("ficha", "") + " " + reg.get("cliente", ""))
            if any(e in nombre for e in EXCEPCIONES_NICOLAS):
                excep.add(ficha.get("cliente") or c)
                continue
            for regla in ("noProspectar", "otroVendedor"):
                if ficha.get(regla):
                    reg.setdefault("reglas", []).append(regla)
                    fuera[(regla, ficha.get("cliente") or c)] += 1
        for (regla, cli), n in sorted(fuera.items()):
            flags.setdefault(regla, []).append(cli)
        if flags.get("otroVendedor"):
            H("AVISO", "otro_vendedor", f"{len(flags['otroVendedor'])} clientes de otro vendedor (se cargan como dato, no se trabajan): {', '.join(flags['otroVendedor'][:8])}")
        if flags.get("noProspectar"):
            H("AVISO", "no_prospectar", f"{len(flags['noProspectar'])} clientes marcados no prospectar (dato sí, gestión no): {', '.join(flags['noProspectar'][:8])}")
        if excep:
            H("INFO", "excepciones", f"Clientes de Nicolás aunque otra fuente diga lo contrario: {', '.join(sorted(excep))}.")
        if sin_crm:
            H("INFO", "sin_ficha", f"{len(sin_crm)} CUIT del reporte no están en datacenter/clientes_resumen (clientes nuevos o sin facturación cargada).")
            resumen["cuitsSinCRM"] = sorted(sin_crm)
    else:
        H("AVISO", "sin_crm", "No se cruzó con el CRM (falta --crm): no se chequearon otro vendedor ni no prospectar.")
    if "vendedor" in m:
        vend = Counter(r.get("vendedor", "(vacío)") for r in filas)
        H("INFO", "vendedores", "Vendedores en el reporte: " + ", ".join(f"{v} ({n})" for v, n in vend.most_common(8))
          + ". Las ventas de Nicolás cuentan aunque figuren como 'Ventas Horizon'.")

    return armar_resultado(ruta, hoja, tipo, m, filas, cuarentena, hallazgos, resumen, hash_archivo,
                           {"cabecera": cab, "noMapeadas": no_mapeadas, "filaTitulos": fila_cab + 1})


def resumir(filas, m):
    fechas = [r["fecha"] for r in filas if r.get("fecha")]
    por_mes = defaultdict(lambda: {"filas": 0, "totales": defaultdict(float)})
    tot = defaultdict(float)
    campo = ("usd" if "usd" in m else "bruto" if "bruto" in m else "importe" if "importe" in m
             else "debe" if "debe" in m else None)
    for r in filas:
        mes = (r.get("fecha") or "sin-fecha")[:7]
        por_mes[mes]["filas"] += 1
        if campo:
            mon = r.get("moneda") or "SIN_MONEDA"
            v = (r.get("debe") or 0) - (r.get("haber") or 0) if campo == "debe" else (r.get(campo) or 0)
            por_mes[mes]["totales"][mon] += v
            tot[mon] += v
    return {
        "desde": min(fechas) if fechas else None,
        "corte": max(fechas) if fechas else None,
        "campoTotal": "Debe-Haber" if campo == "debe" else campo,
        "totales": {k: round(v, 2) for k, v in tot.items()},
        "porMes": {k: {"filas": v["filas"], "totales": {a: round(b, 2) for a, b in v["totales"].items()}}
                   for k, v in sorted(por_mes.items())},
        "cuits": sorted({r["cuit"] for r in filas if r.get("cuit")}),
    }


FORMAS = r"\b(s ?a ?s|s ?r ?l|s ?a ?u|s ?a|s ?c ?a|s ?h|s ?a ?c ?i|ltda|coop(erativa)?|ltd|inc|y otros)\b"


def nombre_base(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[.,&()\-/']", " ", s)
    s = re.sub(FORMAS, " ", s)
    return re.sub(r"[^a-z0-9]", "", s)


def ar(x):
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt(iso):
    return dt.date.fromisoformat(iso).strftime("%d/%m/%Y") if iso else "—"


def armar_resultado(ruta, hoja, tipo, m, filas, cuarentena, hallazgos, resumen, hash_archivo, extra):
    errores = [h for h in hallazgos if h[0] == "ERROR"]
    return {
        "veredicto": "FALLA" if errores else "PASA",
        "archivo": os.path.basename(ruta), "hoja": hoja, "hash": hash_archivo, "tipo": tipo,
        "controlador": f"control_reportes.py v{VERSION}",
        "generado": dt.datetime.now().isoformat(timespec="seconds"),
        "columnas": {k: extra.get("cabecera", [])[v] for k, v in m.items()} if m else {},
        "noMapeadas": extra.get("noMapeadas", []), "filaTitulos": extra.get("filaTitulos"),
        "filasValidas": len(filas), "filasCuarentena": len(cuarentena),
        "desde": (resumen or {}).get("desde"), "corte": (resumen or {}).get("corte"),
        "campoTotal": (resumen or {}).get("campoTotal"),
        "totales": (resumen or {}).get("totales", {}), "porMes": (resumen or {}).get("porMes", {}),
        "cuits": (resumen or {}).get("cuits", []), "cuitsSinCRM": (resumen or {}).get("cuitsSinCRM", []),
        "clientesSinCUIT": (resumen or {}).get("clientesSinCUIT", []),
        "hallazgos": [{"nivel": n, "codigo": c, "texto": t} for n, c, t in hallazgos],
        "_filas": filas, "_cuarentena": cuarentena,
    }


def linea(res):
    errs = [h["texto"] for h in res["hallazgos"] if h["nivel"] == "ERROR"]
    base = (f"{res['veredicto']} · {res['archivo']}" + (f" [{res['hoja']}]" if res["hoja"] not in ("csv",) else "")
            + f" · {res['tipo']} · {res['filasValidas']} filas · corte {fmt(res['corte'])}"
            + f" · {res['filasCuarentena']} en cuarentena")
    return base + (f" · motivo: {errs[0]}" if errs else "")


def escribir_salida(res, carpeta):
    os.makedirs(carpeta, exist_ok=True)
    filas, cuar = res.pop("_filas"), res.pop("_cuarentena")
    with open(os.path.join(carpeta, "resultado.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    with open(os.path.join(carpeta, "limpio.json"), "w", encoding="utf-8") as f:
        json.dump({"meta": {k: res[k] for k in ("archivo", "hoja", "hash", "tipo", "desde", "corte", "veredicto", "controlador", "generado")},
                   "filas": filas}, f, ensure_ascii=False)
    with open(os.path.join(carpeta, "cuarentena.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["fila_excel", "motivo", "contenido"])
        for nro, mot, vals in cuar:
            w.writerow([nro, mot, " | ".join("" if vacio(v) else str(v) for v in vals)])
    orden = {"ERROR": 0, "AVISO": 1, "INFO": 2}
    md = [f"# Control · {res['archivo']}" + (f" · {res['hoja']}" if res["hoja"] != "csv" else ""), "",
          f"**{linea(res)}**", "",
          f"- Tipo detectado: {res['tipo']} · títulos en fila {res['filaTitulos']}",
          f"- Período: {fmt(res['desde'])} → {fmt(res['corte'])}"]
    if res["totales"]:
        md.append(f"- Totales ({res['campoTotal']}, por moneda, sin mezclar): "
                  + " · ".join(f"{k} {ar(v)}" for k, v in res["totales"].items()))
    md.append(f"- Columnas usadas: " + ", ".join(f"{k}←{v}" for k, v in res["columnas"].items()))
    if res["noMapeadas"]:
        md.append(f"- Columnas sin mapear (quedan en 'extra'): {', '.join(res['noMapeadas'][:15])}")
    md += ["", "## Hallazgos"]
    for h in sorted(res["hallazgos"], key=lambda h: orden[h["nivel"]]):
        md.append(f"- **{h['nivel']}** · {h['texto']}")
    md += ["", "Regla: se carga al datacenter solo si PASA y Nicolás dice «hacelo». Nunca se pisa lo cargado: se agrega con su corte."]
    with open(os.path.join(carpeta, "informe.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")


def cargar_crm(ruta):
    d = json.load(open(ruta, encoding="utf-8"))
    d = d.get("data", d)
    return d.get("clientes", d if isinstance(d, list) else [])


def main():
    ap = argparse.ArgumentParser(description="Control de calidad y auditoría de reportes para el datacenter de Horizon")
    ap.add_argument("archivos", nargs="+")
    ap.add_argument("--crm")
    ap.add_argument("--anterior")
    ap.add_argument("--salida", default="control")
    ap.add_argument("--hoy")
    a = ap.parse_args()
    hoy = dt.date.fromisoformat(a.hoy) if a.hoy else dt.date.today()
    crm = cargar_crm(a.crm) if a.crm else None
    anterior = json.load(open(a.anterior, encoding="utf-8")) if a.anterior else None
    codigo = 0
    for ruta in a.archivos:
        try:
            h = hashlib.sha256(open(ruta, "rb").read()).hexdigest()[:16]
            tablas = leer_tablas(ruta)
        except Exception as e:  # noqa: BLE001
            print(f"FALLA · {os.path.basename(ruta)} · no se pudo leer: {e}")
            codigo = max(codigo, 2)
            continue
        if not tablas:
            print(f"FALLA · {os.path.basename(ruta)} · el archivo está vacío")
            codigo = max(codigo, 1)
            continue
        for hoja, df in tablas:
            res = controlar(ruta, hoja, df, crm, anterior, hoy, h)
            nombre = re.sub(r"[^\w.-]+", "_", os.path.splitext(os.path.basename(ruta))[0] + ("" if len(tablas) == 1 else f"__{hoja}"))
            carpeta = os.path.join(a.salida, nombre)
            print(linea(res) + f"  → {carpeta}/informe.md")
            escribir_salida(res, carpeta)
            if res["veredicto"] == "FALLA":
                codigo = max(codigo, 1)
    sys.exit(codigo)


if __name__ == "__main__":
    main()

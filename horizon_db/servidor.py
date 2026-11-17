#!/usr/bin/env python3
"""Horizon DB · conector MCP v1.0 (Etapa 1: solo lectura).

Servidor MCP por stdio, solo biblioteca estándar (no hace falta instalar paquetes).
Claude Code y la app de escritorio de Claude lo arrancan solos; no se corre a mano.

    python -I servidor.py [--db C:\\HorizonDB\\horizon.db]

Abre la base en modo solo lectura: ninguna herramienta puede escribir.
"""
import argparse, json, os, sys, traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import consultas as C  # noqa: E402

VERSION = "1.1.0"
PROTOCOLOS = ("2025-06-18", "2025-03-26", "2024-11-05")

INSTRUCCIONES = (
    "Horizon DB: la base de Nicolás (Horizon Trading) en su PC, armada desde el CRM. Solo lectura. "
    "Al escribir «Loki» se llama primero apertura_loki. Para una cuenta, ficha_cliente; para «a quién llamo», "
    "seguimientos_hoy; antes de preguntarle algo a Nicolás, buscar_memoria. El Sales Engine es el único que "
    "decide: la agenda de las fichas es dato, no decisión. El precio vigente sale de HIVE.")

TEXTO = {"type": "string"}
HERRAMIENTAS = [
    ("apertura_loki", "Arranque de Loki en una consulta: estado de la base, orden del Sales Engine, agenda "
     "vencida, controles y el resumen de correr_dia. Usar al escribir «Loki».", {}, [],
     lambda cx, a: C.apertura_loki(cx, a.get("hoy"))),
    ("ficha_cliente", "Todo de una cuenta: datos, OLT, próxima acción, decisión del Sales Engine, "
     "cotizaciones, últimas compras e historial. Acepta CUIT, id de ficha o parte del nombre.",
     {"consulta": TEXTO}, ["consulta"], lambda cx, a: C.ficha_cliente(cx, a["consulta"])),
    ("estado_cliente", "Tarjeta «LOKI · INTELIGENCIA COMERCIAL» de una cuenta, armada en una consulta: ficha, "
     "compras por comprobante (anuladas marcadas por Stockfish), último precio, grupo y sus cotizaciones abiertas, "
     "Sales Engine, stock y alertas A1-A9. Usar para «estado / status / ficha de X». Antes, consultar HIVE "
     "(precio_producto y consultar_stock del producto principal) y pasar precio_isp y stock_hive. Devuelve el "
     "resumen y el HTML de la tarjeta para mostrar con show_widget.",
     {"consulta": TEXTO, "precio_isp": {"type": "number"}, "stock_hive": {"type": "number"},
      "fecha_hive": TEXTO}, ["consulta"],
     lambda cx, a: C.estado_cliente(cx, a["consulta"], a.get("hoy"), a.get("precio_isp"),
                                    a.get("stock_hive"), a.get("fecha_hive"))),
    ("seguimientos_hoy","A quién llamar hoy: primero el orden del Sales Engine, después la agenda vencida "
     "o de hoy de las fichas (sin perdidas ni cuentas fuera).", {"hoy": TEXTO}, [],
     lambda cx, a: C.seguimientos_hoy(cx, a.get("hoy"))),
    ("buscar_producto", "Stock según la copia de HIVE (con la fecha de la foto) y el último precio cotizado "
     "como referencia. Acepta código o parte del nombre.", {"texto": TEXTO}, ["texto"],
     lambda cx, a: C.buscar_producto(cx, a["texto"])),
    ("facturas_sin_cargar", "Facturas del libro de ventas de Finnegans sin sus líneas de producto en el CRM.",
     {"dias": {"type": "integer", "minimum": 1, "maximum": 400}}, [],
     lambda cx, a: C.facturas_sin_cargar(cx, a.get("dias", 60), a.get("hoy"))),
    ("duplicados_cuit", "CUIT con más de una ficha (candidatos a unificar con «hacelo»).", {}, [],
     lambda cx, a: C.duplicados_cuit(cx)),
    ("buscar_memoria", "Busca un tema en decisiones de Nicolás, aprendizajes de Claude e historial de las "
     "cuentas. Usar antes de preguntarle algo a Nicolás.", {"tema": TEXTO}, ["tema"],
     lambda cx, a: C.buscar_memoria(cx, a["tema"])),
]
POR_NOMBRE = {h[0]: h for h in HERRAMIENTAS}


def lista_herramientas():
    out = []
    for nombre, desc, props, req, _ in HERRAMIENTAS:
        props = dict(props)
        if nombre in ("apertura_loki", "facturas_sin_cargar", "estado_cliente"):
            props["hoy"] = {"type": "string", "description": "AAAA-MM-DD; por defecto, hoy en Argentina"}
        out.append({"name": nombre, "description": desc,
                    "inputSchema": {"type": "object", "properties": props, "required": req},
                    "annotations": {"readOnlyHint": True}})
    return out


def llamar(db, nombre, args):
    h = POR_NOMBRE.get(nombre)
    if not h:
        return {"content": [{"type": "text", "text": f"Herramienta desconocida: {nombre}"}], "isError": True}
    faltan = [r for r in h[3] if not args.get(r)]
    if faltan:
        return {"content": [{"type": "text", "text": f"Falta: {', '.join(faltan)}"}], "isError": True}
    try:
        cx = C.abrir(db)
        try:
            texto = h[4](cx, args)
        finally:
            cx.close()
        return {"content": [{"type": "text", "text": texto}], "isError": False}
    except Exception as e:  # el error vuelve como texto, el servidor sigue vivo
        return {"content": [{"type": "text", "text": f"FALLA · {type(e).__name__}: {e}"}], "isError": True}


def responder(db, msg):
    metodo, mid = msg.get("method"), msg.get("id")
    if mid is None:  # notificación: no lleva respuesta
        return None
    if metodo == "initialize":
        pedido = (msg.get("params") or {}).get("protocolVersion")
        res = {"protocolVersion": pedido if pedido in PROTOCOLOS else PROTOCOLOS[0],
               "capabilities": {"tools": {"listChanged": False}},
               "serverInfo": {"name": "horizon-db", "version": VERSION},
               "instructions": INSTRUCCIONES}
    elif metodo == "ping":
        res = {}
    elif metodo == "tools/list":
        res = {"tools": lista_herramientas()}
    elif metodo == "tools/call":
        p = msg.get("params") or {}
        res = llamar(db, p.get("name"), p.get("arguments") or {})
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"Método no soportado: {metodo}"}}
    return {"jsonrpc": "2.0", "id": mid, "result": res}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.environ.get("HORIZON_DB", C_DB()))
    db = ap.parse_args().db
    entrada = sys.stdin.buffer
    salida = sys.stdout.buffer
    for linea in entrada:
        linea = linea.strip()
        if not linea:
            continue
        try:
            msg = json.loads(linea.decode("utf-8"))
        except ValueError:
            r = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "JSON inválido"}}
        else:
            try:
                r = responder(db, msg)
            except Exception:
                traceback.print_exc(file=sys.stderr)
                r = {"jsonrpc": "2.0", "id": msg.get("id"), "error": {"code": -32603, "message": "error interno"}}
        if r is not None:
            salida.write(json.dumps(r, ensure_ascii=False).encode("utf-8") + b"\n")
            salida.flush()


def C_DB():
    return os.path.join(os.path.expanduser("~"), "HorizonDB", "horizon.db")


if __name__ == "__main__":
    main()

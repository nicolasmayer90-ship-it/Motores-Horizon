#!/usr/bin/env python3
"""Horizon DB · autotest v2.0. Datos inventados (ninguna cuenta real), sanos y sabotajes.

    python -I probar.py   → RESULTADO: PASA | FALLA

Prueba: la carga, cada consulta, que la base sea de solo lectura, que un CUIT repetido y
una factura sin líneas se detecten, que una carga rota no pise la base buena y que el
conector MCP responda por stdio.
"""
import json, os, subprocess, sys, tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import cargar, consultas as C  # noqa: E402

HOY = "2026-11-16"
fallas = []


def chequear(nombre, cond, detalle=""):
    print(f"{'PASA ' if cond else 'FALLA'} · {nombre}{' · ' + detalle if detalle and not cond else ''}")
    if not cond:
        fallas.append(nombre)


def escribir(ruta, obj):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False)


def armar_export(raiz):
    escribir(f"{raiz}/oportunidades/a-alfa.json", {
        "empresa": "Alfa Fibra", "cuit": "30-11111111-1", "etapa": "cotizado", "prioridad": "A",
        "proximaFecha": "2026-11-16", "proximaAccion": "Renovar NM90", "marcaOlt": "FiberHome",
        "historial": [{"t": "2026-11-10T12:00:00Z", "txt": "pidió 100 ONT"}]})
    escribir(f"{raiz}/oportunidades/b-beta.json", {
        "empresa": "Beta Net", "cuit": "30-22222222-2", "etapa": "perdido", "proximaFecha": "2026-11-01",
        "pago": "cheques 0-120", "otroVendedor": "Mati",
        "cuitsAdicionales": [{"cuit": "30-44444444-4", "nombre": "Beta Sur"}],
        "contactosAdicionales": [{"nombre": "Ana", "cargo": "compras", "celular": "11 5555", "fuente": "prueba"}]})
    escribir(f"{raiz}/oportunidades/b-beta-2.json", {  # sabotaje: mismo CUIT que Beta
        "empresa": "Beta Net SRL", "cuit": "30222222222", "etapa": "contactado"})
    escribir(f"{raiz}/oportunidades/b-beta-vieja.json", {  # ya unificada en Beta: no es un duplicado abierto
        "empresa": "Beta vieja", "cuit": "30222222222", "etapa": "contactado", "archivada": True,
        "unificadaEn": "b-beta"})
    escribir(f"{raiz}/oportunidades/d-delta.json", {  # sabotaje: CUIT adicional que es el principal de otra ficha
        "empresa": "Delta", "cuit": "30-55555555-5", "etapa": "contactado",
        "cuitsAdicionales": [{"cuit": "30444444444"}]})
    escribir(f"{raiz}/oportunidades/g-gama.json", {"empresa": "Gama", "cuit": "", "etapa": "prospecto",
                                                   "proximaFecha": "2026-11-15", "proximaAccion": "llamar"})
    escribir(f"{raiz}/oportunidades/g-gama-2.json", {"empresa": "Gama ", "etapa": "prospecto"})
    escribir(f"{raiz}/oportunidades/f-fuera.json", {"empresa": "Fuera SA", "cuit": "30-33333333-3",
                                                    "etapa": "contactado", "proximaFecha": "2026-11-14"})
    escribir(f"{raiz}/cotizaciones/2026-11-01-alfa-nm90.json", {
        "numero": "NM90", "oportunidadId": "a-alfa", "cuit": "30-11111111-1", "cliente": "Alfa Fibra",
        "fecha": "2026-11-01", "vence": "2026-11-10", "estado": "enviada", "neto": 3800, "total": 4199,
        "items": [{"codigo": "9001", "articulo": "ONT Prueba X", "cantidad": 100, "precio": 38}],
        "hz_operacion": {"pago": "confirmado", "pagoAt": "2026-11-13T15:21:00Z", "despacho": "pendiente"}})
    escribir(f"{raiz}/stockfish_fichas/a-alfa.json", {"empresa": "Alfa Fibra", "etapa": "cotizado",
        "sf_compras": {"nFacturas": 1, "primera": "2026-10-20", "ultima": "2026-10-20", "usdBrutoNeto": 1900},
        "sf_nHallazgos": {"alta": 1, "media": 0, "baja": 2},
        "sf_comprobantes": [  # sabotaje A60: la FA 0007 está anulada por NC y no tiene que contar
            {"fecha": "2026-03-01", "tipo": "F", "comp": "A-00005-00000007", "moneda": "USD", "bruto": 760, "total": 839.8, "anulada": True},
            {"fecha": "2026-03-05", "tipo": "NC", "comp": "A-00005-00000008", "moneda": "USD", "bruto": -760, "total": -839.8},
            {"fecha": "2026-10-20", "tipo": "F", "comp": "A-00005-00000001", "moneda": "USD", "bruto": 1900, "total": 2099}],
        "sf_lineas": [
            {"fecha": "2026-03-01", "tipo": "F", "comp": "A-00005-00000007", "items": ["20 × ONT Prueba X [FH]"]},
            {"fecha": "2026-10-20", "tipo": "AJ", "comp": "A-00005-00000001",
             "items": ["0 × Descuento Comercial (Iva 10,5%) [-]", "50 × ONT Prueba X [FH]"]}]})
    escribir(f"{raiz}/datacenter/grupos.json", {"grupos": {"prueba": {
        "nombre": "Grupo Prueba", "fichas": ["a-alfa", "g-gama"], "fuente": "probar.py"}}})
    escribir(f"{raiz}/reportes/r21.json", {
        "formato": {"f": ["fecha", "tipo", "cliente", "cuit", "cuitPorNombre", "comprobante", "producto", "detalle",
                          "cantidad", "pendiente", "vendedor", "marca", "familia", "subfamilia", "deposito", "_fila",
                          "reglas"]},
        "dic": {"tipo": ["Remito de Venta"], "cliente": ["ALFA FIBRA SA"], "producto": ["ONT Prueba X"],
                "vendedor": ["Nicolás"], "marca": ["FH"], "familia": ["ONU"], "subfamilia": ["GPON"],
                "deposito": ["Central"]},
        "d": [["2026-10-21", 0, 0, "30111111111", 0, "R-0001-00000001", 0, None, 50, 0, 0, 0, 0, 0, 0, 1, None]]})
    escribir(f"{raiz}/facturacion/30111111111.json", {"cliente": "ALFA FIBRA SA", "cuit": "30111111111", "lineas": [
        {"comprobante": "A-00005-00000001", "fecha": "2026-10-20", "tipo": "F", "cod": "X",
         "producto": "ONT Prueba X", "cantidad": 50},
        {"comprobante": "A-00005-00000004", "fecha": "2026-10-30", "tipo": "F", "cod": "X",  # corte de líneas
         "producto": "ONT Prueba X", "cantidad": 10},
        {"comprobante": "A-00005-00000003", "fecha": "2026-10-26", "tipo": "NC", "cod": "X",
         "producto": "ONT Prueba X", "cantidad": -5}]})
    escribir(f"{raiz}/facturacion/30222222222.json", {"cliente": "BETA", "cuit": "30222222222", "lineas": [
        {"comprobante": "A-00005-00000002", "fecha": "2022-01-01", "tipo": "F", "cod": "Y",  # sabotaje: mismo número, otra cuenta
         "producto": "Viejo", "cantidad": 1}]})
    fmt = {"f": ["fecha", "tipocomp", "moneda", "cliente", "cuit", "cuitPorNombre", "comprobante",
                 "bruto", "otros", "total", "tc", "detalle", "fechaAlta", "usuario", "_fila"]}
    dic = {"tipocomp": ["Factura de Venta Electrónica", "Nota de Crédito de Ventas Electrónica"],
           "moneda": ["USD"], "cliente": ["ALFA FIBRA SA"], "usuario": ["x"]}
    escribir(f"{raiz}/reportes/r15.json", {"formato": fmt, "dic": dic, "d": [
        ["2026-10-20", 0, 0, 0, "30111111111", 1, "A-00005-00000001", 1900, 199, 2099, 1, None, "", 0, 1]]})
    escribir(f"{raiz}/reportes/r15_2.json", {"formato": fmt, "d": [  # sabotaje: factura sin líneas
        ["2026-10-25", 0, 0, 0, "30111111111", 1, "A-00005-00000002", 500, 52, 552, 1, None, "", 0, 2],
        ["2026-10-26", 1, 0, 0, "30111111111", 1, "A-00005-00000003", -500, -52, -552, 1, None, "", 0, 3],
        ["2026-09-01", 0, 0, 0, "30999999999", 0, "A-00005-00000009", 700, 70, 770, 1, None, "", 0, 4],  # sin ficha
        ["2026-09-02", 0, 0, 0, "30333333333", 0, "A-00005-00000010", 100, 10, 110, 1, None, "", 0, 5]]})  # cuenta fuera
    escribir(f"{raiz}/datacenter/hive_stock.json", {"corte": "2026-11-06", "productos": {
        "9001": {"nombre": "ONT Prueba X", "marca": "FH", "stock": 500, "transito": 0}}})
    escribir(f"{raiz}/datacenter/decisiones.json", {"lineas": ["1. 01/11 · Nicolás · Alfa se cotiza en USD"]})
    escribir(f"{raiz}/datacenter/aprendizajes.json", {"aprendizajes": [
        {"id": "A1", "error": "inventé un precio de Alfa", "patron": "p", "regla": "precio de HIVE", "test": "t"}]})
    escribir(f"{raiz}/datacenter/restricciones.json", {"cuentasFuera": {
        "f-fuera": {"cuit": "30333333333", "empresa": "Fuera SA", "motivo": "otro vendedor"}}})
    escribir(f"{raiz}/salida/sales_hoy.json", {"hoy": HOY, "filas": [
        {"id": "a-alfa", "empresa": "Alfa Fibra", "puesto": 1, "empujon": "RENOVAR", "palabras": "Renovar NM90",
         "usd": 4199, "esperado": 600, "obligatorio": True, "hoy": True, "evidencia": ["NM90"]},
        {"id": "g-gama", "empresa": "Gama", "puesto": 2, "empujon": "—", "hoy": False}]})
    with open(f"{raiz}/salida/resumen.txt", "w", encoding="utf-8") as fh:
        fh.write("# RESUMEN de prueba\n")


def main():
    with tempfile.TemporaryDirectory() as tmp:
        raiz, db = os.path.join(tmp, "crm"), os.path.join(tmp, "horizon.db")
        armar_export(raiz)
        conteos = cargar.armar(raiz, db)
        chequear("carga: 8 fichas, 1 cotización, 5 comprobantes", conteos["clientes"] == 8 and
                 conteos["cotizaciones"] == 1 and conteos["libro_ventas"] == 5, str(conteos))
        cx = C.abrir(db)

        # v2.0: lo que leen los motores y antes no entraba
        q = lambda sql: [tuple(r) for r in cx.execute(sql).fetchall()]  # noqa: E731
        chequear("v2: CUIT principal y adicional de la misma ficha",
                 sorted(q("SELECT cuit, principal FROM cliente_cuits WHERE cliente_id='b-beta'")) ==
                 [("30222222222", 1), ("30444444444", 0)], str(q("SELECT * FROM cliente_cuits")))
        chequear("v2: contacto adicional", q("SELECT nombre, cargo FROM contactos") == [("Ana", "compras")])
        chequear("v2: pago y otro vendedor en columnas",
                 q("SELECT pago, otro_vendedor FROM clientes WHERE id='b-beta'") == [("cheques 0-120", "Mati")])
        chequear("v2: archivada y unificada en columnas",
                 q("SELECT archivada, unificada_en FROM clientes WHERE id='b-beta-vieja'") == [("True", "b-beta")])
        # v2.1: integridad
        chequear("v2.1: la ficha unificada no cuenta como duplicado",
                 q("SELECT fichas FROM v_duplicados_cuit WHERE cuit='30222222222'") == [(2,)],
                 str(q("SELECT * FROM v_duplicados_cuit")))
        chequear("v2.1: sabotaje: CUIT adicional repetido en dos fichas detectado",
                 q("SELECT fichas FROM v_duplicados_cuit WHERE cuit='30444444444'") == [(2,)],
                 str(q("SELECT * FROM v_duplicados_cuit")))
        chequear("v2.1: comprador sin ficha detectado y cuenta con ficha no",
                 q("SELECT cuit, facturas, usd_facturado FROM v_compradores_sin_ficha") == [("30999999999", 1, 700.0)],
                 str(q("SELECT * FROM v_compradores_sin_ficha")))
        chequear("v2: operación de la cotización (pago y despacho)",
                 q("SELECT pago, pago_at, despacho FROM cotizacion_operacion") ==
                 [("confirmado", "2026-11-13T15:21:00Z", "pendiente")])
        chequear("v2: libro con tc y usuario", q("SELECT tc, usuario FROM libro_ventas WHERE comprobante='A-00005-00000001'") ==
                 [(1.0, "x")])
        chequear("v2: remito del reporte 21 con nombres traducidos",
                 q("SELECT tipo, producto, cantidad, vendedor FROM remitos") == [("Remito de Venta", "ONT Prueba X", 50.0, "Nicolás")])
        chequear("v2: Stockfish con resumen de compras y hallazgos",
                 q("SELECT n_facturas, usd_bruto_neto, n_hallazgos FROM stockfish") == [(1, 1900.0, 3)])
        chequear("v2: la ficha entera queda en doc", json.loads(q("SELECT doc FROM clientes WHERE id='b-beta'")[0][0])["pago"] == "cheques 0-120")

        import comparar  # noqa: E402
        res, dif = comparar.comparar(raiz, db)
        chequear("comparar: base recién cargada = CRM (0 diferencias)", not dif, " | ".join(dif))
        escribir(f"{raiz}/oportunidades/a-alfa.json", {**json.load(open(f"{raiz}/oportunidades/a-alfa.json", encoding="utf-8")),
                                                       "proximaFecha": "2026-12-01"})
        os.makedirs(f"{raiz}/cotizaciones", exist_ok=True)
        escribir(f"{raiz}/cotizaciones/2026-11-20-nueva.json", {"numero": "NM91", "estado": "enviada"})
        res, dif = comparar.comparar(raiz, db)
        chequear("sabotaje: comparar ve el campo cambiado en la ficha",
                 any("oportunidades/a-alfa: distinto en proximaFecha" in d for d in dif), " | ".join(dif))
        chequear("sabotaje: comparar ve la cotización que falta en la base",
                 any("cotizaciones/2026-11-20-nueva" in d and "falta en la base" in d for d in dif), " | ".join(dif))
        os.remove(f"{raiz}/cotizaciones/2026-11-20-nueva.json")
        cx.close()
        cargar.armar(raiz, db)
        cx = C.abrir(db)

        # v2.2: grupos y tarjeta de estado
        chequear("v2.2: grupos cargados desde datacenter/grupos",
                 sorted(tuple(r) for r in cx.execute("SELECT grupo, cliente_id FROM grupos")) ==
                 [("prueba", "a-alfa"), ("prueba", "g-gama")])
        t = C.estado_cliente(cx, "Alfa", HOY, precio_isp=40, stock_hive=480, fecha_hive=HOY)
        tarjeta = t.split("<<<TARJETA")[1] if "<<<TARJETA" in t else ""
        chequear("estado: devuelve la tarjeta LOKI sin campos sin llenar",
                 "LOKI · INTELIGENCIA COMERCIAL" in tarjeta and "{{" not in tarjeta, t[:300])
        chequear("estado: muestra el empuje del Sales Engine", "RENOVAR" in t, t[:300])
        chequear("sabotaje A60: la factura anulada no suma y se nombra como anulada",
                 "Anuladas con NC (no cuentan): FA 0007" in tarjeta and ">50 unidades" not in tarjeta
                 and "50 <span" in tarjeta, tarjeta[-1500:])
        chequear("estado: último precio por unidad sin el descuento (1900 / 50 = 38)", "USD 38 + IVA" in tarjeta, tarjeta)
        chequear("estado: usa el precio y el stock de HIVE que se le pasan", "USD 40,00" in tarjeta and ">480<" in tarjeta)
        t = C.estado_cliente(cx, "g-gama", HOY)
        chequear("estado: avisa la cotización abierta de otra ficha del grupo (A8)",
                 "A8 Alfa Fibra (mismo grupo) tiene la NM90 abierta" in t, t[:600])
        chequear("estado: sin precio de HIVE lo pide", "falta el precio vigente" in t)
        chequear("estado: ambiguo pide elegir", C.estado_cliente(cx, "Beta").startswith("Ambiguo"))

        t = C.apertura_loki(cx, HOY)
        chequear("apertura: empuje de hoy del Sales Engine", "empujes de hoy: 1" in t and "Alfa Fibra · RENOVAR" in t, t)
        chequear("apertura: trae el resumen de correr_dia", "RESUMEN de prueba" in t)
        chequear("apertura: controles cuentan 1 factura, 2 CUIT repetidos y 1 comprador sin ficha",
                 "1 facturas" in t and "2 CUIT" in t and "1 nombres repetidos" in t and "1 CUIT que compraron sin ficha" in t, t)

        t = C.seguimientos_hoy(cx, HOY)
        chequear("agenda: entra Gama (vencida)", "Gama (g-gama)" in t, t)
        chequear("agenda: no entra la perdida (Beta)", "b-beta)" not in t, t)
        chequear("agenda: no entra la cuenta fuera", "Fuera SA" not in t, t)

        t = C.ficha_cliente(cx, "30-11111111-1")
        chequear("ficha por CUIT con guiones", t.startswith("Alfa Fibra (a-alfa)"), t)
        chequear("ficha: cotización, compra e historial", "NM90" in t and "50 × ONT Prueba X" in t and "pidió 100 ONT" in t, t)
        chequear("sabotaje: la NC se muestra como nota de crédito, no como compra",
                 "NOTA DE CRÉDITO (resta) A-00005-00000003 · 5 × ONT Prueba X" in t, t)
        chequear("ficha por nombre ambiguo pide elegir", C.ficha_cliente(cx, "Beta").startswith("Ambiguo"))
        chequear("ficha inexistente lo dice", C.ficha_cliente(cx, "Zeta").startswith("Sin coincidencias"))
        chequear("ficha de cuenta fuera lo avisa", "CUENTA FUERA" in C.ficha_cliente(cx, "f-fuera"))

        t = C.buscar_producto(cx, "9001")
        chequear("producto: stock con fecha de foto y último precio", "stock 500" in t and "2026-11-06" in t and "USD 38" in t, t)

        t = C.facturas_sin_cargar(cx, 60, HOY)
        chequear("sabotaje: factura sin líneas detectada aunque otra cuenta tenga el mismo número", "A-00005-00000002" in t and "FALTA CARGAR" in t, t)
        chequear("la NC no cuenta como factura sin líneas", "A-00005-00000003" not in t, t)
        chequear("la factura con líneas no aparece", "A-00005-00000001" not in t, t)

        t = C.duplicados_cuit(cx)
        chequear("sabotaje: CUIT repetido detectado", "30222222222 · 2 fichas" in t, t)
        chequear("sabotaje: nombre repetido sin CUIT detectado", "«gama» · 2 fichas" in t, t)

        chequear("memoria: decisión y aprendizaje", "decisión 1" in C.buscar_memoria(cx, "Alfa") and
                 "aprendizaje A1" in C.buscar_memoria(cx, "Alfa"))
        chequear("memoria vacía lo dice", "recién ahí se le pregunta" in C.buscar_memoria(cx, "inexistente"))

        try:
            cx.execute("DELETE FROM clientes")
            chequear("solo lectura", False, "pudo borrar")
        except Exception:
            chequear("solo lectura: la base no deja escribir", True)
        cx.close()

        os.remove(os.path.join(raiz, "oportunidades", "a-alfa.json"))
        with open(os.path.join(raiz, "oportunidades", "a-alfa.json"), "w") as fh:
            fh.write("{roto")
        try:
            cargar.armar(raiz, db)
            chequear("carga rota falla", False, "no falló")
        except Exception:
            cx = C.abrir(db)
            n = cx.execute("SELECT COUNT(*) FROM clientes").fetchone()[0]
            cx.close()
            chequear("sabotaje: carga rota no pisa la base buena", n == 8, f"quedaron {n}")

        msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                 "params": {"name": "ficha_cliente", "arguments": {"consulta": "Alfa"}}},
                {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "ficha_cliente", "arguments": {}}}]
        r = subprocess.run([sys.executable, "-I", os.path.join(AQUI, "servidor.py"), "--db", db],
                           input="\n".join(json.dumps(m) for m in msgs) + "\n", capture_output=True,
                           text=True, encoding="utf-8", timeout=60)
        resp = {x["id"]: x for x in (json.loads(l) for l in r.stdout.splitlines() if l.strip())}
        chequear("MCP: initialize", resp.get(1, {}).get("result", {}).get("serverInfo", {}).get("name") == "horizon-db", r.stderr)
        chequear("MCP: la notificación no lleva respuesta", len(resp) == 4, str(list(resp)))
        nombres = [t["name"] for t in resp.get(2, {}).get("result", {}).get("tools", [])]
        chequear("MCP: 8 herramientas de lectura", len(nombres) == 8 and "estado_cliente" in nombres and "apertura_loki" in nombres, str(nombres))
        texto = resp.get(3, {}).get("result", {}).get("content", [{}])[0].get("text", "")
        chequear("MCP: ficha_cliente responde", texto.startswith("Alfa Fibra"), texto)
        chequear("MCP: falta un argumento → error claro", resp.get(4, {}).get("result", {}).get("isError") is True)

    print(f"\nRESULTADO: {'PASA' if not fallas else 'FALLA'} · {len(fallas)} fallas")
    return 0 if not fallas else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Horizon DB · autotest v1.0. Datos inventados (ninguna cuenta real), sanos y sabotajes.

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
        "empresa": "Beta Net", "cuit": "30-22222222-2", "etapa": "perdido", "proximaFecha": "2026-11-01"})
    escribir(f"{raiz}/oportunidades/b-beta-2.json", {  # sabotaje: mismo CUIT que Beta
        "empresa": "Beta Net SRL", "cuit": "30222222222", "etapa": "contactado"})
    escribir(f"{raiz}/oportunidades/g-gama.json", {"empresa": "Gama", "cuit": "", "etapa": "prospecto",
                                                   "proximaFecha": "2026-11-15", "proximaAccion": "llamar"})
    escribir(f"{raiz}/oportunidades/g-gama-2.json", {"empresa": "Gama ", "etapa": "prospecto"})
    escribir(f"{raiz}/oportunidades/f-fuera.json", {"empresa": "Fuera SA", "cuit": "30-33333333-3",
                                                    "etapa": "contactado", "proximaFecha": "2026-11-14"})
    escribir(f"{raiz}/cotizaciones/2026-11-01-alfa-nm90.json", {
        "numero": "NM90", "oportunidadId": "a-alfa", "cuit": "30-11111111-1", "cliente": "Alfa Fibra",
        "fecha": "2026-11-01", "vence": "2026-11-10", "estado": "enviada", "neto": 3800, "total": 4199,
        "items": [{"codigo": "9001", "articulo": "ONT Prueba X", "cantidad": 100, "precio": 38}]})
    escribir(f"{raiz}/facturacion/30111111111.json", {"cliente": "ALFA FIBRA SA", "cuit": "30111111111", "lineas": [
        {"comprobante": "A-00005-00000001", "fecha": "2026-10-20", "tipo": "F", "cod": "X",
         "producto": "ONT Prueba X", "cantidad": 50},
        {"comprobante": "A-00005-00000004", "fecha": "2026-10-30", "tipo": "F", "cod": "X",  # corte de líneas
         "producto": "ONT Prueba X", "cantidad": 10}]})
    fmt = {"f": ["fecha", "tipocomp", "moneda", "cliente", "cuit", "cuitPorNombre", "comprobante",
                 "bruto", "otros", "total", "tc", "detalle", "fechaAlta", "usuario", "_fila"]}
    dic = {"tipocomp": ["Factura de Venta Electrónica", "Nota de Crédito de Ventas Electrónica"],
           "moneda": ["USD"], "cliente": ["ALFA FIBRA SA"], "usuario": ["x"]}
    escribir(f"{raiz}/reportes/r15.json", {"formato": fmt, "dic": dic, "d": [
        ["2026-10-20", 0, 0, 0, "30111111111", 1, "A-00005-00000001", 1900, 199, 2099, 1, None, "", 0, 1]]})
    escribir(f"{raiz}/reportes/r15_2.json", {"formato": fmt, "d": [  # sabotaje: factura sin líneas
        ["2026-10-25", 0, 0, 0, "30111111111", 1, "A-00005-00000002", 500, 52, 552, 1, None, "", 0, 2],
        ["2026-10-26", 1, 0, 0, "30111111111", 1, "A-00005-00000003", -500, -52, -552, 1, None, "", 0, 3]]})
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
        chequear("carga: 6 fichas, 1 cotización, 3 comprobantes", conteos["clientes"] == 6 and
                 conteos["cotizaciones"] == 1 and conteos["libro_ventas"] == 3, str(conteos))
        cx = C.abrir(db)

        t = C.apertura_loki(cx, HOY)
        chequear("apertura: empuje de hoy del Sales Engine", "empujes de hoy: 1" in t and "Alfa Fibra · RENOVAR" in t, t)
        chequear("apertura: trae el resumen de correr_dia", "RESUMEN de prueba" in t)
        chequear("apertura: controles cuentan 1 factura y 1 CUIT repetido",
                 "1 facturas" in t and "1 CUIT" in t and "1 nombres repetidos" in t, t)

        t = C.seguimientos_hoy(cx, HOY)
        chequear("agenda: entra Gama (vencida)", "Gama (g-gama)" in t, t)
        chequear("agenda: no entra la perdida (Beta)", "b-beta)" not in t, t)
        chequear("agenda: no entra la cuenta fuera", "Fuera SA" not in t, t)

        t = C.ficha_cliente(cx, "30-11111111-1")
        chequear("ficha por CUIT con guiones", t.startswith("Alfa Fibra (a-alfa)"), t)
        chequear("ficha: cotización, compra e historial", "NM90" in t and "50 × ONT Prueba X" in t and "pidió 100 ONT" in t, t)
        chequear("ficha por nombre ambiguo pide elegir", C.ficha_cliente(cx, "Beta").startswith("Ambiguo"))
        chequear("ficha inexistente lo dice", C.ficha_cliente(cx, "Zeta").startswith("Sin coincidencias"))
        chequear("ficha de cuenta fuera lo avisa", "CUENTA FUERA" in C.ficha_cliente(cx, "f-fuera"))

        t = C.buscar_producto(cx, "9001")
        chequear("producto: stock con fecha de foto y último precio", "stock 500" in t and "2026-11-06" in t and "USD 38" in t, t)

        t = C.facturas_sin_cargar(cx, 60, HOY)
        chequear("sabotaje: factura sin líneas detectada", "A-00005-00000002" in t and "FALTA CARGAR" in t, t)
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
            chequear("sabotaje: carga rota no pisa la base buena", n == 6, f"quedaron {n}")

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
        chequear("MCP: 7 herramientas de lectura", len(nombres) == 7 and "apertura_loki" in nombres, str(nombres))
        texto = resp.get(3, {}).get("result", {}).get("content", [{}])[0].get("text", "")
        chequear("MCP: ficha_cliente responde", texto.startswith("Alfa Fibra"), texto)
        chequear("MCP: falta un argumento → error claro", resp.get(4, {}).get("result", {}).get("isError") is True)

    print(f"\nRESULTADO: {'PASA' if not fallas else 'FALLA'} · {len(fallas)} fallas")
    return 0 if not fallas else 1


if __name__ == "__main__":
    sys.exit(main())

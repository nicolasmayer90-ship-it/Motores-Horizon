#!/usr/bin/env python3
"""Cinco cosas del día v2.0 · Horizon CRM · VISTA del Sales Engine (11/11/2026, hacelo de Nicolás 15:15)

v2.0: cinco_cosas ya no calcula nada. Las cinco cosas (entrega, cotización, responder, reposición, reactivación)
las decide el Sales Engine v4.4 con las reglas únicas de datacenter/reglas_motor, en el mismo cálculo que los
empujes del día. Este script solo las muestra. Así una cuenta no puede salir empujada acá y frenada allá
(choques del 11/11: Buena Onda 3,4x, Cablenet en cadencia, compra típica de Infinitel 9.000 vs 9.945).
Hasta v1.4 tenía reglas propias: quedan en datacenter/respaldo_2026-11-11_motores_pre_v44.

Uso:
  python3 -I cinco_cosas.py dia --sales <salida --json del Sales Engine> --hoy AAAA-MM-DD [--json salida.json]
  python3 -I cinco_cosas.py test
FRENO si la salida del Sales Engine no es de hoy, es anterior a v4.4 o no trae las cinco cosas.
"""
import argparse, datetime as dt, hashlib, json, sys

VERSION = "2.0"
LUGARES = ["ENTREGA", "COTIZACION", "RESPONDER", "REPOSICION", "REACTIVACION"]


def usd(x):
    return "USD " + f"{x or 0:,.0f}".replace(",", ".")


def huella(o):
    return hashlib.sha256(json.dumps(o, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()[:12]


def version_ok(v):
    try:
        a, b = (int(x) for x in str(v).split(".")[:2])
        return (a, b) >= (4, 4)
    except ValueError:
        return False


def validar(sales, hoy):
    """Lista de motivos de FRENO (vacía = se puede mostrar)."""
    m = []
    if not version_ok(sales.get("version")):
        m.append(f"Sales Engine v{sales.get('version')}: hace falta v4.4 o más")
    if sales.get("hoy") != hoy:
        m.append(f"la salida del Sales Engine es del {sales.get('hoy')}, no de hoy {hoy}: re-correrlo")
    if "cinco" not in sales:
        m.append("la salida del Sales Engine no trae las cinco cosas")
    return m


def render(sales, hoy):
    items = sales.get("cinco") or {}
    ctl = (sales.get("control") or {}).get("cinco") or {}
    d = dt.date.fromisoformat(hoy)
    L = [f"# Cinco cosas del día v{VERSION} · {d:%d/%m/%Y} · vista del Sales Engine v{sales.get('version')} "
         f"(salida {sales.get('huella')}, reglas {sales.get('reglasHuella')})", ""]
    for n, lugar in enumerate(LUGARES, 1):
        it = items.get(lugar)
        if not it:
            L.append(f"{n}. {lugar}: nada que cumpla la regla hoy")
            continue
        L.append(f"{n}. {lugar} · {it['empresa']} ({it['cuenta']}) · {usd(it['monto'])}")
        L.append(f"   dato: {it['dato']}")
        if lugar in ("COTIZACION", "REPOSICION") and it.get("p"):
            L.append(f"   P(pedido) {it['p']:.0%} ({it.get('pOrigen')}) · esperado {usd(it.get('esperado'))}"
                     + (" · POR VENCER" if it.get("porVencer") else ""))
        org = it.get("jugadaOrigen") or ""
        L.append(f"   jugada: {it.get('jugadaTxt')} ({it.get('jugada')}, {'motor por defecto' if org == 'defecto' else org})"
                 + (f" · {it['porQue']}" if it.get("porQue") else ""))
        L.append(f"   candidatos en este lugar: {it['candidatos']}" + (f" · segundo: {it['segundo']}" if it.get("segundo") else ""))
    fr = sales.get("bloqueadas") or {}
    L += ["", f"Frenadas (no salen en ninguna vista): {', '.join(v['empresa'] for v in fr.values()) or 'ninguna'}",
          f"Sin repetir: {'sí' if ctl.get('sinRepetir') else 'NO'} · candidatos: {ctl.get('candidatos')}",
          f"Huella vista: {huella(items)}",
          "Regla: el Sales Engine decide; esta vista no cambia nada. Cambiar reglas solo con «hacelo»."]
    return "\n".join(L)


def cmd_dia(a):
    sales = json.load(open(a.sales, encoding="utf-8"))
    m = validar(sales, a.hoy)
    if m:
        print("FRENO: " + " · ".join(m))
        return 3
    print(render(sales, a.hoy))
    if a.json:
        json.dump({"version": VERSION, "hoy": a.hoy, "vistaDe": sales.get("huella"), "items": sales["cinco"],
                   "huella": huella(sales["cinco"])}, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return 0 if ((sales.get("control") or {}).get("cinco") or {}).get("sinRepetir") else 2


def cmd_test(_):
    ok = True

    def t(c, msg):
        nonlocal ok
        print(("PASA " if c else "FALLA") + " · " + msg)
        ok &= bool(c)
    it = {"COTIZACION": {"cuenta": "nodo", "empresa": "Nodo Net", "monto": 20097.19, "dato": "Cerrar NM51", "p": 0.13,
                         "pOrigen": "banco", "esperado": 2552, "porVencer": True, "jugada": "SG", "jugadaTxt": "seguimiento",
                         "jugadaOrigen": "banco", "porQue": "", "candidatos": 1, "segundo": None}}
    s = {"version": "4.4", "hoy": "2026-11-11", "huella": "abc", "reglasHuella": "r1", "cinco": it,
         "control": {"cinco": {"sinRepetir": True, "candidatos": {"COTIZACION": 1}}}, "bloqueadas": {"tpp": {"empresa": "TPP"}}}
    t(validar(s, "2026-11-11") == [], "salida de hoy v4.4 se muestra")
    t(validar(dict(s, hoy="2026-11-10"), "2026-11-11") != [], "salida de otro día = FRENO")
    t(validar(dict(s, version="4.3"), "2026-11-11") != [], "Sales Engine anterior a v4.4 = FRENO")
    t(validar({k: v for k, v in s.items() if k != "cinco"}, "2026-11-11") != [], "sin cinco cosas = FRENO")
    out = render(s, "2026-11-11")
    t("Nodo Net" in out and "NM51" in out and "USD 20.097" in out, "muestra exactamente lo que decidió el Sales Engine")
    t("ENTREGA: nada" in out and "TPP" in out.split("Frenadas")[1], "lugar vacío y frenadas a la vista")
    t(version_ok("4.10") and version_ok("5.0") and not version_ok("x"), "comparación de versiones")
    print("RESULTADO:", "PASA" if ok else "FALLA")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    d = sub.add_parser("dia")
    d.add_argument("--sales", required=True)
    d.add_argument("--hoy", required=True)
    d.add_argument("--json")
    sub.add_parser("test")
    a = ap.parse_args()
    return cmd_dia(a) if a.cmd == "dia" else cmd_test(a) if a.cmd == "test" else ap.print_help()


if __name__ == "__main__":
    sys.exit(main())

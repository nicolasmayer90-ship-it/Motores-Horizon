#!/usr/bin/env python3
"""Verifica que los motores sean idénticos a los sellados (huellas.json) y corre sus autotests.
Uso: python3 -I verificar.py   → RESULTADO: PASA | FALLA (código de salida 0 / 1). Solo biblioteca estándar."""
import hashlib, json, os, subprocess, sys

AQUI = os.path.dirname(os.path.abspath(__file__))


def h12(ruta):
    with open(ruta, encoding="utf-8", newline="") as fh:
        return hashlib.sha256(fh.read().encode()).hexdigest()[:12]


def main():
    cfg = json.load(open(os.path.join(AQUI, "huellas.json"), encoding="utf-8"))
    ok = True
    for ruta, m in sorted(cfg["motores"].items()):
        p = os.path.join(AQUI, ruta)
        if not os.path.exists(p):
            print(f"FALLA · {ruta}: no está"); ok = False; continue
        h = h12(p)
        if h != m["huella"]:
            print(f"FALLA · {ruta}: huella {h} y la sellada es {m['huella']} ({m['doc']} v{m['version']})"); ok = False; continue
        if not m.get("test"):
            print(f"PASA  · {ruta}: huella {h} (sin autotest)"); continue
        r = subprocess.run([sys.executable, "-I", p] + m["test"], capture_output=True, text=True, cwd=os.path.dirname(p))
        fin = [l for l in (r.stdout + r.stderr).splitlines() if "RESULTADO" in l]
        bien = r.returncode == 0
        print(f"{'PASA ' if bien else 'FALLA'} · {ruta}: huella {h} · test {fin[-1].strip() if fin else 'código ' + str(r.returncode)}")
        if not bien:
            print((r.stdout + r.stderr)[-1500:]); ok = False
    print(f"\nRESULTADO: {'PASA' if ok else 'FALLA'} · manifiesto {cfg['manifiesto']} ({cfg['sellado']})")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

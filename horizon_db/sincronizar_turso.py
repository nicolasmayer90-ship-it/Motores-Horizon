#!/usr/bin/env python3
"""Copia la base local de Horizon DB (horizon.db) a Turso, entera y en UNA transacción.

La PC es la única que escribe (dec. 140): después de cada carga (cargar.py) se corre esto y la
copia en Turso queda igual a la local. Si algo falla a mitad de camino, Turso hace ROLLBACK y
queda como estaba. Al final compara, tabla por tabla, cantidad de filas y huella del contenido.

Sin datos ni credenciales en este archivo:
  URL    -> variable TURSO_URL o --url (libsql://... o https://...)
  token  -> variable TURSO_TOKEN o el archivo ~/.horizon/turso_db_token.txt (fuera del repo)

Uso:
  python -I sincronizar_turso.py --url libsql://<base>.turso.io [--db RUTA] [--solo-comparar]
Sale 0 si PASA, 1 si FALLA.
"""
import argparse, base64, hashlib, json, os, sqlite3, sys, urllib.request

DB_LOCAL = os.path.join(os.path.expanduser('~'), 'HorizonDB', 'horizon.db')
TOKEN_ARCHIVO = os.path.join(os.path.expanduser('~'), '.horizon', 'turso_db_token.txt')
LOTE = 300  # sentencias por pedido HTTP


def token():
    t = os.environ.get('TURSO_TOKEN')
    if not t and os.path.exists(TOKEN_ARCHIVO):
        t = open(TOKEN_ARCHIVO, encoding='utf-8').read().strip()
    if not t:
        sys.exit('Falta el token: variable TURSO_TOKEN o archivo ' + TOKEN_ARCHIVO)
    return t


class Turso:
    """Cliente mínimo del protocolo HTTP de libSQL (Hrana v2, /v2/pipeline) con baton para
    mantener la misma conexión (y la misma transacción) entre pedidos."""

    def __init__(self, url, tok):
        self.url = url.replace('libsql://', 'https://').rstrip('/') + '/v2/pipeline'
        self.tok, self.baton = tok, None

    def pedir(self, stmts, cerrar=False):
        reqs = [{'type': 'execute', 'stmt': s} for s in stmts]
        if cerrar:
            reqs.append({'type': 'close'})
        body = {'baton': self.baton, 'requests': reqs}
        r = urllib.request.Request(self.url, data=json.dumps(body).encode('utf-8'),
                                   headers={'Authorization': 'Bearer ' + self.tok, 'Content-Type': 'application/json'})
        resp = json.load(urllib.request.urlopen(r, timeout=120))
        self.baton = None if cerrar else resp.get('baton')
        for i, x in enumerate(resp['results']):
            if x['type'] != 'ok':
                raise RuntimeError(f"Turso rechazó la sentencia {i}: {x.get('error')}")
        return [x['response'].get('result') for x in resp['results'] if x['response']['type'] == 'execute']

    def consulta(self, sql):
        res = self.pedir([{'sql': sql}], cerrar=True)[0]
        return [[v_py(c) for c in fila] for fila in res['rows']]


def v_hrana(v):
    if v is None: return {'type': 'null'}
    if isinstance(v, bool) or isinstance(v, int): return {'type': 'integer', 'value': str(int(v))}
    if isinstance(v, float): return {'type': 'float', 'value': v}
    if isinstance(v, bytes): return {'type': 'blob', 'base64': base64.b64encode(v).decode().rstrip('=')}
    return {'type': 'text', 'value': str(v)}


def v_py(c):
    t = c['type']
    if t == 'null': return None
    if t == 'integer': return int(c['value'])
    if t == 'float': return float(c['value'])
    if t == 'blob': return base64.b64decode(c['base64'] + '=' * (-len(c['base64']) % 4))
    return c['value']


def huella(filas):
    h = hashlib.sha256()
    for f in filas:
        h.update(json.dumps([x.hex() if isinstance(x, bytes) else x for x in f], ensure_ascii=False,
                            default=str).encode('utf-8'))
    return h.hexdigest()[:16]


def esquema(loc):
    tablas = loc.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
                         "ORDER BY name").fetchall()
    indices = loc.execute("SELECT sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL").fetchall()
    return tablas, [i[0] for i in indices]


def copiar(loc, t, tablas, indices):
    print('Copiando a Turso en una transacción…')
    # Turso controla claves foráneas; se difiere el control al COMMIT (las tablas se copian en orden alfabético)
    t.pedir([{'sql': 'BEGIN'}, {'sql': 'PRAGMA defer_foreign_keys = ON'}])
    try:
        remotas = [r[0] for r in t.pedir([{'sql': "SELECT name FROM sqlite_master WHERE type='table' "
                                                  "AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '_litestream%'"}])[0]['rows']]
        t.pedir([{'sql': f'DROP TABLE IF EXISTS "{v_py(n)}"'} for n in remotas] +
                [{'sql': s} for _, s in tablas] + [{'sql': s} for s in indices])
        for nombre, _ in tablas:
            cols = [c[1] for c in loc.execute(f'PRAGMA table_info("{nombre}")')]
            ins = f'INSERT INTO "{nombre}" ({", ".join(chr(34) + c + chr(34) for c in cols)}) VALUES ({", ".join("?" * len(cols))})'
            lote, n = [], 0
            for fila in loc.execute(f'SELECT * FROM "{nombre}"'):
                lote.append({'sql': ins, 'args': [v_hrana(v) for v in fila]})
                if len(lote) >= LOTE:
                    t.pedir(lote); n += len(lote); lote = []
            if lote:
                t.pedir(lote); n += len(lote)
            print(f'  {nombre:<18} {n:>6} filas')
        t.pedir([{'sql': 'COMMIT'}], cerrar=True)
    except Exception:
        try:
            t.pedir([{'sql': 'ROLLBACK'}], cerrar=True)
        except Exception:
            pass
        raise


def comparar(loc, t, tablas):
    print('Control local contra Turso (filas y huella del contenido):')
    ok = True
    for nombre, _ in tablas:
        orden = ', '.join(str(i + 1) for i in range(len(loc.execute(f'PRAGMA table_info("{nombre}")').fetchall())))
        a = loc.execute(f'SELECT * FROM "{nombre}" ORDER BY {orden}').fetchall()
        b = [tuple(f) for f in t.consulta(f'SELECT * FROM "{nombre}" ORDER BY {orden}')]
        ha, hb = huella(a), huella(b)
        igual = len(a) == len(b) and ha == hb
        ok &= igual
        print(f'  {nombre:<18} local {len(a):>6}  turso {len(b):>6}  {"OK" if igual else "DISTINTO"}')
    print('RESULTADO:', 'PASA' if ok else 'FALLA')
    return ok


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--url', default=os.environ.get('TURSO_URL'))
    ap.add_argument('--db', default=DB_LOCAL)
    ap.add_argument('--solo-comparar', action='store_true')
    a = ap.parse_args()
    if not a.url:
        sys.exit('Falta la URL: --url o variable TURSO_URL')
    loc = sqlite3.connect(f'file:{a.db}?mode=ro', uri=True)
    t = Turso(a.url, token())
    tablas, indices = esquema(loc)
    if not a.solo_comparar:
        copiar(loc, t, tablas, indices)
    sys.exit(0 if comparar(loc, t, tablas) else 1)


if __name__ == '__main__':
    main()

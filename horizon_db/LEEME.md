# Horizon DB · base y conector en tu PC (Etapa 1)

Base SQLite con todo el CRM ordenado por CUIT y un conector («servidor MCP») que le entrega a
Claude cada dato ya armado, en una sola consulta. **Etapa 1 = solo lectura**: ninguna
herramienta escribe, ni en la base, ni en el CRM, ni en HIVE.

**Acá no hay datos.** La base (`horizon.db`) vive en tu PC, en `C:\Users\<vos>\HorizonDB\`,
y nunca se sube a GitHub.

## Qué hay

| Archivo | Qué hace |
|---|---|
| `esquema.sql` | Las tablas (v2.0): clientes (con la ficha entera en `doc`), historial, CUIT de cada ficha (principal y adicionales), contactos, cotizaciones (enteras en `doc`), ítems, operación de la cotización (pedido, pago, despacho, entrega), líneas de factura, libro de ventas (con tc, otros y usuario), remitos (reporte 21), Stockfish, stock, orden del Sales Engine, decisiones, aprendizajes y cuentas fuera |
| `cargar.py` | Arma la base desde la exportación del CRM. La arma en un archivo aparte y reemplaza la anterior solo si todo salió bien |
| `comparar.py` | Compara la base con la exportación del CRM: cada ficha, cotización y ficha de Stockfish campo por campo, y las filas de facturación, libro y remitos. `RESULTADO: PASA · 0 diferencias` o la lista de lo que no coincide |
| `consultas.py` | Las consultas (lo que contesta cada herramienta) |
| `servidor.py` | El conector MCP. Lo arranca Claude solo |
| `probar.py` | Autotest con datos inventados: `python -I probar.py` → `RESULTADO: PASA` |

Solo biblioteca estándar de Python: no se instala ningún paquete.

## Las 7 herramientas

| Herramienta | Qué te devuelve | Reemplaza a |
|---|---|---|
| `apertura_loki` | Estado de la base, empujes del Sales Engine, agenda de la semana, controles y el resumen del día | El arranque de Loki |
| `ficha_cliente` | Todo de una cuenta (por CUIT, id o nombre) | Bajar fichas y buscar a mano |
| `seguimientos_hoy` | Orden del Sales Engine y, después, la agenda vencida | Recorrer la ronda |
| `buscar_producto` | Stock de la copia de HIVE (con la fecha de la foto) y el último precio cotizado | Consultar el PM |
| `facturas_sin_cargar` | Facturas de Finnegans sin sus líneas en el CRM | El control que hoy hace Fundetec |
| `duplicados_cuit` | CUIT con más de una ficha y nombres repetidos sin CUIT | Encontrarlos de casualidad |
| `buscar_memoria` | Decisiones, aprendizajes e historial sobre un tema | `correr_dia.py consulta` |

Reglas que respeta: el Sales Engine es el único que decide (la agenda de las fichas se muestra
como dato), el precio vigente sale de HIVE y lo ambiguo se pregunta, no se elige.

## Instalar en tu PC (Windows 11) · una sola vez

1. Instalá **Git para Windows** (git-scm.com) y **Python 3** (python.org; en el instalador
   marcá «Add python.exe to PATH»).
2. Instalá **Claude Code** desde PowerShell, siguiendo la guía oficial (code.claude.com), y entrá
   con tu cuenta del plan Pro.
3. Bajá el repositorio:
   ```
   git clone https://github.com/nicolasmayer90-ship-it/Motores-Horizon C:\Horizon\Motores-Horizon
   ```
4. Probá que todo ande:
   ```
   python -I C:\Horizon\Motores-Horizon\horizon_db\probar.py
   ```
   Tiene que terminar en `RESULTADO: PASA`.
5. Conectá el conector a Claude Code (queda guardado para todos los chats):
   ```
   claude mcp add --scope user horizon-db -- python -I C:\Horizon\Motores-Horizon\horizon_db\servidor.py
   ```
6. Para la app de escritorio de Claude: Configuración → Desarrollador → Editar configuración, y
   sumar en `claude_desktop_config.json`:
   ```json
   {"mcpServers": {"horizon-db": {"command": "python",
     "args": ["-I", "C:\\Horizon\\Motores-Horizon\\horizon_db\\servidor.py"]}}}
   ```

## Cargar la base (cada día, hasta que llegue la Etapa 3)

1. En Claude Code escribís «Loki»: baja el CRM a `C:\HorizonDB\crm` y corre `correr_dia.py`
   como hoy.
2. Después: `python -I C:\Horizon\Motores-Horizon\horizon_db\cargar.py --raiz C:\HorizonDB\crm`
3. Control: `python -I C:\Horizon\Motores-Horizon\horizon_db\comparar.py --raiz C:\HorizonDB\crm`
   tiene que dar `PASA · 0 diferencias` antes de copiar a Turso.
4. Listo: `apertura_loki`, `ficha_cliente` y las demás contestan desde la base.

Si la base es de otro día, `apertura_loki` lo avisa en la primera línea.

## Copia en Turso (dec. 140)

La base también vive en Turso para que el Claude de la nube la lea en vivo. **La PC es la única
que escribe**: después de cada carga se copia entera, en una sola transacción, y se controla
tabla por tabla (filas y huella del contenido).

4. Después de `cargar.py`:
   `python -I C:\Horizon\Motores-Horizon\horizon_db\sincronizar_turso.py --url libsql://<base>.turso.io`
   Tiene que terminar en `RESULTADO: PASA`. Si algo falla, Turso queda como estaba (ROLLBACK).
   `--solo-comparar` controla sin copiar.

El conector (`servidor.py`) sigue leyendo el archivo local: la PC abre igual de rápido y no
depende de internet. El token de escritura va en la variable `TURSO_TOKEN` o en
`%USERPROFILE%\.horizon\turso_db_token.txt`, **nunca en este repositorio**. El de solo lectura
es para la nube y no se guarda en la PC.

## Lo que sigue

- **Etapa 3:** la carga se hace sola desde HIVE, Finnegans y el CRM (sin fotos viejas).
- **Etapa 4:** herramientas que escriben (minutas, seguimientos), siempre con tu «hacelo», y
  el procesador de chats de WhatsApp. Recién ahí el CUIT pasa a ser llave única: antes hay
  que unificar las fichas repetidas que marca `duplicados_cuit`.

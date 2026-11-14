# Motores Horizon

Código de los motores del sistema Horizon. **Solo código y tests: ningún dato.** Las fichas, la facturación, los precios, el stock y los contactos viven en el datacenter (artifact Horizon CRM), nunca acá. Repositorio **privado**: los casos de oro usan nombres de cuentas reales.

## Regla 1: los motores se mudan, no se reescriben

Cada archivo de `motores/` es idéntico, byte por byte, al código sellado en el manifiesto del datacenter (versión en `huellas.json`). `python3 -I verificar.py` controla las huellas y corre los autotests; GitHub lo corre en cada cambio.

Un cambio de motor: de a uno, con comparación antes/después (y Fishtest si toca una regla de decisión), con el «hacelo» de Nicolás, y actualiza su huella en el mismo commit. Nunca se mezcla mudar con mejorar.

| Archivo | Motor | Qué hace |
|---|---|---|
| `motores/conciliador.py` | Conciliador | cruza factura · remito · ficha (C1/C4) |
| `motores/sales_engine.py` | Sales Engine | el único que decide el día |
| `motores/cinco_cosas.py` | Cinco cosas | vista del Sales Engine |
| `motores/stockfish_auditor.py` | Stockfish | historia de cada cuenta |
| `motores/stockfish_controles.py` | Controles de Stockfish | entrada y salida cierran |
| `motores/control_reportes.py` | Control de reportes | PASA/FALLA de un Excel/CSV de Finnegans antes de cargarlo |
| `motores/correr_dia.py` | Orquestador | una orden para la cadena del día, escritura validada, selector |
| `motores/inicio_loki.py` | Inicio | integridad, coherencia y resumen del día |
| `motores/banco_manos.py`, `motores/banco_montecarlo.py` | Banco de manos | se quedan hasta que Fishtest decida |
| `motores/archivo/stockfish_v1.py` | Stockfish v1 | archivado: vuelve solo si gana en Fishtest |

Pendientes de mudar (paso 3a del boceto): cotizador y Diseño V8 del PM, cada uno con su foto de oro antes.

## Foto de oro

La salida completa de la cadena del 13/11 (la que dio todo PASA) está en el datacenter: `respaldo_2026-11-14_oro_motores_1..3`. El sistema nuevo, con las mismas entradas, tiene que dar lo mismo campo por campo.

# Fase 2: correcciones de seguridad y validación

Esta etapa corrige los dos pendientes operativos de la segunda revisión del PR #1. No ejecuta exportaciones de Earth Engine, no entrena modelos ni da por aprobada la definición de bosque o el protocolo espacial.

## Organización del trabajo

- **Base:** commit `211320d3496930bfa0d647c966196a5a7d3bd7fc` del PR #1.
- **Rama separada:** `fix/fase2-salida-segura`, para no editar simultáneamente la rama de Anahi.
- **Primer commit:** `47b9669`, conservación de la salida anterior, protección de rutas, bloqueo y pruebas de regresión.
- **Segundo commit:** `c7a7719`, rechazo de dataset vacío, splits incompletos, parámetros inválidos e índices duplicados, con pruebas.
- **Tercer commit:** documentación del comportamiento y los límites pendientes. No reescribe los commits anteriores.

## Comportamiento corregido

### Conservar la corrida anterior

Los parches nuevos se escriben en un temporal hermano del destino. Ante una etiqueta ausente, un manifiesto incompleto, un error de lectura/cálculo/escritura o una validación fallida, la salida anterior no se reemplaza.

Si la generación termina bien, se renombra la salida anterior a un respaldo y se publica la nueva. Un fallo ordinario de publicación restaura la salida anterior; si la restauración también falla, el respaldo queda conservado y el error informa su ruta.

Se rechazan rutas de salida que interfieran con las entradas, raíces sensibles, enlaces simbólicos y carpetas con archivos ajenos. Un bloqueo evita que dos invocaciones de este script escriban simultáneamente el mismo destino; no protege de modificaciones manuales externas.

### No publicar datasets inutilizables

Después de descartar parches se comprueba que existan muestras, que train/val/test estén representados y que no haya IDs duplicados ni diferencias entre el índice y los archivos. La presencia de bloques asignados antes del descarte ya no se confunde con disponibilidad efectiva de muestras.

Los tamaños deben ser positivos y el bloque múltiplo del parche. `min-useful` debe ser mayor que cero y menor o igual que uno, para impedir aceptar parches enteramente ignorados.

La falta de pérdida en test se informa como limitación; no se exige una cantidad positiva ni se recomienda buscar una semilla según el rendimiento. Una partición válida estructuralmente todavía puede ser insuficiente para evaluar detección de pérdida.

## Verificación reproducible

En un entorno Python 3.12 con `requirements.txt`, desde la raíz de la rama:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/check_repository.py
```

En Linux, usar `.venv/bin/python` en ambos comandos. Las pruebas no requieren red, GEE, GPU ni los TIFF reales; generan entradas sintéticas en directorios temporales.

La ejecución local completa dio 55 pruebas aprobadas, frente a las 31 de la base. Se observaron avisos de deprecación de Rasterio, no fallos; estos tiempos de pruebas no son mediciones de inferencia.

Los casos incorporados verifican:

- Conservación byte a byte de la salida ante etiqueta ausente, manifiesto incompleto y fallo durante la segunda escritura.
- Rechazo de rutas peligrosas o ajenas, manejo de carpetas vacías y bloqueo de otra corrida.
- Rechazo de enlaces simbólicos; este caso puede omitirse en Windows si el sistema no permite crearlos.
- Restauración ante fallo de publicación y conservación del respaldo si también falla la restauración.
- Dataset vacío o sin test, tanto desde cero como al reemplazar un dataset previo.
- Parámetros inválidos y repetición de zonas sin publicar un índice duplicado.

Se mantiene la prueba anterior que regenera con otra semilla y exige correspondencia entre archivos e índice. No se afirmó haber probado la ejecución en la laptop Windows: debe comprobarse allí antes de la demo.

## Límites y siguiente paso

La publicación usa dos renombrados en el mismo disco y no promete atomicidad ante apagados abruptos. Hay que conservar espacio para la salida anterior y la nueva; si hay una interrupción forzada, revisar bloqueo, temporales y respaldo manualmente antes de limpiarlos.

Siguen pendientes la exportación autenticada y auditoría de MapBiomas, decisión de clases, separación espacial, corrección de observabilidad del baseline exploratorio y evaluación con datos reales. Estas correcciones no cambian A/B, C en reserva ni la prioridad de la demo histórica offline.

La siguiente decisión es revisar e integrar estos commits en la rama del PR #1 y repetir CI. Fusionar con `main` o pasar a la exportación de etiquetas requiere confirmación del equipo; no forma parte de esta etapa.

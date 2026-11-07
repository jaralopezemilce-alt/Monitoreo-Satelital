# Guía de la fase 2: dataset de entrenamiento

Objetivo: unir las imágenes ya preparadas en la ingesta con las etiquetas de MapBiomas y obtener parches para entrenar y evaluar la U-Net con una partición reproducible. La independencia espacial entre splits todavía requiere definir y verificar una separación adicional.

## Idea general

```text
Ingesta (ya hecha, Emilce)                  Etiquetas (Earth Engine)
data/interim/historical-inputs-v1/          fase2_export_mapbiomas.py  (o export_mapbiomas_pilot.js)
  <zona>/<fecha>/stack.tif  (B02..NDVI)       -> data/interim/labels-mapbiomas-v1/
  <zona>/<fecha>/valid.tif                       <zona>_mapbiomas_c5_v2_<año>.tif  (30 m, nodata 255)
              \                                 /
               └──────── fase2_make_patches.py ┘
                                 │
           data/processed/dataset-v1/patches/*.npz  +  index.csv (split)  +  config.json (auditoría)
```

Zonas activas: A_boqueron (EPSG:32720) y B_alto_paraguay (EPSG:32721), cada una de 10 × 10 km (1000 × 1000 px de 10 m), definidas en `configs/training_zones.geojson`. Fechas históricas: A 21/10/2022 y 21/09/2023; B 01/10/2022 y 16/09/2023.

## Paso 1: exportar las etiquetas

Opción Python, sin Drive (requiere `requirements-gee.txt` y `GEE_PROJECT`):

```powershell
.\.venv\Scripts\python.exe scripts/fase2_export_mapbiomas.py
```

Usa la misma grilla que `scripts/export_mapbiomas_pilot.js`: origen de la grilla Sentinel, píxel de 30 m, clases originales y nodata 255. Imprime el histograma de clases por zona y año, avisa si aparecen códigos no listados y escribe `manifests/mapbiomas-labels-v1.json` con SHA-256. El manifiesto se versiona; los TIFF no.

La opción del Code Editor (`docs/mapbiomas-export.md`) sigue siendo válida: produce los mismos nombres de archivo, que hay que copiar a `data/interim/labels-mapbiomas-v1/`.

## Paso 2: definición de bosque (decisión del equipo)

En `src/chaco_monitor/labels.py`:

| Etiqueta | Códigos MapBiomas | Justificación |
|---|---|---|
| **Bosque (1)** | 3 leñosas cerradas (≥ 65 %), 4 leñosas abiertas (20–65 %), 6 leñosas inundables | Vegetación leñosa natural con cobertura suficiente |
| **No bosque (0)** | Sólo los de `NON_FOREST_CODES`: pastura 15, agricultura 18/19, pastizales 12/42/43/44, agua 26/33, plantación 9… | Lista explícita |
| **Ignorar (255)** | 45 leñosas dispersas, 0 y 27 no observado, **255 nodata**, cualquier código no listado, píxeles con `valid.tif = 0` o stack −9999 | Un píxel sin dato nunca se cuenta como no bosque |

**Pérdida** = bosque en 2022 y no bosque en 2023. La regeneración no cuenta como pérdida. Si cualquiera de las dos fechas es "ignorar", el píxel se ignora.

## Paso 3: cortar parches con partición espacial

```powershell
.\.venv\Scripts\python.exe scripts/fase2_make_patches.py
```

- Las etiquetas de 30 m se remuestrean a la grilla de 10 m por vecino más cercano; lo que no cubren queda en 255.
- Cada zona se divide en **bloques de 256 × 256 px** (2,56 km). Cada bloque va entero a train, val o test (≈ 70/15/15, semilla 42), con al menos un bloque de val y uno de test por zona.
- Dentro de cada bloque se cortan 4 parches de **128 × 128 px** que nunca cruzan el borde del bloque.
- Se descartan parches con menos del 80 % de píxeles útiles.
- Cada parche se guarda una sola vez en `patches/`; el split vive sólo en `index.csv`. Si la carpeta ya tiene un dataset, el script se detiene sin `--overwrite`. Con esa opción genera y valida la nueva corrida en un temporal del mismo disco y recién entonces reemplaza la anterior; no borra primero.
- Se rechazan salidas solapadas con imágenes o etiquetas, raíces sensibles, enlaces simbólicos y carpetas con archivos ajenos al formato `index.csv`, `config.json`, `patches/`. No agregar archivos personales dentro de la carpeta del dataset.
- La salida se publica solo si tiene muestras en train, val y test después de los descartes, sin IDs duplicados y con correspondencia entre índice y archivos. Si no hay parches o falta un split, el proceso termina con error y conserva la salida anterior.
- `config.json` guarda los parámetros, el resumen por split y una auditoría por zona: % de bosque por año, % ignorado, hectáreas de pérdida según MapBiomas y códigos desconocidos.

Orden de magnitud: 1000 px → 3 × 3 bloques → 36 parches por zona, unos 72 pares para A y B antes de descartes. Es poco: el entrenamiento usará aumentación (rotaciones y espejados).

## Qué revisar antes de congelar el dataset v1

1. `unknown_codes` vacío en el manifiesto y en `config.json`; si no, decidir esos códigos y actualizar `labels.py`.
2. Revisar cantidades y clases de cada split. Si test no tiene pérdida, documentar la limitación y definir un criterio de partición o estratificación antes de entrenar; no elegir semillas según el rendimiento del modelo ni prometer pérdida positiva.
3. Superponer `mb_code` sobre el RGB en QGIS para 5–10 parches: ¿MapBiomas coincide con lo que se ve en esa fecha?
4. Referencia manual de test, separada de las pseudoetiquetas, según el plan.

## Limitaciones a declarar en el informe

- MapBiomas es un mapa anual de 30 m (Random Forest sobre Landsat): son **pseudoetiquetas**, no verdad de terreno.
- Desfase temporal: la etiqueta anual puede no coincidir con la fecha exacta de la escena Sentinel.
- El remuestreo de 30 m a 10 m produce bordes escalonados; no agrega detalle real.
- Los bloques contiguos pueden pertenecer a splits distintos. No se ha implementado una franja de separación ni demostrado independencia espacial.
- La fase 1 permanece exploratoria: su tratamiento de observaciones inválidas sigue pendiente y no debe usarse aún como estimación validada.

## Regeneración segura y recuperación

```powershell
.\.venv\Scripts\python.exe scripts/fase2_make_patches.py --overwrite
.\.venv\Scripts\python.exe -m pytest -q
```

La semilla predeterminada sigue siendo 42 y se conserva en `config.json`. La validación de salida no demuestra que las etiquetas sean correctas: sigue siendo necesaria la auditoría visual y metodológica.

Se necesita espacio libre para conservar el dataset anterior y construir el nuevo. Un archivo hermano `.dataset-v1.lock` bloquea escritores simultáneos; no eliminarlo mientras exista una ejecución activa.

Ante un cierre forzado o un corte de energía, pueden quedar temporales `.dataset-v1.staging-*`, un respaldo `.dataset-v1.backup-*` o el bloqueo. Los dos renombrados no son una transacción atómica ante un corte de energía: detener procesos, comprobar qué salida es completa y recuperar el respaldo si corresponde antes de limpiar. No borrar automáticamente un respaldo ni una carpeta ajena.

Consultar `docs/fase2-correcciones.md` para los casos de prueba y el alcance de esta etapa.

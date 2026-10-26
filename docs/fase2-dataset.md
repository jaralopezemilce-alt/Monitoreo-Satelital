# Guía de la fase 2: dataset de entrenamiento

Objetivo: obtener parches de imágenes **con su etiqueta** (bosque/no bosque y pérdida) para entrenar y evaluar la U-Net sin hacer trampa.

## Idea general

```text
Earth Engine                         Computadora local (sin internet)
-------------                         --------------------------------
Sentinel-2 2022 (jul-oct) ┐
Sentinel-2 2023 (jul-oct) ├─► fase2_export_gee.py ─► data/interim/gee/<zona>_<año>.tif
MapBiomas Chaco 2022/2023 ┘                                   │
                                                              ▼
                                                fase2_make_patches.py
                                                              │
                                    data/processed/patches/{train,val,test}/*.npz + index.csv
```

## Por qué 2022/2023 y no 2025/2026

Las etiquetas de MapBiomas Chaco Colección 5 llegan hasta **2023**. El modelo se entrena con años que tienen etiqueta (experimento histórico) y después se **aplica** a 2025/2026 en la demo. No se presenta el caso histórico como si fuera de los últimos meses.

## Paso 1: exportar desde Earth Engine

```powershell
.\.venv\Scripts\python.exe scripts/fase2_export_gee.py --zones A_boqueron B_alto_paraguay C_presidente_hayes
```

Por cada zona arma una **ventana de 10 × 10 km** centrada en la candidata (más datos que el recorte de la demo) y descarga un GeoTIFF por año con 7 bandas en la misma grilla UTM de 10 m:

| Banda | Contenido |
|---|---|
| 1–4 | B2, B3, B4, B8 (reflectancia × 10000, nodata −9999) |
| 5 | NDVI × 10000 |
| 6 | `valid`: 1 si hubo observación sin nubes |
| 7 | `mb_code`: código original de MapBiomas |

También imprime qué clases de MapBiomas hay en cada ventana y actualiza `manifests/gee_exports.json` (tamaño, SHA-256, fechas, escenas, CRS). Ese manifiesto **sí** se sube a Git; los TIFF no.

A_boqueron se exporta en UTM 20S (EPSG:32720); B y C en UTM 21S (EPSG:32721), porque quedan al este del meridiano −60°.

## Paso 2: definición de bosque (decisión del equipo)

En `src/chaco_monitor/labels.py`:

| Etiqueta | Códigos MapBiomas | Justificación |
|---|---|---|
| **Bosque (1)** | 3 leñosas cerradas (≥ 65 %), 4 leñosas abiertas (20–65 %), 6 leñosas inundables | Vegetación leñosa natural con cobertura suficiente |
| **Ignorar (255)** | 45 leñosas dispersas (5–20 %), 0 y 27 no observado, píxeles sin observación | Ambiguas: pueden ser pastura con árboles o bosque ralo |
| **No bosque (0)** | Todo lo demás: pastura 15, agricultura 18/19, pastizal 12, agua 26/33… | — |

**Pérdida (cambio)** = bosque en 2022 y no bosque en 2023. La regeneración no cuenta como pérdida. Si cualquiera de las dos fechas es "ignorar", el píxel se ignora en entrenamiento y métricas.

Para cambiar la definición, editar `FOREST_CODES` / `IGNORE_CODES`; las pruebas de `tests/test_fase2.py` muestran el efecto esperado.

## Paso 3: cortar parches con partición espacial

```powershell
.\.venv\Scripts\python.exe scripts/fase2_make_patches.py --zones A_boqueron B_alto_paraguay C_presidente_hayes
```

- Cada ventana se divide en **bloques de 256 × 256 px** (2,56 km). Cada bloque va entero a train, val o test (≈ 70/15/15, semilla 42), y siempre hay al menos un bloque de val y uno de test por zona.
- Dentro de cada bloque se cortan 4 parches de **128 × 128 px**. Un parche nunca cruza el borde de un bloque, así que parches vecinos casi idénticos no aparecen en train y test a la vez (fuga de datos).
- Se descartan parches con menos del 80 % de píxeles útiles (nubes o clases ignoradas).
- Cada `.npz` contiene `x_t1`, `x_t2` (5 canales: B2, B3, B4, B8, NDVI), `y_t1`, `y_t2` y `change`.

Orden de magnitud: una ventana de 10 km tiene unos 1000 × 1000 px → 3 × 3 bloques → 36 parches por zona, y unos 108 pares de fechas para las 3 zonas antes de descartes. Es poco: la siguiente fase usa aumentación (rotaciones y espejados) y, si hace falta, `--window-km 12` o más zonas.

## Qué revisar antes de congelar el dataset v1

1. Porcentaje de píxeles válidos por zona y año (manifiesto); repetir con otra ventana estacional si es bajo.
2. Proporción de bosque y de pérdida por split (resumen del script e `index.csv`): **test debe tener píxeles de pérdida**.
3. Superposición visual de `mb_code` sobre el RGB en QGIS para 5–10 parches: ¿MapBiomas coincide con lo que se ve?
4. Referencia manual de test: según el plan, el test se revisa a mano y no depende solo de MapBiomas.

## Limitaciones a declarar en el informe

- MapBiomas es un mapa anual a 30 m clasificado con Random Forest sobre Landsat: son **pseudoetiquetas**, no verdad de terreno.
- Desfase temporal: la etiqueta anual puede no coincidir con la mediana de julio a octubre.
- La resolución 30 m → 10 m (vecino más cercano) produce bordes escalonados.

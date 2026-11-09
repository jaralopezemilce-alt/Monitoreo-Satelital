# Resultados (conjunto de prueba)

Datos reales; nada simulado. Conjunto de **prueba**: 8 parches de 128 × 128 px (4 de Boquerón y 4 de Alto Paraguay), **131 072 píxeles**, todos observables (0 píxeles 255). Clase positiva: **pérdida de cobertura boscosa** (bosque 2022 → no bosque 2023, MapBiomas Chaco Col. 5, clases 3/4/6). Métricas por píxel de la clase positiva.

Época (mejor IoU de validación) y umbral (mejor F1 de validación) se eligieron **sólo con validación**. El modelo desplegado (API y visor) es la **semilla 42**, fijada antes de evaluar en prueba.

## Métricas

| Método | Umbral | IoU | F1 | Precisión | Recall | Accuracy |
|---|---|---|---|---|---|---|
| **U-Net semilla 42 (desplegado)** | 0,50 | **0,6632** | **0,7975** | 0,8107 | 0,7848 | 0,8110 |
| U-Net semilla 1 | 0,50 | 0,6864 | 0,8140 | 0,8084 | 0,8197 | 0,8223 |
| U-Net semilla 2 | 0,45 | 0,6885 | 0,8155 | 0,8375 | 0,7947 | 0,8295 |
| U-Net, media ± desvío (3 semillas) | – | 0,679 ± 0,014 | 0,809 ± 0,010 | 0,819 ± 0,016 | 0,800 ± 0,018 | 0,821 ± 0,009 |
| Línea base dNDVI (NDVI₂₀₂₃ − NDVI₂₀₂₂ < umbral) | −0,125 | 0,5783 | 0,7329 | 0,8162 | 0,6649 | 0,7701 |

La media ± desvío describe la variabilidad entre tres ejecuciones sobre el **mismo** conjunto de prueba, no tres conjuntos independientes.

## Matrices de confusión (píxeles)

| Método | TP | FP | FN | TN |
|---|---|---|---|---|
| U-Net semilla 42 | 48 788 | 11 392 | 13 381 | 57 511 |
| U-Net semilla 1 | 50 960 | 12 077 | 11 209 | 56 826 |
| U-Net semilla 2 | 49 407 | 9 588 | 12 762 | 59 315 |
| dNDVI | 41 338 | 9 307 | 20 831 | 59 596 |

Pérdida de referencia en prueba: TP + FN = 62 169 px = **621,7 ha**. Predicción de la semilla 42: 601,8 ha; dNDVI: 506,5 ha (1 px = 100 m²).

Reproducir: `python scripts/fase3_confusion.py` (escribe `outputs/fase3_confusion_test.json`).

## Tiempo de inferencia

Medición informal, **una repetición**, notebook sin GPU: **0,26 s** para un área de 3,36 km² vía `POST /predict`. Incluye lectura de rasters locales, preprocesamiento, inferencia U-Net y vectorización; no incluye descarga (datos locales) ni el navegador. Pendiente: medición con repeticiones.

## Limitaciones

- Referencia = pseudoetiqueta MapBiomas (anual, origen Landsat 30 m), no verdad de terreno.
- 2 zonas, 1 par de fechas, 72 parches; proporción de pérdida 25 % / 39 % / 47 % en train / val / test.
- Sin franja de separación entre bloques vecinos; los parches cubren el 59 % de cada zona.
- La salida es **pérdida estimada de cobertura boscosa**, no desmonte confirmado ni atribución de causa.

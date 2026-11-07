# Fase 3: entrenamiento y evaluación

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-train.txt
.\.venv\Scripts\python.exe scripts/fase3_train.py
```

Requiere `data/processed/dataset-v1` (fase 2). Tarda unos minutos en CPU.

## Qué hace

1. Carga los parches de `train` y `val`. Cada parche tiene 10 canales: B02, B03, B04, B08 y NDVI de 2022, más los mismos de 2023.
2. Entrena una U-Net chica (`src/chaco_monitor/model.py`, ~0,5 M parámetros, escrita sin librerías extra) con BCE + Dice. Los píxeles 255 se ignoran. Aumentación: rotaciones de 90° y espejado.
3. Guarda el epoch con mejor IoU en validación.
4. Con validación elige el umbral de la U-Net y el de la línea base dNDVI (NDVI 2023 − NDVI 2022).
5. Mide **una sola vez** en `test` las dos opciones y escribe `outputs/fase3/metrics.json`.

## Salidas

| Archivo | Contenido | ¿Git? |
|---|---|---|
| `models/unet-v1.pt` | Pesos, umbral y orden de bandas | No (Drive) |
| `outputs/fase3/training_log.csv` | Pérdida y métricas de validación por epoch | No |
| `outputs/fase3/metrics.json` | IoU, F1, precisión, recall y hectáreas en test: U-Net vs dNDVI | No; se copia al informe |

## Cómo leer las métricas

- **IoU / F1 de la clase pérdida**: las métricas principales del informe.
- **Precisión**: de lo que el modelo marca en rojo, cuánto es pérdida según MapBiomas.
- **Recall**: de la pérdida de MapBiomas, cuánta encuentra el modelo.
- **ha pred / ha ref**: hectáreas marcadas frente a hectáreas de referencia en test.

Las referencias son pseudoetiquetas MapBiomas (30 m), así que las métricas miden el acuerdo con MapBiomas, no con la verdad de terreno. Con 8 parches de test, los números tienen mucha varianza.

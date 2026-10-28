# API REST (FastAPI)

Inferencia real de la U-Net, en CPU y sin internet, sobre las zonas precargadas A_boqueron y B_alto_paraguay.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-api.txt
.\.venv\Scripts\python.exe -m uvicorn api.main:app --port 8000
```

Abrir http://127.0.0.1:8000/docs para probar cada endpoint desde el navegador.

Necesita en disco `data/interim/historical-inputs-v1/` (de `prepare_pilot.py`) y `models/unet-v1.pt` (de `fase3_train.py`). Si también existe `data/interim/labels-mapbiomas-v1/`, cada respuesta incluye la referencia de MapBiomas.

## Endpoints

| Método | Ruta | Qué devuelve |
|---|---|---|
| GET | `/health` | Si están la ingesta, el modelo y las etiquetas |
| GET | `/zones` | Zonas, límites en lon/lat y fechas de las escenas |
| GET | `/zones/{zona}/rgb/{rol}.png` | Fondo color verdadero en lon/lat; los límites van en el header `X-Bounds` |
| POST | `/predict` | Pérdida de bosque en el área pedida |

Ejemplo de `/predict`:

```json
{"zone": "A_boqueron", "bbox": [-60.62, -21.84, -60.60, -21.825]}
```

Responde con hectáreas de pérdida, % de píxeles válidos, fechas reales de adquisición, tiempo de inferencia, `loss_geojson` (polígonos rojos para el mapa), `no_observable_geojson` (nubes o sin dato) y, si hay etiquetas, la pérdida según MapBiomas en la misma área.

## Reglas

- Área máxima por pedido: 4 km² (variable `CHACO_MAX_AREA_KM2`).
- Fuera de la zona, zona o par desconocido, o bbox mal formado: error 404/422 con explicación. Nunca procesa otra zona sin avisar.
- Sin píxeles válidos en las dos fechas: error "no evaluable", nunca "0 ha".
- El umbral es el elegido con validación durante el entrenamiento (guardado en el `.pt`).
- El modelo lee 32 píxeles extra alrededor del área para que los bordes tengan contexto.
- Advertencia para la demo: el área elegida puede caer en bloques de entrenamiento. Para mostrar la capacidad real, conviene elegir áreas de los bloques de test (ver `data/processed/dataset-v1/index.csv`).

# Visor web

Página que muestra una zona del Chaco, deja dibujar un rectángulo y pinta en rojo
la pérdida de bosque que detecta la U-Net. La sirve la misma API (FastAPI), así que
no hace falta un servidor aparte ni internet.

## Cómo abrirlo

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-api.txt   # una sola vez
.\.venv\Scripts\python.exe -m uvicorn api.main:app --port 8000
```

Abrir <http://127.0.0.1:8000/> (redirige a `/visor/`).

Necesita en disco: `data/interim/historical-inputs-v1`, `data/interim/labels-mapbiomas-v1`,
`data/processed/dataset-v1` (solo para dibujar los bloques) y `models/unet-v1.pt`.

## Uso

1. Elegir zona (A · Boquerón o B · Alto Paraguay).
2. Alternar fondo **Antes / Después** para ver el cambio a ojo.
3. **Dibujar área a analizar** y arrastrar un rectángulo (máximo 4 km²; Esc cancela).
4. Aparece en rojo la pérdida detectada, en gris lo no observable (nubes / sin dato),
   y en el panel: hectáreas, hectáreas según MapBiomas, acuerdo y tiempo.

Los bloques con borde **amarillo punteado** son los de prueba (test): el modelo no los
vio al entrenar. Para la demo conviene dibujar dentro de ellos; fuera de ellos el
acuerdo con MapBiomas sale inflado porque el modelo ya conoce esas zonas.

## Archivos

| Archivo | Qué hace |
|---|---|
| `index.html` | Estructura de la página |
| `styles.css` | Colores y diseño (también para celular) |
| `app.js` | Mapa, dibujo del rectángulo, llamada a `/predict` y panel de resultados |
| `vendor/leaflet/` | Leaflet 1.9.4 copiado localmente (licencia BSD-2) para funcionar offline |

El fondo no usa teselas de internet: es la imagen Sentinel-2 RGB que entrega
`GET /zones/{zona}/rgb`. Los bloques salen de `GET /zones/{zona}/splits`.

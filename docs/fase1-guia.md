# Guía de la fase 1: NDVI entre dos fechas y baseline de pérdida

Esta guía es para que **las dos integrantes** puedan ejecutar, entender y explicar la fase 1 en la defensa.

## Qué hace el script

`scripts/fase1_ndvi_baseline.py` responde una pregunta simple: *¿dónde había vegetación densa en una fecha y ya no la hay en la otra?*

1. **Conexión:** se conecta a Google Earth Engine (GEE), que procesa las imágenes en la nube; no hace falta bajar escenas completas.
2. **Imagen sin nubes:** para cada período (T1 y T2) junta todas las escenas Sentinel-2 L2A, quita nubes con Cloud Score+ (píxel válido si `cs_cdf >= 0,60`) y calcula la **mediana** de cada píxel.
3. **NDVI:** `NDVI = (NIR - Rojo) / (NIR + Rojo) = (B8 - B4) / (B8 + B4)`. Bosque denso ≈ 0,6–0,9; pastura seca o suelo desnudo ≈ 0,1–0,4.
4. **Cambio:** `dNDVI = NDVI_T2 - NDVI_T1`. Negativo = la vegetación bajó.
5. **Regla de pérdida (baseline):** se marca en rojo si `NDVI_T1 > 0,55`, `dNDVI < -0,25` y `NDVI_T2 < 0,40`, y si el parche tiene al menos 50 píxeles (0,5 ha).
6. **Salidas:** hectáreas, GeoTIFF en UTM (para medir en metros) y un mapa HTML con capas.

Esta regla es la **baseline**: el informe IEEE comparará la U-Net contra ella. No es una estimación validada.

### Por qué T1 y T2 en la misma estación

El bosque chaqueño es semicaducifolio: en invierno pierde hojas y su NDVI baja sin que haya desmonte. Comparar mayo contra septiembre puede confundir fenología con deforestación. Por eso los valores por defecto son junio–septiembre de 2025 contra junio–septiembre de 2026.

## Preparación (una sola vez por computadora)

```powershell
git clone https://github.com/jaralopezemilce-alt/Monitoreo-Satelital.git
cd Monitoreo-Satelital
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-gee.txt
.\.venv\Scripts\earthengine.exe authenticate
setx GEE_PROJECT "id-del-proyecto-compartido"
```

Después de `setx`, cerrar y volver a abrir la terminal de VS Code. Las dos integrantes usan el **mismo** Project ID; cada una se autentica con su propia cuenta de Google, que debe tener acceso al proyecto (IAM: *Service Usage Consumer* y *Earth Engine Resource Writer*).

## Ejecución

```powershell
.\.venv\Scripts\python.exe scripts/fase1_ndvi_baseline.py --zone A_boqueron
.\.venv\Scripts\python.exe scripts/fase1_ndvi_baseline.py --zone B_alto_paraguay
.\.venv\Scripts\python.exe scripts/fase1_ndvi_baseline.py --zone C_presidente_hayes
```

Opciones útiles: `--t1 2025-06-01 2025-09-30 --t2 2026-06-01 2026-09-30`, `--bbox OESTE SUR ESTE NORTE` para otra área y `--no-download` para obtener solo números y mapa.

Resultados en `outputs/fase1/<zona>/`: `stats.json`, `mapa.html`, `ndvi_T1_T2_dNDVI.tif` y `mask_perdida_baseline.tif`. Esa carpeta no se sube a Git.

## Cómo revisar el mapa

Abrir `mapa.html` y alternar **RGB T1** y **RGB T2** con la capa roja activa. Un desmonte real suele tener bordes rectos y suelo claro en T2. Anotar falsos positivos (caminos, lagunas secas, pasturas previas) y desmontes omitidos.

## Corrida exploratoria registrada (26 oct 2026)

Primera prueba con el script original, en un rectángulo **adyacente** a la candidata A, no dentro de ella: bbox `[-60.72, -21.95, -60.60, -21.85]`, UTM 20S.

| Dato | Valor |
|---|---|
| Escenas T1 (jun–sep 2025) / T2 (jun–sep 2026) | 15 / 16 |
| Área analizada | 13.766,5 ha |
| Pérdida baseline | 196,9 ha (1,4 %) |
| NDVI medio T1 → T2 | 0,567 → 0,504 |
| dNDVI mín / medio / máx | −0,714 / −0,063 / 0,676 |
| Píxeles válidos | 97,0 % (los faltantes son bordes de la reproyección a UTM) |

Pendiente: repetir en las zonas candidatas con este script y revisar visualmente las zonas rojas antes de usar la cifra en el informe.

## Errores comunes

| Error | Causa y solución |
|---|---|
| `Falta GEE_PROJECT` | Ejecutar `setx GEE_PROJECT "..."` y reabrir la terminal |
| `Caller does not have required permission` | Project ID incorrecto o cuenta sin rol IAM en el proyecto |
| `Sin escenas Sentinel-2` | Ampliar las fechas |
| `Total request size ... must be less than` | Área demasiado grande para descarga directa; achicar la bbox |

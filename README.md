# Monitoreo Satelital del Chaco Paraguayo

Proyecto académico de segmentación bosque/no bosque y detección de pérdida de cobertura entre fechas. Entrega prevista: **9 de noviembre de 2026**; equipo de dos integrantes, presupuesto cero, entrenamiento en GPU gratuita y demo con inferencia en CPU.

## Estado real (8/11/2026)

**Sistema completo y funcionando**, con datos reales y sin resultados simulados:

| Componente | Estado | Dónde |
|---|---|---|
| Ingesta Sentinel-2 L2A, zonas A (Boquerón) y B (Alto Paraguay), 2022→2023 | Listo | `scripts/prepare_pilot.py`, `manifests/` |
| Etiquetas MapBiomas Chaco Col. 5 (bosque = clases 3, 4, 6) | Listo | `scripts/fase2_export_mapbiomas.py`, `manifests/mapbiomas-labels-v1.json` |
| Dataset de parches 128×128 con partición espacial por bloques | Listo | `scripts/fase2_make_patches.py`, `docs/fase2-dataset.md` |
| U-Net (10 canales) + línea base dNDVI, 3 semillas | Listo | `scripts/fase3_train.py`, `docs/fase3-entrenamiento.md` |
| Métricas de prueba y matrices de confusión | Listo | **`docs/resultados.md`** |
| API REST (FastAPI) con inferencia real | Listo | `api/`, `api/README.md` |
| Visor web (Leaflet, offline) | Listo | `web/`, `web/README.md` |
| Docker (extra) | Listo | `Dockerfile`, `docker-compose.yml`, `docs/docker.md` |

Resultado principal en prueba (modelo desplegado, semilla 42): **IoU 0,663 · F1 0,797** frente a IoU 0,578 · F1 0,733 de la línea base dNDVI. Detalle en `docs/resultados.md`.

## Cómo ejecutar el visor

Requiere en disco `data/interim/historical-inputs-v1`, `data/interim/labels-mapbiomas-v1`, `data/processed/dataset-v1` y `models/unet-v1.pt` (no están en Git; ver "Datos, licencias y pesos").

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-api.txt   # una vez
.\.venv\Scripts\python.exe -m uvicorn api.main:app --port 8000
```

o con Docker: `docker compose up --build`. Abrir <http://127.0.0.1:8000/>, elegir zona, **Dibujar área a analizar** (≤ 4 km²) dentro de un bloque de prueba (borde amarillo). La pérdida detectada aparece en rojo, lo no observable en gris. Swagger de la API: <http://127.0.0.1:8000/docs>.

## Objetivo y alcance

- Demo principal con el par histórico 2022/2023, dentro de A/B y con datos locales.
- Par reciente de mayo/septiembre de 2026 como prueba de estabilidad y falsas alertas.
- Insumos históricos ampliados a 100 km² por zona para entrenamiento posterior.
- U-Net compacta con canales B2/B3/B4/B8/NDVI y baseline de umbral NDVI.
- FastAPI e interfaz local; ejecución en CPU y medición de latencia real.
- Inferencia en vivo sobre datos preparados, no reproducción de resultados fijos.
- Modo online opcional con área limitada, timeout y retorno explícito al modo offline.
- Informe IEEE en español, exactamente tres páginas incluyendo referencias; defensa de diez minutos y dos de preguntas.

La salida será **pérdida de bosque estimada**, no una certificación legal ni una atribución de causa. Las nubes, sombras y píxeles ambiguos se excluirán; no se contabilizarán como no bosque.

## Estructura

```text
.github/workflows/       Pruebas automáticas
api/                    FastAPI, pendiente
configs/                Zonas y configuración de ejecución
data/
  raw/                  Datos originales, fuera de Git
  interim/              Intermedios, fuera de Git
  processed/            Dataset final, fuera de Git
docs/                   Plan, fuentes, diseño y revisión
docs/evidence/          Miniaturas y tablas pequeñas de prospección
manifests/              Metadatos, URLs y checksums
models/                 Pesos, fuera de Git
notebooks/              Entrenamiento Colab/Kaggle, pendiente
outputs/                Resultados de ejecuciones, fuera de Git
scripts/                Prospección y controles del repositorio
src/chaco_monitor/      Funciones reutilizables
tests/                  Pruebas
web/                    Visor, pendiente
```

## Instalación en Windows 11

Usar Python 3.12 de 64 bits y Git. Estos comandos se ejecutan desde PowerShell en la raíz del repositorio y no requieren activar scripts de PowerShell:

```powershell
git clone https://github.com/jaralopezemilce-alt/Monitoreo-Satelital.git
cd Monitoreo-Satelital
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
```

El repositorio es privado: la segunda integrante necesita una invitación del propietario. No colocar tokens en archivos ni comandos versionados.

En Linux/macOS:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pytest -q
```

## Scripts de Earth Engine (fases 1 y 2)

Requieren `requirements-gee.txt`, `earthengine authenticate` y la variable `GEE_PROJECT` con el ID del proyecto compartido:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-gee.txt
.\.venv\Scripts\earthengine.exe authenticate
setx GEE_PROJECT "proyecto-deforestacion-510013"   # reabrir la terminal después
.\.venv\Scripts\python.exe scripts/fase1_ndvi_baseline.py --zone A_boqueron
.\.venv\Scripts\python.exe scripts/fase2_export_mapbiomas.py
.\.venv\Scripts\python.exe scripts/fase2_make_patches.py
```

## Reproducir la prospección

La primera ejecución requiere internet y descarga dos tiles comprimidos de Hansen. No es necesaria para ejecutar las pruebas unitarias ni será parte del arranque de la demo.

```powershell
.\.venv\Scripts\python.exe scripts/scout_sources.py --cache data/raw/hansen --out outputs/prospection
.\.venv\Scripts\python.exe scripts/review_candidates.py --evidence outputs/prospection --raw data/raw/hansen --out outputs/review
```

Consultar `docs/evidence/selected_scenes.csv` para IDs, fechas, nubosidad de escena y calidad local por SCL. Los porcentajes locales son de una grilla reducida de inspección, no la evaluación final a resolución nativa.

## Reproducir o verificar la ingesta

La ingesta interpreta la radiometría según colección, alinea fechas a UTM de 10 m
y produce B02/B03/B04/B08/NDVI, SCL y máscara de observabilidad. Esa máscara
**no es bosque/no bosque** y no reemplaza las etiquetas.

```powershell
.\.venv\Scripts\python.exe scripts/prepare_pilot.py --out data/interim/pilot-v1
.\.venv\Scripts\python.exe scripts/prepare_pilot.py --zones configs/training_zones.geojson --historical-only --out data/interim/historical-inputs-v1
```

Los dos paquetes de datos se entregan como adjuntos de la conversación, fuera de Git.
Después de descomprimirlos dentro de `data/interim/`, estos controles no necesitan internet:

```powershell
.\.venv\Scripts\python.exe scripts/verify_ingestion.py data/interim/pilot-v1
.\.venv\Scripts\python.exe scripts/verify_ingestion.py data/interim/historical-inputs-v1
```

Para MapBiomas, seguir `docs/mapbiomas-export.md`; no se ha ejecutado una exportación
autenticada. Leer `docs/ingestion-stage-report.md` para resultados, limitaciones y
qué debe verificarse antes de la siguiente etapa.

## Datos, licencias y pesos

No se versionarán TIFF/JP2, pesos ni datos de entrenamiento. Se propone Drive o Kaggle para el paquete compartido; el proveedor, enlace y permisos definitivos están pendientes de acuerdo. El repositorio conservará manifiestos con nombre, tamaño, SHA-256, procedencia, licencia y versión.

No se activó Git LFS por defecto, para no introducir cuotas como dependencia del proyecto. Las miniaturas de evidencia son pequeñas; no sustituyen los originales.

Los datos Sentinel son abiertos y requieren atribución para sus derivados; la fórmula aplicable es “Contains modified Copernicus Sentinel data [Year]” ([aviso legal Copernicus](https://sentinels.copernicus.eu/documents/247904/690755/Sentinel_Data_Legal_Notice)). Hansen GFC 2025 v1.13 se distribuye bajo CC BY 4.0, con crédito Hansen/UMD/Google/USGS/NASA ([distribución](https://storage.googleapis.com/earthenginepartners-hansen/GFC-2025-v1.13/download.html)).

Las demás fuentes y el acceso pendiente a MapBiomas están documentados en `docs/sources.md`. No se concede aún una licencia pública al código: el repositorio sigue privado y esa decisión corresponde a sus autoras.

## Reproducibilidad y evaluación

- Semilla oficial 42, fijada antes de evaluar en prueba; semillas 1 y 2 para medir variabilidad.
- Partición espacial por bloques de 256 px antes de generar parches.
- Época (mejor IoU de validación) y umbral (mejor F1 de validación) elegidos sólo con validación.
- IoU, F1, precisión, recall, accuracy y matriz de confusión de la clase pérdida: `docs/resultados.md`.
- Tiempo de inferencia: medición informal en CPU (ver `docs/resultados.md`).
- Sin resultados simulados ni métricas inventadas.

**No realizado** (limitaciones declaradas): referencia visual manual de test, evaluación sobre el par 2026, IoU por clase/mIoU y medición de latencia con repeticiones.

## Cómo verificar el estado actual

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/check_repository.py
git log --oneline
```

Las pruebas (`tests/`) cubren coordenadas, radiometría, NDVI, máscaras, dataset, modelo, inferencia, API y servicio del visor. En CI se ejecutan las que no requieren PyTorch/FastAPI y además se construye la imagen Docker con una prueba de humo.

## Flujo de trabajo del equipo

Crear ramas cortas por tarea, commits pequeños y revisión cruzada. Ejemplos: `feat: validar area de consulta`, `test: cubrir bbox invalida`, `docs: registrar licencia Sentinel`.

No reescribir commits compartidos ni añadir resultados manuales como si fueran salidas del modelo. Cada fase termina con evidencia, instrucciones de verificación y aprobación antes de continuar.

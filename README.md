# Monitoreo Satelital del Chaco Paraguayo

Proyecto académico de segmentación bosque/no bosque y detección de pérdida de cobertura entre fechas. Entrega prevista: **9 de noviembre de 2026**; equipo de dos integrantes, presupuesto cero, entrenamiento en GPU gratuita y demo con inferencia en CPU.

## Estado real

**Fase 2 en curso: dataset.** Acceso a Earth Engine resuelto con un proyecto de Google Cloud compartido. Hay scripts para la baseline NDVI (`docs/fase1-guia.md`) y para exportar Sentinel-2 + MapBiomas y cortar parches con partición espacial (`docs/fase2-dataset.md`); la exportación real y su auditoría están pendientes.

**Fase 1: base del repositorio y prospección de fuentes.** Hay validaciones de bounding boxes, pruebas unitarias, scripts reproducibles de consulta y revisión de tres candidatas; todavía no hay dataset de entrenamiento, pesos entrenados, API ni visor implementados.

Los recortes de inspección no son el dataset final. Las fechas recientes tienen observaciones utilizables, pero la inspección inicial no confirma un desmonte nuevo inequívoco entre mayo y septiembre de 2026; no se presentará un cambio estacional como deforestación.

## Objetivo y alcance

- Dos zonas aprobadas, seleccionables en un mapa, con dos fechas recientes preparadas para el modo offline.
- Experimento histórico separado, compatible temporalmente con las etiquetas.
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
setx GEE_PROJECT "id-del-proyecto-compartido"   # reabrir la terminal después
.\.venv\Scripts\python.exe scripts/fase1_ndvi_baseline.py --zone A_boqueron
.\.venv\Scripts\python.exe scripts/fase2_export_gee.py --zones A_boqueron B_alto_paraguay C_presidente_hayes
.\.venv\Scripts\python.exe scripts/fase2_make_patches.py --zones A_boqueron B_alto_paraguay C_presidente_hayes
```

## Reproducir la prospección

La primera ejecución requiere internet y descarga dos tiles comprimidos de Hansen. No es necesaria para ejecutar las pruebas unitarias ni será parte del arranque de la demo.

```powershell
.\.venv\Scripts\python.exe scripts/scout_sources.py --cache data/raw/hansen --out outputs/prospection
.\.venv\Scripts\python.exe scripts/review_candidates.py --evidence outputs/prospection --raw data/raw/hansen --out outputs/review
```

Consultar `docs/evidence/selected_scenes.csv` para IDs, fechas, nubosidad de escena y calidad local por SCL. Los porcentajes locales son de una grilla reducida de inspección, no la evaluación final a resolución nativa.

## Datos, licencias y pesos

No se versionarán TIFF/JP2, pesos ni datos de entrenamiento. Se propone Drive o Kaggle para el paquete compartido; el proveedor, enlace y permisos definitivos están pendientes de acuerdo. El repositorio conservará manifiestos con nombre, tamaño, SHA-256, procedencia, licencia y versión.

No se activó Git LFS por defecto, para no introducir cuotas como dependencia del proyecto. Las miniaturas de evidencia son pequeñas; no sustituyen los originales.

Los datos Sentinel son abiertos y requieren atribución para sus derivados; la fórmula aplicable es “Contains modified Copernicus Sentinel data [Year]” ([aviso legal Copernicus](https://sentinels.copernicus.eu/documents/247904/690755/Sentinel_Data_Legal_Notice)). Hansen GFC 2025 v1.13 se distribuye bajo CC BY 4.0, con crédito Hansen/UMD/Google/USGS/NASA ([distribución](https://storage.googleapis.com/earthenginepartners-hansen/GFC-2025-v1.13/download.html)).

Las demás fuentes y el acceso pendiente a MapBiomas están documentados en `docs/sources.md`. No se concede aún una licencia pública al código: el repositorio sigue privado y esa decisión corresponde a sus autoras.

## Reproducibilidad y evaluación previstas

- Semilla inicial 42; configuración y particiones guardadas.
- Particiones espaciales antes de generar parches; todas las fechas de un bloque en el mismo conjunto.
- Referencia visual manual de test separada de las pseudoetiquetas de entrenamiento.
- IoU por clase/mIoU, F1, precision, recall, accuracy y matriz de confusión.
- Evaluación independiente de la máscara de cambio, no sólo de cada fecha.
- Tiempo de inferencia en CPU y latencia completa de API, medidos por separado.
- Sin resultados simulados ni métricas inventadas.

## Cómo verificar el estado actual

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/check_repository.py
git log --oneline
```

Las pruebas actuales validan coordenadas y límites de superficie; **no prueban todavía segmentación, inferencia, API ni interfaz**. Docker Compose y los comandos de entrenamiento se documentarán cuando esas fases estén implementadas y verificadas.

## Flujo de trabajo del equipo

Crear ramas cortas por tarea, commits pequeños y revisión cruzada. Ejemplos: `feat: validar area de consulta`, `test: cubrir bbox invalida`, `docs: registrar licencia Sentinel`.

No reescribir commits compartidos ni añadir resultados manuales como si fueran salidas del modelo. Cada fase termina con evidencia, instrucciones de verificación y aprobación antes de continuar.

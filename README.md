# Monitoreo Satelital del Chaco Paraguayo

Proyecto académico de detección de pérdida estimada de cobertura boscosa entre imágenes Sentinel-2 mediante una U-Net, una API REST y un visor geográfico web. Presentación: 9 de noviembre de 2026.

## Estado y alcance de la versión presentada

Prototipo funcional offline sobre dos zonas piloto: Boquerón y Alto Paraguay. La inferencia se ejecuta sobre el rectángulo seleccionado y datos locales preparados; no consiste en reproducir polígonos de resultado previamente guardados. No es un servicio de monitoreo de todo el Chaco ni de actualización automática.

| Componente | Implementación y evidencia |
|---|---|
| Imágenes | Sentinel-2 L2A, par histórico 2022–2023; scripts/prepare_pilot.py |
| Referencia | MapBiomas Chaco Colección 5, integración v2; manifiesto manifests/mapbiomas-labels-v1.json |
| Dataset | Parches de 128 × 128 píxeles y partición por bloques; docs/fase2-dataset.md |
| Modelo | U-Net de 10 canales: B2/B3/B4/B8/NDVI de cada fecha; tres semillas de entrenamiento |
| Comparación | Línea base dNDVI y métricas de prueba; docs/resultados.md |
| API | FastAPI, POST /predict; api/main.py |
| Interfaz | Leaflet, imágenes locales y resultados en rojo; web/ |
| Despliegue | Dockerfile y docker-compose.yml; requiere datos y pesos locales |

La salida es una estimación de pérdida de cobertura boscosa, no una certificación de deforestación, una atribución de causa ni un dictamen legal.

## Ejecutar el visor

Desde la raíz del repositorio, con el entorno virtual preparado:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-api.txt
.\.venv\Scripts\python.exe -m uvicorn api.main:app --port 8000
```

Abrir http://127.0.0.1:8000/. Documentación de la API: http://127.0.0.1:8000/docs.

El modelo requiere models/unet-v1.pt y la ingesta data/interim/historical-inputs-v1. Para mostrar la comparación con MapBiomas y los bloques del dataset también deben estar disponibles data/interim/labels-mapbiomas-v1 y data/processed/dataset-v1. Los archivos pesados no están incluidos en Git. Clonar el repositorio no basta para ejecutar la demo completa.

Alternativa con Docker, si ya está instalado y configurado:

```powershell
docker compose up --build
```

Docker monta data/ y models/ en solo lectura; no descarga automáticamente los insumos ni entrena el modelo.

## Uso y significado de los bloques amarillos

1. Elegir una zona piloto.
2. Comparar las imágenes antes/después.
3. Dibujar un rectángulo dentro de la cobertura precargada, de menos de 4 km² para evitar exceder el límite al ajustar a la grilla de píxeles.
4. El sistema ejecuta la predicción y muestra hectáreas estimadas, superficie observable y tiempo de procesamiento. Rojo: pérdida estimada. Gris: no observable.

El amarillo identifica bloques reservados para prueba. Se recomienda usarlos en la demostración para no presentar áreas de entrenamiento como evaluación independiente. No es una frontera de funcionamiento del modelo: el visor permite solicitar otras áreas dentro de la cobertura disponible y del límite de superficie. Fuera de las zonas precargadas la solicitud se rechaza por falta de cobertura de los insumos locales.

## Resultados documentados

| Método | IoU de pérdida | F1 de pérdida |
|---|---:|---:|
| U-Net desplegada, semilla 42 | 0,6632 | 0,7975 |
| Línea base dNDVI | 0,5783 | 0,7329 |

Prueba: ocho parches, 131 072 píxeles, sobre el par 2022–2023. La referencia son pseudoetiquetas MapBiomas, no observaciones de terreno. Época y umbral se seleccionaron con validación. Las semillas adicionales describen variabilidad sobre el mismo conjunto de prueba. Matrices de confusión y demás métricas: docs/resultados.md.

La medición de 0,26 s para 3,36 km² es informal y de una sola repetición en CPU. No representa una garantía de latencia, no incluye descarga de imágenes ni tiempo del navegador.

## Limitaciones

- Cobertura territorial: no se implementó el procesamiento de cualquier ubicación del Chaco. La versión utiliza imágenes descargadas, alineadas y preparadas para dos zonas piloto. Falta integrar al visor la búsqueda, descarga y preparación automática de imágenes de nuevas ubicaciones y validar allí el modelo. Esta es una limitación de la implementación y su evaluación, no una imposibilidad del método.
- Superficie por consulta: el límite predeterminado es 4 km², equivalentes a 400 ha. Es configurable mediante CHACO_MAX_AREA_KM2; no demuestra una capacidad máxima de la U-Net. El rendimiento y consumo de memoria con superficies mayores no están caracterizados.
- Temporalidad: la API y el visor actuales usan 2022–2023. No se cumplió el monitoreo validado de los últimos meses. Los insumos o planes relativos a 2026 no equivalen a una evaluación realizada ni a un par habilitado en la interfaz.
- Referencia: MapBiomas aporta mapas anuales de 30 m. Su remuestreo a 10 m no agrega detalle real y la etiqueta anual puede no coincidir con la fecha exacta de Sentinel-2. La definición operativa de bosque usa clases 3, 4 y 6; ver src/chaco_monitor/labels.py.
- Validación: solo dos zonas y un par temporal; conjunto de prueba pequeño. No se completaron una referencia visual manual independiente, evaluación sobre 2026 ni IoU por clase/mIoU. Los bloques no tienen una franja de separación adicional, por lo que no se ha demostrado independencia espacial completa.
- Representatividad: los estudios de caso se seleccionaron buscando cambios conocidos; no permiten estimar la deforestación regional ni garantizar generalización a todo el Chaco.
- Visualización: la vectorización omite manchas menores de 0,04 ha; el total de hectáreas se calcula sobre los píxeles positivos antes de ese filtro, por lo que puede diferir de la suma de polígonos visibles.
- Reproducibilidad: datos y pesos se distribuyen fuera de Git. El enlace de distribución y sus permisos no están especificados aquí; deben coordinarse con las autoras. No hay descarga automática del paquete de demo.
- Alcance científico: no se atribuyen causas ni se confirma desmonte con verificación de campo. El acuerdo mostrado contra MapBiomas en una consulta no reemplaza las métricas del conjunto de prueba.

## Trabajo futuro

Integrar ingesta para nuevas ubicaciones y fechas; ampliar y diversificar entrenamiento y prueba; validar cambios recientes con referencia independiente; evaluar superficies mayores y latencia con repeticiones; incorporar separación espacial adicional y documentar la distribución reproducible de datos y pesos. Estas mejoras no se presentan como implementadas.

## Estructura y documentación

- api/: API REST y servicio del visor.
- web/: interfaz Leaflet y dependencias locales.
- src/chaco_monitor/: preprocesamiento, etiquetas, dataset, modelo e inferencia.
- scripts/: ingesta, exportación, entrenamiento y controles.
- configs/ y manifests/: configuración y trazabilidad.
- tests/: pruebas automatizadas.
- docs/: metodología, fuentes, resultados y despliegue.
- data/, models/ y outputs/: datos, pesos y salidas locales no versionados.

La exportación MapBiomas está registrada en manifests/mapbiomas-labels-v1.json, generado el 27/10/2026. Algunas notas de planificación en docs/ conservan estados anteriores; para el alcance presentado consultar este README, los manifiestos y docs/resultados.md.

## Verificación local

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/check_repository.py
```

Estos comandos deben ejecutarse en el entorno local correspondiente. La lectura del repositorio no verifica por sí sola que los datos estén instalados ni que la demo funcione en otra computadora.

## Fuentes, licencias y preparación de datos

Consultar docs/sources.md, docs/mapbiomas-export.md, docs/fase2-dataset.md, docs/fase3-entrenamiento.md y docs/docker.md. Las fases de Earth Engine requieren requirements-gee.txt, autenticación y GEE_PROJECT; no son necesarias para cada inferencia con datos ya preparados.

Atribuciones: Contains modified Copernicus Sentinel data [Year], usando el año de los insumos correspondientes; MapBiomas Chaco, CC BY 4.0; Hansen/UMD/Google/USGS/NASA, GFC 2025 v1.13, CC BY 4.0, utilizado en prospección. Las condiciones y procedencia se documentan en docs/sources.md. No se declara una licencia pública del código en este README.

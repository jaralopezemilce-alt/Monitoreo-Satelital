# Plan de entrega al 9 de noviembre de 2026

Este calendario reemplaza al plan ideal de ocho semanas como planificación operativa. Se trabaja del 26 de octubre al 8 de noviembre, con entrega el día 9; es un alcance de alto riesgo, no una garantía de que cuatro veces menos tiempo produzca el mismo nivel de validación.

## Condiciones de viabilidad

- Dos integrantes con dedicación concentrada: supuesto provisional de 4–6 horas diarias por persona; falta confirmar disponibilidad y experiencia de la compañera.
- Un único modelo compacto y una baseline; sin búsqueda amplia de hiperparámetros.
- Dos zonas pequeñas offline y un tercer candidato como reserva, no tres pipelines.
- Separar experimento histórico y demostración reciente, sin exigir que todos los casos recientes tengan cambio positivo.
- Aprobar decisiones diariamente; no avanzar de fase sin confirmación.
- No recortar evaluación, procedencia de datos, demo real o informe para añadir el modo online.

## Calendario y responsabilidades

Los roles no presuponen que una integrante ya domine una tecnología. Propongo Emilce como responsable de integración/datos y la segunda integrante como responsable de etiquetas/evaluación; se pueden intercambiar después de conocer sus fortalezas.

| Fecha | Hito y fase | Emilce | Segunda integrante | Verificación / puerta de salida |
|---|---|---|---|---|
| 26 oct | Investigación y base Git | Revisar repositorio y restricciones offline | Revisar candidatas y condiciones académicas | Tres candidatas documentadas, pruebas de base y decisiones pendientes explícitas |
| 27 oct | Cierre de selección; ingesta piloto | Instalar entorno, elegir 2 zonas y resolver acceso a etiquetas | Revisar muestras/fechas y acordar definición de bosque | Zonas aprobadas; una descarga multiespectral y una máscara verificadas |
| 28 oct | Preprocesamiento | Escalas, grilla común, SCL, NDVI y parches | Controles geométricos, fechas, nodata y normalización | Piloto reproducible con overlay y valores plausibles |
| 29 oct | Dataset y máscaras | Particiones espaciales y manifiestos | Anotación de test/revisión de pseudoetiquetas | Dataset v1 congelado; sin solape entre splits |
| 30 oct | Baseline y primer entrenamiento | U-Net pequeña en Kaggle/Colab, checkpoint | Umbral NDVI sobre validación; métricas | Corrida completa recuperable y baseline medible |
| 31 oct | Cierre de modelo y evaluación | Una corrección justificada si hace falta; congelar pesos | Test reservado y matriz de confusión; errores | Tabla de métricas reales; no prometer que U-Net gana |
| 1 nov | Cambio y CPU | Transición bosque→no bosque y raster métrico | Referencia de cambio y benchmark en laptop | Hectáreas verificadas con geometría sintética; tiempo real registrado |
| 2 nov | API | Implementar FastAPI con inferencia y resultados | Probar área/fechas inválidas, nubes y cobertura | Endpoint real probado desde cliente HTTP |
| 3 nov | Visor | Integrar mapa, selección y API | Revisar rojo/no observable, textos y metadatos | Flujo completo en vivo desde interfaz |
| 4 nov | Docker y modo offline | Construir servicios y paquete de datos/pesos | Probar instalación y arranque con Wi-Fi apagado | Dos consultas reales offline; restauración documentada |
| 5 nov | Extensión online condicionada | Sólo si todo lo anterior funciona: descarga acotada | Probar timeout y retorno explícito a offline | Si falla, deshabilitar online; demo principal sigue funcionando |
| 6 nov | Congelamiento de funciones | Corregir errores críticos y preparar release | Consolidar resultados, figuras y limitaciones | No añadir funciones; paquete completo y README final |
| 7 nov | Informe y defensa | Metodología/arquitectura y demo | Contexto, discusión, referencias y ensayo | IEEE de exactamente 3 páginas; guion de 10 min |
| 8 nov | Ensayo final y respaldo | Ensayo offline en laptop objetivo | Preguntas difíciles, segundo equipo y revisión final | Dos ensayos, checklist y archivos listos para entregar |
| 9 nov | Entrega | Verificar enlaces/versión | Verificar PDF y material de defensa | Entregar versión congelada, no modificarla en el aula |

La escritura del informe comienza al cerrar cada fase y la semana final se usa para compactarlo y revisarlo, no para inventar metodología retrospectivamente. El alcance mínimo incluye todos los entregables obligatorios, con el modo online como única extensión prescindible.

## Dos experimentos separados

### Histórico

Propuesta: imágenes 2022/2023, pseudoetiquetas MapBiomas de esos años más revisión manual y referencia de test separada. Las fechas concretas de las tres candidatas ya están en `docs/evidence/selected_scenes.csv`.

No limitar el entrenamiento a los recortes de demo: propondría ampliar dos entornos históricos a aproximadamente 10 × 10 km cada uno, sujetos a revisión de calidad y aprobación. Con dos fechas y parches de 128 × 128 a 10 m, eso da un orden de magnitud de 240 parches no solapados antes de exclusiones, no miles de ejemplos independientes; si faltan clases o bloques de test, ajustar el tamaño antes de congelar el dataset.

Las ventanas mayores requieren comprobar nuevamente cobertura y nubes: las fechas verificadas para el pequeño candidato no garantizan validez en todo su entorno. El entrenamiento sigue en GPU remota y la demo sólo procesa su recorte de hasta 4 km² en CPU.

Un mapa anual no garantiza coincidencia con una adquisición de septiembre/octubre; se revisarán cambios dentro del año y se ignorarán o corregirán píxeles temporalmente incompatibles. Si no se obtiene MapBiomas, se debe aprobar una alternativa antes de avanzar: WorldCover 2021 con imágenes de 2021 o anotación manual acotada; no se sustituirán etiquetas sin documentarlo.

### Reciente

Propuesta inicial: mayo frente a septiembre de 2026, con escenas utilizables confirmadas en las tres candidatas. Son observaciones recientes, pero la inspección actual no confirma una nueva remoción inequívoca entre ellas; una salida de estabilidad es válida y no se forzará un mapa rojo.

Si la cátedra exige un caso reciente positivo, la siguiente fase debe dedicar una búsqueda acotada de hasta medio día a otro recorte o intervalo y someterlo a aprobación. No se presentará el caso histórico como si fuera de los últimos meses.

## Puntos de recorte

- Si el 29 de octubre no hay dataset usable, reducir a una zona de entrenamiento con bloques separados y una zona externa de test; no eliminar el test.
- Si no hay GPU disponible, reducir parches/épocas y conservar checkpoints; buscar la otra plataforma gratuita sin alterar las condiciones del servicio.
- Si el 1 de noviembre la CPU es lenta, reducir el área seleccionable, no sustituir inferencia por capturas.
- Si el 4 de noviembre no hay demo offline, cancelar inmediatamente el modo online y dedicar el día 5 a integración.
- Si la cátedra rechaza pseudoetiquetas, replantear el tamaño del dataset con máscaras manuales; no afirmar que el requisito está resuelto.

## Estado del cierre de fase 1

Quedan preparados el repositorio, tres candidatas con coordenadas, escenas históricas/recientes, evidencia visual, un piloto de revisión de Hansen y pruebas de límites geométricos. Faltan aprobación de zonas, disponibilidad de la segunda integrante y acceso/exportación de MapBiomas; no se inició entrenamiento ni implementación de la API/visor.

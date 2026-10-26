# Contrato de los modos offline y online

Este documento fija decisiones de diseño para implementar después de aprobar las zonas. No describe una aplicación ya terminada.

## Modo offline obligatorio

Se distribuirán dos zonas y dos fechas recientes por zona en un paquete externo a Git; el experimento histórico tendrá datos y manifiestos separados. Cada paquete incluirá bandas alineadas, máscara de calidad, metadatos, miniaturas de fondo, pesos y sus checksums.

El usuario seleccionará una zona y dibujará o escogerá un recorte dentro de ella. La API validará cobertura y fechas, ejecutará inferencia en CPU sobre ambas imágenes, calculará cambio únicamente donde ambas son válidas y devolverá máscara/visualización y hectáreas.

- Límite inicial: 4 km² por solicitud; los polígonos candidatos de prospección son mayores, aproximadamente 15 km², y no equivalen al área máxima de inferencia.
- Entrenamiento histórico: ventanas propuestas de aproximadamente 10 × 10 km alrededor de las zonas aprobadas, con controles adicionales de calidad; no reducir el dataset al pequeño rectángulo usado en la demo.
- Tamaños para benchmark: 1, 2 y 4 km², lote 1 y parches de 128 × 128.
- Arquitectura inicial: U-Net de cinco canales, canales internos [16, 32, 64, 128], con reducción posterior si fuera necesario.
- Fuera de cobertura o fecha no incluida: error explícito, nunca procesar otra zona/fecha sin avisar.
- Sin píxeles válidos: resultado no evaluable, no cero hectáreas.
- Recursos web: JavaScript, CSS, iconos y fondos locales; sin CDN, fuentes remotas ni teselas online obligatorias.
- Arranque sin internet: imágenes Docker construidas o cargadas previamente, volúmenes y pesos disponibles. El primer `pip install`, `docker pull` o build no será considerado operación offline.
- Prueba de aceptación: desactivar Wi-Fi, iniciar servicios sin descargar dependencias y ejecutar dos solicitudes distintas que realmente llamen al modelo.

## Modo online opcional

Se habilitará mediante configuración sólo cuando el camino offline esté probado. Al dibujar un AOI nuevo, se validarán pertenencia al Chaco, geometría y límite de 4 km² antes de consultar imágenes.

- Ventanas no superpuestas de ±15 días alrededor de cada fecha objetivo, inicialmente; si se superponen, pedir fechas más separadas.
- Mostrar la fecha real de adquisición elegida y requerir consentimiento visible si difiere del día solicitado.
- Consultar metadatos, filtrar nubosidad, leer SCL local y después descargar sólo las bandas necesarias.
- Límites propuestos: 15 s para conexión, 90 s por operación de lectura y 180 s de presupuesto global de solicitud; máximo un reintento controlado y caché por escena/área.
- Si no hay escenas válidas, hay un error de red o se agota el tiempo: mostrar causa y ofrecer “Volver a zonas precargadas”.
- Nunca devolver la máscara de una zona precargada como si perteneciera al polígono nuevo; el usuario debe volver a seleccionar el área offline.
- Limpiar archivos parciales y conservar metadatos de fallos sin tokens ni información sensible.
- No entrenar ni actualizar pesos dentro de una solicitud REST.

Si el modo online no pasa pruebas el 5 de noviembre, quedará deshabilitado en la entrega y documentado como trabajo futuro. No es razonable poner en riesgo la demo obligatoria por una extensión no confirmada por la cátedra.

## Benchmark de CPU

El hardware objetivo es la ASUS Vivobook de Emilce: Windows 11, i7-13620H, 16 GB de RAM, GPU integrada no utilizada para la inferencia. Este entorno remoto no es esa laptop; ningún tiempo medido aquí se presentará como un resultado de su equipo.

Mediremos, para cada tamaño, arranque/carga del modelo, inferencia de cada fecha, posprocesamiento y latencia total de API. Usaremos tres calentamientos y diez repeticiones medidas para mediana y p95, registrando versión de PyTorch, hilos, RAM máxima y tamaño efectivo.

Objetivo de ingeniería, no promesa: intentar mantener la solicitud de demo por debajo de 15 segundos; si no se cumple, reducir el área a 1–2 km². La reducción de resolución sólo se aceptará explícitamente y deberá reflejarse en la documentación y cálculo de hectáreas.

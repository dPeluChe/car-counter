# Tareas pendientes: detección de autos y rutas

Revisión documental y de código: 2026-09-14. Fuente única de pendientes. [Estado verificado](GUIDES/VERIFIED_STATE.md), [protocolo manual](GUIDES/MANUAL_VALIDATION.md) e [historial heredado](TASK_COMPLETED/LEGACY.md).

**Foco autorizado:** detección de autos, continuidad de IDs y rutas para una presentación verificable. Este ciclo documenta; no cambia algoritmos ni instala servicios.

## Cómo leer el estado

`[x]` significa implementación/evidencia local identificada, no precisión humana ni despliegue. `[ ]` requiere trabajo o prueba. No se cerrará una tarea por existir un script o por conservar el mismo total de cruces. Las tareas heredadas sin fecha se identifican como tales; no se inventa antigüedad.

La suite verificada tiene 316 pruebas aprobadas y 15 omitidas por dependencias opcionales. El video de demo cubre 300 frames y una sola línea. Sus cinco autos y un bus son predicciones del sistema, no ground truth humano.

## Orden del ciclo

| Orden | Tarea | Resultado necesario |
|---|---|---|
| 1 | TODO-028 | Referencia humana y procedencia de imágenes/eventos |
| 2 | TODO-032 | Medición y mejora de detección de autos |
| 3 | TODO-030 | Continuidad de identidad y errores por evento |
| 4 | TODO-031 | Perfil de rutas completas y video de evidencia |
| Condicional P0 | TODO-029 | Geometría coherente cuando se mueve la cámara |
| En paralelo con pruebas humanas | TODO-033 | Configurador utilizable y parámetros persistentes |
| Después de exactitud | TODO-023 / TODO-024 | Rendimiento y formatos con beneficio medido |
| Operación opcional | TODO-034 | Cron activado y verificado desde entorno permitido |

No se establece un porcentaje aprobado de precisión todavía. El revisor define con el responsable de la presentación el alcance, las clases y los umbrales antes de seleccionar parámetros. Las pruebas manuales PRUEBA-01 a PRUEBA-08 están detalladas en la guía.

## TODO-028: Referencias humanas de detección y rutas

**Prioridad:** P0. **Fecha de alta:** no registrada en el backlog heredado. **Estado:** herramientas implementadas, dataset humano no completado. Es requisito de aceptación para TODO-031, TODO-032 y TODO-030.

**Objetivo:** medir detección y aforo por separado sobre el mismo material, con procedencia verificable. Una predicción del modelo nunca es automáticamente verdad humana.

- [x] Extraer imágenes y deduplicarlas con `scripts/extract_validation_frames.py`.
- [x] Generar preetiquetas sin sobrescribir anotaciones existentes, con `flags.reviewed=false`, usando `scripts/pre_label_frames.py`.
- [x] Evaluar cajas/clases con el perfil real mediante `scripts/evaluate_pipeline.py`; exigir revisión y rechazar imágenes faltantes o referencias duplicadas.
- [x] Disponer de evaluador de eventos con referencia `reviewed=true`, hash y límites de frames.
- [ ] Añadir manifiesto de extracción con SHA-256 de video, índice original desde 1, timestamp, imagen y FPS. Actualmente `frame_0000.jpg` es un índice de exportación y pierde esa correspondencia; no sirve para inferir el tiempo original.
- [ ] Rechazar explícitamente formas no compatibles o convertirlas con una regla probada: el parser actual solo lee `shape_type=rectangle` e ignora polígonos/máscaras. No evaluar asistencia de segmentación como si fueran cajas revisadas.
- [ ] Seleccionar escenas con autos pequeños, tráfico denso, oclusiones, bordes de ROI, fondo sin autos y vehículos estacionados; incluir más de un tramo.
- [ ] Separar tramos usados para ajustar parámetros de los usados para aceptar el cambio; evitar usar imágenes casi iguales como validación independiente.
- [ ] Corregir todas las cajas/clases del alcance en LabelMe u otro editor compatible; añadir también autos omitidos. Registrar revisor, fecha y alcance antes de marcar `flags.reviewed=true`.
- [ ] Contar eventos humanos independientemente del overlay: frame, ruta/sentido, clase y casos incompletos; no copiar eventos predichos a la referencia.
- [ ] Acordar clases incluidas en el aforo (por ejemplo autos, buses, motos y vans), tratamiento de ambiguos y márgenes al inicio/final.
- [ ] Acordar por escrito los umbrales de aceptación de precisión, recall y F1 por clase/ruta y una tolerancia temporal justificada por FPS y confirmación.
- [ ] Guardar ejecución de evaluación real con perfiles y reportes; no usar porcentajes de ejemplo como resultado.

**Archivos relevantes:** los tres scripts anteriores, `carcounter/validation.py`, `scripts/validate_routes.py`. **Entregable:** imágenes, anotaciones revisadas, manifiesto, referencia de eventos y reporte. `data/` y `output/` están ignorados por Git; acordar copia de respaldo del dataset sin subir videos ni datos por defecto.

**Pruebas manuales:** PRUEBA-02, PRUEBA-04 y PRUEBA-08. La integración visual con LabelMe y funciones opcionales de asistencia no se ha verificado aquí. No se promete tiempo de anotación ni ganancia de precisión por usar un asistente.

## TODO-032: Calidad de detección de autos `added: 2026-09-14`

**Prioridad:** P0. **Depende de:** TODO-028. **Estado:** detector compartido implementado; mejora de precisión real sin acreditar.

**Especificación:** separar falsos positivos del fondo, autos omitidos, cajas duplicadas y clase errónea. Revisar autos pequeños/ocluídos, vehículos estacionados y bordes de ROI. El modelo de referencia es VisDrone y no debe interpretarse con IDs de clase COCO. Las clases incluidas en aforo se acuerdan antes de excluir buses, vans o motos.

**Archivos relevantes:** `carcounter/detection.py`, `carcounter/detector.py`, `carcounter/constants.py`, `carcounter/calibration.py`, `scripts/evaluate_pipeline.py`, `tests/test_detection.py`, `tests/test_pipeline_profile.py`.

- [x] Detector y filtros compartidos entre calibración y runtime; clases desde los pesos; SAHI entrega cajas globales a un único tracker.
- [ ] Revisar primero errores concretos sobre datos humanos; no elegir configuración por máximo número de cajas.
- [ ] Comparar confianza global/por clase, filtros geométricos, `imgsz`, ROI y SAHI variando un factor cada vez.
- [ ] Medir precisión, recall y F1 de `car` y de las demás clases del alcance, separando localización de clasificación y mostrando TP/FP/FN.
- [ ] Probar autos próximos y límites de tiles antes de aceptar NMS más agresivo; documentar si elimina autos distintos.
- [ ] Probar consenso de clase contra etiquetas humanas. La clase se congela tras el primer conteo; documentar errores persistentes y decidir si hace falta otro criterio.
- [ ] Evaluar pesos alternativos o entrenamiento solo cuando los errores medidos justifiquen el costo, con tramos reservados de validación.

**Entregable:** perfil candidato, matriz de experimentos, imágenes de errores y reporte contra referencia revisada. Cambiar modelo/ROI/resolución/SAHI o bajar el piso de confianza requiere otra caché; el replay no crea detecciones ausentes.

**Prueba manual:** PRUEBA-02. **Cierre:** mejora en las métricas acordadas sin ocultar vehículos válidos mediante recortes/exclusiones. Un auto estacionado detectado no es por sí mismo falso positivo.

## TODO-033: Validación del configurador y calibración `added: 2026-09-14`

**Prioridad:** P0 para que el revisor pueda probar. **Estado:** lógica probada, GUI no validada visualmente en esta sesión.

**Archivos relevantes:** `setup.py`, `setup_panels/calib_tests.py`, `setup_panels/step1_calibration.py`, `setup_panels/step2_preview.py`, `setup_panels/step3_sahi.py`, `carcounter/app_config.py`.

- [ ] Abrir el configurador en el escritorio y confirmar carga del video/modelo del perfil, controles visibles y desplazamiento lateral.
- [ ] Verificar muestras de distintos frames, correspondencia uno a uno y aplicación explícita de filtros desde cinco muestras.
- [ ] Guardar/reabrir una copia y comparar modelo, ROI, muestras, confianza, clases, SAHI y parámetros de tracker; registrar cualquier campo perdido.
- [ ] Verificar limpieza de muestras/filtros y cambio de modelo sin reutilizar resultados visuales de otro detector.
- [ ] Registrar frame de referencia de la calibración geométrica y su relación con el primer frame procesado; detectar desalineación si se calibra otro encuadre de cámara.
- [ ] Contrastar preview y ejecución con idéntico perfil y frames, sin confundir una muestra parcial con recall de toda la escena.

**Prueba manual:** PRUEBA-05. **Cierre:** recorrido visual reproducible, persistencia comprobada y perfil usado en runtime identificable. No se afirma que haya controles GUI para todos los flags de CLI.

## TODO-034: Activación controlada del cron local `added: 2026-09-14`

**Prioridad:** secundaria; no bloquea pruebas de detección/rutas.

- [x] Script `scripts/recurring_review.py`, prompt, guía y 19 pruebas de condiciones/lanzamiento simulado.
- [ ] Ejecutar consulta real de cuota desde terminal permitida y confirmar cuenta/modelo utilizados sin exponer credenciales.
- [ ] Instalar conservando otros trabajos, comprobar `crontab -l` y registrar la fecha efectiva de inicio.
- [ ] Observar una ejecución real enfocada en detección/rutas y comprobar informe, exclusión mutua, omisión por falta de cuota y pausa de futuras ejecuciones.

**Límite actual:** cron no instalado. El entorno bloqueó `crontab` y el estado SQLite de Codex bajo `~/.codex`. No asumir autoactivación, cuota disponible o encendido del equipo. La guía [RECURRING_CODE_REVIEW_CRON.md](GUIDES/RECURRING_CODE_REVIEW_CRON.md) es el procedimiento operativo.

## TODO-030: Validación de eventos y continuidad de IDs `added: 2026-09-07`

**Prioridad:** P0. **Estado:** exportación y evaluador temporal implementados; comparación humana de trackers pendiente. **Depende de:** TODO-028.

**Archivos relevantes:** `carcounter/counting.py`, `carcounter/tracking.py`, `carcounter/export.py`, `scripts/validate_routes.py`, `tests/test_route_validation.py`, `tests/test_counting_regressions.py`.

- [x] Exportar cada evento con frame de confirmación, ID, clase, ruta y sentido u origen/destino, conservando totales y eventos de tracks purgados.
- [x] Emparejar uno a uno por tiempo, ruta y clase; informar precisión, recall, F1, omisiones y predicciones sin pareja.
- [x] Exigir referencia revisada, mismo SHA-256 y tramo válido; una referencia vacía no aprueba la aceptación.
- [x] Usar consenso de clase por track hasta el primer conteo y conservar la clase del resultado.
- [ ] Revisar pérdidas de ID en oclusiones, cambios de ID cerca de líneas/zonas y IDs duplicados del mismo auto.
- [ ] Comparar ByteTrack y BoT-SORT sobre una caché común; variar un parámetro por experimento y registrar parámetros efectivos. `with_reid=true` no está soportado en el wrapper actual.
- [ ] Añadir referencia de identidad física por auto para casos ambiguos; el evaluador actual solo empareja ruta/clase/tiempo, no valida identidad.
- [ ] Distinguir con evidencia duplicación, falso positivo, clase errónea y desfase temporal; no llamar duplicado a toda predicción sin pareja.
- [ ] Revisar el fallback de clase `car` de SORT cuando no hay asociación con una detección; definir y probar tratamiento de clase desconocida.
- [ ] Acordar tratamiento de repetición de una misma ruta, vuelta completa y reingreso antes de ampliar el conteo actual por ID.

**Entregable:** tabla por variante con video/hash/tramo, FP/FN/F1, cambios de ID revisados, eventos sin pareja y casos visuales. **Pruebas manuales:** PRUEBA-03, PRUEBA-04 y PRUEBA-08. **Cierre:** mejora sobre casos humanos reservados para validación, sin regresión en rutas o clases relevantes.

## TODO-031: Rutas completas para la presentación `added: 2026-09-14`

**Prioridad:** P0. **Estado:** geometría de demo parcial; rutas completas sin validar. **Depende de:** TODO-028, TODO-030 y TODO-029 si la cámara desplaza el encuadre.

**Objetivo:** contar origen y destino de autos que completan el trayecto visible, sin confundir un cruce de línea con una ruta completa.

**Especificación:** definir bocacalles y sentidos del alcance; guardar un perfil separado en modo `zones`; ubicar zonas donde entrar/salir sea inequívoco, sin invadir el anillo. La ROI debe cubrir observaciones de origen, tránsito y destino. Documentar las zonas solapadas, autos presentes al inicio/final, retornos y vueltas múltiples. El contador actual termina una ruta en la primera zona distinta al origen que cumple permanencia y cuenta una ruta por ID; cualquier cambio de política requiere implementación y pruebas explícitas.

**Archivos relevantes:** `setup_panels/step2_zones.py`, `carcounter/config_io.py`, `carcounter/runtime.py`, `carcounter/counting.py`, `tests/test_counting_regressions.py`.

- [ ] Guardar mapa de rutas permitidas, ROI y zonas en un perfil distinto al ejemplo de una línea.
- [ ] Añadir validación de geometría que identifique zonas inalcanzables por la región de detección y destinos prematuros, con diagnóstico comprensible.
- [ ] Reproducir A→B, paso junto a una salida sin tomarla y trayectoria incompleta con reglas documentadas.
- [ ] Comparar eventos y matriz origen/destino contra revisión humana del mismo video y tramo.
- [ ] Entregar video, JSON con eventos, CSV de tracks/OD y reporte de rutas revisadas, sin presentar IDs como autos.

**Pruebas manuales:** PRUEBA-04 y PRUEBA-06. **Cierre:** rutas del alcance revisadas, incidentes clasificados y umbrales acordados alcanzados; no basta conservar seis cruces de Anillo oeste.

## TODO-029: Movimiento de cámara y geometría del conteo `added: 2026-09-07`

**Prioridad:** P0 cuando afecta el tramo presentado. **Estado:** monitor implementado; corrección geométrica pendiente.

**Evidencia:** `carcounter/camera_motion.py`, `scripts/audit_camera_motion.py`, `main.py` y `tests/test_camera_motion.py`. El monitor excluye la ROI de inferencia al buscar fondo, estima una transformación de similitud y comprueba puntos de conteo. En las muestras registradas: 7.8113 px de deriva en video normal y 85.2845 px en el acelerado, con puntos distintos. No son medidas de exactitud de aforo.

**Especificación:** elegir un sistema de referencia único para imagen, cajas, ROI, exclusiones y zonas/líneas. Comparar estabilizar imágenes antes de inferencia frente a transformar coordenadas; documentar qué se hace en bordes sin cobertura y cómo afecta la firma de caché. No reutilizar una caché incompatible ni aplicar dos compensaciones inconsistentes. La compensación del tracker BoT-SORT no mueve las zonas de conteo.

- [x] Estimar deriva del fondo y ofrecer detención opcional por CLI/JSON.
- [x] Probar traslación, rotación, coordenadas originales, falta de textura y rechazo de resultado incompleto.
- [ ] Mantener sincronizados detección, tracking y geometría durante la corrección elegida.
- [ ] Rechazar cambios de escena, correspondencias insuficientes y regiones sin cobertura; explicar el motivo en la salida.
- [ ] Calibrar tolerancia con casos revisados, no elevarla para ocultar el fallo.
- [ ] Comparar FP/FN y eventos antes/después sobre el mismo tramo humano, incluyendo estabilidad de los puntos físicos de entrada/salida.

**Prueba manual:** PRUEBA-07. **Cierre:** mejora medida de las rutas afectadas y rechazo verificable cuando no se puede mantener el encuadre. El control de 5 px es experimental y está desactivado por defecto.

## Fuera del foco de la presentación

## TODO-023: Rendimiento del flujo real

**Prioridad:** P1 después de la referencia humana. **Fecha de alta:** no registrada. **Depende de:** TODO-028 y exactitud estable de detección/rutas.

**Hallazgo:** `scripts/benchmark_pipeline.py` existe, pero no carga el perfil del aforo: usa zonas vacías, parámetros propios, una copia de frame como visualización y JPEG como aproximación de escritura. No representa el pipeline real completo. `main.py --benchmark` sí ejecuta el perfil, pero agrupa detección y tracking en la etapa `detection`.

- [x] Profiler y exportación de benchmark existentes.
- [ ] Hacer que el benchmark comparta perfil, ROI, clases, filtros y tracker con producción.
- [ ] Separar inferencia, asociación, conteo, control de cámara, dibujo y escritura; reportar además tiempo total, carga de pesos/hashes y dispositivo.
- [ ] Medir memoria y tiempos en el tramo objetivo sin mezclar varias corridas que compitan por CPU/GPU.
- [ ] Si el cuello medido lo justifica, probar prelectura, batching de detección o escritura asíncrona manteniendo orden de frames y semántica del tracker.
- [ ] Comparar eventos y métricas antes/después; distinguir FPS de replay de FPS con inferencia.

**Cierre:** reducción medida de tiempo/memoria con exactitud conservada en los casos revisados. No asumir que GPU, más resolución o batches mejorarán esta máquina.

## TODO-024: Evaluar formatos ONNX y TensorRT

**Prioridad:** P2, después de TODO-023. **Fecha de alta:** no registrada.

- [x] `scripts/export_model.py` exporta ONNX; CLI real: `--model` y `--imgsz`.
- [ ] Verificar que un modelo exportado carga y conserva nombres de clases, cajas, filtros, tracking y eventos sobre el perfil revisado.
- [ ] Comparar `.pt` y `.onnx` con el mismo `imgsz`, video, dispositivo y métricas humanas, incluyendo tiempo de carga y errores numéricos.
- [ ] Añadir `--half` u otros formatos solo si el backend/hardware lo soporta y una prueba muestra beneficio; el script actual no tiene esos argumentos.
- [ ] Evaluar TensorRT únicamente con CUDA disponible y después de ONNX; registrar versiones y compatibilidad.

**Cierre:** mejora medida con precisión aceptada. No se promete aceleración 2x/3x ni equivalencia automática de FP16. Los nombres de modelos en ejemplos históricos no acreditan que los pesos existan localmente.

## TODO-019: Persistencia local libSQL

**Prioridad:** secundaria, fuera del ciclo de detección/rutas. **Fecha de alta:** no registrada. **Estado:** código existente; backend real pendiente de verificar con dependencias instaladas.

- [x] Módulo `carcounter/db.py` con `init_db`, `save_run` y `list_runs`, esquema e historial local.
- [x] Integración de `db.save_run()` al finalizar correctamente `main.py`; CLI `python -m carcounter.db list`.
- [x] JSON independiente de la disponibilidad de la DB; dependencias opcionales documentadas.
- [ ] Ejecutar pruebas con `libsql-experimental` instalado y comprobar persistencia tras cerrar/reabrir.
- [ ] Verificar valores guardados contra JSON/OD del mismo run, sin almacenar un proceso fallido como completado.

**Cierre:** pruebas del backend real, datos consistentes y evidencia de lectura posterior. Los tests omitidos no acreditan esa validación. Embeddings y búsqueda de vehículos por similitud permanecen como idea futura, no como requisito de esta entrega.

## TODO-025: Verificación visual de vectores de dirección

**Prioridad:** secundaria; el foco de presentación son rutas origen/destino. **Fecha de alta:** no registrada.

- [x] `carcounter/drawing.py` implementa `draw_direction_vectors`; el runtime la llama en modo `directions`.
- [x] Hay editor de direcciones en `setup_panels/step2_directions.py` y pruebas de dibujo/conteo.
- [ ] Revisar visualmente en escritorio que guardar/reabrir conserve puntas, nombres y orientación de las flechas.
- [ ] Comprobar con un movimiento conocido que la dirección asignada coincide con lo dibujado, sin confundirla con una ruta A→B.

**Prueba manual:** PRUEBA-05, con copia de perfil en modo `directions`. **Cierre:** prueba visual registrada; no volver a implementar un dibujado que ya existe.

## TODO-026: Verificar API local opcional

**Prioridad:** secundaria, fuera del ciclo de detección/rutas. **Fecha de alta:** no registrada.

- [x] `carcounter/api.py` y `--serve` exponen salud, estadísticas, historial, detalle y MJPEG.
- [x] `tests/test_api.py` existe; requisitos opcionales documentados.
- [ ] Ejecutar con `fastapi`, `uvicorn` y dependencias de prueba; verificar respuestas, errores y stream durante procesamiento real.
- [ ] Comparar conteo/frames de la API con JSON del mismo run; comprobar historial solo cuando la DB esté disponible.

**Cierre:** evidencia con backend instalado. No presentar las pruebas omitidas ni endpoints descritos como una comprobación real del servicio. No publicar el servicio ni cambiar su exposición como parte de este ciclo documental.

## TODO-022: Evaluación de supervision

**Prioridad:** investigación diferida. **Fecha de alta:** no registrada.

- [x] Existe `docs/RESEARCH/SUPERVISION_EVAL.md`, fechado 2026-04-15.
- [x] El proyecto ya tiene máscaras de zonas, confirmación de cruces y dibujo de trayectorias.
- [ ] Si se retoma una migración, contrastar la API que se vaya a instalar y medir contra el mismo perfil/video; el informe histórico no ejecutó benchmark ni prototipo.
- [ ] Registrar decisión con evidencia de mantenimiento o comportamiento, sin tratar estimaciones de milisegundos como tiempos medidos.

El informe heredado propone descartar la migración completa. No se reabre ese trabajo antes de validar detección y rutas; cambiar de biblioteca no es un resultado de producto por sí mismo.

# Tareas pendientes: detección de autos y rutas

Única lista de pendientes. Lo ya comprobado está en [VERIFIED_STATE.md](GUIDES/VERIFIED_STATE.md); lo completado, por mes, en [TASK_COMPLETED/](TASK_COMPLETED/). Pruebas manuales: [MANUAL_VALIDATION.md](GUIDES/MANUAL_VALIDATION.md).

**Foco:** detección de autos, continuidad de IDs y rutas para una presentación verificable. Una tarea no se cierra porque exista un script ni porque se conserve el mismo total de cruces. Las tareas sin `added:` son heredadas, de fecha desconocida.

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
| Opcional | TODO-036 | Replay y control de cámara desde el wizard |

Grupos, conteo origen/destino, tramo y propuesta de aceptación (±20 %): [COUNTING_SCOPE.md](GUIDES/COUNTING_SCOPE.md). La aceptación se confirma con la primera referencia humana.

## TODO-028: Referencias humanas de detección y rutas

**Prioridad:** P0. **Estado:** herramientas implementadas (ver [2609](TASK_COMPLETED/2609.md)), dataset humano no completado. Es requisito de aceptación para TODO-031, TODO-032 y TODO-030.

**Objetivo:** medir detección y aforo por separado sobre el mismo material, con procedencia verificable. Una predicción del modelo nunca es automáticamente verdad humana.

- [ ] Añadir manifiesto de extracción con SHA-256 de video, índice original desde 1, timestamp, imagen y FPS. Actualmente `frame_0000.jpg` es un índice de exportación y pierde esa correspondencia; no sirve para inferir el tiempo original.
- [ ] Rechazar explícitamente formas no compatibles o convertirlas con una regla probada: el parser actual solo lee `shape_type=rectangle` e ignora polígonos/máscaras. No evaluar asistencia de segmentación como si fueran cajas revisadas.
- [ ] Seleccionar escenas con autos pequeños, tráfico denso, oclusiones, bordes de ROI, fondo sin autos y vehículos estacionados; incluir más de un tramo.
- [ ] Separar tramos usados para ajustar parámetros de los usados para aceptar el cambio; evitar usar imágenes casi iguales como validación independiente.
- [ ] Corregir todas las cajas/clases del alcance en LabelMe u otro editor compatible; añadir también autos omitidos. Registrar revisor, fecha y alcance antes de marcar `flags.reviewed=true`.
- [ ] Contar eventos humanos independientemente del overlay: frame, ruta/sentido, clase y casos incompletos; no copiar eventos predichos a la referencia.
- [ ] Acordar márgenes al inicio/final del tramo y el trato de vehículos que ya están dentro del encuadre.
- [ ] Contar eventos humanos con grupos EPS en dos pasadas o por dos personas y reconciliar diferencias antes de `reviewed=true`.
- [ ] Confirmar o ajustar con esa referencia la [propuesta de aceptación](GUIDES/COUNTING_SCOPE.md#criterio-de-aceptación-propuesta) y fijar la tolerancia temporal según FPS y confirmación.
- [ ] Guardar ejecución de evaluación real con perfiles y reportes; no usar porcentajes de ejemplo como resultado.

**Archivos relevantes:** `scripts/extract_validation_frames.py`, `scripts/pre_label_frames.py`, `scripts/evaluate_pipeline.py`, `carcounter/validation.py`, `scripts/validate_routes.py`. **Entregable:** imágenes, anotaciones revisadas, manifiesto, referencia de eventos y reporte. `data/` y `output/` están ignorados por Git; acordar copia de respaldo del dataset sin subir videos ni datos por defecto.

**Pruebas manuales:** PRUEBA-02, PRUEBA-04 y PRUEBA-08. La integración visual con LabelMe y funciones opcionales de asistencia no se ha verificado. No se promete tiempo de anotación ni ganancia de precisión por usar un asistente.

## TODO-032: Calidad de detección de autos `added: 2026-09-14`

**Prioridad:** P0. **Depende de:** TODO-028. **Estado:** detector compartido implementado; mejora de precisión real sin acreditar.

**Especificación:** separar falsos positivos del fondo, autos omitidos, cajas duplicadas y clase errónea. Revisar autos pequeños/ocluídos, vehículos estacionados y bordes de ROI. El modelo de referencia es VisDrone y no debe interpretarse con IDs de clase COCO. Medir en especial los cruces entre grupos EPS: combi detectada como `van`, pickup como `truck`, remolques y patines sin clase ([COUNTING_SCOPE.md](GUIDES/COUNTING_SCOPE.md#donde-el-modelo-y-el-criterio-eps-no-coinciden)).

**Archivos relevantes:** `carcounter/detection.py`, `carcounter/detector.py`, `carcounter/constants.py`, `carcounter/calibration.py`, `scripts/evaluate_pipeline.py`, `tests/test_detection.py`, `tests/test_pipeline_profile.py`.

- [ ] Revisar primero errores concretos sobre datos humanos; no elegir configuración por máximo número de cajas.
- [ ] Comparar confianza global/por clase, filtros geométricos, `imgsz`, ROI y SAHI variando un factor cada vez.
- [ ] Medir precisión, recall y F1 de `car` y de las demás clases del alcance, separando localización de clasificación y mostrando TP/FP/FN.
- [ ] Probar autos próximos y límites de tiles antes de aceptar NMS más agresivo; documentar si elimina autos distintos.
- [ ] Probar consenso de clase contra etiquetas humanas. La clase se congela tras el primer conteo; documentar errores persistentes y decidir si hace falta otro criterio.
- [ ] Hacer configurable por perfil el mapeo clase → grupo (`settings.class_groups`, con `CLASS_GROUPS` como valor por defecto).
- [ ] En la referencia humana anotar también el tipo visible (auto, van, combi, pickup, remolque) y, con la matriz de confusión, decidir con datos a qué grupo van `van` y `truck`.
- [ ] Evaluar pesos alternativos o entrenamiento solo cuando los errores medidos justifiquen el costo, con tramos reservados de validación.

**Entregable:** perfil candidato, matriz de experimentos, imágenes de errores y reporte contra referencia revisada. Qué cambios exigen otra caché: [DETECTION_TUNING.md](GUIDES/DETECTION_TUNING.md#grabar-una-vez-y-repetir-sin-inferencia).

**Prueba manual:** PRUEBA-02. **Cierre:** mejora en las métricas acordadas sin ocultar vehículos válidos mediante recortes/exclusiones. Un auto estacionado detectado no es por sí mismo falso positivo.

## TODO-033: Validación del configurador y calibración `added: 2026-09-14`

**Prioridad:** P0 para que el revisor pueda probar. **Estado:** lógica probada, GUI sin validar en escritorio.

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

- [ ] Ejecutar consulta real de cuota desde terminal permitida y confirmar cuenta/modelo utilizados sin exponer credenciales.
- [ ] Instalar conservando otros trabajos, comprobar `crontab -l` y registrar la fecha efectiva de inicio.
- [ ] Observar una ejecución real enfocada en detección/rutas y comprobar informe, exclusión mutua, omisión por falta de cuota y pausa de futuras ejecuciones.
- [ ] Confirmar que el sandbox `workspace-write` de Codex permite `git push` y `gh pr create`; si no, que el script cree rama, push y PR tras la ejecución.

**Límite actual:** cron no instalado. El entorno del agente bloqueó `crontab` y el estado SQLite de Codex bajo `~/.codex`. No asumir autoactivación, cuota disponible o encendido del equipo. Procedimiento: [RECURRING_CODE_REVIEW_CRON.md](GUIDES/RECURRING_CODE_REVIEW_CRON.md).

## TODO-030: Validación de eventos y continuidad de IDs `added: 2026-09-07`

**Prioridad:** P0. **Estado:** exportación y evaluador temporal implementados; comparación humana de trackers pendiente. **Depende de:** TODO-028.

**Archivos relevantes:** `carcounter/counting.py`, `carcounter/tracking.py`, `carcounter/export.py`, `scripts/validate_routes.py`, `tests/test_route_validation.py`, `tests/test_counting_regressions.py`.

- [ ] Revisar pérdidas de ID en oclusiones, cambios de ID cerca de líneas/zonas y IDs duplicados del mismo auto.
- [ ] Reporte de vehículos incompletos: tracks que confirmaron origen y nunca destino, contados por acceso, con recorte de imagen del primer y último frame (caja, ID, clase, frame) para revisar si falló por oclusión, imagen poco clara o geometría.
- [ ] Marcar candidatos a cambio de ID: un track que termina y otro que empieza cerca, con clase compatible, en pocos frames; incluirlos en el mismo reporte con ambas imágenes.
- [ ] Comparar ByteTrack y BoT-SORT sobre una caché común; variar un parámetro por experimento y registrar parámetros efectivos. `with_reid=true` no está soportado en el wrapper actual.
- [ ] Añadir referencia de identidad física por auto para casos ambiguos; el evaluador actual solo empareja ruta/clase/tiempo, no valida identidad.
- [ ] Distinguir con evidencia duplicación, falso positivo, clase errónea y desfase temporal; no llamar duplicado a toda predicción sin pareja.
- [ ] Revisar el fallback de clase `car` de SORT cuando no hay asociación con una detección; definir y probar tratamiento de clase desconocida.
- [ ] Acordar tratamiento de repetición de una misma ruta, vuelta completa y reingreso antes de ampliar el conteo actual por ID.

**Entregable:** tabla por variante con video/hash/tramo, FP/FN/F1, cambios de ID revisados, eventos sin pareja y casos visuales. **Pruebas manuales:** PRUEBA-03, PRUEBA-04 y PRUEBA-08. **Cierre:** mejora sobre casos humanos reservados para validación, sin regresión en rutas o clases relevantes.

## TODO-031: Rutas completas para la presentación `added: 2026-09-14`

**Prioridad:** P0. **Estado:** geometría de demo parcial; rutas completas sin validar. **Depende de:** TODO-028, TODO-030 y TODO-029 si la cámara desplaza el encuadre.

**Objetivo:** contar origen y destino de autos que completan el trayecto visible, sin confundir un cruce de línea con una ruta completa.

**Especificación:** definir bocacalles y sentidos del alcance; guardar un perfil separado en modo `zones`; ubicar zonas donde entrar/salir sea inequívoco, sin invadir el anillo. La ROI debe cubrir observaciones de origen, tránsito y destino. Documentar las zonas solapadas, autos presentes al inicio/final, retornos y vueltas múltiples. Regla actual del contador en [ROUNDABOUT_GUIDE.md](GUIDES/ROUNDABOUT_GUIDE.md#ubicar-zonas-de-origen-y-destino); cualquier cambio de política requiere implementación y pruebas explícitas.

**Archivos relevantes:** `setup_panels/step2_zones.py`, `carcounter/config_io.py`, `carcounter/runtime.py`, `carcounter/counting.py`, `tests/test_counting_regressions.py`.

- [ ] Guardar mapa de rutas permitidas, ROI y zonas en un perfil distinto al ejemplo de una línea.
- [ ] Añadir validación de geometría que identifique zonas inalcanzables por la región de detección y destinos prematuros, con diagnóstico comprensible.
- [ ] Reproducir A→B, paso junto a una salida sin tomarla y trayectoria incompleta con reglas documentadas.
- [ ] Comparar eventos y matriz origen/destino contra revisión humana del mismo video y tramo.
- [ ] Exportar la matriz origen/destino por grupo EPS también en CSV (hoy está en `routes_by_group` del JSON).
- [ ] Entregar video, JSON con eventos, CSV de tracks/OD y reporte de rutas revisadas, sin presentar IDs como autos.

**Pruebas manuales:** PRUEBA-04 y PRUEBA-06. **Cierre:** rutas del alcance revisadas, incidentes clasificados y umbrales acordados alcanzados; no basta conservar los cruces de una sola línea.

## TODO-029: Movimiento de cámara y geometría del conteo `added: 2026-09-07`

**Prioridad:** P0 cuando afecta el tramo presentado. **Estado:** monitor implementado (ver [2609](TASK_COMPLETED/2609.md)); corrección geométrica pendiente. Mediciones de deriva en [VERIFIED_STATE.md](GUIDES/VERIFIED_STATE.md). En el video completo, contra el frame de las 3:00: estable (5 px o menos) entre 1:30 y 9:30; 6 a 9 px dentro del tramo oficial; 7 a 19 px antes de 1:15 y 5 a 13 px después de 9:44 ([detalle](GUIDES/COUNTING_SCOPE.md#estabilidad-del-dron-en-el-video-completo)).

**Especificación:** elegir un sistema de referencia único para imagen, cajas, ROI, exclusiones y zonas/líneas. Comparar estabilizar imágenes antes de inferencia frente a transformar coordenadas; documentar qué se hace en bordes sin cobertura y cómo afecta la firma de caché. No reutilizar una caché incompatible ni aplicar dos compensaciones inconsistentes. La compensación del tracker BoT-SORT no mueve las zonas de conteo.

- [ ] Pedir a EPS o al operador los archivos originales del dron (`DJI_*.MP4` y `.SRT`) de cada vuelo: los videos actuales perdieron la telemetría por frame al exportarse ([detalle](GUIDES/COUNTING_SCOPE.md#metadatos-del-video)).
- [ ] Perfil con varios tramos: guardar en un solo perfil el rango de frames, el frame de referencia y la geometría de cada tramo, y que `main.py` cambie de geometría al pasar de tramo, para contar el video completo en una sola pasada sin perder los tracks en los cortes.
- [ ] Una sola geometría para todo el video: transformar zonas, líneas y exclusiones por frame con la similitud estimada respecto al frame donde se dibujaron, y rechazar los frames sin estimación fiable.
- [ ] Mantener sincronizados detección, tracking y geometría durante la corrección elegida.
- [ ] Rechazar cambios de escena, correspondencias insuficientes y regiones sin cobertura; explicar el motivo en la salida.
- [ ] Calibrar tolerancia con casos revisados, no elevarla para ocultar el fallo.
- [ ] Comparar FP/FN y eventos antes/después sobre el mismo tramo humano, incluyendo estabilidad de los puntos físicos de entrada/salida.

**Prueba manual:** PRUEBA-07. **Cierre:** mejora medida de las rutas afectadas y rechazo verificable cuando no se puede mantener el encuadre. El control de 5 px es experimental y está desactivado por defecto.

## TODO-036: Replay y control de cámara desde el wizard `added: 2026-09-14`

**Prioridad:** P2. El resto del trabajo heredado se cerró (ver [2609](TASK_COMPLETED/2609.md)).

- [ ] `python -m carcounter` no expone `--record-detections`/`--replay-detections` ni `--camera-max-drift-px` (este último sí se toma de `settings.camera_max_drift_px` del perfil) y solo muestra el código de salida de `main.py`, no el motivo del fallo.

## Fuera del foco de la presentación

### TODO-023: Rendimiento del flujo real

**Prioridad:** P1 después de la referencia humana. **Depende de:** TODO-028 y exactitud estable de detección/rutas.

**Hallazgo:** `scripts/benchmark_pipeline.py` no carga el perfil del aforo: usa zonas vacías, parámetros propios, una copia de frame como visualización y JPEG como aproximación de escritura. No representa el pipeline real completo. `main.py --benchmark` sí ejecuta el perfil, pero agrupa detección y tracking en la etapa `detection`.

- [ ] Hacer que el benchmark comparta perfil, ROI, clases, filtros y tracker con producción.
- [ ] Separar inferencia, asociación, conteo, control de cámara, dibujo y escritura; reportar además tiempo total, carga de pesos/hashes y dispositivo.
- [ ] Medir memoria y tiempos en el tramo objetivo sin mezclar varias corridas que compitan por CPU/GPU.
- [ ] Si el cuello medido lo justifica, probar prelectura, batching de detección o escritura asíncrona manteniendo orden de frames y semántica del tracker.
- [ ] Comparar eventos y métricas antes/después; distinguir FPS de replay de FPS con inferencia.

**Cierre:** reducción medida de tiempo/memoria con exactitud conservada en los casos revisados. No asumir que GPU, más resolución o batches mejorarán esta máquina.

### TODO-024: Evaluar formatos ONNX y TensorRT

**Prioridad:** P2, después de TODO-023.

- [ ] Verificar que un modelo exportado carga y conserva nombres de clases, cajas, filtros, tracking y eventos sobre el perfil revisado.
- [ ] Comparar `.pt` y `.onnx` con el mismo `imgsz`, video, dispositivo y métricas humanas, incluyendo tiempo de carga y errores numéricos.
- [ ] Añadir `--half` u otros formatos solo si el backend/hardware lo soporta y una prueba muestra beneficio; el script actual solo tiene `--model` e `--imgsz`.
- [ ] Evaluar TensorRT únicamente con CUDA disponible y después de ONNX; registrar versiones y compatibilidad.

**Cierre:** mejora medida con precisión aceptada. No se promete aceleración 2x/3x ni equivalencia automática de FP16.

### TODO-019: Persistencia local libSQL

**Prioridad:** secundaria. **Estado:** pruebas con el backend real pasan (incluye eventos y migración); falta contrastar con un run real.

- [ ] Verificar valores guardados contra JSON/OD del mismo run, sin almacenar un proceso fallido como completado.

**Cierre:** pruebas del backend real, datos consistentes y evidencia de lectura posterior. Embeddings y búsqueda de vehículos por similitud quedan como idea futura.

### TODO-025: Verificación visual de vectores de dirección

**Prioridad:** secundaria; el foco de presentación son rutas origen/destino.

- [ ] Revisar visualmente en escritorio que guardar/reabrir conserve puntas, nombres y orientación de las flechas.
- [ ] Comprobar con un movimiento conocido que la dirección asignada coincide con lo dibujado, sin confundirla con una ruta A→B.

**Prueba manual:** PRUEBA-05, con copia de perfil en modo `directions`. **Cierre:** prueba visual registrada; no volver a implementar un dibujado que ya existe.

### TODO-026: Verificar API local opcional

**Prioridad:** secundaria.

- [ ] Ejecutar con `fastapi`, `uvicorn` y dependencias de prueba; verificar respuestas, errores y stream durante procesamiento real.
- [ ] Comparar conteo/frames de la API con JSON del mismo run; comprobar historial solo cuando la DB esté disponible.

Desde 2026-09-14 `tests/test_api.py` corre completo con `TestClient` (incluye `events_count` y `recent_events`); eso no prueba el servicio durante un procesamiento real.

**Cierre:** evidencia con backend instalado. No publicar el servicio ni cambiar su exposición.

### TODO-022: Evaluación de supervision

**Prioridad:** investigación diferida. El [informe](RESEARCH/SUPERVISION_EVAL.md) propone descartar la migración completa.

- [ ] Si se retoma una migración, contrastar la API que se vaya a instalar y medir contra el mismo perfil/video; el informe no ejecutó benchmark ni prototipo.
- [ ] Registrar decisión con evidencia de mantenimiento o comportamiento, sin tratar estimaciones de milisegundos como tiempos medidos.

No se reabre antes de validar detección y rutas; cambiar de biblioteca no es un resultado de producto por sí mismo.

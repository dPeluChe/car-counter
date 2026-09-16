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

**Prioridad:** P0 para que el revisor pueda probar. **Estado:** lógica probada, GUI sin validar en escritorio. La auditoría del 2026-09-15 encontró defectos de pérdida de datos, dibujo, autosave y lanzamiento desde el wizard; fase A y ronda 2 corregidas y verificadas con ventanas ocultas (ver [2609](TASK_COMPLETED/2609.md)), falta la verificación visual. El rediseño del flujo queda en TODO-037.

**Archivos relevantes:** `setup.py`, `setup_panels/calib_tests.py`, `setup_panels/step1_calibration.py`, `setup_panels/step2_preview.py`, `setup_panels/step3_sahi.py`, `carcounter/app_config.py`.

- [ ] Abrir el configurador en el escritorio y confirmar carga del video/modelo del perfil, controles visibles y desplazamiento lateral.
- [ ] Verificar en escritorio lo corregido en la fase A de UI (2026-09-15): zoom ajustado al abrir, ROI visible con zoom y pan, espacio dentro de nombres sin activar pan, pausar el preview y dibujar sobre ese frame, rangos de filtros visibles en la barra lateral, mensajes de validación al guardar, diálogo de checkpoint después de cargar el perfil.
- [ ] Verificar el wizard en escritorio: "Configurar zonas" abre el configurador con el perfil elegido y al volver informa si se guardó; "Ejecutar" crea la carpeta de corrida, "Cancelar" detiene el proceso y un error muestra las últimas líneas del log; los botones caben en la ventana.
- [ ] Verificar en escritorio lo corregido en la ronda 2 (2026-09-15): dibujar y quitar la ROI de inferencia arrastrando sobre el video y confirmar que se guarda y se relee; abrir con `--model` explícito y comprobar que el perfil no lo pisa; cargar un perfil sin `sahi.enabled` y confirmar que SAHI queda apagado; guardar un perfil sin tocar el tracker y comparar que no cambió ningún campo.
- [ ] Verificar en escritorio el preview con detecciones: la ventana no se congela y las cajas van uno o dos segundos atrasadas respecto al video (comportamiento esperado, no defecto); un error apaga las detecciones y el video sigue.
- [ ] Verificar en escritorio el wizard de la ronda 2: "Ejecutar" con un perfil inválido avisa qué corregir en vez de lanzar la corrida; sin perfil preseleccionado; el resumen del Paso 3 muestra modo, geometría, video, modelo y ROI; "Cancelar" cierra un configurador abierto tras confirmar.
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
- [ ] Con zonas del tramo oficial, correr `make review-tracks` y clasificar a mano la causa de cada track perdido y de los primeros candidatos a cambio de ID (oclusión, imagen poco clara, geometría o tracker).
- [ ] Reducir la fragmentación ([cifra actual](GUIDES/VERIFIED_STATE.md)): comparar `track_buffer`, umbrales y BoT-SORT midiendo fragmentación y rutas completas con `make review-tracks`.
- [ ] NMS sin clase en YOLO: `carcounter/detector.py` llama al modelo sin `agnostic_nms`, así que una caja `car` y otra `van` sobre el mismo vehículo sobreviven; ByteTrack asocia por IoU y la segunda caja puede crear un ID nuevo. Solo aplica a la ruta sin SAHI: con SAHI, `carcounter/geometry.py:apply_nms` suprime por IoU sin mirar la clase y ese duplicado no sobrevive. Es la causa probable del mejor candidato del replay (ID 385 `car` → ID 397 `van`, mismo lugar, un frame): en ese replay 38 de los 83 candidatos cambian de clase. Medir con replay antes y después: candidatos con cambio de clase, fragmentación y eventos.
- [ ] Registrar desde `UltralyticsTracker` los tracks perdidos, removidos y creados por frame, para detectar cambios de ID sin heurística de distancia.
- [ ] Exportar el frame absoluto del video en `counting_events` y en el CSV de tracks, para que la referencia humana y los recortes usen la misma numeración que un reproductor.
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

**Prioridad:** P0 cuando afecta el tramo presentado. **Estado:** monitor implementado (ver [2609](TASK_COMPLETED/2609.md)); corrección geométrica pendiente. Mediciones de deriva en [VERIFIED_STATE.md](GUIDES/VERIFIED_STATE.md). En el video completo, contra el frame de las 3:00: estable (casi siempre 5 px o menos) entre 1:30 y 9:30; 0.1 a 9 px dentro del tramo oficial; de 19 bajando a 5.5 px antes de 1:15 y 5 a 13 px después de 9:44 ([detalle](GUIDES/COUNTING_SCOPE.md#estabilidad-del-dron-en-el-video-completo)).

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

## TODO-037: Rediseño del flujo de configurador y wizard (fase B) `added: 2026-09-15`

**Prioridad:** P1, después de corregir los defectos de fase A y de la revisión en escritorio (TODO-033). **Evidencia:** auditoría de UI del 2026-09-15 (configurador, wizard y prueba dinámica con ventanas ocultas).

- [ ] Configurador en pasos EPS: perfil y fuente, exclusiones, zonas de entrada/salida por acceso, validar detección (opcional), tracking y reglas de conteo, resumen y guardar. La región de inferencia ya se dibuja y se edita desde el Paso 1 (ronda 2).
- [ ] Controles para campos que hoy solo se copian del perfil: `camera_max_drift_px`, `min_origin_frames`, `min_dest_frames`, `min_crossing_frames`, `match_thresh`, tolerancia por línea.
- [ ] Confianza por clase generada desde las clases del modelo cargado (incluye bicycle, tricycle) en vez de sliders fijos car/moto/bus/truck/van.
- [ ] Mostrar detecciones descartadas (ROI, exclusión, filtros de muestras) con otro color y contador; cuadrícula SAHI calculada sobre la ROI.
- [ ] Sidebar con scroll de rueda y acciones principales fijas fuera del scroll; seleccionar un elemento carga su nombre y permite renombrar; deshacer también en exclusiones y `Command-z` en macOS.
- [ ] Wizard: paso de perfil al inicio con resumen y `AppConfig.validate()`; paso de resultados con resumen, "Abrir carpeta", "Revisar tracks" (`review_incomplete_tracks.py`) y "Validar rutas" (`validate_routes.py`).
- [ ] Wizard: opciones de corrida faltantes (inicio y máximo de frames, SAHI, dispositivo, sin ventana, grabar o repetir caché, deriva de cámara); cubre también TODO-036.

## TODO-038: Costo de SAHI por tile y su efecto en las clases `added: 2026-09-15`

**Prioridad:** P1, después de la referencia humana (TODO-028). **Estado:** medido, sin cambio aplicado. **Depende de:** TODO-028 para tener contra qué comparar que no sea la configuración actual.

**Hallazgo:** SAHI reescala cada tile a `settings.imgsz` (1600 por defecto), así que un tile de 512 se amplía 3.1x. `carcounter/detection.py:detect_objects` reasigna `sahi_model.image_size` en cada frame y le gana a lo que fija `carcounter/runtime.py:load_sahi`.

**Medido** (`glorieta_test1min`, VisDrone, tile 512, overlap 0.2, conf 0.10, una corrida por configuración, las tres seguidas en la misma sesión):

| `image_size` | Frame completo | Tramo de 300 frames con ROI | Eventos | Ligeros | Pesados |
|---|---|---|---|---|---|
| 1600 (actual) | 61 602 ms/frame | 73.6 s (4.08 FPS) | 5 | 3 | 2 |
| 640 | 9 316 ms/frame | 19.8 s (15.12 FPS) | 6 | 5 | 1 |
| 512 | 6 805 ms/frame | 17.1 s (17.53 FPS) | 6 | 5 | 1 |

**Por qué no se cambió:** bajar `image_size` no solo detecta menos, reasigna clases. Con 640 el `truck` del frame 187 sale como `car` y cambia de grupo, de modo que el aforo del tramo pasa de 3 ligeros y 2 pesados a 5 y 1. La clase es justo lo que define el grupo EPS. Además en 1600 salen 245 cajas `motor`, 11 `bicycle`, 6 `tricycle` y 5 `awning-tricycle`; con 640 quedan 99 `motor` y ninguna `bicycle` ni `tricycle`, o sea que el grupo `dos_ruedas` se borra casi entero (en este tramo no hubo eventos de ese grupo, así que no alteró el resultado).

La comparación a frame completo no decide: de las 1022 cajas que 640 pierde contra 1600 (conf ≥ 0.25), solo 68 caen dentro de la ROI, y el resto ocurre en zonas que nunca llegan a evento.

- [ ] Repetir sobre varios tramos y contra referencia humana revisada, no contra la salida de 1600, antes de mover el valor.
- [ ] Separar el `imgsz` del frame completo del tamaño con que se infiere cada tile: hoy es el mismo campo y por eso el costo escala con una resolución que el tile no tiene.
- [ ] Medir el efecto sobre los grupos EPS, no solo sobre el total de eventos (`routes_by_group`).

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

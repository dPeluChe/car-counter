# Estado verificado del flujo

Revisión: 2026-09-14. Fuentes: código local, suite de pruebas y artefactos indicados. Implementado no significa validado en producción.

## Capacidades y evidencia

| Área | Implementación existente | Evidencia y límite |
|---|---|---|
| Detección | YOLO, SAHI y RF-DETR entregan cajas globales al tracker; clases resueltas desde el modelo | Pruebas de integración; ejecución real con YOLO VisDrone. No hay comparación humana que demuestre un detector ganador |
| Calibración | Perfil compartido, muestras por frame, correspondencia IoU y filtros explícitos desde cinco muestras | Funciones probadas. La interfaz Tk no se pudo abrir en esta sesión |
| Tracking | ByteTrack, BoT-SORT, SORT y wrapper opcional OC-SORT | ByteTrack y BoT-SORT se ejecutaron con la misma caché. El wrapper rechaza `with_reid=true`; BoT-SORT aquí no implica ReID de apariencia |
| Conteo | Zonas, líneas finitas con confirmación y direcciones | Pruebas sintéticas y replay de una línea. Zonas A→B todavía sin demostración humana del aforo completo |
| Clase de vehículo | Mayoría por track hasta el primer conteo, conservada después | Pruebas de ruido de clase. Cambiaron 44 clases de tracks en el replay; no se han revisado como correcciones humanas |
| Eventos | `counting_events` con frame, ID, clase, ruta y geometría | Seis eventos del video real y pruebas de conservación tras purga |
| Evaluación | Cajas por IoU/clase; eventos por ruta, clase y tiempo | Pruebas con errores controlados. Emparejar eventos no prueba identidad física del auto |
| Cámara | ORB/RANSAC opcional; detiene si hay deriva excesiva o estimación no fiable | Tramo estable de 60 frames aprobado; otra ejecución detenida en frame 228. No estabiliza video ni geometría |
| Replay | Caché SQLite de cajas previas a filtros/tracking, firma y cierre completo | Comparaciones de eventos y trayectorias. Evita inferencia; sus FPS no son FPS del detector |
| Automatización | Instalador de cron y consulta de cuota | Pruebas simuladas de condiciones. Cron no instalado; consulta real bloqueada al iniciar estado local de Codex |

## Caso reproducible local

Perfil: [aerial_counting.example.json](aerial_counting.example.json).

| Campo | Valor comprobado |
|---|---|
| Video | `assets/glorieta_test1min.mp4`, 1920×1080, 1799 frames |
| SHA-256 | `92f2dac20caedb03a36704a60080e260fea13a6b4b691cc8760accffb2708c8a` |
| Modelo | `models/yolo/yolov8l-visdrone.pt` |
| Tramo de demo | Frames 1-300, unos diez segundos |
| Región de inferencia | `[680,350,960,750]`, en coordenadas originales |
| Resolución de inferencia | `imgsz=640` |
| Piso de confianza | `0.10` |
| Tracker de referencia | ByteTrack; umbral alto/nuevo `0.25`, bajo `0.10`, buffer `30`, `fuse_score=false` |
| SAHI | Desactivado en el perfil de referencia |
| Línea | Anillo oeste, `(750,550)` a `(865,550)`, dos observaciones de confirmación |
| Resultado del sistema | Seis cruces: cinco autos y un bus. No es referencia humana |

La caché `output/aerial_low_conf.sqlite` contiene 300 frames. No sirve para ejecutar el minuto completo ni para cambiar ROI, resolución, modelo o SAHI. La firma incluye parámetros adicionales; el programa valida compatibilidad. Puede aumentarse el piso de confianza, pero no recuperar cajas debajo del piso grabado.

## Artefactos existentes

| Archivo local | Uso |
|---|---|
| `output/aerial_demo_20260914.mp4` | Video de 300 frames; se revisó visualmente el último frame, no se hizo conteo humano integral |
| `output/aerial_demo_20260914.json` | Resultado asociado al video |
| `output/aerial_events_consensus.json` | Resultado del replay final, con eventos |
| `output/aerial_events_consensus_tracks.csv` | Trayectorias y clases del replay final |
| `output/aerial_events_truth_template.json` | Plantilla vacía con `reviewed=false`; no es ground truth |
| `output/camera_normal.json`, `output/camera_fast.json` | Muestreo de movimiento del fondo; puntos de control distintos entre videos |

Los máximos estimados de deriva fueron 7.8113 px en el normal y 85.2845 px en el acelerado. No son velocidades de autos ni porcentajes de error. El umbral de 5 px se usó como experimento, no como tolerancia aprobada del proyecto.

## Validación automática y límites

La última ejecución de `env/bin/python -m pytest -q` aprobó 316 pruebas y omitió 15 por dependencias opcionales. Las omisiones no equivalen a pruebas aprobadas de DB/API.

No hay porcentaje de precisión humana confirmado, nueva calibración de todas las entradas/salidas, estabilización automática, entrenamiento de pesos, benchmark de ONNX/TensorRT ni despliegue verificado. El backlog describe sus criterios; no deben presentarse como capacidades ya probadas.

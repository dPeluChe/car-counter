# Mejoras de detección y calibración, 7 de septiembre de 2026

La calibración y ejecución comparten el detector y filtros. ByteTrack y BoT-SORT reciben cajas globales de YOLO, SAHI o RF-DETR. La caché permite repetir el tracking y conteo sin cargar los pesos ni ejecutar inferencia.

## Evidencia de ejecución

Video `glorieta_test1min.mp4`, VisDrone, ROI `[680,350,960,750]`, resolución 640 y CPU. Los primeros cinco experimentos usan los mismos 300 frames; SAHI usa únicamente los primeros 12.

| Prueba | Confianza mínima | Tracker / fusión | Tiempo del loop | FPS | IDs | Cruces |
|---|---:|---|---:|---:|---:|---:|
| Detección compartida y grabación | 0.25 | ByteTrack / true | 56.81 s | 5.28 | 280 | 6 |
| Replay de esa grabación | 0.25 | ByteTrack / true | 2.41 s | 124.37 | 280 | 6 |
| Perfil con asociación de cajas débiles | 0.10 | ByteTrack / false | 57.40 s | 5.23 | 282 | 6 |
| Replay del perfil nuevo | 0.10 | ByteTrack / false | 2.71 s | 110.60 | 282 | 6 |
| Replay con compensación de movimiento | 0.10 | BoT-SORT / false | 6.76 s | 44.38 | 283 | 6 |
| SAHI, tiles 256, 12 frames | 0.10 | ByteTrack / false | 30.16 s | 0.40 | 87 | 0 |

Los dos pares de CSV de inferencia/replay son idénticos byte por byte, incluyendo IDs y resúmenes de trayectorias. Las seis detecciones de cruce fueron un bus y cinco autos. El replay del perfil nuevo fue unas 21 veces más rápido que su grabación en estas ejecuciones; esa diferencia proviene de evitar inferencia, no de acelerar el detector.

BoT-SORT no cambió el total de cruces de este tramo. La prueba corta de SAHI verifica integración y persistencia del tracker, no permite comparar exactitud de aforo. Los tiempos no incluyen carga de pesos ni lectura de hashes; algunas pruebas compartieron CPU. No son mediciones de producción en GPU.

Artefactos locales:

- `output/aerial_shared*` y `output/aerial_replay*`: primera comparación.
- `output/aerial_low_conf*`: perfil nuevo, caché y repetición.
- `output/aerial_botsort_replay*`: comparación con BoT-SORT.
- `output/aerial_sahi*`: integración SAHI con ByteTrack.
- `output/aerial_review.mp4`, JSON y CSV: video final de 300 frames con marcador de conteo confirmado. El CSV coincide con la inferencia original. Se revisó visualmente el último frame renderizado.

## Fallos corregidos en esta etapa

- Calibración, vista previa y scripts utilizaban IDs COCO incluso con VisDrone. Ahora resuelven las clases desde los pesos cargados.
- La vista global elegía el método con más cajas y cambiaba los filtros; el recuadro se validaba con una inferencia ampliada distinta a producción. Ahora se prueba el perfil real y las muestras de varios frames, con IoU mínimo de 0.50.
- Los filtros por tamaño se activaban al dibujar un solo vehículo. Ahora requieren una acción explícita sobre un conjunto de muestras; limpiarlas también retira restricciones cargadas.
- En la versión instalada, fusionar confianza e IoU en la segunda asociación impedía recuperar detecciones de confianza baja. El perfil nuevo usa `fuse_score=false`, con pruebas de continuidad y de rechazo de IDs nuevos débiles.
- SAHI forzaba SORT. Ahora fusiona detecciones antes del tracker seleccionado y comparte confianza y resolución con la calibración.
- El evaluador ignoraba las clases al emparejar y permitía que errores entre frames se compensaran. Ahora separa localización y clasificación, suma errores por frame y utiliza ROI y filtros reales.
- Las preetiquetas podían sobrescribir correcciones humanas. Ahora conserva archivos existentes y exige revisión confirmada para evaluar.
- Las excepciones podían terminar con mensaje de éxito. Ahora el proceso devuelve error y evita exportar un conteo fallido como completado.
- El marcador de demo mostraba IDs como total. Ahora muestra cruces/rutas confirmados y separa los IDs. Las flechas se convierten a caracteres que OpenCV puede dibujar.

## Movimiento de cámara comprobado

Se añadió un monitor ORB/RANSAC del fondo y el comando `scripts/audit_camera_motion.py`. El parámetro opcional `--camera-max-drift-px` de `main.py` comprueba cada frame y detiene el conteo si el desplazamiento supera el umbral o la estimación deja de ser fiable. No corrige la geometría automáticamente.

| Ejecución | Resultado |
|---|---|
| Video normal completo, muestras cada 30 frames | Desplazamiento máximo estimado de 7.8113 px en los puntos de conteo |
| Video acelerado, muestras cada 10 frames | Desplazamiento máximo estimado de 85.2845 px en sus puntos configurados |
| Replay normal con límite 5 px, comprobación por frame | Detenido en frame 228, desplazamiento 5.2119 px, sin JSON ni CSV de resultado terminado |
| Mismo replay limitado a 60 frames | 60 comprobaciones aprobadas, desplazamiento máximo 1.3751 px, metadatos exportados |

Los dos videos usan geometrías distintas; estos valores no comparan precisión del detector ni velocidad de vehículos. Los informes son `output/camera_normal.json`, `output/camera_fast.json` y `output/aerial_camera_stable.json`. El umbral de 5 px necesita validación humana antes de adoptarse como criterio de producción. La comprobación por frame encontró el exceso antes que el muestreo cada 30 frames.

## Verificación y límites

281 pruebas aprobadas, 15 omitidas por dependencias opcionales. Incluyen replay real de CLI con video sintético, prohibición de cargar pesos durante replay, conteo de cruce, fallos de tracking o comprobación de cámara sin exportación exitosa, cachés incompatibles/incompletas, clases de VisDrone, asociación débil, SAHI global y evaluación con errores controlados. Las pruebas de cámara cubren traslación, rotación, escala de coordenadas, movimiento dentro de la ROI y falta de textura. Pasaron compilación de Python y `git diff --check`.

No se pudo abrir la interfaz Tk en este entorno: incluso `tkinter.Tk()` en un proceso mínimo terminó antes de crear la ventana. Se probaron sus funciones de detección y configuración, pero el desplazamiento y los controles requieren revisión visual en el escritorio del usuario.

No hay nuevas anotaciones humanas del video real. Mantener seis cruces no demuestra la exactitud de toda la glorieta. El perfil sigue siendo parcial; faltan geometría del aforo completo, corrección del movimiento de cámara y comparación contra conteo humano. No se activó estabilización geométrica ni se entrenaron pesos.

La [guía de calibración y replay](../GUIDES/DETECTION_TUNING.md) contiene los comandos y criterios. Los cambios están locales, sin commit, PR ni despliegue.

# Car Counter — atajos de ejecucion y pruebas.
# Uso: `make help`. Variables sobreescribibles: make run VIDEO=assets/otro.mp4 FRAMES=3000

PYTHON  ?= env/bin/python
VIDEO   ?= assets/glorieta_fast.MP4
CONFIG  ?= config/config.json
MODEL   ?= models/yolo/yolov11l.pt
FRAMES  ?= 1500
OUTDIR  ?= output
TRUTH   ?= data/validation/route_truth.json
RESULTS ?= $(OUTDIR)/results.json
ARGS    ?=

.DEFAULT_GOAL := help

.PHONY: help install setup run run-full run-aerial replay-aerial segment-video test benchmark \
        validate-routes val-extract val-prelabel val-evaluate clean

help: ## Muestra esta ayuda
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## Instala dependencias en el entorno env/
	$(PYTHON) -m pip install -r requirements.txt

setup: ## Abre el configurador GUI para dibujar zonas (genera CONFIG)
	$(PYTHON) setup.py --video $(VIDEO) --config $(CONFIG)

run: ## Corre el pipeline en un clip corto (FRAMES frames) -> results.json + od_matrix.csv
	$(PYTHON) main.py --config $(CONFIG) --video $(VIDEO) --max-frames $(FRAMES) \
		--output-json $(OUTDIR)/results.json --output-od-csv $(OUTDIR)/od_matrix.csv

run-full: ## Corre el pipeline sobre el video completo
	$(PYTHON) main.py --config $(CONFIG) --video $(VIDEO) \
		--output-json $(OUTDIR)/results.json --output-od-csv $(OUTDIR)/od_matrix.csv

run-aerial: ## Demo de aforo en video normal con VisDrone y recorte (300 frames)
	$(PYTHON) main.py --config docs/GUIDES/aerial_counting.example.json --no-sahi \
		--headless --max-frames 300 --output $(OUTDIR)/aerial_demo.mp4 \
		--output-json $(OUTDIR)/aerial_demo.json --output-tracks-csv $(OUTDIR)/aerial_demo_tracks.csv

replay-aerial: ## Misma demo desde la cache aerial_low_conf.sqlite, sin inferencia ni video
	$(PYTHON) main.py --config docs/GUIDES/aerial_counting.example.json --no-sahi \
		--headless --no-save --max-frames 300 --replay-detections $(OUTDIR)/aerial_low_conf.sqlite \
		--output-json $(OUTDIR)/aerial_replay.json --output-tracks-csv $(OUTDIR)/aerial_replay_tracks.csv

segment-video: ## Divide VIDEO en tramos de camara estable -> segments.json + frame de referencia por tramo
	$(PYTHON) scripts/segment_video.py --video $(VIDEO) --output-json $(OUTDIR)/segments.json \
		--frames-dir $(OUTDIR)/segments $(ARGS)

test: ## Corre la suite de tests
	$(PYTHON) -m pytest tests/ -v

benchmark: ## Mide ms/frame por etapa del pipeline
	$(PYTHON) scripts/benchmark_pipeline.py --video $(VIDEO) --model $(MODEL)

# --- Validacion end-to-end del conteo de rutas (origen -> destino) ---
validate-routes: ## Compara RESULTS vs conteo humano (TRUTH) por ruta; ARGS extra
	$(PYTHON) scripts/validate_routes.py --results $(RESULTS) --truth $(TRUTH) $(ARGS)

# --- Validacion de deteccion por frame (flujo LabelMe) ---
val-extract: ## Paso 1: extrae y dedupe frames del video
	$(PYTHON) scripts/extract_validation_frames.py --video $(VIDEO)

val-prelabel: ## Paso 2: pre-etiqueta frames con YOLO teacher
	$(PYTHON) scripts/pre_label_frames.py --model $(MODEL)

val-evaluate: ## Paso 4: evalua deteccion vs ground truth LabelMe
	$(PYTHON) scripts/evaluate_pipeline.py --config $(CONFIG)

clean: ## Borra salidas generadas (output/ y results)
	rm -rf $(OUTDIR)/*.mp4 $(OUTDIR)/*.json $(OUTDIR)/*.csv $(OUTDIR)/benchmarks

REPO := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
VENV := $(REPO)/.venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
UVICORN := $(VENV)/bin/uvicorn
HOST ?= 127.0.0.1
PORT ?= 8787

.PHONY: help install start stop health

help: ## Show targets
	@grep -E '^[a-zA-Z0-9_-]+:.*?##' $(MAKEFILE_LIST) | awk -F':.*?## ' '{printf "  %-12s %s\n", $$1, $$2}'

install: ## Create .venv and install deps
	python3 -m venv "$(VENV)"
	"$(PIP)" install -U pip
	"$(PIP)" install -r "$(REPO)/requirements.txt"

start: ## Start Linterna (creates data/ + SQLite on boot)
	@test -x "$(UVICORN)" || $(MAKE) install
	mkdir -p "$(REPO)/data"
	cd "$(REPO)" && LINTERNA_DATA="$(REPO)/data" "$(UVICORN)" server.main:app --host "$(HOST)" --port "$(PORT)" --reload

health: ## curl /health
	curl -fsS "http://$(HOST):$(PORT)/health" && echo

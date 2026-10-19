# VESK — raccourcis de développement
SHELL := /bin/bash
PY ?= python3
TARGET ?= $(HOME)/.claude/skills

.PHONY: help install link uninstall test selftest demo clean

help:
	@echo "make install     installe les 19 skills dans $(TARGET)"
	@echo "make link        installation par liens symboliques"
	@echo "make test        tests unitaires (sans FFmpeg)"
	@echo "make selftest    38 contrôles + pipeline de bout en bout"
	@echo "make demo        génère une démo dans ./demo"
	@echo "make clean       supprime les caches Python"

install:
	bash scripts/install.sh --target "$(TARGET)"

link:
	bash scripts/install.sh --target "$(TARGET)" --mode link --force

uninstall:
	@for d in skills/*/; do rm -rf "$(TARGET)/$$(basename $$d)"; done
	@echo "skills retirés de $(TARGET)"

test:
	$(PY) -m unittest discover -s tests -v

selftest:
	bash scripts/selftest.sh

demo:
	@mkdir -p demo
	@bash scripts/demo.sh demo

clean:
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
	find . -name '*.pyc' -delete

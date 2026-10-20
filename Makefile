# VESK — raccourcis de développement
SHELL := /bin/bash
PY ?= python3
TARGET ?= $(HOME)/.claude/skills

.PHONY: help install link test validate selftest demo clean

help:
	@echo "make install    installe les 20 skills dans $(TARGET)"
	@echo "make link       installe par liens symboliques (mise à jour instantanée)"
	@echo "make test       tests unitaires (sans FFmpeg)"
	@echo "make validate   vérifie les SKILL.md et exécute chaque CLI en --help"
	@echo "make selftest   38 contrôles + pipeline de bout en bout"
	@echo "make demo       génère une démo complète dans ./demo"
	@echo "make clean      supprime les caches Python"

install:
	bash scripts/install.sh --target "$(TARGET)"

link:
	bash scripts/install.sh --target "$(TARGET)" --mode link --force

test:
	$(PY) -m unittest discover -s tests -v

validate:
	$(PY) tests/validate_skills.py --help-check

selftest:
	bash scripts/selftest.sh

demo:
	@mkdir -p demo
	bash scripts/demo.sh demo

clean:
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
	find . -name '*.pyc' -delete

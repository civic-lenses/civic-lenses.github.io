# AI-assisted (Claude Code, claude.ai) — https://claude.ai
-include .env
export

.DEFAULT_GOAL := help

.PHONY: help venv install data features train run notebook lint clean

help:
	@echo ""
	@echo "\033[2m# Setup\033[0m"
	@echo "  \033[36mvenv\033[0m       Create .venv and install all dependencies"
	@echo "  \033[36minstall\033[0m    Install Python dependencies (no venv)"
	@echo "  \033[36mnotebook\033[0m   Launch Jupyter in notebooks/"
	@echo ""
	@echo "\033[2m# Data & Models\033[0m"
	@echo "  \033[36mdata\033[0m       Fetch raw data from all sources"
	@echo "  \033[36mfeatures\033[0m   Preprocess and build unified dataset"
	@echo "  \033[36mtrain\033[0m      Train all three models"
	@echo ""
	@echo "\033[2m# App\033[0m"
	@echo "  \033[36mrun\033[0m        Start the app locally"
	@echo ""
	@echo "\033[2m# Dev\033[0m"
	@echo "  \033[36mlint\033[0m       Run ruff linter"
	@echo "  \033[36mclean\033[0m      Remove __pycache__ and .pyc files"
	@echo ""

venv:
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r requirements.txt jupyter ipykernel
	.venv/bin/python -m ipykernel install --user --name civic-lenses --display-name "civic-lenses"
	@echo "\033[32m  venv ready — run: source .venv/bin/activate\033[0m"

install:
	pip3 install -r requirements.txt

notebook:
	.venv/bin/jupyter notebook notebooks/

data:
	python3 scripts/make_dataset.py

features:
	python3 scripts/preprocess.py

train:
	python3 scripts/naive_baseline.py
	python3 scripts/classical.py

run:
	python3 main.py

lint:
	ruff check .

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; \
	find . -name "*.pyc" -delete

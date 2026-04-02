##
## Notion Intelligence Layer — developer Makefile
## Usage: make <target>
##

VENV        := .venv
PYTHON      := $(VENV)/Scripts/python
PIP         := $(VENV)/Scripts/pip
PYTEST      := $(VENV)/Scripts/pytest
ACTIVATE    := $(VENV)/Scripts/activate

IMAGE       := notion-agent
CHROMA_VOL  := notion-agent-chroma

.DEFAULT_GOAL := help

# ─── Setup ─────────────────────────────────────────────────────────────────

.PHONY: venv
venv:                          ## Create the virtual environment
	python -m venv $(VENV)
	$(PIP) install --upgrade pip

.PHONY: install
install: venv                  ## Install all runtime dependencies
	$(PIP) install -r requirements.txt

.PHONY: install-dev
install-dev: venv              ## Install runtime + dev/test dependencies
	$(PIP) install -r requirements-dev.txt

.PHONY: setup
setup: install-dev             ## Full first-time setup (venv + all deps)
	@echo ""
	@echo "✓  Environment ready.  Run: source $(ACTIVATE)"

# ─── Tests ─────────────────────────────────────────────────────────────────

.PHONY: check
check: test                    ## Gate check — all tests must pass before review or phase gate

.PHONY: test
test:                          ## Run the test suite
	$(PYTEST)

.PHONY: test-cov
test-cov:                      ## Run tests with HTML coverage report
	$(PYTEST) --cov=notion_agent --cov-report=term-missing --cov-report=html

.PHONY: test-fast
test-fast:                     ## Run tests, stop on first failure
	$(PYTEST) -x -q

# ─── Agent commands ────────────────────────────────────────────────────────

.PHONY: ingest
ingest:                        ## Index the Notion workspace into ChromaDB
	$(PYTHON) -m notion_agent ingest

.PHONY: ingest-force
ingest-force:                  ## Force re-index of all pages
	$(PYTHON) -m notion_agent ingest --force

.PHONY: search
search:                        ## Semantic search (usage: make search Q="your query")
	$(PYTHON) -m notion_agent search "$(Q)"

.PHONY: run
run:                           ## Run the agent (usage: make run P="your prompt")
	$(PYTHON) -m notion_agent run "$(P)"

.PHONY: demo
demo:                          ## Run the pre-built workspace audit demo
	$(PYTHON) -m notion_agent demo

.PHONY: demo-dry
demo-dry:                      ## Dry-run the demo (no writes to Notion)
	$(PYTHON) -m notion_agent demo --dry-run

.PHONY: log
log:                           ## Show recent agent runs
	$(PYTHON) -m notion_agent log

.PHONY: rollback
rollback:                      ## Roll back a run (usage: make rollback RUN=20260402_143022)
	$(PYTHON) -m notion_agent rollback "$(RUN)"

# ─── Docker ────────────────────────────────────────────────────────────────
# ChromaDB runs embedded (local file), so no compose needed — just one image.
# The chroma volume persists the index across container runs.

.PHONY: docker-build
docker-build:                  ## Build the Docker image
	docker build -t $(IMAGE) .

.PHONY: docker-ingest
docker-ingest:                 ## Run ingestion inside Docker (mounts chroma volume + .env)
	docker run --rm \
		--env-file .env \
		-v $(CHROMA_VOL):/data/chroma \
		$(IMAGE) ingest

.PHONY: docker-search
docker-search:                 ## Semantic search in Docker (usage: make docker-search Q="query")
	docker run --rm \
		--env-file .env \
		-v $(CHROMA_VOL):/data/chroma \
		$(IMAGE) search "$(Q)"

.PHONY: docker-run
docker-run:                    ## Run the agent in Docker (usage: make docker-run P="prompt")
	docker run --rm \
		--env-file .env \
		-v $(CHROMA_VOL):/data/chroma \
		$(IMAGE) run "$(P)"

.PHONY: docker-demo
docker-demo:                   ## Run the demo in Docker
	docker run --rm \
		--env-file .env \
		-v $(CHROMA_VOL):/data/chroma \
		$(IMAGE) demo

.PHONY: docker-clean
docker-clean:                  ## Remove the Docker image and chroma volume
	docker rmi $(IMAGE) 2>/dev/null || true
	docker volume rm $(CHROMA_VOL) 2>/dev/null || true

# ─── Housekeeping ──────────────────────────────────────────────────────────

.PHONY: clean
clean:                         ## Remove generated artefacts (chroma, pycache, coverage)
	rm -rf .chroma htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true

.PHONY: clean-all
clean-all: clean               ## Also remove the virtualenv
	rm -rf $(VENV)

# ─── Help ──────────────────────────────────────────────────────────────────

.PHONY: help
help:                          ## Print this help
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*##"}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

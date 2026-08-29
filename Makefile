# Chef Andino - one-word verbs for students.
#
#   make setup    create a virtualenv and install the package in editable mode
#   make test     run the whole pytest suite
#   make lint     run ruff (style + docstring checks)
#   make schemas  regenerate the JSON Schema files from the Pydantic models
#   make seed     load synthetic survey responses + inventory into .localdata/
#   make demo     full offline demo: seed -> freeze -> run agent -> show menu

VENV := .venv
PY := $(VENV)/bin/python
CHEF := $(VENV)/bin/chef
CDK_ARGS ?=
SYNTH_CDK_ARGS ?= $(if $(strip $(CDK_ARGS)),$(CDK_ARGS),-c hostname=chef.example.com -c hostedZoneId=Z1234567890 -c hostedZoneName=example.com)

.PHONY: setup test lint schemas seed demo clean infra-synth infra-test cloud-deploy cloud-smoke cloud-load cloud-reset cloud-destroy

setup:
	python3 -m venv $(VENV)
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -e ".[dev,aws]"
	python3 -m venv infra/.venv
	infra/.venv/bin/python -m pip install -r infra/requirements.txt boto3

test:
	$(PY) -m pytest

lint:
	$(VENV)/bin/ruff check src tests scripts

schemas:
	$(PY) -m chef_andino.contracts.export

seed:
	$(CHEF) seed

demo:
	$(CHEF) reset --yes
	$(CHEF) seed
	$(CHEF) stats
	$(CHEF) freeze
	$(CHEF) run-agent
	$(CHEF) show-menu

infra-synth:
	$(PY) scripts/stage_bedrock_corpus.py
	npm --prefix frontend ci
	npm --prefix frontend run build
	JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION=1 npx aws-cdk@2 synth $(SYNTH_CDK_ARGS)

infra-test: infra-synth
	infra/.venv/bin/python -m pytest infra/tests

clean:
	rm -rf $(VENV) .localdata .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -not -path "./frontend/*" -exec rm -rf {} +

cloud-deploy: test lint schemas infra-test
	@test -n "$(strip $(CDK_ARGS))" || (echo "CDK_ARGS with hostname, hostedZoneId, and hostedZoneName is required" && exit 2)
	$(CHEF) reset --yes
	$(CHEF) seed
	$(CHEF) freeze
	$(CHEF) run-agent
	$(PY) scripts/build_initial_fallback.py
	JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION=1 npx aws-cdk@2 deploy --all \
		--require-approval never --outputs-file .cloud/outputs.json $(CDK_ARGS)
	$(PY) scripts/export_cloud_outputs.py
	$(PY) scripts/cloud_postdeploy.py --ingest --upload-fallback
	$(PY) scripts/cloud_smoke.py

cloud-smoke:
	$(PY) scripts/cloud_smoke.py

cloud-load:
	$(PY) scripts/cloud_smoke.py --load-test

cloud-reset:
	$(PY) scripts/cloud_smoke.py --reset-only

cloud-destroy:
	@test -n "$(strip $(CDK_ARGS))" || (echo "CDK_ARGS with hostname, hostedZoneId, and hostedZoneName is required" && exit 2)
	JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION=1 npx aws-cdk@2 destroy --all --force $(CDK_ARGS)

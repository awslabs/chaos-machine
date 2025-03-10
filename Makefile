timestamp = $(shell date "+%Y%m%d.%H%M")
project_root = $(PWD)

check-env:
	@ $(if $(ENVIRONMENT),,$(error The ENVIRONMENT variable is not set in the environment. Please set and try again.))
	@ $(if $(AWS_DEFAULT_REGION),,$(error The AWS_DEFAULT_REGION variable is not set in the environment. Please set and try again.))

venv: python-version ?= 3.11
venv: install-path ?=
venv:
	python$(python-version) -m venv .venv; \
	source .venv/bin/activate; \
	if [ -n "$(install-path)" ]; then \
		python -m pip install -r requirements.txt -t $(install-path); \
	else \
		python -m pip install -r requirements.txt; \
	fi

pytest/az-disruption: dir = examples/tests
pytest/az-disruption: check-env
	@ cd $(dir); \
	$(MAKE) -f $(project_root)/Makefile venv; \
	source .venv/bin/activate; \
	pytest az-disruption.py -v -s --experiment-template-id ${experiment-template-id}

pytest: pytest/az-disruption

# To install pre-commit to run automatically, add pre-commit to requirements.txt, activate the .venv, then run `pre-commit install`
pre-commit: venv
	source .venv/bin/activate; \
	pre-commit run -a; \
	deactivate

layer/package: dir ?= lambda/layer
layer/package: python-version ?= 3.11
layer/package: path ?= python/lib/python$(python-version)/site-packages
layer/package: schema-path ?= _docs/schemas/chaos-machine-input.json
layer/package: name ?= chaos-machine
layer/package:
	@cd $(dir); \
	$(MAKE) -f $(project_root)/Makefile venv install-path=$(path); \
	mkdir -p schemas; \
	cp ../../$(schema-path) schemas/; \
	zip -r $(name).zip python schemas; \
	deactivate

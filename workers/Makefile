.PHONY: edit train generate smoke-edit smoke-train smoke-generate install

install:
	pip install -e .

edit:
	python edit_worker.py

train:
	python train_worker.py

generate:
	python generate_worker.py

smoke-edit:
	python scripts/smoke_local.py --worker edit --message tests/edit.json

smoke-train:
	python scripts/smoke_local.py --worker train --message tests/train.json

smoke-generate:
	python scripts/smoke_local.py --worker generate --message tests/generate.json

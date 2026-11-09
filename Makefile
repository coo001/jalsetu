PY ?= .venv/bin/python
PORT ?= 8080

.PHONY: test eval run

test:
	$(PY) -m pytest -q

eval:
	$(PY) eval/run_eval.py

run:
	$(PY) -m uvicorn app.main:app --host 0.0.0.0 --port $(PORT)

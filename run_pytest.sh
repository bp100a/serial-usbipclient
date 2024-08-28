#!/bin/bash
# run pytest
source ./venv/Scripts/activate
export PYTHONPATH=./
PYTEST_ARGS=(-n auto -v --timeout=30 --cov --cov-branch --cov-config=.coveragerc)
pytest "${PYTEST_ARGS[@]}"

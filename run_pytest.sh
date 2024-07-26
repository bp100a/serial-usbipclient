#!/bin/bash
# run pytest
export PYTHONPATH=./
PYTEST_ARGS=(-n auto -v --timeout=30 --cov --cov-branch --cov-config=.coveragerc --junitxml="test-reports/pytest_result.xml")
pytest "${PYTEST_ARGS[@]}"
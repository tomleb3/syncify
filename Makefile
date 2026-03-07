.PHONY: init run clean

init:
	uv venv
	. .venv/bin/activate && uv sync

run:
	. .venv/bin/activate && python syncify.py

clean:
	rm -rf .venv __pycache__ .mypy_cache

.PHONY: init setup bot run clean

init:
	uv venv
	. .venv/bin/activate && uv sync

setup:
	. .venv/bin/activate && python setup.py

bot:
	. .venv/bin/activate && python bot.py

run:
	. .venv/bin/activate && python syncify.py

clean:
	rm -rf .venv __pycache__ .mypy_cache

.PHONY: init setup auth bot run clean

init:
	uv venv --clear --quiet
	. .venv/bin/activate && uv sync --locked --quiet

setup:
	. .venv/bin/activate && python setup.py

auth:
	. .venv/bin/activate && python auth.py

bot:
	. .venv/bin/activate && python bot.py

run:
	gh workflow run syncify.yml
	@echo 'Workflow dispatched. View logs: gh run watch'

clean:
	rm -rf .venv __pycache__ .mypy_cache

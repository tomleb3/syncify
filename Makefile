.PHONY: init setup auth run run-local clean

# Create/update venv and install dependencies
init:
	uv sync --quiet

# Interactive setup (authorize, pick playlists, push to GitHub)
setup:
	uv run python setup.py

# Obtain a Spotify refresh token and push to GitHub
auth:
	uv run python auth.py

# Trigger a sync via the GitHub Actions workflow
run:
	gh workflow run syncify.yml
	@echo 'Workflow dispatched. View logs: gh run watch'

# Run syncify.py locally
run-local:
	uv run python syncify.py

# Remove generated files
clean:
	rm -rf .venv __pycache__ .mypy_cache

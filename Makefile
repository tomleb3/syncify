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
# Optionally set SYNCIFY_GH_REPO=owner/repo to target a different runtime repo.
run:
	gh workflow run syncify.yml $(if $(SYNCIFY_GH_REPO),--repo $(SYNCIFY_GH_REPO))
	@echo 'Workflow dispatched. View logs: gh run watch $(if $(SYNCIFY_GH_REPO),--repo $(SYNCIFY_GH_REPO))'

# Run syncify.py locally
run-local:
	uv run python syncify.py

# Remove generated files
clean:
	rm -rf .venv __pycache__ .mypy_cache

.PHONY: run dev lint fmt seed test clean install

# Install dependencies
install:
	pip install -r requirements.txt

# Run production server
run:
	uvicorn server.app:app --host 0.0.0.0 --port 8000

# Run development server with reload
dev:
	uvicorn server.app:app --reload --host 0.0.0.0 --port 8000

# Initialize database
init-db:
	python -m server.persistence.init_db

# Seed database with test data
seed:
	python -m server.persistence.seed_data

# Run tests
test:
	pytest tests/ -v

# Lint code
lint:
	flake8 server/ tests/ --max-line-length=100 --ignore=E501,W503
	mypy server/ --ignore-missing-imports

# Format code
fmt:
	black server/ tests/ --line-length=100
	isort server/ tests/

# Clean up temporary files
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	rm -rf static/tts/*
	rm -f pharmacy_voice.db

# Start ngrok tunnel (requires ngrok installed)
tunnel:
	ngrok http 8000

# Full setup for development
setup: install init-db seed
	@echo "Setup complete! Now run 'make tunnel' in another terminal and update PUBLIC_HOST in .env"

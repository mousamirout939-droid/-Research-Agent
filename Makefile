.PHONY: install run test eval eval-mock lint clean docker-build docker-run

install:
	pip install -r requirements.txt
	cp -n .env.example .env || true

run:
	python app.py

test:
	pytest -v

eval:
	python -m eval.run_eval

eval-mock:
	python -m eval.run_eval --mock

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache
	find cache -name "*.json" -delete 2>/dev/null || true

docker-build:
	docker build -t research-agent .

docker-run:
	docker run --rm -p 7860:7860 --env-file .env research-agent

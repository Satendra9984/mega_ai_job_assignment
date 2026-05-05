up:
	docker compose up --build

down:
	docker compose down

test:
	docker compose exec backend pytest -v

verify:
	curl -sf http://localhost:8000/openapi.json > /dev/null && echo "backend OK"
	curl -sf http://localhost:3000 > /dev/null && echo "frontend OK"

logs:
	docker compose logs -f backend

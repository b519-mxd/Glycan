FROM python:3.11-slim

WORKDIR /app
RUN pip install --no-cache-dir poetry==1.8.3

COPY pyproject.toml README.md ./
COPY common ./common
COPY literature_retrieval ./literature_retrieval
COPY information_extraction ./information_extraction
COPY evidence_fusion ./evidence_fusion
COPY knowledge_graph ./knowledge_graph
COPY reasoning ./reasoning
COPY api ./api
COPY scripts ./scripts
COPY data ./data
COPY config.json ./config.json

RUN poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi

EXPOSE 8000
CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"]

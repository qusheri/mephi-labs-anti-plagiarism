FROM python:3.12-slim AS algos-builder

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential cmake \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/back/algos
COPY back/algos/CMakeLists.txt ./
COPY back/algos/include ./include
COPY back/algos/src ./src
RUN cmake -S . -B build -DANTIPLAG_ALGOS_BUILD_TESTS=OFF \
    && cmake --build build --target antiplag_algos_cli --config Release


FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY back/requirements.txt ./back/requirements.txt
RUN pip install --no-cache-dir -r back/requirements.txt

COPY back ./back
COPY --from=algos-builder /app/back/algos/build/antiplag_algos_cli /app/back/algos/build/antiplag_algos_cli

ENV ANTIPLAG_ALGOS_CLI=/app/back/algos/build/antiplag_algos_cli

CMD ["uvicorn", "back.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

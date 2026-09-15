# ===================================================
# Cupella Build File
# ===================================================


# Check if file exists and is not empty
assert-files +files:
    #!/usr/bin/env bash
    set -euo pipefail
    for f in {{ files }}; do
        if [ ! -s "$f" ]; then
            echo "ASSERTION FAILED: '$f' fehlt oder ist leer!" >&2
            exit 1
        fi
    done

# Install dependencies for development
install:
    eget quarto-dev/quarto-cli
    eget nektos/act
    eget getzola/zola --to $HOME/.local/bin

# Generate documentation
@docs:
    zola --root docs build

# Generate JSONL file
@test-data:
  python3 -m test.generator -n 5000 -o data/bronze/raw_stream.jsonl

# Stream data to local ingest pipeline
@stream-data amount="5000":
    #!/usr/bin/env bash
    set -euo pipefail
    python3 -m test.generator -n {{amount}} | while read -r line; do
        curl -s -X POST http://127.0.0.1:8080 \
            -H "Content-Type: application/json" \
            -d "$line" > /dev/null
    done

# Build all container images locally
@build:
  # Build Container Images
  podman build -t cupella-bronze container/bronze/
  podman build -t cupella-tasks container/tasks/
  podman build -t cupella-report container/report/

# BRONZE Step: Ingest raw data
@bronze:
  # Run (mounts local directory ./data/bronze ein)
  podman run -d --name cupella-bronze \
    -p 8080:8080 \
    -p 9090:9090 \
    -v ./data/bronze:/data/bronze:Z \
    localhost/cupella-bronze

# SILVER Step: Check data consistency and create OLAP file.
@silver:
    podman run --rm \
        -v {{ invocation_directory() }}/data:/app/data:Z \
        cupella-tasks -m tasks.curate

# GOLD Step: Aggregate data, Create models
@gold:
    podman run --rm \
        -v {{ invocation_directory() }}/data:/app/data:Z \
        cupella-tasks -m tasks.extract
    podman run --rm \
        -v {{ invocation_directory() }}/data:/app/data:Z \
        cupella-tasks -m tasks.forecast

# Generate report.
@report:
    podman run --rm \
        -v "$(pwd):/workspace:Z" \
        -w /workspace \
        cupella-report \
        render reports/telemetry.qmd --output-dir output

# Test the complete pipeline
@test:
    just bronze && sleep 2
    just stream-data
    just silver
    just gold
    just report
    just stop
    just assert-files just assert-files \
        "data/silver/*.parquet" \
        "data/silver/report.html" \
        "data/gold/sensor_forecast.parquet"

# Start local Caddy server for contents
@serve:
    caddy run

# Stop the ingestion daemon
@stop:
    podman stop cupella-bronze
    -podman rm cupella-bronze

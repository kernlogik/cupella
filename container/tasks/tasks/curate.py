from datetime import datetime, timezone
import json
import os

import polars as pl
from jinja2 import Template

WORK_DIR = os.getcwd()

# 1. Schema explizit vorgeben (verhindert unbemerkte Typ-Drifts)
SCHEMA = {
    "event_id": pl.Utf8,
    "timestamp": pl.Utf8,
    "device_id": pl.Utf8,
    "payload": pl.Struct(
        {
            "temperature": pl.Float64,
            "humidity": pl.Float64,
            "status": pl.Utf8,
        }
    ),
}

TEMPLATE = """<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <title>Cupella Audit</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 600px; margin: 2rem auto; }
    table { width: 100%; border-collapse: collapse; }
    td, th { padding: 8px; border-bottom: 1px solid #ddd; text-align: left; }
    td.number { text-align: right; }
    .muted { color: gray }
  </style>
</head>
<body>
  <h2>Pipeline Audit</h2>
  <p class="muted">Processed {{ processed_at_human }}</p>
  <table>
    <tr><th>Input Records</th><td class="number">{{ input_records }}</td></tr>
    <tr><th>Valide Records</th><td class="number"><strong>{{ valid_records }}</strong></td></tr>
    <tr><th>Duplikate</th><td class="number">{{ duplicates_dropped }}</td></tr>
    <tr><th>Ausreisser</th><td class="number">{{ outliers_dropped }}</td></tr>
  </table>
</body>
</html>"""


def process_partition(input_path: str, output_parquet: str, audit_path: str):
    # 2. Ingest
    df_raw = pl.read_ndjson(input_path, schema=SCHEMA)
    initial_count = len(df_raw)

    # 3. Flattening & Typisierung
    df_flattened = df_raw.select(
        pl.col("event_id"),
        pl.col("timestamp").str.to_datetime(time_zone="UTC").dt.replace_time_zone(None).alias("ts"),
        pl.col("device_id"),
        pl.col("payload").struct.field("temperature").alias("temp"),
        pl.col("payload").struct.field("humidity").alias("humidity"),
        pl.col("payload").struct.field("status").alias("status"),
    )

    # 4. Deduplizierung
    df_dedup = df_flattened.unique(subset=["event_id"], keep="first")
    duplicate_count = initial_count - len(df_dedup)

    # 5. Datenqualitäts-Checks
    null_temp_count = df_dedup.filter(pl.col("temp").is_null()).height
    null_humidity_count = df_dedup.filter(pl.col("humidity").is_null()).height

    # Plausibilitätsfilter: Nur plausible Messwerte behalten
    valid_condition = (
        pl.col("temp").is_not_null()
        & pl.col("temp").is_between(-40.0, 85.0)
        & pl.col("humidity").is_between(0.0, 100.0)
    )

    df_clean = df_dedup.filter(valid_condition)
    outlier_count = len(df_dedup) - len(df_clean)

    # 6. Parquet schreiben (nur kuratierte Daten, Snappy oder ZSTD komprimiert)
    df_clean.write_parquet(output_parquet, compression="zstd", statistics=True)

    # 7. Audit-Bericht sichern
    audit_data = {
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "input_records": initial_count,
        "valid_records": len(df_clean),
        "duplicates_dropped": duplicate_count,
        "outliers_dropped": outlier_count,
        "null_temperatures": null_temp_count,
        "null_humidities": null_humidity_count,
    }

    with open(audit_path, "w", encoding="utf-8") as f:
        json.dump(audit_data, f, indent=2)

    dt = datetime.fromisoformat(audit_data["processed_at"])
    audit_data["processed_at_human"] = dt.strftime("%d.%m.%Y %H:%M:%S UTC")
    with open(f"{WORK_DIR}/data/silver/report.html", "w") as f:
        f.write(Template(TEMPLATE).render(**audit_data))


if __name__ == "__main__":
    process_partition(
        input_path=f"{WORK_DIR}/data/bronze/2026-09-15/*.jsonl",
        output_parquet=f"{WORK_DIR}/data/silver/events-2026-09-15.parquet",
        audit_path=f"{WORK_DIR}/data/silver/audit-2026-09-15.json",
    )

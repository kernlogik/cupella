from pathlib import Path
import polars as pl

import os

WORK_DIR = os.getcwd()



def build_gold_hourly(
    silver_glob: str, output_parquet: str = f"{WORK_DIR}/data/gold/sensor_hourly.parquet"
):
    Path(output_parquet).parent.mkdir(parents=True, exist_ok=True)

    (
        pl.scan_parquet(silver_glob)
        .with_columns(pl.col("ts").dt.truncate("1h").alias("window_start"))
        .group_by(["window_start", "device_id"])
        .agg(
            pl.len().alias("sample_count"),
            pl.col("temp").min().round(2).alias("temp_min"),
            pl.col("temp").mean().round(2).alias("temp_avg"),
            pl.col("temp").max().round(2).alias("temp_max"),
            pl.col("temp").quantile(0.95).round(2).alias("temp_p95"),
            pl.col("humidity").mean().round(1).alias("humidity_avg"),
        )
        .sort(["window_start", "device_id"])
        .collect()
        .write_parquet(output_parquet, compression="zstd", statistics=True)
    )


if __name__ == "__main__":
    build_gold_hourly(f"{WORK_DIR}/data/silver/*.parquet")

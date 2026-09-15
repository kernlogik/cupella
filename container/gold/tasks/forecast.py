import logging
import os
from datetime import timedelta
from pathlib import Path
import numpy as np
import polars as pl
from sklearn.linear_model import Ridge

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
WORK_DIR = os.getcwd()


def forecast_sensor(df_device: pl.DataFrame, steps_ahead: int = 3) -> pl.DataFrame:
    device_id = df_device["device_id"][0]
    history_rows = df_device.sort("window_start")
    history = history_rows["temp_avg"].to_list()
    last_time = history_rows["window_start"].max()
    n_points = len(history)

    forecast_rows = []

    # Fall A: Genug Historie für Ridge Regression (mind. 5 Punkte nach Lags -> mind. 7 Stunden)
    if n_points >= 7:
        df_feat = (
            history_rows.with_columns(
                pl.col("temp_avg").shift(1).alias("lag_1"),
                pl.col("temp_avg").shift(2).alias("lag_2"),
                pl.col("temp_avg").rolling_mean(3).alias("roll_3"),
            )
            .drop_nulls()
        )
        X = df_feat.select(["lag_1", "lag_2", "roll_3"]).to_numpy()
        y = df_feat["temp_avg"].to_numpy()

        model = Ridge(alpha=1.0).fit(X, y)
        curr_hist = list(history)

        for step in range(1, steps_ahead + 1):
            x_pred = np.array([[curr_hist[-1], curr_hist[-2], np.mean(curr_hist[-3:])]])
            y_pred = float(model.predict(x_pred)[0])
            target_time = last_time + timedelta(hours=step)
            forecast_rows.append(
                {"window_start": target_time, "device_id": device_id, "temp_avg": round(y_pred, 2), "is_forecast": True}
            )
            curr_hist.append(y_pred)

    # Fall B: Zu wenig Daten -> Naives Modell (letzter Messwert / Persistence)
    else:
        logging.warning(
            f"Sensor '{device_id}' hat nur {n_points} Datenpunkt(e). Nutze naiven Forecast (Persistence)."
        )
        last_val = history[-1]
        for step in range(1, steps_ahead + 1):
            forecast_rows.append(
                {
                    "window_start": last_time + timedelta(hours=step),
                    "device_id": device_id,
                    "temp_avg": round(last_val, 2),
                    "is_forecast": True,
                }
            )

    return pl.DataFrame(forecast_rows)


def run_forecast(
    input_parquet: str = f"{WORK_DIR}/data/gold/sensor_hourly.parquet",
    output_parquet: str = f"{WORK_DIR}/data/gold/sensor_forecast.parquet",
):
    path = Path(input_parquet)
    if not path.exists():
        logging.error(f"Eingabedatei {input_parquet} existiert nicht.")
        return

    df = pl.read_parquet(input_parquet)
    if df.is_empty():
        logging.warning("Eingabetabelle ist leer.")
        return

    df_history = df.select(
        pl.col("window_start"),
        pl.col("device_id"),
        pl.col("temp_avg"),
        pl.lit(False).alias("is_forecast"),
    )

    forecast_dfs = []
    for (device_id,), group in df.group_by(["device_id"]):
        fc = forecast_sensor(group, steps_ahead=3)
        if not fc.is_empty():
            forecast_dfs.append(fc)

    # Immer schreiben: Historie + Vorhersagen
    df_all = pl.concat([df_history, *forecast_dfs]).sort(["device_id", "window_start"])
    Path(output_parquet).parent.mkdir(parents=True, exist_ok=True)
    df_all.write_parquet(output_parquet, compression="zstd")
    logging.info(f"{len(df_all)} Zeilen nach {output_parquet} geschrieben.")


if __name__ == "__main__":
    run_forecast()

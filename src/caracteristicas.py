import pandas as pd

def crear_caracteristicas(df):
    df = df.copy()

    inicio = pd.to_datetime(
        df["fec_deteccion"], errors="coerce"
    )
    fin = pd.to_datetime(
        df["fec_estimada"], errors="coerce"
    )

    df["intervalo_fechas_horas"] = (
        (fin - inicio).dt.total_seconds() / 3600
    ).round(2)

    df.loc[
        df["intervalo_fechas_horas"] < 0,
        "intervalo_fechas_horas"
    ] = float("nan")

    df["dia_semana"] = inicio.dt.dayofweek

    df["es_fin_de_semana"] = (
        df["dia_semana"] >= 5
    ).astype("boolean")

    df["cantidad_areas_reportadas"] = (
        df["areas_afectadas"]
        .fillna("")
        .apply(
            lambda x: len([
                area for area in str(x).split(";")
                if area.strip()
            ])
        )
    )

    return df
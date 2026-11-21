"""Serie historica OHLCV de un activo. Solo lectura."""

import os
from datetime import datetime, timedelta

from pyIol2 import IOLAPIError, IOLClient, Markets


def main() -> None:
    symbol = os.getenv("IOL_SYMBOL", "GGAL")
    dias = int(os.getenv("IOL_HISTORY_DAYS", "30"))
    username = os.environ["IOL_USERNAME"]
    password = os.environ["IOL_PASSWORD"]

    # La API espera "YYYY-MM-DD HH:MM:SS". Se pide desde la apertura del rango.
    hasta = datetime.now()
    desde = hasta - timedelta(days=dias)
    start = desde.strftime("%Y-%m-%d 00:00:00")
    end = hasta.strftime("%Y-%m-%d 23:59:59")

    try:
        with IOLClient(username, password) as client:
            serie = client.get_historical_bars(symbol, start, end, market=Markets.BCBA)
            print(f"{serie.symbol} {serie.market}: {serie.total_bars} velas")
            print(f"  ventana: {start} -> {end}")
            for vela in serie.bars:
                print(
                    f"  {vela.datetime} "
                    f"O={vela.open} H={vela.high} L={vela.low} C={vela.close} "
                    f"V={vela.volume}"
                )
    except KeyError as exc:
        raise SystemExit(f"Falta la variable de entorno {exc}") from exc
    except IOLAPIError as exc:
        raise SystemExit(f"Fallo la consulta a IOL: {exc}") from exc


if __name__ == "__main__":
    main()

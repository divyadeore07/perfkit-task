import csv
import math
from datetime import datetime
from pathlib import Path
import pandas as pd

REQUIRED_COLUMNS = [
    "trade_id", "symbol", "side", "quantity",
    "entry_price", "exit_price", "entry_date", "exit_date", "fees",
]


def _parse_date(text: str) -> pd.Timestamp:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return pd.Timestamp(datetime.strptime(text.strip(), fmt))
        except ValueError:
            pass
    raise ValueError(f"invalid date '{text}'")


def load_trades(filepath: str | Path) -> tuple[pd.DataFrame, list[dict]]:
    path = Path(filepath)
    if not path.is_file():
        raise FileNotFoundError(f"Trade file not found: {filepath}")

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        headers = [h.strip() for h in (reader.fieldnames or [])]
        missing = [c for c in REQUIRED_COLUMNS if c not in headers]
        if missing:
            raise ValueError(f"Missing required columns: {', '.join(missing)}")

        seen, valid, rejections = set(), [], []
        for raw in reader:
            row = {k.strip(): (v or "").strip() for k, v in raw.items() if k}
            tid = row.get("trade_id") or "<missing>"
            sig = tuple(row[c] for c in REQUIRED_COLUMNS)

            if sig in seen:
                rejections.append({"trade_id": tid, "reason": "Exact duplicate of an earlier row"})
                continue
            seen.add(sig)

            try:
                symbol = row["symbol"].upper()
                side = row["side"].upper()
                if not symbol or side not in ("LONG", "SHORT"):
                    raise ValueError(f"Invalid side '{row['side']}' (must be LONG or SHORT)")

                vals = {k: float(row[k]) for k in ("quantity", "entry_price", "exit_price", "fees")}
                if any(not math.isfinite(v) for v in vals.values()):
                    raise ValueError("Non-finite numeric value")
                if vals["quantity"] <= 0 or not vals["quantity"].is_integer():
                    raise ValueError(f"Quantity must be a positive whole number, got '{row['quantity']}'")
                if vals["entry_price"] <= 0 or vals["exit_price"] <= 0 or vals["fees"] < 0:
                    raise ValueError("Prices must be > 0 and fees >= 0")

                entry_dt, exit_dt = _parse_date(row["entry_date"]), _parse_date(row["exit_date"])
                if exit_dt < entry_dt:
                    raise ValueError(f"exit_date ({row['exit_date']}) is before entry_date ({row['entry_date']})")

                valid.append({
                    "trade_id": tid, "symbol": symbol, "side": side,
                    "quantity": int(vals["quantity"]), "entry_price": vals["entry_price"],
                    "exit_price": vals["exit_price"], "entry_date": entry_dt,
                    "exit_date": exit_dt, "fees": vals["fees"],
                })
            except ValueError as err:
                rejections.append({"trade_id": tid, "reason": str(err)})

    return (pd.DataFrame(valid) if valid else pd.DataFrame(columns=REQUIRED_COLUMNS)), rejections
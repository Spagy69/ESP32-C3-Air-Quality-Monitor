"""Sweep prahu detekce nabijeni pro uspavany rezim.

Duvod, proc to je v repu: prahy DOMA cesty se uz jednou naladily na jediny
zaznam a druhy je shodil (viz README, Known Issues). Tenhle skript pousti
navrzene pravidlo pres VSECHNY tri relevantni zaznamy najednou, takze se da
po kazde zmene prahu znovu overit, ze nesedi na hrane.

Bez diakritiky zamerne - konzole na Windows si s ni v pipe neporadi.

Spusteni:  python data/threshold-sweep.py
"""
import csv
import datetime as dt
import os

BASE = os.path.dirname(os.path.abspath(__file__))

# latch/release/confirm musi odpovidat konstantam v packages/sensors.yaml
LATCH_MV = 20.0
RELEASE_MV = 0.0
RELEASE_CONFIRM = 3


def load_voltage(folder):
    path = os.path.join(BASE, folder, "all-sensors.csv")
    rows = []
    with open(path, encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            if not r["entity_id"].endswith("battery_voltage"):
                continue
            try:
                rows.append((dt.datetime.fromisoformat(
                    r["last_changed"].replace("Z", "+00:00")), float(r["state"])))
            except ValueError:
                pass          # unavailable / unknown
    rows.sort()
    return rows


def median3(seq):
    """Same median-of-3 the battery_voltage lambda does, incl. its warm-up."""
    out, h1, h2 = [], None, None
    for t, v in seq:
        out.append((t, v if h2 is None else sorted([v, h1, h2])[1]))
        h2, h1 = h1, v
    return out


def simulate(seq, latch_mv, release_mv, confirm):
    charging, prev, events, count = False, None, [], 0
    for t, v in seq:
        if prev is not None:
            step = (v - prev) * 1000.0
            if not charging:
                if step > latch_mv:
                    charging, count = True, 0
                    events.append((t, "ON"))
            elif step < release_mv:
                count += 1
                if count >= confirm:
                    charging, count = False, 0
                    events.append((t, "OFF"))
            else:
                count = 0
        prev = v
    return events


# Nocni zaznam uz je jeden vzorek na probuzeni; nabijeci zaznamy vzorkuji po
# 60s, takze se z nich bere kazdy desaty, aby to odpovidalo 10min spanku.
CASES = [
    ("2026-08-22-charging-from-empty", 10, "ON ~14:30, OFF ~18:10"),
    ("2026-08-23-charging-warm",       10, "ON ~22:27, zadny OFF (vyrez konci driv)"),
    ("2026-08-23-cesta-baseline",       1, "NIC - nenabijelo se"),
]


if __name__ == "__main__":
    print("latch=+%.0fmV  release=<%.0fmV  confirm=%d\n"
          % (LATCH_MV, RELEASE_MV, RELEASE_CONFIRM))
    for folder, stride, expected in CASES:
        seq = median3(load_voltage(folder)[::stride])
        events = simulate(seq, LATCH_MV, RELEASE_MV, RELEASE_CONFIRM)
        got = " ".join("%s@%s" % (k, t.strftime("%H:%M")) for t, k in events)
        print("%s" % folder)
        print("   ocekavano: %s" % expected)
        print("   dostal:    %s\n" % (got or "(nic)"))

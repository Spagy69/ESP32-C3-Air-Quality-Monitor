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


def simulate(seq, latch_mv, release_mv, confirm, inclusive=False):
    """inclusive=True testuje variantu 'step <= 0' misto 'step < 0'."""
    charging, prev, events, count = False, None, [], 0
    for t, v in seq:
        if prev is not None:
            step = (v - prev) * 1000.0
            if not charging:
                if step > latch_mv:
                    charging, count = True, 0
                    events.append((t, "ON"))
            elif (step <= release_mv if inclusive else step < release_mv):
                count += 1
                if count >= confirm:
                    charging, count = False, 0
                    events.append((t, "OFF"))
            else:
                count = 0
        prev = v
    return events

# Nabijeci zaznamy vzorkuji po 60s, takze se z nich bere kazdy desaty, aby to
# odpovidalo 10min spanku, a median se dopocitava.
#
# U zaznamu z uspavaneho rezimu zalezi na tom, KDY vznikly:
#   - cesta-baseline je z doby PRED opravou, kdy median pres probuzeni
#     nefungoval (jeho globaly byly restore_value: false). Publikovane
#     hodnoty jsou tedy syrove vzorky a median se na ne dopocitava.
#     Bez nej ten zaznam dava falesne sepnuti v 06:07 - je to zaroven
#     nejlepsi dukaz, ze median neni ozdoba.
#   - 2026-08-28 uz je s opravenym firmwarem, takze publikovana hodnota UZ
#     JE vystup medianu. Dopocitavat ho znovu by znamenalo filtrovat dvakrat.
#
# drop_first zahazuje prvni vzorek u zaznamu ze spanku: ten pochazi ze
# studeneho bootu, kde firmware bezi jinou vetvi a last_wake_batt_v jeste
# nema. Bez toho by sweep sepnul o jedno probuzeni driv, nez to udelal
# skutecny firmware.
#           slozka                              stride median drop  ocekavano
CASES = [
    ("2026-08-22-charging-from-empty",      10, True,  False,
     "ON ~14:30, OFF ~18:08"),
    ("2026-08-23-charging-warm",            10, True,  False,
     "ON ~22:27, zadny OFF (vyrez konci driv)"),
    ("2026-08-23-cesta-baseline",            1, True,  True,
     "NIC - nenabijelo se"),
    ("2026-08-28-cesta-nabijeni-a-chladnuti", 1, False, True,
     "ON 17:41, OFF 19:15 - jedina realna regrese ve spanku, sedi na HA"),
]


if __name__ == "__main__":
    print("latch=+%.0fmV  release=%.0fmV  confirm=%d"
          % (LATCH_MV, RELEASE_MV, RELEASE_CONFIRM))
    print()
    for folder, stride, remedian, drop_first, expected in CASES:
        raw = load_voltage(folder)[::stride]
        if drop_first:
            raw = raw[1:]
        seq = median3(raw) if remedian else raw
        print("%s" % folder)
        print("   ocekavano:   %s" % expected)
        for label, inc in (("step <  0 :", False), ("step <= 0 :", True)):
            events = simulate(seq, LATCH_MV, RELEASE_MV, RELEASE_CONFIRM, inc)
            got = " ".join("%s@%s" % (k, t.strftime("%H:%M")) for t, k in events)
            print("   %s   %s" % (label, got or "(nic)"))
        print()

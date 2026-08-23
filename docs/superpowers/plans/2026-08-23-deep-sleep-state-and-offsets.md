# Stav a offsety v uspávaném režimu - implementační plán

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Opravit čtyři chyby, které vzniknou tím, že deep sleep je plný reboot, zatímco firmware je psaný pro nepřetržitý běh - teplota o 3.55 °C mimo, nefunkční mediány, nefunkční detekce nabíjení a chybějící procenta baterky.

**Architecture:** Stav se rozdělí do tří tříd podle toho, co má přežít (nic / spánek / spánek i vypnutí); třída „jen spánek" se realizuje flash-backed globály, které se při studeném bootu vynulují. Klidový offset teploty se přestane odečítat v probuzeních ze spánku, klíčem je `cold_boot`. Detekce nabíjení dostane ve spánku vlastní, jednodušší větev nad krokem mezi probuzeními. Mediány BMP180 se opraví zrychlením pollingu místo perzistence.

**Tech Stack:** ESPHome 2026.4.0, ESP32-C3 (XIAO), Arduino framework, čisté YAML + C++ lambdy. Žádný testovací framework - ověřuje se `esphome config`, `esphome compile` a simulacemi nad CSV v `data/`.

**Spec:** [`docs/superpowers/specs/2026-08-23-deep-sleep-state-and-offsets-design.md`](../specs/2026-08-23-deep-sleep-state-and-offsets-design.md)

## Global Constraints

- **Nepushovat.** Commituje se jen lokálně, `git push` až na výslovné vyžádání (CLAUDE.md).
- **Bez attribution v commitech.** Žádné `Co-Authored-By`, žádný `Claude-Session:` trailer, žádná zmínka o asistentovi (CLAUDE.md).
- **Dokumentace i komentáře nesou původ čísla.** Když se něco odhaduje nebo extrapoluje, musí to být napsané u toho (CLAUDE.md).
- **`esphome` není v PATH** - volá se `python -m esphome ...` z `C:\Users\lagys\air-quality-monitor`.
- Komentáře v YAML/lambdách jsou **anglicky** (stávající konvence souborů), dokumentace v `.md` **česky**.
- `secrets.yaml` se nikdy necommituje.
- **DOMA větev detekce nabíjení se nemění** - je ověřená proti dvěma nabíjecím záznamům.
- Konstanty: `CHARGE_STEP_V = 0.020`, release `< 0.0`, `RELEASE_CONFIRM = 3`, `COOLDOWN_MIN = 150`, `bmp085 update_interval = 5s`.

## File Structure

| soubor | odpovědnost | mění se v úkolu |
|---|---|---|
| `air-quality-monitor.yaml` | substituce, `on_boot`, vynulování třídy B | 1 |
| `packages/globals.yaml` | deklarace stavu a jeho životnost | 1 |
| `packages/sensors.yaml` | offset teploty, filtry, detekce nabíjení, procenta | 2, 3, 4, 5, 6 |
| `packages/display.yaml` | podmínka vlnovky | 6 |
| `packages/menu.yaml` | nastavení rozladění při vstupu do spánku | 6 |
| `data/threshold-sweep.py` | reprodukovatelný sweep prahů (nový) | 4 |
| `README.md`, `HANDOFF.md`, `data/README.md` | dokumentace | 7 |

---

### Task 1: Třídy perzistence a vynulování při studeném bootu

Zavádí třídu B („přežít spánek, ne vypnutí"). Bez tohohle úkolu nemá žádný z dalších kam ukládat stav.

**Files:**
- Modify: `packages/globals.yaml`
- Modify: `air-quality-monitor.yaml`

**Interfaces:**
- Consumes: nic
- Produces: globály `batt_v_hist1`, `batt_v_hist2` (float, class B), `is_charging` (bool, class B), `discharge_confirm_count` (int, class B), `last_wake_batt_v` (float, class B), `charge_minutes` (float, class B), `disturb_minutes` (float, class B), `batt_reading_counted` (bool, class C). Substituce `${cooldown_min}` = `"150"`.

- [ ] **Step 1: Překlopit `batt_v_hist1`/`batt_v_hist2` na class B**

V `packages/globals.yaml` nahraď:

```yaml
  - id: batt_v_hist1
    type: float
    restore_value: false
    initial_value: '0'
  - id: batt_v_hist2
    type: float
    restore_value: false
    initial_value: '0'
```

za:

```yaml
  # Class B: must survive deep sleep, must NOT survive a power cycle.
  # See the invalidation block in air-quality-monitor.yaml's on_boot.
  #
  # These used to be class C, which quietly disabled the median in every
  # deep-sleep mode: a wake lasts ~26s and battery_voltage polls at 60s, so
  # exactly one reading arrives and `batt_v_hist2 > 0` was never true - the
  # code fell straight through to the raw sample. Measured over 59 cycles of
  # data/2026-08-23-cesta-baseline/: raw wake-to-wake steps have sd 8.02mV
  # and a worst false positive of +21.6mV, while the same steps through the
  # median have sd 2.16mV and a worst false positive of +0.96mV. The charging
  # rule below needs the second set of numbers to work at all.
  - id: batt_v_hist1
    type: float
    restore_value: true
    initial_value: '0'
  - id: batt_v_hist2
    type: float
    restore_value: true
    initial_value: '0'
```

- [ ] **Step 2: Překlopit `is_charging` a `discharge_confirm_count` na class B**

Nahraď:

```yaml
  - id: is_charging
    type: bool
    restore_value: false
    initial_value: 'false'
```

za:

```yaml
  # Class B - the charging flag has to survive the reboot that every wake
  # is, or the deep-sleep detection path can never latch across cycles.
  - id: is_charging
    type: bool
    restore_value: true
    initial_value: 'false'
```

Nahraď:

```yaml
  - id: discharge_confirm_count
    type: int
    restore_value: false
    initial_value: '0'
```

za:

```yaml
  # Class B - in the deep-sleep path this counts wakes, not readings
  # (3 confirmations = 3 wakes = 30min), so it must cross reboots.
  - id: discharge_confirm_count
    type: int
    restore_value: true
    initial_value: '0'
```

- [ ] **Step 3: Přidat nové globály**

Za blok `full_confirm_count` (konec sekce „charging detection") vlož:

```yaml
  # --- deep-sleep-only bookkeeping (class B unless noted) ---
  # Median-filtered voltage as of the previous wake. The deep-sleep charging
  # rule is a step against this, not a trend against a moving average: at one
  # sample per 10min a charge adds ~+40mV per step while discharge takes off
  # ~1.3mV, and the median keeps the noise at 2.16mV sd.
  - id: last_wake_batt_v
    type: float
    restore_value: true
    initial_value: '0'
  # Minutes of charging accumulated across wakes. millis() restarts on every
  # wake, so charge_start_ms cannot measure a charge that spans sleeps.
  - id: charge_minutes
    type: float
    restore_value: true
    initial_value: '0'
  # Minutes since the enclosure was last thermally disturbed - entering sleep
  # warm, or any detected charging step. Drives the "~" marker in deep-sleep
  # modes (packages/display.yaml). Stops incrementing once it reaches
  # ${cooldown_min}, which also stops it writing to flash.
  - id: disturb_minutes
    type: float
    restore_value: true
    initial_value: '${cooldown_min}'
  # Class C. True once battery_voltage has published in THIS boot. A wake is
  # normally ~26s so the 60s poll fires once, but a button wake or STAY can
  # keep the device up longer and fire it twice - the per-wake counters must
  # not be advanced twice.
  - id: batt_reading_counted
    type: bool
    restore_value: false
    initial_value: 'false'
```

- [ ] **Step 4: Přidat substituci `cooldown_min`**

V `air-quality-monitor.yaml` nahraď:

```yaml
substitutions:
  device_name: "air-quality-monitor"
  friendly_name: "Air Quality Monitor"
```

za:

```yaml
substitutions:
  device_name: "air-quality-monitor"
  friendly_name: "Air Quality Monitor"
  # How long after a thermal disturbance the temperature stays marked "~" in
  # deep-sleep modes. Referenced from packages/sensors.yaml, display.yaml and
  # menu.yaml, so it lives here rather than as three copies of a literal.
  #
  # 144min is where the measured cool-down curve
  # (data/2026-08-23-cesta-baseline/) drops below 0.5C of its plateau, and
  # 0.5C is the accuracy the whole device claims - below that the reading is
  # as trustworthy as it ever gets. Rounded up to 150.
  cooldown_min: "150"
```

- [ ] **Step 5: Přidat vynulování třídy B do `on_boot`**

V `air-quality-monitor.yaml` nahraď:

```yaml
        - lambda: |-
            auto cause = esp_sleep_get_wakeup_cause();
            id(cold_boot)      = (cause == ESP_SLEEP_WAKEUP_UNDEFINED);
            id(wake_was_timer) = (cause == ESP_SLEEP_WAKEUP_TIMER);
        - delay: 1500ms
```

za:

```yaml
        - lambda: |-
            auto cause = esp_sleep_get_wakeup_cause();
            id(cold_boot)      = (cause == ESP_SLEEP_WAKEUP_UNDEFINED);
            id(wake_was_timer) = (cause == ESP_SLEEP_WAKEUP_TIMER);
        # Class-B state must survive deep sleep but NOT a power cycle.
        # ESPHome only offers flash-backed globals (restore_value: true),
        # which survive both, so the second half is enforced here: any boot
        # that is not a deep-sleep wake throws the sleep-scoped state away.
        #
        # Without this, `is_charging` would come back true after a week on
        # the shelf, and a stale `last_wake_batt_v` would look like a huge
        # voltage step and latch charging on the first reading.
        #
        # cold_boot is also true after an OTA reboot, so this clears there
        # too. That is the safe direction - re-deriving beats trusting a
        # flag from before the reboot.
        #
        # disturb_minutes is reset to "settled", not to zero: a device that
        # just powered on has a cold enclosure. The real value is set when
        # it actually enters sleep, see packages/menu.yaml.
        - lambda: |-
            if (id(cold_boot)) {
              id(batt_v_hist1) = 0.0f;
              id(batt_v_hist2) = 0.0f;
              id(last_wake_batt_v) = 0.0f;
              id(is_charging) = false;
              id(discharge_confirm_count) = 0;
              id(charge_minutes) = 0.0f;
              id(disturb_minutes) = (float) ${cooldown_min};
            }
        - delay: 1500ms
```

- [ ] **Step 6: Ověřit konfiguraci**

```bash
cd "C:/Users/lagys/air-quality-monitor" && python -m esphome config air-quality-monitor.yaml > /dev/null && echo "CONFIG OK"
```

Očekávané: `CONFIG OK` a návratový kód 0. Pozor: v dumpu se vyskytuje řetězec `log_level: ERROR` v `sdkconfig_options` - to **není** chyba, nehledej `ERROR` grepem, řiď se návratovým kódem.

- [ ] **Step 7: Ověřit kompilaci**

```bash
cd "C:/Users/lagys/air-quality-monitor" && python -m esphome compile air-quality-monitor.yaml 2>&1 | tail -5
```

Očekávané: `Successfully compiled program.`

- [ ] **Step 8: Commit**

```bash
cd "C:/Users/lagys/air-quality-monitor" && git add packages/globals.yaml air-quality-monitor.yaml && git commit -F- <<'EOF'
Rozdělit globály podle toho, co má přežít spánek

Deep sleep je plný reboot, takže restore_value: false znamená "zahodit
každých 10 minut". Tím se tiše vypnul medián napětí (batt_v_hist1/2) i
celý stav detekce nabíjení.

Nová třída: přežít spánek, ne vypnutí. ESPHome takovou nemá - flash
přežije obojí - takže se druhá půlka vynutí v on_boot: co není probuzení
ze spánku, to sleep-scoped stav vynuluje. Jinak by se is_charging po
týdnu na polici probudilo jako true a zastaralé last_wake_batt_v by
vypadalo jako obří skok napětí.

Číslo, kvůli kterému to má smysl: kroky napětí mezi probuzeními mají
syrově sd 8.02 mV a nejhorší falešný kladný +21.6 mV, přes medián
2.16 mV a +0.96 mV. Pravidlo detekce nabíjení potřebuje tu druhou sadu.

disturb_minutes startuje jako "ustálené", ne nula - po zapnutí vypínačem
je krabička studená.
EOF
```

---

### Task 2: Offset teploty se ve spánku neodečítá

Opravuje hlavní chybu: publikovaná teplota je v uspávaném režimu o 3.55 °C pod realitou.

**Files:**
- Modify: `packages/sensors.yaml` (lambda v `bmp085` → `temperature` → `filters`)

**Interfaces:**
- Consumes: `id(cold_boot)` z Tasku 1 (existoval už předtím, jen se nově čte tady)
- Produces: nic pro další úkoly

- [ ] **Step 1: Klíčovat offset na `cold_boot`**

V `packages/sensors.yaml` nahraď:

```yaml
        - lambda: |-
            const float REST_OFFSET_BMP180   = 2.46f;  // measured, see above
            const float CHARGE_OFFSET_BMP180 = 0.0f;   // measured: no constant works, see SCD41 above

            float extra = REST_OFFSET_BMP180;
            if (id(is_charging)) extra += CHARGE_OFFSET_BMP180;

            float corrected = x - extra;
            id(cached_temp_bmp180) = corrected;
            return corrected;
```

za:

```yaml
        - lambda: |-
            const float REST_OFFSET_BMP180   = 2.46f;  // measured, see above
            const float CHARGE_OFFSET_BMP180 = 0.0f;   // measured: no constant works, see SCD41 above

            // The rest offset only exists while the device runs continuously.
            // cold_boot is false exactly when this boot is a deep-sleep wake,
            // which means the enclosure spent the whole sleep interval
            // settling at ambient and this reading lands ~3s after boot -
            // there is no self-heating in it to subtract.
            //
            // Measured: data/2026-08-23-cesta-baseline/ ran 12.4h at a 4.2%
            // duty cycle (26s awake per 626s) and the published temperature
            // sat 3.55C BELOW a reference thermometer - 2.46C of unearned
            // offset plus a 1.09C residual that one reading cannot resolve.
            //
            // Order-of-magnitude check rather than a second constant: 2.46C
            // at ~34mA/4V puts the enclosure near 18 K/W, so the ~0.3mA that
            // stays alive through sleep is worth ~0.02C. Zero is the right
            // number here, not a convenient approximation.
            //
            // Keyed on physical history, not on the deep-sleep menu setting,
            // for the same reason the display picks its temperature source
            // by "does a live reading exist" instead of by mode.
            //
            // Known asymmetry left in place: after a cold power-on cold_boot
            // is true and the offset is subtracted even though the enclosure
            // is equally cold - that is the documented -1.1C at 10 minutes,
            // and it stays hidden behind the "~" warm-up marker rather than
            // being modelled from uptime (v1 was burned by exactly that
            // class of time-based correction).
            float extra = id(cold_boot) ? REST_OFFSET_BMP180 : 0.0f;
            if (id(is_charging)) extra += CHARGE_OFFSET_BMP180;

            float corrected = x - extra;
            id(cached_temp_bmp180) = corrected;
            return corrected;
```

- [ ] **Step 2: Ověřit konfiguraci a kompilaci**

```bash
cd "C:/Users/lagys/air-quality-monitor" && python -m esphome config air-quality-monitor.yaml > /dev/null && echo "CONFIG OK" && python -m esphome compile air-quality-monitor.yaml 2>&1 | tail -3
```

Očekávané: `CONFIG OK` a `Successfully compiled program.`

- [ ] **Step 3: Commit**

```bash
cd "C:/Users/lagys/air-quality-monitor" && git add packages/sensors.yaml && git commit -F- <<'EOF'
Klidový offset se v probuzeních ze spánku neodečítá

REST_OFFSET_BMP180 = 2.46 byl změřený v DOMA, kde zařízení běží pořád a
krabička se od sebe sama trvale hřeje. V uspávaném režimu je vzhůru 26 s
ze 626 a BMP180 se čte ~3 s po bootu, tedy ve stavu, do kterého se
krabička dostala za 10 min spánku. Není tam co odečítat.

Změřeno v data/2026-08-23-cesta-baseline/: publikovaná teplota seděla
3.55 °C pod referenčním teploměrem. Z toho 2.46 dělal tenhle offset,
zbylých 1.09 je zbytek, který jedním odečtem rozhodnout nejde.

Klíčem je cold_boot, ne nastavení režimu - fyzická historie ("tenhle
boot je probuzení ze spánku"), stejná logika, jakou displej používá při
výběru zdroje teploty.

Kontrola řádu: 2.46 °C při ~34 mA a 4 V dává ~18 K/W, takže ~0.3 mA
klidového odběru ve spánku odpovídá ~0.02 °C. Nula je správně.
EOF
```

---

### Task 3: Mediány BMP180 a tlaku zrychlením pollingu

Filtr proti jednomu špatnému I2C čtení ve spánku nedělá nic, protože se okno nikdy nenaplní. Řeší se rychlejším čtením, ne perzistencí.

**Files:**
- Modify: `packages/sensors.yaml` (`bmp085` platform header + oba `median` bloky + oba `filters` konce)

**Interfaces:**
- Consumes: nic
- Produces: nic pro další úkoly

- [ ] **Step 1: Zrychlit polling**

V `packages/sensors.yaml` nahraď:

```yaml
  - platform: bmp085
    address: 0x77
    update_interval: 60s
```

za:

```yaml
  - platform: bmp085
    address: 0x77
    # 5s, matching the SCD41 above, so the median filters below actually
    # have a window to fill. At 60s a deep-sleep wake (~26s) delivered
    # exactly one reading, the window never filled, and with
    # send_first_at: 1 the filter published that single raw sample - i.e.
    # it was a no-op in the mode that needs it most. Proven in
    # data/2026-08-23-cesta-baseline/: a -0.886C outlier went straight
    # through at 14:43:48 local.
    #
    # At 5s a wake delivers ~5 readings and the median works inside one
    # boot, so none of this needs flash-backed state.
    #
    # Costs nothing: a BMP180 conversion is ~5uA*s, so 0.2 readings/s
    # averages ~1uA against ~34mA for the whole device.
    update_interval: 5s
```

- [ ] **Step 2: Publikovat jen plně filtrované hodnoty (teplota)**

V bloku `temperature:` nahraď:

```yaml
        - median:
            window_size: 3
            send_every: 1
            send_first_at: 1
```

za:

```yaml
        - median:
            window_size: 3
            send_every: 1
            # 3, not 1: with send_first_at: 1 the first two readings of every
            # boot are published as the median of a partial window, i.e. raw.
            # In a deep-sleep wake that is most of them. Costs ~15s of extra
            # latency after a boot, during which the display falls back to
            # the cached value and marks it - the honest trade.
            send_first_at: 3
```

Pozor: identický `median` blok je v souboru **dvakrát** (teplota a tlak). Tenhle krok mění ten v `temperature:`, další krok ten v `pressure:`. Rozliš je podle okolního kontextu, ne slepou náhradou všech výskytů.

- [ ] **Step 3: Přidat `delta` filtr za korekční lambdu (teplota)**

V bloku `temperature:` nahraď:

```yaml
            float corrected = x - extra;
            id(cached_temp_bmp180) = corrected;
            return corrected;
```

za:

```yaml
            float corrected = x - extra;
            id(cached_temp_bmp180) = corrected;
            return corrected;
        # Publish only meaningful changes, same reasoning and same placement
        # as the SCD41's delta above: at 5s polling this would otherwise put
        # ~12 rows/min into HA's recorder for a value that drifts by well
        # under 0.2C an hour. AFTER the lambda on purpose, so the cache still
        # updates on every reading and the display's fallback cannot go stale
        # just because HA does not need the row.
        - delta: 0.05
```

- [ ] **Step 4: Totéž pro tlak**

V bloku `pressure:` nahraď `send_first_at: 1` za `send_first_at: 3` (stejné zdůvodnění, komentář stačí kratší):

```yaml
        - median:
            window_size: 3
            send_every: 1
            # 3, not 1 - see the temperature median above for why.
            send_first_at: 3
```

a nahraď:

```yaml
        - lambda: |-
            id(cached_pressure) = x;
            return x;
```

za:

```yaml
        - lambda: |-
            id(cached_pressure) = x;
            return x;
        # Same reasoning as the temperature delta above. 0.1 hPa is well
        # under any real weather trend and well over the residual noise the
        # median leaves behind.
        - delta: 0.1
```

- [ ] **Step 5: Ověřit, že se interval propsal do konfigurace**

```bash
cd "C:/Users/lagys/air-quality-monitor" && python -m esphome config air-quality-monitor.yaml 2>/dev/null | grep -c "send_first_at: 3"
```

Očekávané: `2` (teplota a tlak).

- [ ] **Step 6: Ověřit kompilaci**

```bash
cd "C:/Users/lagys/air-quality-monitor" && python -m esphome compile air-quality-monitor.yaml 2>&1 | tail -3
```

Očekávané: `Successfully compiled program.`

- [ ] **Step 7: Commit**

```bash
cd "C:/Users/lagys/air-quality-monitor" && git add packages/sensors.yaml && git commit -F- <<'EOF'
Medián BMP180 ve spánku nedělal nic - zrychlit polling místo perzistence

Filtr proti jednomu špatnému I2C čtení potřebuje naplnit okno, jenže při
update_interval: 60s dorazí za ~26s probuzení jediné čtení a se
send_first_at: 1 filtr publikuje medián z jednovzorkového okna, tedy ten
vzorek. V data/2026-08-23-cesta-baseline/ tudy prošel výkyv -0.886 °C.

Řešení není persistovat historii přes flash, ale číst rychleji: při 5s
dorazí za probuzení ~5 čtení a vestavěný filtr funguje uvnitř jednoho
bootu. Ušetří to čtyři globály.

send_first_at: 3, aby se nepublikovala nefiltrovaná čtení na začátku
bootu. Za korekční lambdy přibyl delta filtr, jinak by 5s polling sypal
do recorderu ~12 řádků za minutu; umístění za lambdu je stejné
rozhodnutí jako u SCD41, aby se cache aktualizovala každým čtením.

Energeticky zdarma: převod BMP180 stojí ~5 uA*s, při 0.2 čtení/s tedy
~1 uA proti ~34 mA celkem.
EOF
```

---

### Task 4: Detekce nabíjení ve spánku

Ve spánku nemůže EWMA pravidlo fungovat (jeden vzorek za probuzení). Dostane vlastní větev nad krokem mezi probuzeními, s prahy prohnanými sweepem.

**Files:**
- Modify: `packages/sensors.yaml` (lambda `battery_voltage`, blok „Charging detection")
- Modify: `packages/sensors.yaml` (template `charging_duration`)
- Create: `data/threshold-sweep.py`

**Interfaces:**
- Consumes: `last_wake_batt_v`, `charge_minutes`, `disturb_minutes`, `batt_reading_counted`, `is_charging`, `discharge_confirm_count` z Tasku 1; `${cooldown_min}` z Tasku 1
- Produces: `id(disturb_minutes)` se nuluje při každém kroku nad prahem - na tom staví Task 6

- [ ] **Step 1: Obalit stávající DOMA cestu a přidat větev pro spánek**

V `packages/sensors.yaml` nahraď (je to konec lambdy `battery_voltage`):

```yaml
      } else {
        id(batt_v_slow_avg) = v;
      }
      // Last-resort backstop, now that both a real disconnect (the trend
      // rule) and a finished charge (high and flat) are detected above.
      // Nothing known should reach this any more - if `Charging Duration`
      // ever shows a clean 180.0min again, one of those two rules missed
      // something and this is covering for it.
      if (id(is_charging) && (millis() - id(charge_start_ms) > 3UL * 60UL * 60UL * 1000UL)) {
        id(is_charging) = false;
      }
      id(prev_batt_v) = v;
      id(cached_battery_v) = v;
      return v;
```

za:

```yaml
      } else {
        id(batt_v_slow_avg) = v;
      }
      // Last-resort backstop, now that both a real disconnect (the trend
      // rule) and a finished charge (high and flat) are detected above.
      // Nothing known should reach this any more - if `Charging Duration`
      // ever shows a clean 180.0min again, one of those two rules missed
      // something and this is covering for it.
      if (id(is_charging) && (millis() - id(charge_start_ms) > 3UL * 60UL * 60UL * 1000UL)) {
        id(is_charging) = false;
      }
      }  // end of the continuous-run path

      id(prev_batt_v) = v;
      id(cached_battery_v) = v;
      return v;
```

Následně vlož **před** řádek `      // --- Charging detection from a slow voltage trend ---` tenhle blok, který otevře podmínku a přidá větev pro spánek.

**Pozor na dvě věci:** blok končí `} else {`, takže stávající DOMA kód se tím ocitne uvnitř nové větve - zkontroluj, že závorky vycházejí (`if (!cold_boot) {` … `} else {` … `}` z předchozího kroku). A **přeodsaď zabalený DOMA blok o dvě mezery**, jinak zůstane opticky mimo svou větev; v takhle okomentovaném souboru to je rozdíl mezi čitelným a nečitelným.

```cpp
      // Two regimes, two rules, because the sampling is different by an
      // order of magnitude.
      //
      // Running continuously (cold_boot): one reading every 60s, and the
      // per-sample charging signal is only ~+4mV against ~18mV of noise -
      // hopeless on its own, which is why the path below averages over a
      // ~10min EWMA baseline. That path is verified against two real charge
      // captures and is NOT touched here.
      //
      // Woken from deep sleep (!cold_boot): one reading per wake, and the
      // ~10min of averaging comes for free in the gap between them. A charge
      // adds ~+40mV per 10min step while discharge takes off ~1.3mV, and the
      // median leaves 2.16mV of noise - so a plain step against the previous
      // wake beats the EWMA and needs no confirmation counts to latch.
      //
      // It also side-steps the end-of-charge problem entirely. The EWMA has a
      // dead zone (constant voltage -> trend 0, which is between the latch and
      // release thresholds), and closing it took the FULL_V/flatness heuristic
      // and two rounds of tuning. A step rule has no dead zone: constant
      // voltage gives step 0, which is below the release threshold.
      if (!id(cold_boot)) {
        // Swept against both charge captures down-sampled to 10min, with the
        // overnight record as the regression - see data/threshold-sweep.py.
        //   latch:   identical results anywhere from +12 to +30mV, and zero
        //            false latches across 72 undisturbed wakes even at +10mV,
        //            so +20mV sits in the middle of a wide plateau.
        //   release: +5mV oscillates (ON->OFF->ON inside 20min) because the
        //            CV phase of a charge is flat; "< 0" does not.
        //   confirm: 2 releases 58min early, 3 lands within 2min of the
        //            measured end of charge, 4 runs past the capture. 3 is
        //            the one we can evidence; later is the safe direction.
        const float CHARGE_STEP_V   = 0.020f;
        const int   RELEASE_CONFIRM = 3;

        // A wake is ~26s and this sensor polls at 60s, so it normally fires
        // once. A button wake or STAY can keep the device up longer and fire
        // it twice - the per-wake counters must not advance twice.
        if (!id(batt_reading_counted)) {
          id(batt_reading_counted) = true;
          float mins = (float) id(sleep_interval_minutes);

          if (id(last_wake_batt_v) > 0.0f) {
            float step = v - id(last_wake_batt_v);
            if (step > CHARGE_STEP_V) {
              if (!id(is_charging)) {
                id(is_charging) = true;
                id(charge_minutes) = 0.0f;
              }
              id(discharge_confirm_count) = 0;
              // Every rise, not just the latching one, so the marker stays
              // pinned for the whole constant-current phase.
              id(disturb_minutes) = 0.0f;
            } else if (id(is_charging)) {
              if (step < 0.0f) {
                id(discharge_confirm_count)++;
                if (id(discharge_confirm_count) >= RELEASE_CONFIRM) {
                  id(is_charging) = false;
                  id(discharge_confirm_count) = 0;
                }
              } else {
                id(discharge_confirm_count) = 0;
              }
            }
          }
          id(last_wake_batt_v) = v;

          if (id(is_charging)) id(charge_minutes) += mins;
          // Stops at the cap, which also stops it writing to flash.
          if (id(disturb_minutes) < (float) ${cooldown_min}) id(disturb_minutes) += mins;
        }
      } else {
```

- [ ] **Step 2: Opravit dobu nabíjení, aby přežila spánek**

V `packages/sensors.yaml` nahraď:

```yaml
    lambda: |-
      if (!id(is_charging)) return 0.0f;
      return (millis() - id(charge_start_ms)) / 60000.0f;
```

za:

```yaml
    lambda: |-
      if (!id(is_charging)) return 0.0f;
      // millis() restarts on every deep-sleep wake, so charge_start_ms can
      // only measure a charge inside one boot. In deep-sleep modes the
      // battery lambda accumulates whole sleep intervals into charge_minutes
      // instead - see the "!cold_boot" branch there.
      if (!id(cold_boot)) return id(charge_minutes);
      return (millis() - id(charge_start_ms)) / 60000.0f;
```

- [ ] **Step 3: Uložit sweep do repa, ať je reprodukovatelný**

Vytvoř `data/threshold-sweep.py`:

```python
"""Sweep prahu detekce nabijeni pro uspavany rezim.

Duvod, proc to je v repu: prahy DOMA cesty se uz jednou naladily na jediny
zaznam a druhy je shodil (viz README, Known Issues). Tenhle skript pousti
navrzene pravidlo pres VSECHNY tri relevantni zaznamy najednou, takze se
da po kazde zmene prahu znovu overit, ze nesedi na hrane.

Spusteni:  python data/threshold-sweep.py
"""
import csv
import datetime as dt
import os

BASE = os.path.dirname(os.path.abspath(__file__))


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


# The overnight record is already one sample per wake; the charge captures
# poll at 60s, so take every 10th sample to match a 10min sleep interval.
CASES = [
    ("2026-08-22-charging-from-empty", 10, "1x ON ~14:30, 1x OFF ~18:10"),
    ("2026-08-23-charging-warm",       10, "1x ON ~22:27, zadny OFF (vyrez konci driv)"),
    ("2026-08-23-cesta-baseline",       1, "NIC - nenabijelo se"),
]

if __name__ == "__main__":
    print("latch=+20mV  release=<0mV  confirm=3\n")
    for folder, stride, expected in CASES:
        seq = median3(load_voltage(folder)[::stride])
        events = simulate(seq, 20.0, 0.0, 3)
        got = " ".join("%s@%s" % (k, t.strftime("%H:%M")) for t, k in events)
        print("%-32s ocekavano: %s" % (folder, expected))
        print("%-32s dostal:    %s\n" % ("", got or "(nic)"))
```

- [ ] **Step 4: Spustit sweep a ověřit, že prahy pořád sedí**

```bash
cd "C:/Users/lagys/air-quality-monitor" && python data/threshold-sweep.py
```

Očekávané: `charging-from-empty` → `ON@14:30 OFF@18:08`; `charging-warm` → `ON@22:27` a nic dalšího; `cesta-baseline` → `(nic)`.

- [ ] **Step 5: Ověřit konfiguraci a kompilaci**

```bash
cd "C:/Users/lagys/air-quality-monitor" && python -m esphome config air-quality-monitor.yaml > /dev/null && echo "CONFIG OK" && python -m esphome compile air-quality-monitor.yaml 2>&1 | tail -3
```

Očekávané: `CONFIG OK` a `Successfully compiled program.`

- [ ] **Step 6: Commit**

```bash
cd "C:/Users/lagys/air-quality-monitor" && git add packages/sensors.yaml data/threshold-sweep.py && git commit -F- <<'EOF'
Detekce nabíjení dostane ve spánku vlastní, jednodušší větev

EWMA pravidlo potřebuje řadu vzorků; ve spánku dorazí za probuzení jeden
a pak se zařízení rebootuje. Ve spánku proto místo něj krok proti
minulému probuzení: nabíjení přidá ~+40 mV za deset minut, vybíjení
ubere ~1.3 mV, a medián drží šum na 2.16 mV.

Odpadá tím i dead zone EWMA (konstantní napětí -> trend 0, tedy mezi
prahy), kvůli které vznikla heuristika FULL_V/plochost a dvě kola
ladění. Krok dead zone nemá: konstantní napětí dá krok 0, což je pod
uvolňovacím prahem.

Prahy nejsou od oka. data/threshold-sweep.py pouští pravidlo přes obě
nabíjecí sady podvzorkované na 10 min i přes noční záznam jako regresi:
- práh sepnutí dává identický výsledek od +12 do +30 mV a nula falešných
  sepnutí za 72 probuzení i při +10 mV, takže +20 nesedí na hraně
- uvolnění +5 mV osciluje (ON-OFF-ON za 20 min), protože CV fáze je
  plochá; "< 0" ne
- potvrzení: 2 pouští o 58 min dřív, 3 trefí konec nabíjení na dvě
  minuty, 4 už za koncem záznamu

Charging Duration se ve spánku počítá z charge_minutes, protože millis()
se každým probuzením nuluje.

DOMA cesta se nemění.
EOF
```

---

### Task 5: Procenta baterky se publikují z lambdy napětí

Odstraňuje závod, kvůli kterému `Battery Level` chyběl nejméně v 21 ze 72 probuzení.

**Files:**
- Modify: `packages/sensors.yaml` (konec lambdy `battery_voltage`, template `battery_level`)

**Interfaces:**
- Consumes: `id(battery_level)` musí být definované (je, ve stejném souboru níž)
- Produces: nic pro další úkoly

- [ ] **Step 1: Počítat a publikovat procenta z lambdy napětí**

V `packages/sensors.yaml` nahraď (konec lambdy `battery_voltage`, po úpravě z Tasku 4):

```yaml
      id(prev_batt_v) = v;
      id(cached_battery_v) = v;
      return v;
```

za:

```yaml
      id(prev_batt_v) = v;
      id(cached_battery_v) = v;

      // Battery percentage is published from here rather than from its own
      // template tick. Both used to run on independent 60s intervals, and
      // ESPHome starts each component's interval at now + a random offset in
      // [0, 5s) (Scheduler::calculate_interval_offset_) - independently per
      // component. Whenever the percentage fired first it found no voltage
      // state, bailed out, and published nothing; with a ~26s awake window
      // there is no second chance that wake, so HA recorded `unknown`. That
      // happened in 21 of 72 wakes in data/2026-08-23-cesta-baseline/,
      // despite a code comment claiming the ordering made it impossible.
      //
      // Computing it here removes the race by construction: the voltage is
      // in scope, so there is nothing to be too early for.
      const float BATT_EMPTY_V = 3.00f;
      const float BATT_FULL_V  = 4.12f;  // measured, see the Battery Level comment below
      float pct = (v - BATT_EMPTY_V) / (BATT_FULL_V - BATT_EMPTY_V) * 100.0f;
      if (pct > 100) pct = 100;
      if (pct < 0) pct = 0;
      id(cached_battery_pct) = pct;
      id(battery_level).publish_state(pct);

      return v;
```

- [ ] **Step 2: Zrušit vlastní tik `battery_level`**

Nahraď:

```yaml
  - platform: template
    name: "Battery Level"
    id: battery_level
    unit_of_measurement: "%"
    device_class: battery
    state_class: measurement  # template sets no default - see battery_voltage
    update_interval: 60s
    lambda: |-
      // Bail out if the voltage sensor hasn't produced anything yet.
      // Without this, .state is NaN, every comparison against it is false
      // so the clamps below don't catch it, and the NaN lands in
      // cached_battery_pct - which is flash-backed, so the display would
      // come up showing "nan%" on the next boot. In practice the voltage
      // sensor is registered first and runs first on a shared 60s tick, so
      // this shouldn't trigger; it costs one branch to not depend on that.
      if (!id(battery_voltage).has_state()) return {};

      const float BATT_EMPTY_V = 3.00f;
      const float BATT_FULL_V  = 4.12f;  // measured, see comment above

      float v = id(battery_voltage).state;
      float pct = (v - BATT_EMPTY_V) / (BATT_FULL_V - BATT_EMPTY_V) * 100.0f;
      if (pct > 100) pct = 100;
      if (pct < 0) pct = 0;
      id(cached_battery_pct) = pct;
      return pct;
```

za:

```yaml
  - platform: template
    name: "Battery Level"
    id: battery_level
    unit_of_measurement: "%"
    device_class: battery
    state_class: measurement  # template sets no default - see battery_voltage
    # No lambda and no interval on purpose: the value is pushed from the
    # battery_voltage lambda above, the moment a voltage exists. Polling this
    # on its own 60s tick is what caused the race that dropped the percentage
    # in 21 of 72 wakes - the old comment here claimed registration order made
    # that impossible, and the data says otherwise.
    update_interval: never
```

- [ ] **Step 3: Ověřit konfiguraci a kompilaci**

```bash
cd "C:/Users/lagys/air-quality-monitor" && python -m esphome config air-quality-monitor.yaml > /dev/null && echo "CONFIG OK" && python -m esphome compile air-quality-monitor.yaml 2>&1 | tail -3
```

Očekávané: `CONFIG OK` a `Successfully compiled program.`

Poznámka k ověření: spec zmiňuje regresi „ani jedno probuzení bez platné hodnoty". **Simulovat to ze stolu nejde** - závod je v plánovači ESPHome, ne v datech, a oprava ho odstraňuje konstrukcí (napětí je v lambdě v scope, takže není na co být brzo). Skutečné ověření je hardwarové a je v Tasku 7 Step 4.

- [ ] **Step 4: Commit**

```bash
cd "C:/Users/lagys/air-quality-monitor" && git add packages/sensors.yaml && git commit -F- <<'EOF'
Procenta baterky publikovat z lambdy napětí, ne vlastním tikem

Battery Level chyběl v 21 ze 72 probuzení nočního záznamu. Obě šablony
měly update_interval: 60s a ESPHome plánuje první běh intervalu na
now + náhodný offset v [0, 5 s), nezávisle pro každou komponentu. Když
padla procenta dřív než napětí, uplatnila se pojistka has_state(),
nepublikovalo se nic - a protože je zařízení vzhůru jen ~26 s, druhá
šance v tom probuzení nepřišla.

Komentář v kódu přitom tvrdil, že to nastat nemůže ("the voltage sensor
is registered first and runs first on a shared 60s tick"). Data říkají
opak, takže jde pryč i s pojistkou, kterou už není proti čemu potřebovat.
EOF
```

---

### Task 6: Vlnovka pokrývá okno chladnutí

Poslední díra: krabička přenesená z bytu do auta čte 2.5 h moc vysoko a nic to neoznačí.

**Files:**
- Modify: `packages/menu.yaml` (obě cesty do deep sleepu)
- Modify: `packages/display.yaml:194`

**Interfaces:**
- Consumes: `disturb_minutes` z Tasku 1, jeho nulování při stoupnutí napětí z Tasku 4, `${cooldown_min}` z Tasku 1
- Produces: nic pro další úkoly

- [ ] **Step 1: Nastavit rozladění při automatickém usnutí**

V `packages/menu.yaml` nahraď:

```yaml
                  - lambda: |-
                      id(display_on) = false;
                      id(oled_display).turn_off();
                      id(deep_sleep_1).set_sleep_duration(id(sleep_interval_minutes) * 60UL * 1000UL);
                      // Park the SCD41 before sleeping - see the comment on
                      // scd41_stop_before_sleep in packages/sensors.yaml.
                      id(scd41_hub).write_command((uint16_t) 0x3F86);  // stop_periodic_measurement
```

za:

```yaml
                  - lambda: |-
                      id(display_on) = false;
                      id(oled_display).turn_off();
                      id(deep_sleep_1).set_sleep_duration(id(sleep_interval_minutes) * 60UL * 1000UL);
                      // How thermally disturbed is the enclosure as it goes
                      // to sleep? A device that has been running for a while
                      // is warm and its temperature means nothing until it
                      // cools (~2.5h measured), so mark it. One that only
                      // just booted never got warm - marking that would put
                      // a "~" on the single most common path into CESTA
                      // (switch the device on in the car, pick the preset,
                      // let it sleep) for no reason.
                      //
                      // A step, not a ramp, and it deliberately errs towards
                      // marking: 5min against the enclosure's ~45min time
                      // constant is under 0.2C of warm-up.
                      id(disturb_minutes) = (millis() < 5UL * 60UL * 1000UL)
                                          ? (float) ${cooldown_min} : 0.0f;
                      // Park the SCD41 before sleeping - see the comment on
                      // scd41_stop_before_sleep in packages/sensors.yaml.
                      id(scd41_hub).write_command((uint16_t) 0x3F86);  // stop_periodic_measurement
```

- [ ] **Step 2: Totéž pro ruční usnutí kliknutím**

V `packages/menu.yaml` nahraď:

```yaml
                if (id(deep_sleep_mode_enabled)) {
                  id(deep_sleep_1).set_sleep_duration(id(sleep_interval_minutes) * 60UL * 1000UL);
                  id(manual_click_should_sleep) = true;
                }
```

za:

```yaml
                if (id(deep_sleep_mode_enabled)) {
                  id(deep_sleep_1).set_sleep_duration(id(sleep_interval_minutes) * 60UL * 1000UL);
                  // Same disturbance bookkeeping as the auto-off path above -
                  // this is the other way into deep sleep, so it needs it too.
                  id(disturb_minutes) = (millis() < 5UL * 60UL * 1000UL)
                                      ? (float) ${cooldown_min} : 0.0f;
                  id(manual_click_should_sleep) = true;
                }
```

- [ ] **Step 3: Rozšířit podmínku vlnovky**

V `packages/display.yaml` nahraď:

```cpp
      bool suspect = (id(cold_boot) && millis() < WARMUP_MS) || id(is_charging);
```

za:

```cpp
      // Third case, added after data/2026-08-23-cesta-baseline/ showed the
      // gap: an enclosure carried warm from continuous operation into a
      // deep-sleep mode reads high for hours, and neither of the first two
      // conditions covers it - cold_boot is false after a wake, and nothing
      // is charging. Measured cool-down is ~2.5h to within the device's own
      // stated accuracy.
      //
      // Deliberately driven by disturb_minutes rather than by is_charging,
      // even for the charging case in this mode. The CV phase of a charge is
      // flat and indistinguishable from slow discharge by voltage alone, so
      // the charging flag's release edge cannot be trusted to the minute -
      // but the heat it leaves behind decays over ~1.5h, which this window
      // covers regardless of where exactly the flag drops.
      bool suspect = (id(cold_boot) && millis() < WARMUP_MS)
                  || id(is_charging)
                  || (!id(cold_boot) && id(disturb_minutes) < (float) ${cooldown_min});
```

- [ ] **Step 4: Ověřit konfiguraci a kompilaci**

```bash
cd "C:/Users/lagys/air-quality-monitor" && python -m esphome config air-quality-monitor.yaml > /dev/null && echo "CONFIG OK" && python -m esphome compile air-quality-monitor.yaml 2>&1 | tail -3
```

Očekávané: `CONFIG OK` a `Successfully compiled program.`

- [ ] **Step 5: Ověřit, že se substituce propsala na všechna tři místa**

```bash
cd "C:/Users/lagys/air-quality-monitor" && grep -c 'cooldown_min' packages/sensors.yaml packages/display.yaml packages/menu.yaml air-quality-monitor.yaml
```

Očekávané: `sensors.yaml:1`, `display.yaml:1`, `menu.yaml:2`, `air-quality-monitor.yaml:2` (definice + použití ve vynulování).

- [ ] **Step 6: Commit**

```bash
cd "C:/Users/lagys/air-quality-monitor" && git add packages/menu.yaml packages/display.yaml && git commit -F- <<'EOF'
Vlnovka pokryje i chladnutí po přenesení do uspávaného režimu

Poslední díra z nočního záznamu: krabička přenesená z bytu do auta čte
2.5 h moc vysoko a žádná ze tří podmínek vlnovky na to nesedla -
cold_boot je po probuzení false a nenabíjí se.

Čítač disturb_minutes měří, jak dlouho je krabička tepelně v klidu.
Nuluje ho vstup do spánku (pokud zařízení běželo dýl než 5 min, tedy
stihlo se ohřát) a každý krok napětí nad prahem nabíjení. Práh 150 min
je 144 min z log-fitu chladnutí zaokrouhlených nahoru; 144 je bod, kde
chyba klesne pod deklarovanou přesnost zařízení +-0.5 °C.

Rozhodovat se při vstupu do spánku, a ne při přepnutí režimu v menu, je
podstatné: nejběžnější cesta do CESTA je zapnout krabičku v autě a hned
přepnout preset. Tam je studená a vlnovka by svítila zbytečně.

Vlnovka schválně nezávisí na is_charging ani při nabíjení v tomhle
režimu. CV fáze je plochá a od pomalého vybíjení ji podle napětí
rozeznat nejde, takže uvolňovací hraně příznaku se věřit nedá - ale
teplo odeznívá ~1.5 h, což tohle okno pokryje tak jako tak.
EOF
```

---

### Task 7: Dokumentace

Kód a dokumentace se v tomhle repu drží v páru; čtyři Known Issues jsou po předchozích úkolech neaktuální.

Na rozdíl od Tasků 1-6 tenhle úkol **nepředepisuje doslovné znění** - jsou to odstavce o stovkách slov, jejichž formulace závisí na tom, jak nakonec dopadly kroky výš. Předepsané je, **která věta se mění a co musí nově tvrdit**; text píše ten, kdo úkol provádí, a drží se pravidla z CLAUDE.md, že u každého čísla je vidět, odkud je.

**Files:**
- Modify: `README.md`
- Modify: `HANDOFF.md`
- Modify: `data/README.md`

**Interfaces:**
- Consumes: hotové Tasky 1-6
- Produces: nic

- [ ] **Step 1: Přepsat čtyři Known Issues v `README.md`**

Tyhle položky teď popisují opravené chyby a musí se přeznačit na opravené, s číslem a odkazem na záznam:

1. `- **V uspávaném režimu je teplota o 3.55 °C pod realitou - změřeno, zatím neopravené (srpen 2026).**` → přepsat na `~~...~~ **opraveno (srpen 2026)**`, doplnit, že klíčem je `cold_boot`, a **ponechat** otevřený zbytek −1.09 °C i s tím, že je to dvojnásobek deklarované ±0.5 °C a zavře ho až měření třemi odečty.
2. `- **V uspávaném režimu nefunguje žádný filtr, který potřebuje historii...**` → přepsat: mediány BMP180/tlaku opraveny zrychlením pollingu na 5 s, medián napětí a stav nabíjení perzistencí, `Charging` v uspávaném režimu **už sepnout může**.
3. `- **`Battery Level` chybí ve 29 % probuzení...**` → přepsat na opraveno, s mechanismem (publikuje se z lambdy napětí).
4. Položka `- **BMP180 občas pustí jedno úplně vedlejší čtení (opraveno, srpen 2026).**` má na konci větu `**Platí to ale jen v nepřetržitém provozu** - v uspávaném režimu ten filtr nedělá nic...` → tahle výhrada padá, nahradit ji tím, že po zrychlení pollingu filtr funguje v obou režimech.

Do sekce „Kdy je to horší, než říká tabulka" změnit řádek `| V režimu s uspáváním | **−3.55 °C** (změřeno srpen 2026) |` na hodnotu po opravě (**−1.09 °C**) a odstavec pod tabulkou upravit tak, aby už netvrdil, že tu chybu vlnovka neoznačí - nově ji označí okno chladnutí.

Do bloku o vlnovce (`- **Vlnovka.**`) přidat čtvrtý případ (okno chladnutí, 150 min) a smazat větu `**Čtvrtý případ, kde by se objevit měla a neobjeví, je uspávaný režim:**`, která je teď nepravdivá.

- [ ] **Step 2: Doplnit `HANDOFF.md`**

- V sekci v2 STATUS přidat odrážku s datem, co se opravilo a s odkazem na spec i plán.
- Položku `2i.` (tři bugy z nočního záznamu, všechny neopravené) přepsat na `~~...~~ **HOTOVO**` a doplnit, co zbývá otevřené: zbytkových −1.09 °C a hardwarové ověření.
- V seznamu otevřených úkolů doplnit tři nové hardwarové testy z Tasku 7 Step 4.

- [ ] **Step 3: Doplnit `data/README.md`**

V sekci `2026-08-23-cesta-baseline/` u bodů 2, 5 a 6 doplnit větu, že jsou od srpna 2026 opravené a čím. Bod 4 (CO2) doplnit o výsledek simulace armování (72 ze 72). Do sekce „Co ještě chybí změřit" přidat položku o třech odečtech pro CESTA offset, pokud tam po předchozím commitu není v téhle podobě.

- [ ] **Step 4: Doplnit hardwarové testy, které tahle změna vyžaduje**

Do `HANDOFF.md` (seznam otevřených položek) a `README.md` nepatří jen popis, ale i to, co se musí ověřit na železe - žádný z těch bodů nejde ověřit ze stolu:

- Teplota v CESTA musí po flashnutí skočit o ~2.5 °C **nahoru** proti dnešku.
- Po přepnutí nahřáté krabičky do CESTA musí vlnovka zmizet zhruba po 2.5 h; po zapnutí vypínačem a okamžitém přepnutí se objevit **nesmí**.
- Nabíječka zapojená v CESTA: `Charging` musí chytnout do ~20 min.
- **`Battery Level` nesmí v HA vypadnout ani jednou** přes noc v uspávaném režimu (dnes chybí nejméně v 21 ze 72 probuzení). Tohle je jediné ověření té opravy - simulovat ji nejde, viz Task 5 Step 3.
- **Výkyv BMP180 typu −0.886 °C se nesmí opakovat.** Ověřitelné taky jen na novém záznamu: dnešní data mají jedno čtení za probuzení, takže v nich ta oprava vidět být nemůže.

- [ ] **Step 5: Zkontrolovat, že v dokumentaci nezůstalo staré tvrzení**

```bash
cd "C:/Users/lagys/air-quality-monitor" && grep -rn "zatím neopravené\|nefunguje žádný filtr\|neoznačí\|Charging` v uspávaném režimu nemůže sepnout" README.md HANDOFF.md data/README.md
```

Očekávané: žádný výskyt, který by tvrdil, že něco z Tasků 1-6 je pořád rozbité. Výskyty v historických/archivních formulacích (např. popis toho, co bylo *před* opravou) jsou v pořádku, pokud je z věty jasné, že jde o minulost.

- [ ] **Step 6: Commit**

```bash
cd "C:/Users/lagys/air-quality-monitor" && git add README.md HANDOFF.md data/README.md && git commit -F- <<'EOF'
Srovnat dokumentaci se stavem po opravách uspávaného režimu

Čtyři Known Issues popisovaly chyby, které už jsou opravené. Přepsáno na
opraveno i s mechanismem a odkazem na záznam, ze kterého to vyšlo.

Otevřené zůstává a je to v textu vidět: zbytkových -1.09 °C proti
syrovému čtení BMP180. Je to dvojnásobek deklarované přesnosti +-0.5 °C
a zavřou to až tři odečty referenčním teploměrem v uspávaném režimu,
stejný protokol jako u rest-offset.

Doplněny tři hardwarové testy, které tahle změna vyžaduje - teplota musí
po flashnutí skočit o ~2.5 °C nahoru, vlnovka po přenesení nahřáté
krabičky zmizet po ~2.5 h a nezobrazit se po zapnutí studené, a Charging
v CESTA chytnout do ~20 min.
EOF
```

---

## Poznámky k provedení

**Pořadí je závazné.** Task 4 a 6 čtou globály z Tasku 1; Task 5 upravuje tentýž konec lambdy jako Task 4, takže Task 4 musí být hotový dřív, jinak nebude odpovídat text k nahrazení.

**Po každém úkolu se kompiluje.** Není tu žádný testovací framework - `esphome config` a `esphome compile` jsou jediná automatická kontrola, kterou máme, a chytnou překlepy v lambdách i chybějící globály.

**Nic se neflashuje.** Všech sedm úkolů končí v gitu, lokálně. Flashování a hardwarové testy jsou na uživateli.

**Když si sweep v Tasku 4 Step 4 stěžuje**, neposunuj prahy, aby to prošlo - to je přesně chyba, kterou tenhle skript má hlídat. Zjisti, proč se výsledek liší od zaznamenaného, a řekni to.

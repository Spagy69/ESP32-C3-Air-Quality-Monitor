# Návrh: stav a offsety v uspávaném režimu

**Datum:** 23. 8. 2026
**Podklad:** [`data/2026-08-23-cesta-baseline/`](../../../data/README.md) - 12.4 h přes noc, 72 probuzení, s referenčním teploměrem
**Dotčené soubory:** `packages/globals.yaml`, `packages/sensors.yaml`, `packages/display.yaml`, `packages/menu.yaml`, `air-quality-monitor.yaml`, `README.md`, `HANDOFF.md`

## 1. Kořen problému

**Deep sleep je plný reboot, ale firmware je psaný pro nepřetržitý běh.**

Všechny čtyři nalezené bugy jsou jeden ze dvou důsledků:

- **stav, který měl přežít, nepřežil** - mediány, detekce nabíjení, čítače času;
- **konstanta změřená za nepřetržitého běhu se použila tam, kde neplatí** - klidový offset teploty.

Čísla, ze kterých návrh vychází (všechna z nočního záznamu, ne z odhadu):

| veličina | hodnota |
|---|---|
| perioda probuzení | 625.5 s (10 min spánku + ~26 s vzhůru) |
| duty cycle | 26 / 626 = **4.2 %** |
| BMP180 plató (posledních 5 h) | 18.955 °C ± 0.043 (n=22) |
| referenční teploměr | 22.5 °C |
| chyba publikované teploty | **−3.55 °C** |
| chyba syrového čtení | −1.09 °C |
| `Battery Level` chybí | 21 ze 72 probuzení |
| přeživší výkyv BMP180 | −0.886 °C (14:43:48 lokálně) |

## 2. Rozhodnutí

| # | otázka | rozhodnutí | kdo |
|---|---|---|---|
| 1 | laťka pro offset ve spánku | **odečítat nulu**, bez nové konstanty a bez nového měření | uživatel |
| 2 | detekce nabíjení ve spánku | **přepsat na mezi-probuzeními**, doba nabíjení z intervalu spánku | uživatel |
| 3 | vlnovka ve spánku | **jen během chladnutí** (~3 h po přepnutí) | uživatel |
| 4 | flash vs. RTC paměť | **flash + invalidace při studeném bootu** | asistent |
| 5 | medián i na tlak | **ano** | asistent |

**K bodu 4:** čistý `restore_value: true` má u téhle třídy stavu vadu - přežil by i **vypnutí**. `is_charging` by se po týdnu na polici probudilo jako `true` a zastaralé `last_wake_batt_v` by dalo obrovský krok a spustilo falešné nabíjení. Řeší to blok v `on_boot`: když je `cold_boot`, tenhle stav se vynuluje. Tím dostane flash sémantiku RTC paměti bez nové `includes:` hlavičky.

**K bodu 5:** původní chyba byla **jedno špatné I2C čtení, které porušilo oba kanály najednou** (teplotu i tlak, doloženo v `data/2026-08-22-doma-baseline/`). Filtrovat jen jeden by znamenalo mít v repu filtr dokumentovaný jako oprava dvoukanálového bugu, který opravuje jeden kanál.

## 3. Politika perzistence

Dnes je poměr 13 globálů `restore_value: true` proti 26 `false`, a ta hranice vznikla postupně, ne rozhodnutím. Nově se globály dělí do tří tříd:

| třída | co tam patří | `restore_value` | invalidace při `cold_boot` |
|---|---|---|---|
| A - přežít spánek i vypnutí | uživatelská nastavení, cachované hodnoty pro displej | `true` | **ne** |
| B - přežít spánek, ne vypnutí | historie médiánů, stav nabíjení, čítače času | `true` | **ano** |
| C - resetovat se | UI/session stav (`stay_on`, `wake_was_timer`, index menu) | `false` | n/a |

Třída B by správně patřila do RTC paměti (přežije spánek, ne vypnutí, nulové opotřebení). ESPHome ji ale nevystavuje - chtělo by to vlastní `includes:` hlavičku, tedy nový pohyblivý díl. Flash + invalidace dá stejnou sémantiku a zůstane to v YAML.

**Cena, řečená nahlas:** přibude ~6 zápisů na probuzení k dnešním ~6, tedy ~144 dávek/den a ~53 tis./rok. NVS má wear leveling přes celou partition, takže to na roky vyjde - ale je to **odhad, ne měření**.

### Globály třídy B

| globál | dnes | nově | k čemu |
|---|---|---|---|
| `batt_v_hist1`, `batt_v_hist2` | `false` | `true` | medián napětí přes probuzení |
| `is_charging` | `false` | `true` | stav nabíjení přes spánek |
| `last_wake_batt_v` | *nový* | `true` | referenční bod pro krok mezi probuzeními |
| `charge_minutes` | *nový* | `true` | doba nabíjení, když `millis()` nestačí |
| `sleep_mode_minutes` | *nový* | `true` | čítač okna chladnutí |
| `bmp_t_hist1`, `bmp_t_hist2` | *nové* | `true` | medián teploty BMP180 |
| `press_hist1`, `press_hist2` | *nové* | `true` | medián tlaku |

Celkem 3 překlopení a 7 nových globálů třídy B. K nim ještě jeden pomocný bool třídy C (`batt_reading_counted`, `restore_value: false`) - viz 4.4.

## 4. Změny po souborech

### 4.1 `air-quality-monitor.yaml` - invalidace při studeném bootu

Do `on_boot` (za lambdu, která plní `cold_boot`/`wake_was_timer`) přijde blok, který při `cold_boot` vynuluje **všechny globály třídy B**. Tím se z flash paměti stane spánkově-lokální úložiště.

Poznámka: `esp_sleep_get_wakeup_cause()` vrací `ESP_SLEEP_WAKEUP_UNDEFINED` i po OTA rebootu, takže `cold_boot` je pravdivé i tam. Vynulovat stav nabíjení po OTA je **bezpečný směr** - firmware se radši znovu rozkouká, než aby věřil starému příznaku.

### 4.2 `packages/sensors.yaml` - teplota BMP180

```cpp
float extra = id(cold_boot) ? REST_OFFSET_BMP180 : 0.0f;
if (id(is_charging)) extra += CHARGE_OFFSET_BMP180;
```

`!cold_boot` znamená doslova „tenhle boot je probuzení ze spánku", tedy krabička byla 10 min v tepelné rovnováze s okolím a **není co odečítat**. Klíčem je fyzická historie, ne uživatelské nastavení - tím se to nebije se zásadou u displeje, která větvení podle režimu záměrně nepoužívá.

**Známá asymetrie, která zůstává:** po studeném zapnutí je `cold_boot` pravdivé a offset se odečítá, i když je krabička taky studená. To je ta doložená chyba −1.1 °C v 10. minutě. Zůstává schovaná za vlnovkou, protože model podle času byl při brainstormingu odmítnut (v1 se na téhle třídě nápadu spálila, přestřelila o ~4 °C).

**SCD41 se nemění.** Jeho `temperature_offset: 6.7°C` je uvnitř senzoru a ve spánku stejně nic nepublikuje (filtr `SCD41_SETTLE_MS = 3 min` proti 30s oknu), takže tam nemá co pokazit.

### 4.3 `packages/sensors.yaml` - ruční mediány

Vestavěný `median:` filtr se persistovat nedá: `send_first_at: 1` vydá po bootu medián z jednovzorkového okna, tedy ten vzorek sám. Ve spánku je proto **no-op** - doloženo výkyvem −0.886 °C, který prošel.

Nahradí ho stejný ruční vzor, jaký už je u `battery_voltage` (medián ze 3 počítaný v lambdě přes globály), a to u **teploty BMP180 i u tlaku**. Zapojený **před** korekční lambdu, aby se čistila i cachovaná hodnota - to je stávající a správné rozhodnutí, jen se mění mechanismus.

### 4.4 `packages/sensors.yaml` - detekce nabíjení

**DOMA cesta se nemění.** Je ověřená proti dvěma nabíjecím záznamům a nemá smysl ji rozhoupávat.

Ve spánku (`!id(cold_boot)`) běží místo ní jednodušší pravidlo nad mediánem napětí:

```
krok = medián(napětí) − last_wake_batt_v
krok > CHARGE_STEP_V  → nabíjí se
krok < RELEASE_STEP_V → nenabíjí se
last_wake_batt_v = medián(napětí)
```

Proč to stačí - změřeno na 59 cyklech nočního záznamu (mimo první 2 h, kde ještě doznívala relaxace po nabíjení):

| krok mezi probuzeními | sd | nejhorší falešný kladný |
|---|---|---|
| syrový (dnešní stav ve spánku) | 8.02 mV | **+21.6 mV** |
| přes medián ze 3 | 2.16 mV | **+0.96 mV** |

Obnovení mediánu tedy **není kosmetika - je to to, co teprve umožní tohle pravidlo**. Nabíjení zvedne napětí o ~0.004 V/min, tedy ~+40 mV za desetiminutový cyklus, proti nejhoršímu pozorovanému šumu +0.96 mV.

**Odpadá tím i celý problém s koncem nabíjení.** Dobitá baterka dá krok ~−1 mV, což je pod uvolňovacím prahem, takže se příznak pustí sám. Heuristika „vysoko a stojí" (`FULL_V`, `full_confirm_count`), která si vyžádala dvě kola ladění, je ve spánku zbytečná a v téhle větvi se nepoužije.

**Doba nabíjení:** `charge_start_ms = millis()` se probuzením nuluje, takže ve spánku se místo toho přičítá `sleep_interval_minutes` do `charge_minutes`. `Charging Duration` pak čte podle větve.

**Ochrana proti dvojímu přičtení:** `battery_voltage` má interval 60 s a v ~26s okně padne jednou, ale při probuzení tlačítkem nebo v režimu STAY může okno být delší a lambda by se spustila dvakrát. Přičítání i posun `last_wake_batt_v` proto proběhne **jen při prvním čtení po bootu**, hlídané pomocným boolem `batt_reading_counted` (třída C, `restore_value: false`, takže je každé probuzení znovu `false`).

### 4.5 `packages/sensors.yaml` - procenta baterky

Závod zmizí tím, že se procenta přestanou počítat vlastním tikem:

- výpočet se přesune do lambdy `battery_voltage`, kde je napětí z definice k dispozici, a publikuje se přes `id(battery_level).publish_state(pct)`;
- šablona `battery_level` přijde o `lambda` i o `update_interval`.

Dnešní pojistka `if (!id(battery_voltage).has_state()) return {};` tím ztratí smysl a odejde spolu s komentářem, který tvrdil, že závod nastat nemůže.

### 4.6 `packages/display.yaml` + `packages/menu.yaml` - vlnovka během chladnutí

`suspect` dostane čtvrtou podmínku: okno chladnutí po přepnutí do uspávaného režimu.

- čítač `sleep_mode_minutes` se plní stejným způsobem jako `charge_minutes`;
- nuluje se v `menu.yaml` v okamžiku, kdy se `deep_sleep_mode_enabled` přepne na `true`;
- vlnovka se ukazuje, dokud je čítač pod `COOLDOWN_MIN`.

**Odvození prahu:** z log-fitu chladnutí vychází, že se krabička dostane do 0.25 °C od plató za **183 min**. `COOLDOWN_MIN = 180`.

Fit dal τ ≈ 57 min, ale jedna exponenciála to není - z prvních bodů vychází τ 28-44 min a roste, což odpovídá dvěma tepelným hmotám (deska a baterka zvlášť). Práh se proto bere z empirického průběhu, ne z τ.

**Známá nevýhoda, přijatá vědomě:** když se do uspávaného režimu přepne už vychladlá krabička, vlnovka se ukáže zbytečně na 3 h. Alternativa (značit, dokud teplota klesá) si plete chladnutí krabičky s chladnutím auta večer, což je horší chyba.

## 5. Prahy a konstanty

| konstanta | hodnota | odkud |
|---|---|---|
| `REST_OFFSET_BMP180` ve spánku | `0.0` | duty cycle 4.2 %, čtení ~3 s po bootu - fyzika, ne měření |
| `COOLDOWN_MIN` | `180` | log-fit chladnutí: do 0.25 °C za 183 min |
| `CHARGE_STEP_V` | **prozatímně** `+0.020` | mezi nejhorším šumem (+0.96 mV) a signálem (~+40 mV) |
| `RELEASE_STEP_V` | **prozatímně** `+0.005` | všechny pozorované vybíjecí kroky jsou pod ním (nejvyšší byl +0.96 mV), takže se příznak spolehlivě pustí |

**Oba nabíjecí prahy jsou prozatímní a musí se před dokončením prohnat sweepem** proti oběma existujícím nabíjecím záznamům podvzorkovaným na 10 min - stejně, jako se ladily dnešní prahy DOMA cesty. Konkrétní riziko, které sweep musí vyloučit: v CV fázi nabíjení proud dobíhá a přírůstek napětí klesá, takže krok může spadnout pod `RELEASE_STEP_V` ještě během nabíjení a příznak by odpadl předčasně. Pokud se to potvrdí, přidá se hystereze nebo dvě potvrzení na uvolnění.

Prahy vybrané od oka jsou v tomhle projektu zakázané - viz komentář u dnešní heuristiky konce nabíjení, kde přesně tohle stálo jedno kolo navíc.

## 6. Co se záměrně nemění

- **Konstanta pro teplotu ve spánku.** Zbytkových −1.09 °C proti syrovému čtení zůstává. Jeden odečet jedním teploměrem na novou konstantu nestačí - klidový offset v DOMA se dělal ze tří odečtů po pěti minutách plus dvou kontrol platnosti a stejný protokol chce i tenhle.
- **SCD41.** Ve spánku nic nepublikuje, takže tam jeho offset nemá co pokazit.
- **DOMA cesta detekce nabíjení.** Ověřená proti dvěma záznamům.
- **`CHARGE_OFFSET_*`.** Zůstávají `0.0` - to je změřené rozhodnutí ze dvou nabíjecích záznamů, ne nedodělek.

## 7. Ověření

1. `esphome config` + `esphome compile`.
2. **Sweep obou nabíjecích prahů** proti `data/2026-08-22-charging-from-empty/` a `data/2026-08-23-charging-warm/`, podvzorkovaným na 10 min. Musí sepnout na obou a nesmí sedět na hraně - stejné kritérium jako u dnešních prahů DOMA cesty.
3. **Regresní kontrola nad nočním záznamem:** nové pravidlo nesmí za 72 probuzení sepnout ani jednou (nenabíjelo se).
4. **Regresní kontrola procent:** simulace nad nočním záznamem nesmí dát ani jedno probuzení bez platné hodnoty. Dnešní stav pro srovnání: 21 probuzení skončilo `unknown`, 41 mělo platnou hodnotu a u 10 HA nezapsal řádek (hodnota se nezměnila), takže dnešních vadných je **nejméně 21 ze 72**.
5. Na hardwaru: přepnout do CESTA se zapojenou nabíječkou, `Charging` musí chytnout do ~20 min; a ověřit, že vlnovka po přepnutí nahřáté krabičky zmizí zhruba po 3 h.

## 8. Rizika

| riziko | závažnost | co s tím |
|---|---|---|
| CV fáze shodí příznak předčasně | střední | sweep v bodě 7.2 to musí odhalit; záloha je hystereze |
| opotřebení flash z ~12 zápisů/probuzení | nízká | odhad ~53 tis. dávek/rok proti wear levelingu NVS; kdyby vadilo, přesun třídy B do RTC paměti |
| zbytkových −1.09 °C zůstává | střední | vědomé, ale **je to dvojnásobek deklarované přesnosti ±0.5 °C** - oprava snižuje chybu z −3.55 na −1.09, nezavírá ji. Zavře ji až měření třemi odečty, které zůstává na seznamu. |
| vlnovka zbytečně 3 h u vychladlé krabičky | nízká | přijato, alternativa je horší |
| dvojí přičtení čítačů při delším okně | nízká | pojistka „jen první čtení po bootu" (4.4) |

# Návrh: stav a offsety v uspávaném režimu

**Datum:** 23. 8. 2026
**Podklad:** [`data/2026-08-23-cesta-baseline/`](../../../data/README.md) - 12.4 h přes noc, 72 probuzení, s referenčním teploměrem. Prahy nabíjení navíc prohnány oběma nabíjecími záznamy.
**Dotčené soubory:** `packages/globals.yaml`, `packages/sensors.yaml`, `packages/display.yaml`, `packages/menu.yaml`, `air-quality-monitor.yaml`, `README.md`, `HANDOFF.md`

## 1. Kořen problému

**Deep sleep je plný reboot, ale firmware je psaný pro nepřetržitý běh.**

Všechny nalezené bugy jsou jeden ze dvou důsledků:

- **stav, který měl přežít, nepřežil** - mediány, detekce nabíjení, čítače času;
- **konstanta změřená za nepřetržitého běhu se použila tam, kde neplatí** - klidový offset teploty.

Čísla, ze kterých návrh vychází (všechna změřená, ne odhadnutá):

| veličina | hodnota |
|---|---|
| perioda probuzení | 625.5 s (10 min spánku + ~26 s vzhůru) |
| duty cycle | 26 / 626 = **4.2 %** |
| BMP180 plató (posledních 5 h) | 18.955 °C ± 0.043 (n=22) |
| referenční teploměr | 22.5 °C |
| chyba publikované teploty | **−3.55 °C** |
| chyba syrového čtení | −1.09 °C |
| `Battery Level` chybí | nejméně 21 ze 72 probuzení |
| přeživší výkyv BMP180 | −0.886 °C (14:43:48 lokálně) |

## 2. Rozhodnutí

| # | téma | rozhodnutí |
|---|---|---|
| 1 | offset teploty ve spánku | **odečítat nulu**, klíčem je `!cold_boot` |
| 2 | detekce nabíjení ve spánku | **krok mezi probuzeními**, vlastní větev vedle DOMA cesty |
| 3 | vlnovka ve spánku | **okno rozladění, 150 min** |
| 4 | perzistence | **flash + vynulování při `cold_boot`** |
| 5 | mediány BMP180 a tlaku | **rychlejší polling místo perzistence** |
| 6 | procenta baterky | **publikovat z lambdy `battery_voltage`** |

Body 1-3 vybral uživatel z nabídnutých variant, 4-6 asistent. Proti první, commitnuté verzi návrhu se **změnily tři věci**: mechanismus u bodu 5 (4.3), prahy a struktura u bodů 2 a 3 (4.4 a 4.6).

## 3. Politika perzistence

Dnes je poměr 13 globálů `restore_value: true` proti 26 `false`, a ta hranice vznikla postupně, ne rozhodnutím. Nově se dělí do tří tříd:

| třída | co tam patří | `restore_value` | nulovat při `cold_boot` |
|---|---|---|---|
| A - přežít spánek i vypnutí | uživatelská nastavení, cachované hodnoty pro displej | `true` | **ne** |
| B - přežít spánek, ne vypnutí | historie mediánu napětí, stav nabíjení, čítače | `true` | **ano** |
| C - resetovat se | UI/session stav (`stay_on`, `wake_was_timer`, index menu, armování CO2 alarmu) | `false` | n/a |

Třída B by správně patřila do RTC paměti (přežije spánek, ne vypnutí, nulové opotřebení). ESPHome ji ale nevystavuje - chtělo by to vlastní `includes:` hlavičku s `RTC_DATA_ATTR`, tedy nový mechanismus mimo YAML. Flash + vynulování dá **stejnou sémantiku** a zůstane to v dokumentovaných funkcích ESPHome, což v projektu s vypnutým loggerem a dlouhou frontou neotestovaných věcí váží víc než elegance.

**Opotřebení flash:** ~8 zápisů na probuzení, 144 probuzení/den. NVS drží ~126 položek na 4KB stránce a maže až plnou; při 5KB partition to vychází řádově na **stovky mazání ročně na stránku** proti výdrži 100 tis. cyklů. Není to problém. Zůstává to ale výpočet, ne měření.

### Globály třídy B

| globál | dnes | k čemu |
|---|---|---|
| `batt_v_hist1`, `batt_v_hist2` | `false` → `true` | medián napětí přes probuzení |
| `is_charging` | `false` → `true` | stav nabíjení přes spánek |
| `discharge_confirm_count` | `false` → `true` | potvrzení uvolnění (3 probuzení = 30 min) |
| `last_wake_batt_v` | nový | referenční bod pro krok mezi probuzeními |
| `charge_minutes` | nový | doba nabíjení, když `millis()` nestačí |
| `disturb_minutes` | nový | čítač okna rozladění (vlnovka) |

Čtyři překlopení a tři nové. K nim jeden pomocný bool třídy C (`batt_reading_counted`, `restore_value: false`) - viz 4.4.

## 4. Změny po souborech

### 4.1 `air-quality-monitor.yaml` - vynulování při studeném bootu

Do `on_boot`, za lambdu plnící `cold_boot`/`wake_was_timer`, přijde blok, který při `cold_boot` vynuluje **všechny globály třídy B**. Tím se z flash paměti stane spánkově-lokální úložiště.

Bez toho by čistý `restore_value: true` přežil i **vypnutí**: `is_charging` by se po týdnu na polici probudilo jako `true` a zastaralé `last_wake_batt_v` by dalo obrovský krok a spustilo falešné nabíjení.

`esp_sleep_get_wakeup_cause()` vrací `ESP_SLEEP_WAKEUP_UNDEFINED` i po OTA rebootu, takže se stav vynuluje i tam. To je **bezpečný směr** - firmware se radši rozkouká znovu, než aby věřil starému příznaku.

### 4.2 `packages/sensors.yaml` - teplota BMP180

```cpp
float extra = id(cold_boot) ? REST_OFFSET_BMP180 : 0.0f;
if (id(is_charging)) extra += CHARGE_OFFSET_BMP180;
```

`!cold_boot` znamená doslova „tenhle boot je probuzení ze spánku", tedy krabička byla 10 min v tepelné rovnováze s okolím a **není co odečítat**. Klíčem je fyzická historie, ne uživatelské nastavení - tím se to nebije se zásadou u displeje, která větvení podle režimu záměrně nepoužívá.

Kontrola řádu: klidový odběr ve spánku je ~0.3 mA (SCD41 zaparkovaný, dělič, LDO). Tepelný odpor krabičky vychází ze známého bodu - 2.46 °C při ~34 mA a 4 V, tedy ~18 K/W. Ve spánku to dělá **~0.02 °C**. Nula je správně.

Projde všemi případy: probuzení časovačem i tlačítkem (offset 0, krabička byla v rovnováze), OTA i brownout reboot v DOMA (offset se odečítá, krabička je horká), prodloužené okno vzhůru (za 2 min běhu naroste self-heating o ~0.1 °C, zanedbatelné proti τ ≈ 45 min).

**Známá asymetrie, která zůstává:** po studeném zapnutí je `cold_boot` pravdivé a offset se odečítá, i když je krabička taky studená. To je ta doložená chyba −1.1 °C v 10. minutě. Zůstává schovaná za vlnovkou. Zvažena byla rampa podle doby běhu, která by opravila i tohle - zamítnuta, protože by přesností vylepšovala hodnotu, která je stejně označená jako nedůvěryhodná, za cenu modelu podle času (třída nápadu, na které se v1 spálila).

**SCD41 se nemění.** Jeho `temperature_offset: 6.7°C` je uvnitř senzoru a ve spánku stejně nic nepublikuje.

### 4.3 `packages/sensors.yaml` - mediány BMP180 a tlaku ZMĚNA PROTI PRVNÍ VERZI

První verze návrhu chtěla přepsat `median:` na ruční variantu s flash-backed globály. **To je zbytečné.** Filtr nefunguje jen proto, že při `update_interval: 60s` dorazí za probuzení jediné čtení a okno se nikdy nenaplní. Stačí tedy zrychlit polling:

- `update_interval` u `bmp085` z `60s` na **`5s`** (stejně jako SCD41);
- `median` dostane `send_first_at: 3`, aby se publikovaly **jen plně filtrované hodnoty** - dnešní `send_first_at: 1` by první dvě čtení každého probuzení pustil nefiltrovaně;
- za korekční lambdu přibude `delta` filtr, aby se v DOMA nezaplavil recorder dvanácti řádky za minutu. Umístění **za** lambdu je stejné rozhodnutí jako u SCD41: cache se má aktualizovat každým čtením, i když HA řádek nepotřebuje.

V ~26s okně tak dorazí ~5 čtení, okno se naplní a **filtr funguje uvnitř jednoho bootu**. Odpadají čtyři globály i celý problém s perzistencí u dvou ze tří senzorů.

Energeticky je to zdarma: BMP180 spotřebuje na převod ~5 µA·s, při 0.2 čtení/s tedy ~1 µA průměrně proti ~34 mA celkem.

`battery_voltage` zůstává na 60 s. Jeho vzorkovací frekvence je nosná pro prahy DOMA detekce nabíjení a měnit ji by znamenalo přeladit ověřený kód. Jeho medián se proto řeší perzistencí (globály jsou potřeba i pro pravidlo v 4.4).

### 4.4 `packages/sensors.yaml` - detekce nabíjení

**DOMA cesta se nemění.** Je ověřená proti dvěma nabíjecím záznamům.

Ve spánku (`!id(cold_boot)`) běží místo ní pravidlo nad mediánem napětí:

```
krok = medián(napětí) − last_wake_batt_v
krok > +20 mV                        → nabíjí se
krok < 0 mV, třikrát po sobě (30 min) → nenabíjí se
last_wake_batt_v = medián(napětí)
```

Proč medián není kosmetika - změřeno na 59 cyklech nočního záznamu (mimo první 2 h, kde doznívala relaxace po nabíjení):

| krok mezi probuzeními | sd | nejhorší falešný kladný |
|---|---|---|
| syrový (dnešní stav ve spánku) | 8.02 mV | **+21.6 mV** |
| přes medián ze 3 | 2.16 mV | **+0.96 mV** |

Bez mediánu by se práh +20 mV o šum otřel. S ním má rezervu 19 mV. Nabíjení zvedne napětí o ~0.004 V/min, tedy **~+40 mV za desetiminutový cyklus**.

**Doba nabíjení:** `charge_start_ms = millis()` se probuzením nuluje, takže se místo toho přičítá `sleep_interval_minutes` do `charge_minutes`. `Charging Duration` čte podle větve.

**Ochrana proti dvojímu přičtení:** `battery_voltage` má interval 60 s a v ~26s okně padne jednou, ale při probuzení tlačítkem nebo v režimu STAY může být okno delší a lambda by běžela dvakrát. Přičítání čítačů i posun `last_wake_batt_v` proto proběhne **jen při prvním čtení po bootu**, hlídané boolem `batt_reading_counted` (třída C, takže je každé probuzení znovu `false`).

**Heuristika konce nabíjení se v téhle větvi nepoužije.** `FULL_V` a `full_confirm_count` řeší dead zone EWMA pravidla - krok mezi vzorky ji nemá, protože konstantní napětí dá krok 0, což je pod uvolňovacím prahem.

### 4.5 `packages/sensors.yaml` - procenta baterky

Závod zmizí tím, že se procenta přestanou počítat vlastním tikem:

- výpočet se přesune na konec lambdy `battery_voltage`, kde je napětí z definice k dispozici, a publikuje se přes `id(battery_level).publish_state(pct)`;
- šablona `battery_level` přijde o `lambda` i o `update_interval`.

Pojistka `if (!id(battery_voltage).has_state()) return {};` tím ztratí smysl a odejde i s komentářem, který tvrdil, že závod nastat nemůže.

### 4.6 `display.yaml` + `menu.yaml` - vlnovka přes okno rozladění ZMĚNA PROTI PRVNÍ VERZI

První verze vázala vlnovku na časovač od přepnutí režimu a nechávala nabíjení na `is_charging`. Sweep v 7.2 ukázal, že **uvolňovací hrana `is_charging` se přesně trefit nedá** - CV fáze nabíjení je od pomalého vybíjení k nerozeznání, obojí je „vysoko a plocho". Návrh proto **přestává na té hraně stavět**.

Zavádí se jeden čítač `disturb_minutes`, který znamená „jak dlouho je krabička tepelně v klidu", a nuluje ho **cokoliv, co ji rozladí**:

- **vstup do spánku**, podle toho, jak dlouho zařízení do té chvíle běželo v kuse;
- **každý krok napětí nad `CHARGE_STEP_V`** podle 4.4 - tedy ne jen okamžik sepnutí, ale každé další stoupnutí i během už běžícího nabíjení, takže se čítač po celou CC fázi drží na nule.

První bod se **opravil proti první verzi návrhu**, která ho vázala na přepnutí režimu v menu. To je špatný okamžik: nejčastější cesta do CESTA je zapnout krabičku vypínačem v autě a hned přepnout režim - krabička je v tu chvíli studená a vlnovka by svítila 2.5 h zbytečně, a to zrovna v tom nejběžnějším případě. Rozhodovat se má podle toho, jestli se krabička **stihla ohřát**:

```cpp
id(disturb_minutes) = (millis() < 5 min) ? COOLDOWN_MIN : 0.0f;
```

Zařízení, které jde spát do pěti minut od bootu, se ohřát nestihlo a značí se jako ustálené. Cokoliv delšího se bere jako rozladěné. Je to schod, ne rampa, a záměrně chybuje směrem k označení: prahu pět minut proti τ ≈ 45 min odpovídá ohřátí pod 0.2 °C.

Čítač tiká jen v probuzeních ze spánku (`!cold_boot`); v DOMA se nepoužívá, protože tam `is_charging` pokrývá nabíjení sám. Jakmile dosáhne `COOLDOWN_MIN`, přestane se zvyšovat - tím se zároveň zastaví zápisy do flash.

`suspect` v `display.yaml` dostane třetí podmínku:

```cpp
bool suspect = (id(cold_boot) && millis() < WARMUP_MS)   // zahřívání po studeném startu
            || id(is_charging)                            // nabíjení (beze změny)
            || (!id(cold_boot) && id(disturb_minutes) < COOLDOWN_MIN);
```

Přesnost je tím přesunutá tam, kde na ní záleží. `is_charging` zůstává best-effort diagnostika do HA, ale **vlnovka na jeho uvolňovací hraně nezávisí**: teplo z nabíjení odeznívá ~1.5 h, což okno 150 min pokryje i když příznak spadne uprostřed CV fáze.

**Odvození `COOLDOWN_MIN = 150`:** z log-fitu chladnutí klesne chyba pod **0.5 °C za 144 min** - a 0.5 °C je deklarovaná přesnost celého zařízení, tedy hranice, pod kterou už hodnota důvěryhodná je. 150 je 144 zaokrouhlených nahoru. (První verze měla 180 min podle hranice 0.25 °C, což je přísnější, než na co si zařízení kdekoliv jinde troufá.)

**Přijatá nevýhoda:** když se do uspávacího režimu přepne už vychladlá krabička, vlnovka se ukáže zbytečně na 2.5 h. Varianta „značit, dokud teplota klesá" si plete chladnutí krabičky s chladnutím auta večer, což je horší chyba. A zbytečná vlnovka je bezpečný směr.

## 5. Konstanty a odkud jsou

| konstanta | hodnota | odkud |
|---|---|---|
| `REST_OFFSET_BMP180` ve spánku | `0.0` | duty cycle 4.2 %, kontrola řádu přes tepelný odpor dá ~0.02 °C |
| `COOLDOWN_MIN` | `150` min | log-fit chladnutí: pod 0.5 °C za 144 min |
| `CHARGE_STEP_V` | `+0.020` | sweep: necitlivé od +12 do +30 mV, 0 falešných za 72 probuzení |
| release | `< 0` mV | sweep: `+5 mV` osciluje, `<0` ne |
| `RELEASE_CONFIRM` | `3` (30 min) | sweep: 2 pouští o 58 min dřív, 3 trefí konec na 2 min |
| `bmp085 update_interval` | `5s` | aby se naplnilo okno mediánu uvnitř probuzení (~5 čtení) |

Poznámka k `RELEASE_CONFIRM`: ground truth pro konec nabíjení máme jen z **jednoho** záznamu (`charging-from-empty`, skončilo ~18:10Z). Tam `3` pouští v 18:08 a `4` až za koncem výřezu. Obojí je obhájitelné a **pozdější uvolnění je bezpečný směr**; `3` je ta hodnota, kterou umíme doložit. `2` je vyloučené.

## 6. Co se záměrně nemění

- **Konstanta pro teplotu ve spánku.** Zbytkových −1.09 °C zůstává. Jeden odečet jedním teploměrem nestačí - klidový offset v DOMA se dělal ze tří odečtů plus dvou kontrol platnosti.
- **SCD41.** Ve spánku nic nepublikuje.
- **DOMA cesta detekce nabíjení.** Ověřená proti dvěma záznamům.
- **`CHARGE_OFFSET_*`.** Zůstávají `0.0` - změřené rozhodnutí, ne nedodělek.
- **Armování CO2 alarmu.** Ověřeno v 7.3, funguje. `co2_alarm_armed` a `co2_hist1/2` správně zůstávají třída C.

## 7. Ověření

### 7.1 Statické

`esphome config` + `esphome compile`.

### 7.2 Sweep prahů - HOTOVO

Obě nabíjecí sady podvzorkované na 10 min, plus noční záznam jako regrese:

| práh sepnutí | z prázdné | teplé | noční (72 probuzení) |
|---|---|---|---|
| +12 až +30 mV | ON 14:30, OFF 18:08 | ON 22:27, nepouští (výřez končí dřív) | **0 sepnutí** |

(Sloupce OFF platí pro zvolené uvolňovací pravidlo `<0 mV` × 3; samotné uvolnění je rozebrané pod tabulkou.)

Práh je přes celý rozsah **necitlivý** - všech pět hodnot dá identický výsledek, takže +20 mV nesedí na hraně. Falešné sepnutí nenastalo ani při +10 mV.

Uvolnění: `+5 mV` s jedním potvrzením **osciluje** (ON→OFF→ON za 20 min), `<0 mV` ne. Počet potvrzení: 2 → 17:12, 3 → 18:08, 4 → za koncem záznamu. Skutečný konec nabíjení byl ~18:10.

### 7.3 Armování CO2 alarmu - HOTOVO

Otázka, jestli se stabilitní pravidlo („3 čtení do 150 ppm") vejde do 30s okna, byla otevřená. Simulace nad 72 probuzeními nočního záznamu: **armuje se ve všech 72**, pokaždé na 3. čtení, tříminutový fallback se nepoužil ani jednou. Armující čtení se vyhodnocuje i proti prahu, takže alarm má šanci sepnout v každém probuzení.

Neověřuje to, že alarm skutečně sepne - CO2 v záznamu nepřesáhlo 1744 ppm proti prahu 3000. Ověřuje to, že mu v tom nebrání armování.

### 7.4 Regrese, které je potřeba doběhnout

- **Procenta:** simulace nad nočním záznamem nesmí dát ani jedno probuzení bez platné hodnoty. Dnes: 21 `unknown`, 41 platných, 10 bez řádku (hodnota se nezměnila), tedy **nejméně 21 ze 72** vadných.
- **Medián BMP180:** po zrychlení pollingu musí výkyv typu 14:43:48 zmizet. Ověřit lze jen na novém záznamu, protože dnešní data mají jedno čtení za probuzení.

### 7.5 Na hardwaru

- Přepnout do CESTA se zapojenou nabíječkou: `Charging` musí chytnout do ~20 min.
- Po přepnutí nahřáté krabičky musí vlnovka zmizet zhruba po 2.5 h.
- Teplota v CESTA musí skočit o ~2.5 °C nahoru proti dnešku (to je ta oprava).

## 8. Rizika

| riziko | závažnost | co s tím |
|---|---|---|
| `RELEASE_CONFIRM` stojí na jednom ground-truth bodě | střední | pozdější uvolnění je bezpečný směr; vlnovka na té hraně nezávisí (4.6) |
| nabíjení začaté v CV fázi (baterka nad ~95 %) se nemusí zachytit vůbec | střední | krok by byl pod +20 mV; dokumentovat jako známé omezení, teplo z takového dobíjení je stejně nejmenší |
| zbytkových −1.09 °C zůstává | střední | **je to dvojnásobek deklarované ±0.5 °C** - oprava chybu snižuje z −3.55 na −1.09, nezavírá ji |
| zrychlení `bmp085` na 5s změní, co vidí HA | nízká | řeší `delta` filtr; vedlejším efektem je méně řádků v recorderu než dnes |
| opotřebení flash | nízká | výpočet dává stovky mazání stránky ročně proti 100 tis. cyklů |
| vlnovka zbytečně 2.5 h u vychladlé krabičky | nízká | přijato, bezpečný směr |
| dvojí přičtení čítačů při delším okně | nízká | pojistka „jen první čtení po bootu" (4.4) |

# ESP32-C3 Air Quality Monitor

Bateriový monitor kvality vzduchu postavený na Seeed XIAO ESP32-C3, běžící na [ESPHome](https://esphome.io/) a integrovaný do Home Assistant. Měří CO₂, teplotu, vlhkost a tlak, s malým OLED displejem pro stav a tlačítkem pro probuzení / trvalé zapnutí.

<p align="center">
  <img src="images/final.webp" width="400">
</p>


## Funkce

- CO₂, teplota a vlhkost přes Sensirion SCD41
- Sekundární teplota + barometrický tlak přes BMP180
- 128x32 I2C OLED displej, střídá 5 stránek po 3s
- Ovládání tlačítkem: jedno kliknutí probudí displej na 30s, dvojklik přepíná trvalý režim "stay on", drž 5s+ otevře nastavovací menu
- **Nastavovací menu s presety pro dva způsoby použití** (viz [Menu a presety](#menu-a-presety) níže): **DOMA** (na stole, trvale připojeno do HA) a **CESTA** (bez WiFi, hluboký spánek mezi měřeními, lokální CO₂ alarm na displeji)
- **Hluboký spánek** mezi měřeními pro úsporu baterie na cestách, s nastavitelným intervalem (5/10/15/30/60 min) a poslední naměřenou hodnotou uloženou ve flash, takže displej po probuzení/zapnutí hned ukazuje správná čísla, ne "--" nebo staré nesmysly
- **Lokální CO₂ alarm** - když je zařízení bez HA (např. v autě přes noc) a CO₂ přesáhne bezpečný práh, displej se sám rozsvítí a bliká s varováním
- Sledování napětí/procenta baterky přes odporový dělič, s 30x přeexponovaným (oversampled) čtením ADC pro potlačení šumu
- Detekce nabíjení z pomalého klouzavého trendu napětí baterky (odolná vůči krátkodobé WiFi zátěži), entity `Charging` a `Charging Duration`
- Automatické vypnutí displeje kvůli úspoře baterky
- WiFi záložní AP + captive portal, pokud je nakonfigurovaná síť nedostupná

## Hardware / BOM

| Součástka | Poznámka |
|---|---|
| Seeed XIAO ESP32-C3 | Hlavní MCU |
| Sensirion SCD41 | CO₂ / teplota / vlhkost, I2C adresa `0x62` |
| BMP180 | Teplota / tlak, I2C adresa `0x77` |
| SSD1306 128x32 OLED | I2C adresa `0x3C` |
| LiPo baterie ~500mAh | Napájí zařízení. Recyklovaná z jednorázové vapy, viz sekce Baterie níže |
| TP4056 nabíjecí/ochranný modul (s DW01A + FS8205A) | Mezi XIAO BAT+/BAT- a baterkou, viz sekce Baterie níže |
| Externí flat/nálepková WiFi anténa (u.FL) | Nahrazuje vestavěnou PCB anténu na desce, na kabelu, viz [ASSEMBLY.md](ASSEMBLY.md) |
| Tlačítko | Připojeno na GPIO3 |
| Rezistory 220kΩ + 100kΩ | Dělič napětí baterky (BAT+ → GPIO4 → GND) |
| Rezistory 4.7kΩ x2 | Externí I2C pull-upy na SDA a SCL |
| Hlavní vypínač (v2) | V sérii mezi baterkou a TP4056 modulem - úplné odpojení napájení, viz [WIRING.md](WIRING.md) |
| 3D tištěný kryt (PLA), v2 | Nový kryt, viz [`enclosure/README.md`](enclosure/README.md) - postup sestavení v [ASSEMBLY.md](ASSEMBLY.md) zatím odpovídá starému (v1) krytu |

## Zapojení

Kompletní GPIO pinout a schéma zapojení viz [WIRING.md](WIRING.md).

## Firmware

Kompletní ESPHome konfigurace je v [`air-quality-monitor.yaml`](air-quality-monitor.yaml). Před nahráním zkopíruj `secrets.yaml.example` do `secrets.yaml` a doplň vlastní WiFi údaje, API encryption klíč a OTA heslo.

```yaml
wifi_ssid: "your-ssid"
wifi_password: "your-password"
api_encryption_key: "base64-key"
ota_password: "your-ota-password"
fallback_ap_password: "your-fallback-password"
```

**Nadmořská výška:** v `air-quality-monitor.yaml` je u SCD41 nastavené `altitude_compensation: 435m`. Tohle je výchozí hodnota nastavená podle mojí konkrétní lokace, ovlivňuje přesnost přepočtu CO₂. Pokud si tenhle config používáš jinde, uprav si tu hodnotu na nadmořskou výšku svýho místa.

## Menu a presety

Podrž tlačítko 5s+ pro vstup do nastavovacího menu. Uvnitř menu:
- **Jedno kliknutí** - další položka (cyklicky)
- **Dvojklik** - odejít z menu beze změny (co už bylo potvrzeno 5s-holdem, zůstává uložené)
- **Drž 5s+** - potvrdit/přepnout aktuální položku

| Položka | Co dělá |
|---|---|
| REZIM | Aplikuje celý preset (DOMA/CESTA) najednou - viz tabulka níže. Pokud se aktuální nastavení neshoduje s žádným presetem (protože jsi něco upravil ručně), zobrazí se CUSTOM. |
| HA PRIPOJENI | Ruční přepínač WiFi/HA připojení. |
| INTERVAL SPANKU | Cykluje presety [5, 10, 15, 30, 60] minut - jak dlouho spí hluboký spánek. |
| DEEP SLEEP | Když zapnuto, JAKÉKOLIV zhasnutí displeje (30s timeout i ruční klik) rovnou uspí celé zařízení místo pouhého zhasnutí. |
| CO2 ALARM | Zapíná/vypíná lokální varování na displeji při vysokém CO2 (viz níže). |
| ASC KALIBRACE | Zapíná/vypíná automatickou self-kalibraci SCD41 (viz Known Issues níže) - **projeví se až po dalším rebootu/probuzení**, ne okamžitě. Součást presetů DOMA/CESTA (viz tabulka níže), ale jde přepnout i ručně zvlášť. |

| Preset | HA PRIPOJENI | DEEP SLEEP | INTERVAL SPANKU | CO2 ALARM | ASC KALIBRACE |
|---|---|---|---|---|---|
| **DOMA** | zapnuto | vypnuto | - | vypnuto | zapnuto |
| **CESTA** | vypnuto | zapnuto | 10 min | zapnuto | vypnuto |

**CO2 ALARM** je pro situace bez HA (typicky CESTA - např. v autě přes noc): pokud CO2 překročí bezpečný práh (aktuálně 3000ppm spuštění / 2700ppm zhasnutí, hystereze proti blikání), displej se sám rozsvítí a bliká s varováním, i kdyby byl předtím zhasnutý/zařízení v hlubokém spánku. Automatické zhasnutí/uspání se dočasně zablokuje, dokud hodnota neklesne zpátky pod práh - manuální klik tlačítka vždy funguje jako potvrzení/odložení.

Alarm se po každém zapnutí/probuzení **neaktivuje hned** - hodnoty po startu můžou být divoké a nemá z nich spouštět planý poplach. Podrobně (včetně toho, proč SCD41 měří po 5s a ne po 60s) viz [Zahřívání po zapnutí](#zahřívání-po-zapnutí) níže.

## Kryt

3D tištěný z PLA. Zdrojový soubor: [`enclosure/README.md`](enclosure/README.md). Postup sestavení viz [ASSEMBLY.md](ASSEMBLY.md).

## Baterie

Baterie se nenabíjí přímo přes vestavěný nabíjecí obvod XIAO. Mezi XIAO a baterkou je zapojený externí **TP4056 modul**: XIAO BAT+ a BAT- jdou do OUT+ a OUT- na TP4056, a B+ a B- na TP4056 jdou do samotné baterky. TP4056 tak dělá nabíjení místo XIAO desky.

Deska má kromě hlavního TP4056 čipu i DW01A a FS8205A, takže jde o variantu **s ochranou**, ne jen o holou nabíječku. To řeší ochranu proti přebití, podvybití a zkratu. **Empiricky ověřeno (srpen 2026):** při vybití baterky přibližně pod ~2.5V ochrana skutečně sepne a odpojí napájení - v tu chvíli spadne celé zařízení (ESP32 ztratí napájení, protože jde přes stejnou OUT+/OUT- cestu jako dělič napětí baterky - viz [WIRING.md](WIRING.md)). Zařízení se prostě přestane hlásit do HA (offline), nezasílá žádnou špatnou/plovoucí hodnotu - ADC/ESP32 v tu chvíli neběží vůbec.

Za normálního provozu (mimo zásah ochrany) tohle umístění děliče na přesnost ani na detekci nabíjení nemá prakticky žádný vliv - ochranný FET má v sepnutém stavu odpor jen v řádu desítek miliohmů.

Než na to spolehneš dlouhodobě, stojí za to ověřit:
- **Napětí naprázdno a pod zátěží** multimetrem, ať vidíš, jestli se chová jako zdravý článek (viz Known Issues níže pro kalibraci čtení)
- **Fyzický stav článku** (nabobtnání, poškození obalu) před zabudováním do krytu
- **Přítomnost/nepřítomnost ochranného obvodu** - pokud článek nemá vlastní BMS/protection PCB, spoléháš čistě na nabíjecí obvod na XIAO desce

## Zahřívání po zapnutí

Po zapnutí (hlavní vypínač baterky) nejsou hodnoty hned přesné. Z reálného záznamu ([`data/2026-08-22-power-on-warmup/`](data/README.md)) je vidět, že jsou to **dvě fáze, které spolu nesouvisí** - tvar křivky je změřený, konkrétní délka fáze 3 je dopočítaná (viz poznámka pod odrážkami):

| Fáze | Co se děje |
|---|---|
| **0-3 min** | **Chyba samotného SCD41**, ne teplota. Hlásí o ~2 °C víc, vlhkost o ~10-14 % míň. Prokázáno na reálných datech - viz Known Issues. Firmware tahle čtení **zahazuje úplně**, do HA se nedostanou. |
| **3-45 min** | Teprve tady se zahřívá krabička. Teplotní offset platí jen v tepelné rovnováze, takže dokud se box neprohřeje, je hodnota systematicky nízko, i když vypadá stabilně. Datasheet proto žádné číslo nedává, jen říká "in thermal equilibrium". |

Kolik chyby zbývá v které minutě (měřeno na BMP180, který se ustálí kolem 24.15 °C):

| čas | 10 min | 20 min | 30 min | 40 min | 50 min |
|---|---|---|---|---|---|
| chyba | −1.11 °C | −0.58 °C | −0.34 °C | −0.18 °C | −0.06 °C |

Časová konstanta je 13-15 min, ustálení tedy trvá zhruba 3τ.

Firmware to řeší dvěma způsoby:

- **CO₂ alarm se neaktivuje, dokud se hodnoty neuklidní.** Místo pevného čekání sleduje samotná čtení: povolí se, až když jsou 3 čtení po sobě v rozsahu do 150 ppm. Pojistka - pokud se hodnoty neuklidní vůbec, alarm se povolí po 3 minutách tak jako tak (radši hlídat s nejistotou než nehlídat). Jednou povolený se už nevypíná - reálný rychlý nárůst CO₂ v autě by rozptyl překročil a alarm by zmizel přesně ve chvíli, kdy je potřeba.

  SCD41 kvůli tomu měří **po 5s** místo výchozích 60s. Není to kvůli "čerstvějším datům": 5s je vlastní interní vzorkovací rychlost SCD41, takže to nestojí víc energie senzoru, a v režimu CESTA je zařízení vzhůru jen 30s - při pomalejším čtení by na posouzení stability (natož na samotné spuštění alarmu) prostě nezbyl prostor.
- **Prvních 5 čtení SCD41 se zahodí.** Teplota a vlhkost ze SCD41 se první 3 minuty po každém bootu vůbec nepublikují ani neukládají do cache. Není to opatrnost - je to oprava reálného problému, kdy si HA po vybití baterky uložilo jako poslední teplotu hodnotu, která nikdy nebyla naměřená (viz Known Issues).
- **Vlnovka.** `~` před hodnotou (`~25.1 C`) na obou teplotních stránkách i na vlhkosti znamená "tuhle hodnotu neber doslova". Objeví se ve dvou případech: prvních **45 min po studeném startu** (zahřívá se krabička) a **po celou dobu nabíjení** (to je ve skutečnosti ten větší vliv, až +3.7 °C - viz Known Issues). Vlhkost je označená taky, protože ji SCD41 počítá z té samé teploty, takže se veze s ní.

**Po probuzení z deep sleepu se vlnovka nezobrazí** - větev 3V3 se ve spánku nevypíná, takže krabička zůstává tepelně ustálená a zahřívat se nemusí znovu.

> Těch 45 min je změřené, ne odhadnuté. Předchozí hodnota 20 min pocházela z extrapolace záznamu, který se ukázal být teplý restart - fitovat exponenciálu na krátký, skoro ustálený ocas dalo časovou konstantu necelou polovinu skutečné, a odhad tím pádem přestřelil o víc než dvojnásobek.

## Naměřená data

Skoro každé konkrétní číslo v tomhle README (i většina konstant ve firmwaru) pochází z reálného měření, ne z odhadu. Syrové exporty z Home Assistant History jsou ve složce [`data/`](data/README.md) i s popisem, za jakých podmínek každý záznam vznikl a co z něj vyšlo - včetně toho, co ještě chybí změřit.

## Known Issues

- **Napětí/procento baterky není přesné.** Čtení teď vychází o pár procent výš než multimetr (~+2.6 % pozorováno zatím). Hodnoty děliče a čtení ADC jsou principiálně správně, ale přesný multiplikátor ještě nebyl pořádně zkalibrovaný napříč celým rozsahem napětí. Ber procenta baterky jako orientační, ne přesný údaj.
- **Riziko driftu CO₂ auto-kalibrace (ASC) - teď vypínatelné v menu (srpen 2026).** `automatic_self_calibration` je na SCD41 defaultně zapnutá. ASC předpokládá, že senzor pravidelně vidí čerstvý venkovní vzduch (~400ppm) a podle toho si upravuje baseline (klouzavé okno v řádu dní - jedna špatně větraná noc v autě sama o sobě baseline výrazně neurve, okno je navržené přesně proti tomuhle). Pokud senzor sedí dlouhodobě v prostoru, co se málokdy pořádně vyvětrá, ASC si může posunout baseline vůči špatné referenci a časem podhodnocovat CO₂. Nová menu položka **ASC KALIBRACE** (viz Menu a presety výš) jde vypnout/zapnout ručně, např. před cestou - **projeví se až po dalším rebootu/probuzení** zařízení, protože ESPHome umí ASC nastavit jen při startu, ne za běhu; přepnutí v menu proto jen uloží preferenci, kterou firmware aplikuje přes raw I2C příkaz (SCD4x `0x2416`) při příštím bootu. Implementováno bez `persist_settings` (SCD41 vlastní NVM) záměrně - firmware si nastavení pamatuje samo (ESP32 flash) a při každém bootu ho podle potřeby znovu vynutí, takže NVM senzoru se zbytečně neopotřebovává opakovaným zápisem.
- **Detekce nabíjení měla vážný bug, teď opravený a ověřený z obou stran (srpen 2026).** Původní debounce fix (proti false-positive z WiFi zátěže) byl nastavený na příliš vysoký práh - v reálném testu se `Charging` nespustilo ani jednou za celý 2.5h nabíjecí cyklus. Opraveno použitím pomalého klouzavého baseline napětí (časová konstanta ~10min) místo trendu z jednoho vzorku, s nižším prahem (0.015V/-0.01V). Ověřeno v praxi při reálném nabíjení, a od té doby i **proti hodinovému záznamu vybíjení** (`data/2026-08-22-doma-baseline/`): `Charging` zůstalo celou dobu vypnuté a simulace algoritmu nad těmi daty dala maximální trend **-0.0003 V** proti prahu +0.015 V, tedy žádné falešné sepnutí ani zdaleka.
- **Při nabíjení je teplota až o 3.7 °C vyšší než realita a firmware to záměrně neopravuje.** Změřeno proti referenčnímu teploměru přes celý nabíjecí cyklus z prázdné baterky ([`data/2026-08-22-charging-from-empty/`](data/README.md)): ve vrcholu CC fáze (~40 min od zapojení) byla krabička **+3.7 °C** nad svým ustáleným stavem, drželo se to ~30 min a pak to během ~1.5 h kleslo zpátky na nulu, jak nabíjecí proud dobíhal. Stejný tvar na obou senzorech, takže se ohřívá celá krabička. **Konstanta to opravit nemůže:** teplo je úměrné nabíjecímu proudu, a ten závisí na tom, jak prázdná baterka byla - z nuly dostaneš hodinu plného proudu, dobití z 90 % skoro nic. Jedno číslo by muselo být vedle až o ±3.7 °C podle situace. Křivka podle času selže stejně - to zkoušela v1 a v terénu přestřelila o ~4 °C. Firmware proto `CHARGE_OFFSET_*` nechává na `0.0`, publikuje `Charging` do HA (kde se dá filtrovat) a na displeji dává během nabíjení před teplotu `~`.
- **`Charging` nepozná konec nabíjení, jen 3hodinovou pojistku.** Ve stejném záznamu sepnulo správně 5 min po zapojení, ale vyplo se přesně po 3 h - což je bezpečnostní timeout, ne detekce. Skutečné nabíjení skončilo o hodinu dřív (napětí přestalo růst na 4.15 V). Důvod: pokles napětí po dobití je jen ~0.0009 V/min a nikdy nepřekročí práh −0.01 V proti klouzavému baseline. Prakticky to znamená, že `Charging = on` říká "nabíjelo se někdy za poslední 3 hodiny", ne "teče proud právě teď".
- **SCD41 hlásí první ~2 minuty po startu měření o několik °C víc (potvrzeno, ošetřeno).** Není to zahřívání krabičky, je to chování samotného senzoru. Dokázáno dvěma nezávislými způsoby ze záznamu [`data/2026-08-22-cold-start/`](data/README.md): (a) ze **studeného** startu hlásí SCD41 v 6. vteřině o 2.13 °C **víc** než BMP180, ve 2. minutě je naopak pod ním, a pak se srovnají - studený čip nemůže hlásit vysoko; (b) při **brownout restartu** umírající baterky skočil z 24.04 na **28.42 °C za necelých 38 s**, zatímco BMP180 stál na 23.58 - reálná změna o 4.4 °C při klidném druhém senzoru je nemožná. Za celých 6.5 h záznamu jsou skoky nad 1 °C přesně dva a oba sedí na restart. **Ošetřeno:** teplota a vlhkost SCD41 se první 3 min po bootu zahazují (viz [Zahřívání po zapnutí](#zahřívání-po-zapnutí)). **Zbývá ověřit:** jestli to spouští i probuzení z deep sleepu. Při brownoutu i studeném startu senzor ztratil napájení, kdežto v deep sleepu 3V3 běží dál a restartuje se jen měření - to nemusí být totéž. Pokud ano, je v režimu CESTA (30 s vzhůru) teplota ze SCD41 nedostupná úplně a bude se muset brát z BMP180, který transient nemá.
- **Po vybití baterky zůstane v HA viset hodnota, která nebyla naměřená (opraveno).** Když baterka došla ([`data/2026-08-22-cold-start/`](data/README.md)), zařízení se cestou dolů dvakrát brownout-restartovalo a pokaždé stihlo publikovat transient ze SCD41. Poslední, co HA dostalo a pak na tom zůstalo viset, bylo **27.43 °C** (realita 23.58) a **53.7 %** vlhkosti (předtím 64.96). Navíc to vypadalo jako dvě měření, i když bylo jen jedno: po krátkém výpadku spojení poslalo ESPHome ty samé stavy z RAM znovu a HA je zalogovalo jako změnu, protože entita mezitím byla `unavailable`. Poznat se to dá podle **bit-identických** floatů. Opraveno tím zahazováním prvních 3 minut - transient se do HA vůbec nedostane a poslední zapamatovaná hodnota tak zůstane ta poslední skutečně naměřená.
- **Offset self-heatingu se nejspíš liší mezi režimy DOMA a CESTA (nezměřeno).** Klidový offset (`temperature_offset: 5.6°C`, `REST_OFFSET_BMP180: 1.74`) byl ověřený v režimu **DOMA**, kde je zařízení pořád vzhůru se zapnutou WiFi. V **CESTA** zařízení většinu času spí (deep sleep), takže se zahřívá výrazně míň - stejný offset tam pravděpodobně odečítá víc, než by měl, a teplota vyjde podchlazená. Potřebuje vlastní záznam v režimu CESTA proti referenčnímu teploměru; zatím jen zdokumentováno, firmware s tím nepočítá.
- **BMP180 občas pustí jedno úplně vedlejší čtení (opraveno, srpen 2026).** V hodinovém záznamu (`data/2026-08-22-doma-baseline/`, 01:56:54Z) spadla teplota na 24.41 °C mezi sousedy ~24.70 °C - a **stejné čtení** zároveň ukázalo tlak 956.41 hPa proti sousedním ~957.05 hPa. Jde tedy o jedno špatné I2C čtení, ne o šum na jednom kanálu. BMP180 do té doby neměl žádný filtr, takže se ta hodnota propsala do HA, na displej i do cache. Přidán `median` filtr (okno 3) na teplotu i tlak, zapojený **před** korekční lambdu, aby se čistila i cachovaná hodnota.
- **Napětí baterky skákalo nahoru v okamžiku připojení nabíječky - z velké části vyřešeno přepojením v2 (srpen 2026).** Reálný capture (`data/2026-08-21-v1-charger-connect/`) s v1 zapojením (dělič na BAT+/BAT- pinech XIAO, tedy za TP4056 modulem): klidové ~3.72V, hned po zapojení nabíječky skok na ~4.11-4.18V během 1 minuty. Po přepojení horní nohy děliče přímo na B+ baterky (viz [WIRING.md](WIRING.md)) se skok v praxi výrazně zmenšil/zmizel - ukazuje to, že většina toho skoku nebyla čistě vnitřní odpor článku, ale přidaná sériová impedance z trasy/kontaktů TP4056 modulu, kterou nové zapojení obchází. Menší zbytkový skok (čistě z vnitřního odporu článku samotného) je pořád fyzikálně očekávatelný, hlavně u recyklovaného/staršího článku - to není bug.
- **Jednorázové šumové výkyvy v `Battery Voltage` (opraveno, srpen 2026).** Stejný capture ukázal jedno čtení (celá 60s perioda) o ~0.13V níž než sousední - pravděpodobně krátký pokles napájení při WiFi vysílání zasáhl celou dávku 30 oversamplovaných čtení najednou (ta běží v řádu ms po sobě, takže je šum tohohle typu "přeskočí" všechny stejně - oversampling proti němu nepomůže). Medián z posledních 3 čtení se počítá **přímo v lambdě** `battery_voltage` ([`packages/sensors.yaml`](packages/sensors.yaml)), ne jako externí `median` filtr - externí filtr by čistil jen publikovanou hodnotu, zatímco detekce nabíjení by dál viděla syrová čtení (přesně ten bug popsaný o řádek výš). **Potvrzeno funkční** z hodinového záznamu (`data/2026-08-22-doma-baseline/`): ze 64 očekávaných čtení je v HA jen 42 změn, tj. 22× byla publikovaná hodnota bit-identická s předchozí - což je přesně podpis mediánu (znovu vydá dřívější vzorek). U syrového ADC šumu by se float hodnoty takhle neopakovaly. Zbytkový šum je ~0.018 V (≈1.5 % baterky).
- **Bod 4.15V na horním konci rozsahu byl ověřen proti multimetru a sedí** (HA i multimetr shodně 4.15V). Zbytek rozsahu (nízké a střední napětí) zatím ověřený není – jedno starší pozorování uvádělo ~+2.6% odchylku, ale nejspíš z jiné části rozsahu/jiných podmínek. Než se bude věřit `* 3.2` násobiteli napříč celým rozsahem, stojí za to změřit i další body (např. ~3.5V a ~3.8V).
- **Rychlé vybíjení v režimu DOMA.** V testu (srpen 2026, ještě na v1 firmwaru bez deep sleepu) baterka klesla ze 4.15V na 2.71V za ~10 hodin běžného provozu. Hodinový v2 záznam v režimu DOMA (`data/2026-08-22-doma-baseline/`) to potvrzuje: **-0.08 V/h** při zapnuté WiFi a vypnutém displeji. Na to je právě preset **CESTA** (deep sleep) - v DOMA se s trvalým provozem na baterku počítat nedá. Doporučuje se nastavit v Home Assistantu notifikaci na nízké napětí (např. pod 3.3-3.4V), aby se předešlo opakovanému dojíždění až k ochrannému cutoffu (~2.5V, viz sekce Baterie výše) – to urychluje degradaci článku, obzvlášť u recyklovaného.

## Licence

MIT

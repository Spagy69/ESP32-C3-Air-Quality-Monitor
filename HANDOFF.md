# HANDOFF: Air Quality Monitor - kompletní stav projektu

Tento dokument je určen pro AI asistenta, který na projektu pokračuje po mně. Shrnuje celou historii, klíčová rozhodnutí, aktuální stav firmwaru a otevřené věci. Ostatní soubory v tomhle balíčku (README.md, WIRING.md, ASSEMBLY.md, air-quality-monitor.yaml) jsou aktuální projektová dokumentace/kód - tenhle dokument je navíc, jako kontext a historie k nim.

**Poslední aktualizace:** srpen 2026, po implementaci menu systému a hlubokého spánku.

---

## v2 STATUS (nejnovější - čti tohle první)

Probíhá **kompletní redesign firmwaru pro v2** (stejný hardware/zapojení jako v1, ale nový kryt + přidaný hlavní vypínač baterie mezi baterkou a TP4056). Zbytek tohohle dokumentu popisuje historii **v1** - pořád platný kontext k tomu, JAK a PROČ vznikla nynější v2 rozhodnutí, ale konkrétní čísla/chování (menu se 3 položkami, vypnutá dynamická korekce, atd.) už neplatí, byla nahrazená.

**Co se v v2 změnilo:**
- `air-quality-monitor.yaml` rozdělený přes `packages:` do `packages/globals.yaml`, `packages/sensors.yaml`, `packages/display.yaml`, `packages/menu.yaml`.
- Menu má teď 6 položek: REZIM (presety DOMA/CESTA, jinak zobrazí CUSTOM), HA PRIPOJENI, INTERVAL SPANKU, DEEP SLEEP, CO2 ALARM, ASC KALIBRACE.
- **ASC toggle implementováno (srpen 2026)** - viz "fáze 3" poznámka níže v historii v1, byla označená jako rizikovější a neimplementovaná, teď hotovo. Mechanismus: `id(scd41_hub).write_command(...)` (raw I2C, `sensirion_common::SensirionI2CDevice::write_command()` - CRC8 řeší samo) v novém `on_boot` kroku (priorita -150) v `air-quality-monitor.yaml`, ne za běhu z menu - menu jen uloží `id(asc_enabled)`, aplikuje se to při dalším rebootu/probuzení. Bez `scd4x.persist_settings` záměrně (NVM senzoru má omezený počet zápisů, nepotřebujeme ho - vlastní flash ESP32 přes `restore_value` stačí). **Overit na hardwaru:** dočasně zvednout `logger: level:` z `NONE`, přepnout ASC v menu, zkontrolovat log při dalším bootu (žádné I2C chyby, CO2 čtení pokračují normálně).
- Menu displej přepracovaný (srpen 2026) - starý layout (název/stav/hint na 3 řádcích) měl dva reálné bugy nahlášené z hardwaru: hint text přesahoval pod tečkový indikátor a kolidoval s ním, a písmenka s ocáskem (vypnout/zapnout/prepnout) se ořezávala o spodní okraj displeje. Nové rozvržení kopíruje styl běžných senzorových stránek (název+pozice nahoře, velká hodnota uprostřed, tečky dole), hint text zrušen úplně (viz README "Menu a presety").
- Korekce teploty při nabíjení: nahrazen starý (vypnutý, přestřelující) časový model jednoduchým plochým offsetem při `is_charging` - žádná křivka, žádné riziko přestřelení. Konstanty (rest-offset i charging-offset) jsou zatím TODO placeholdery - potřeba přeměřit na novém krytu.
- Přidán lokální CO2 alarm (jen displej, bliká při překročení prahu) pro použití bez HA (např. v autě).
- **CO2 alarm settle-gate + rychlejší SCD41 polling (srpen 2026).** Uživatelský postřeh: hodnoty jsou hned po zapnutí "divoké", nemá se z toho spouštět alarm. Cestou k tomu jsem narazil na skrytý pre-existující bug: `PollingComponent`'s FIRST `update()` čeká celý `update_interval` od bootu (ověřeno v ESPHome scheduler zdrojáku, ne odhad) - při starém `update_interval: 60s` na scd4x by CESTA (deep sleep, auto-off/spánek po 30s) šla spát DŘÍV, než dorazilo první čtení CO2 vůbec, takže alarm (a čerstvá data do HA) by se v CESTA módu prakticky nikdy nestihly vyhodnotit. Oprava: scd4x `update_interval` sníženo na 10s (SCD41 stejně interně vzorkuje po 5s, není to za víc energie), plus nový `co2_reading_settled` flag co přeskočí vyhodnocení alarmu na úplně prvním čtení po bootu (resetuje se každý reboot/probuzení).
- **Ověření proti reálným datům z DOMA režimu (srpen 2026, `data/2026-08-22-doma-baseline/`).** Uživatel dodal hodinový HA export (CO2, obě teploty, vlhkost, tlak, napětí, charging) z běžícího v2 firmwaru, displej vypnutý, bez nabíječky (uživatel psal obojí - data rozhodla: `charging` off celou dobu a napětí monotónně klesá). Co z toho vyšlo:
  - **Teplotní offsety v2 sedí.** SCD41 25.09-25.27 °C celou hodinu (10min průměry 25.12-25.21, žádný náběh), BMP180 24.69-24.79 °C, tj. rozdíl jen 0.44 °C mezi dvěma nezávisle offsetovanými senzory. Uživatel je nezávisle označil za správné. `temperature_offset: 5.6°C` a `REST_OFFSET_BMP180: 1.74f` přenesené z v1 tedy na novém krytu platí - TODO komentáře v `sensors.yaml` zmírněné na "ověřeno proti 1h záznamu, zbývá jedno kontrolní měření teploměrem".
  - **Detekce nabíjení nedělá false-positive.** Simulace algoritmu nad reálnou vybíjecí řadou: max trend **-0.0003 V** proti prahu +0.015 V. Tím je detekce ověřená z obou stran (nabíjení už dřív v praxi, teď i vybíjení).
  - **Median-of-3 na napětí prokazatelně funguje.** Ze 64 očekávaných čtení jen 42 změn v HA = 22× bit-identická hodnota s předchozí, což je přesně podpis mediánu (znovu vydá dřívější vzorek); u syrového ADC šumu by se float hodnoty takhle neopakovaly. Zbytkový šum ~0.018 V.
  - **Vybíjení v DOMA: -0.08 V/h** (WiFi zapnutá, displej vypnutý).
  - **Nalezený bug: BMP180 pustí občas jedno úplně vedlejší čtení.** 01:56:54Z teplota 24.409 mezi sousedy ~24.70 **a zároveň** tlak 956.407 proti ~957.05 - jedno špatné I2C čtení, obě veličiny naráz. BMP180 do té doby neměl žádný filtr. Opraveno `median` filtrem (okno 3, `send_every: 1` - **default je 5**, to by publikovalo jen každé páté čtení) na obou veličinách, zapojeným **před** korekční lambdu, aby se čistila i cachovaná hodnota (stejná split-brain past jako u `battery_voltage`).
- **Zahřívání po studeném zapnutí (srpen 2026).** Rešerše (Sensirion datasheet + ESPHome zdroják) rozdělila dvě věci, co se předtím míchaly dohromady: CO2 potřebuje zahodit první čtení a >3 min na plnou přesnost (vlastnost senzoru, τ63 % = 60 s), zatímco teplota potřebuje desítky minut - a to není o čipu, ale o tepelné rovnováze krabičky, protože `temperature_offset` platí jen v rovnováze. Datasheet proto žádné číslo nedává, jen "in thermal equilibrium". Firmware: `~` před hodnotou na obou teplotních stránkách **a na vlhkosti** (SCD41 ji počítá z té samé teploty) prvních 20 min po studeném startu. Původně to bylo 30 min z ničeho; **20 min je teď odvozeno z reálných dat** - viz bod níž.
- **Změřeno na reálném záznamu po zapnutí (srpen 2026, `data/2026-08-22-power-on-warmup/`).** Křivka má **dvě fáze, které spolu nesouvisí**: (a) 0-1.5 min SCD41 hlásí **+2.5 °C nad plató**, vlhkost -14 %, CO2 +56 ppm, prudce klesá; (b) 1.5-3 min podstřelí o 0.5 °C dolů; (c) 3-15 min se teprve zahřívá krabička, τ = 3.1 min (SCD41) / 5.9 min (BMP180). Doby ustálení: SCD41 do ±0.1 °C od 12.0 min, BMP180 od 9.0 min, vlhkost do ±0.5 % od 10.9 min, CO2 do ±15 ppm od 14.2 min.
  - **Nebyl to studený start** - BMP180 vyrostl celkem jen o 0.37 °C, ale jeho klidový offset je 1.74 °C; vychladlý box by musel vyrůst zhruba o těch 1.74. Uživatel potvrdil: vypnuté jen pár minut. Naměřená čísla jsou tedy spodní mez. `WARMUP_MS = 20 min` proto vychází z τ-extrapolace (BMP180 τ=5.9 min, z plných 1.74 °C na ±0.05 °C = 20.9 min), ne z přímého odečtu.
  - **POZOR - zpochybňuje předchozí předpoklad o deep sleepu.** Ta úvodní fáze **není tepelná**: box byl při zapnutí prakticky na provozní teplotě, takže čip SCD41 musel být *chladnější* než jeho ustálených 30.6 °C raw, a přesto hlásil 33.1. Vychladlý čip nemůže hlásit vysoko. BMP180 dělá pravý opak (startuje na minimu a roste). Vypadá to tedy na chování SCD41 po `start_periodic_measurement` - a ten ESPHome posílá **při každém bootu včetně probuzení z deep sleepu**. V CESTA je zařízení vzhůru 30 s → celé okno by padlo doprostřed skoku, každé probuzení by ukazovalo o ~2 °C víc. **Firmware s tím záměrně nic nedělá, dokud to není ověřené** (viz otevřené položky).
- **OPRAVA dřívějšího tvrzení: PollingComponent NEČEKÁ celý interval.** V `sensors.yaml` (a v tomhle souboru) bylo napsané jako ověřený fakt, že první `update()` přijde až po celém `update_interval`. **Není to pravda.** `Scheduler::calculate_interval_offset_` plánuje první běh na `now + random[0, min(interval/2, 5000ms))`, tedy do 5 s. Skutečný důvod, proč 60s interval nefungoval v CESTA: ten první brzký poll přijde dřív, než má SCD41 `data_ready` (driver stráví ~1.5 s vlastní stop/configure/start sekvencí a senzor pak potřebuje dalších ~5 s), takže se přeskočí - a další je o celý interval dál, to už zařízení spí. Data to potvrzují: BMP180 s 60s intervalem publikoval ~3 s po bootu, SCD41 s 10s až v 11 s. **Závěr (5s je správně) platí dál**, jen zdůvodnění bylo špatné; komentář v `sensors.yaml` je přepsaný a explicitně na tu starou chybu upozorňuje.
- **CO2 alarm: settle-gate nahrazen stabilitním armováním (srpen 2026).** Původní verze (bod výš) přeskočila jen první čtení po bootu (10 s), což na "divoké hodnoty po zapnutí" nestačí. Teď: alarm se povolí, až jsou **3 čtení po sobě v rozsahu <150 ppm**; pojistka - po 3 min uptime se povolí tak jako tak (radši hlídat s nejistotou než nehlídat); jednou povolený se **už nedearmuje** (reálný rychlý nárůst CO2 v autě by rozptyl překročil a alarm by zmizel přesně ve chvíli, kdy je potřeba). Globál `co2_reading_settled` → `co2_alarm_armed` + `co2_hist1`/`co2_hist2`. Kvůli tomu `update_interval` scd4x z 10s na **5s** (= vlastní interní rychlost SCD41, nestojí to víc energie senzoru): v CESTA je zařízení vzhůru jen 30 s, při 10s intervalu jsou to 3 čtení a na vyhodnocení stability nezbývá prostor. Ověřeno simulací nad `data/2026-08-22-doma-baseline/co2.csv`: na ustálených datech se armuje na 3. čtení (15 s), na syntetickém divokém startu (40000→5200→2400→1900→…) až na 6., a na trvale šumících datech spadne na 3min pojistku. Aby 5s polling nezdvojnásobil zápisy do HA recorderu, přidán `delta: 0.05` na teplotu SCD41 a `delta: 0.1` na vlhkost - **za** lambdu, takže cache se pořád plní každým čtením.
- **STUDENÝ START (srpen 2026, `data/2026-08-22-cold-start/`) - 6.5 h záznam, vypnuté ~1 h předtím, běželo do vybití baterky. Nejcennější záznam, odpověděl na tři věci najednou.**
  - **`WARMUP_MS` 20 → 45 min.** BMP180 se ustálí kolem 24.15 °C (plató od 60. min); zbývající chyba: −1.11 °C v 10. min, −0.58 ve 20., −0.34 ve 30., −0.18 ve 40., −0.06 v 50. τ = 13-15 min, ustálení ≈ 3τ. **Moje předchozí hodnota 20 min byla špatně** - vznikla extrapolací z `power-on-warmup`, což byl teplý restart; fit exponenciály na krátký, skoro ustálený ocas dal τ = 5.9 min, tedy necelou polovinu skutečné, a extrapolace přestřelila o víc než 2×. **Poučení do budoucna: τ fitovaná přes krátké okno se nedá extrapolovat na plnou amplitudu.**
  - **Úvodní skok SCD41 je PROKAZATELNĚ artefakt senzoru**, ne teplota - dřív to byla hypotéza, teď dva nezávislé důkazy z jednoho záznamu: (a) ze studeného startu hlásí SCD41 v t=6 s o **2.13 °C víc** než BMP180, ve 2. minutě je naopak **pod ním**, pak se srovnají na +0.49 °C - studený čip nemůže hlásit vysoko; (b) při brownout restartu (10:45:15Z) skočil z 24.04 na **28.42 °C (+4.37) za necelých 38 s**, zatímco BMP180 stál na 23.60/23.59/23.58 - reálná změna 4.4 °C při klidném druhém senzoru je nemožná. Systematická kontrola: skoky >1 °C za celých 6.5 h jsou **přesně dva**, oba na restart. Rozdíl SCD41−BMP180 drží +0.46 až +0.53 °C celých šest hodin.
  - **Vysvětlena anomálie, kterou nahlásil uživatel** ("HA pak ukazovalo data, která neměřil"): jak baterka umírala, zařízení se dvakrát brownout-restartovalo a pokaždé publikovalo transient. Poslední, co HA dostalo a pak na tom zůstalo viset: **27.43 °C** (realita 23.58) a **53.7 % RH** (předtím 64.96). Navíc to vypadá jako dvě měření, i když je jen jedno - po krátkém výpadku spojení poslalo ESPHome ty samé stavy z RAM znovu a HA to zalogovalo jako změnu (entita byla mezitím `unavailable`); poznat podle **bit-identických floatů** (2.93834662437439 dvakrát, u 30× oversamplovaného ADC nemožné náhodou).
  - **OPRAVENO:** nový lambda filtr v `sensors.yaml` na `temperature:` i `humidity:` SCD41 - `if (millis() < 3min) return {};`. Vrací prázdno, takže se čtení **ani nepublikuje, ani necachuje** a displej dál padá na poslední známou dobrou hodnotu. Záměrně **NE** na `co2:` - jeho transient je ~56 ppm proti prahu 3000 a zahazování CO2 by v CESTA (30 s vzhůru) vyhladovělo arming pravidlo alarmu.
  - **Důsledek pro CESTA, který je potřeba vyřešit:** v CESTA neprojde tím filtrem nic (30 s < 3 min), takže teplota/vlhkost zůstanou na poslední cachované hodnotě a nikdy se neaktualizují. Není to regrese (CESTA teplota byla špatná už předtím, jen neviditelně), ale je to slepá ulička. **Nejnadějnější řešení: brát v CESTA teplotu z BMP180**, který transient nemá vůbec (viz důkaz (b) výš) a se SCD41 se za ustáleného stavu shodne na 0.49 °C. Vlhkost by šla dopočítat Magnusem z BMP180 teploty - ta mašinérie v `humidity:` filtru už existuje kvůli charging offsetu. **Nerozhodnuto, čeká na uživatele.**
  - Vedlejší: vybíjení 3.79 → 2.94 V za 6.5 h = **~0.13 V/h** v DOMA (víc než −0.08 V/h z baseline, baterka byla níž ve vybíjecí křivce).
- **NABÍJENÍ + PRVNÍ REFERENČNÍ TEPLOMĚR (srpen 2026, `data/2026-08-22-charging-from-empty/`)** - 4 h, nabíjení z úplně vybité baterky, nabíječka zapojená celou dobu, vedle položený lihový teploměr s ručními odečty (ty jsou v `reference-thermometer.md` v té složce, **v CSV nejsou**). Export je poprvé jeden soubor pro všechny entity (`all-sensors.csv`, rozlišuje `entity_id`).
  - **Teplo z nabíjení = +3.7 °C ve vrcholu**, a `CHARGE_OFFSET_*` proto zůstávají `0.0` - **teď už jako změřené rozhodnutí, ne placeholder**. Průběh nad ustáleným stavem: +3.4 ve 30. min, **+3.7 ve 40. min (vrchol)**, +3.6 v 60., +1.7 ve 100., +0.3 ve 150., 0 v 170. Reference se přitom držela na 23.8-24.2 °C. Stejný tvar na BMP180 (+3.8), takže se ohřívá celá krabička. **Konstanta to opravit nemůže:** teplo je úměrné nabíjecímu proudu a ten závisí na tom, jak prázdná baterka byla; průměr přes cyklus (~1.8 °C) je vedle v obou směrech. Křivka podle času selže stejně - to je přesně v1 model, co přestřelil o ~4 °C. **Řešení: neopravovat, jen označit** - displej dává `~` během `is_charging` (packages/display.yaml).
  - **První absolutní kontrola offsetů.** Po ustálení (nabíjení dokončené) čte SCD41 o **+0.5 až +1.0 °C** víc než lihový teploměr, BMP180 o **+0.3 až +0.7**. Vypadá to, že oba offsety jsou o tolik malé. **Zatím se nic nemění**, protože (a) lihový teploměr má přesnost ±0.5 °C a v poslední hodině skočil o 1.1 °C, zatímco senzory se pohnuly o 0.15 - část rozdílu je chyba odečtu; (b) nabíječka byla pořád zapojená, takže i "ustálený" stav nese zbytkové teplo. Uzavře to jedno 45min měření bez nabíječky, viz otevřené položky.
  - **Mobilní teploměr je k ničemu** - za 30 min ukázal pokles 23.4 → 22.0 °C, zatímco lihový stál a senzory naopak rostly. Telefon měří vlastní čip, jak se po odložení ochlazuje. Do budoucna nepoužívat.
  - **`Charging` nepozná konec nabíjení.** Sepnulo správně 5 min po zapojení, ale vyplo se **přesně po 3 h 00 min 03 s** = bezpečnostní pojistka, ne detekce. Skutečné nabíjení skončilo o hodinu dřív (napětí přestalo růst na 4.150 V a začalo mírně klesat). Pokles po dobití je jen ~0.0009 V/min a nikdy nepřekročí práh -0.01 V proti baseline. `Charging = on` tedy znamená "nabíjelo se někdy za poslední 3 h", ne "teče proud teď". **Opraveno** - viz bod 2f v otevřených úkolech (a pozor, opravovalo se to dvakrát).
  - **Potvrzena ta zamrzlá hodnota**: v 16:15, před bootem, HA pořád ukazovalo SCD41 27.43 °C a BMP180 23.58 - přesně hodnoty z brownoutu v předchozím záznamu, visely tam hodiny. Přímé potvrzení, že ta oprava (zahazování prvních 3 min) byla potřeba.
  - **Ověřen Magnusův přepočet vlhkosti**: RH šla 77 → 60 % zatímco teplota rostla 23.8 → 28.6. Magnus z toho předpoví 58 %, naměřeno 60.5. Ta změna vlhkosti tedy není skutečná, je to jen důsledek nadhodnocené teploty - a přepočet v `humidity:` filtru počítá správně.
- **CESTA WAKE TEST (srpen 2026, `data/2026-08-22-cesta-wake-cycles/`) - otázka 2d ZODPOVĚZENA: ANO, skok se opakuje při každém probuzení, a je ~5.5 °C.** Devět cyklů (DEEP SLEEP on + HA on = CUSTOM, interval 5 min), pokaždé stejně: SCD41 startuje ~5.5 °C nad BMP180 a za 10 s spadne o 0.72-0.76. Rozptyl prvního rozdílu přes všech devět probuzení: **5.36 až 5.59** - naprosto konzistentní. Když zařízení běželo v kuse (blok před prvním uspáním), byl rozdíl normálních **0.31 °C**. Vlhkost stejně: 61.8 % za běhu vs 46.7-50.6 % při probuzení. BMP180 klesá hladce (24.57 → 22.68 za 50 min, chladnutí ve spánku) a **skok nemá vůbec**.
  - **Mechanismus, který sedí na všechny tři záznamy:** první čtení po `start_periodic_measurement` vypadá, jako by na něj nebyl aplikovaný `temperature_offset` (5.6), a ten se dotáhne během ~2 min. Studený start: čip je stejně studený jako krabička → chybějící offset dělá proti BMP180 (který má vlastní offset 1.74) rozdíl ~1.74-2.1 °C, naměřeno 2.13 ✓. Probuzení ze spánku: čip celou dobu spánku běžel dál a je proti chladnoucí krabičce rozehřátý → totéž dělá ~5.5 °C ✓.
  - **Důsledek: v jakémkoliv režimu s deep sleepem je teplota i vlhkost ze SCD41 nepoužitelná.** 30 s vzhůru je řádově míň než ty ~2 min. Zahazovací filtr (3 min) to správně vyhodí, takže se do HA nedostane nesmysl - ale znamená to, že v CESTA nemá teplota odkud brát. **VYŘEŠENO (srpen 2026):** stránka TEPLOTA zkusí popořadě `temp_scd41` → `temp_bmp180` → cache a vezme první, co má `has_state()`. Klíčované záměrně na "existuje živé čtení", ne na `deep_sleep_mode_enabled` - žádné větvení podle režimu, které by se muselo držet v synchronu, a správně to vyjde i v prvních 3 minutách běžného bootu. Vlhkost druhý zdroj nemá (BMP180 ji neměří), takže tam padá na cache a je označená vlnovkou; Magnus přepočet z BMP180 teploty by šel, ale chtělo by to schovat si syrové RH před zahozením do globálu - neuděláno, zatím nepotřeba.
- **Displej se při probuzení časovačem už nerozsvěcí (srpen 2026, na žádost uživatele).** Nový globál `wake_was_timer` (plněný v on_boot prioritě 600 z `esp_sleep_get_wakeup_cause() == ESP_SLEEP_WAKEUP_TIMER`) a v prioritě -100 se podle něj `display_on` nastaví na false + `oled_display.turn_off()`. Rozsvítí se **jen** po tlačítku nebo studeném startu; když se příčina probuzení nedá zjistit, vyhrává displej (bezpečný směr - jediný výstup zařízení je ta obrazovka). 30s okno vzhůru se nemění, to potřebuje WiFi + API + čtení, s displejem nemá nic společného. CO2 alarm si displej pořád rozsvítí sám.
- **SCD41 běžel i během deep sleepu - hlavní žrout baterky (srpen 2026, opraveno).** Senzor není na napájecí větvi ESP32; 3V3 jde i ve spánku, takže dál měřil po 5 s. Datasheet: 243 mJ na měření → při 5s intervalu **~14.7 mA trvale** proti **0.15 mA** v idle, tedy ~100×, a řádově víc než spící ESP32. Naměřeno: při 5min intervalu a 30 s vzhůru (desetina času) bylo vybíjení jen o ~15 % pomalejší než při nepřetržitém běhu (-0.070 V/h proti -0.082 až -0.089 V/h). Zpětný výpočet z always-on dá ~34 mA = ESP s WiFi (~20) + tenhle senzor (~15). Nezávislé potvrzení: teplotní skok při probuzení je ~5.5 °C proti ~2 °C při studeném startu - tak rozehřátý čip být nemůže, pokud neměří.
  - **Oprava:** `id(scd41_hub).write_command((uint16_t) 0x3F86)` (stop_periodic_measurement) v obou cestách do deep sleepu - ve skriptu `display_auto_off` i v ručním single-click handleru (packages/menu.yaml). Odhad: 3-4× delší výdrž v CESTA.
  - **Proč je to bezpečné:** ESPHome při dalším bootu pošle `stop` znovu, tedy už zastavenému senzoru. To se ale děje při každém studeném startu (SCD4x se po zapnutí probouzí v idle) a studené starty prokazatelně fungují - viz `data/2026-08-22-cold-start/`. `write_command` navíc vrací úspěch podle I2C ACK, ne podle sémantiky příkazu.
  - **Vedlejší efekt k ověření:** čip bude při probuzení studený místo rozehřátý, takže by transient měl klesnout z ~5.5 °C na ~2 °C (jako u studeného startu). Zahazovací filtr (3 min) to pokrývá tak jako tak. **Hlavní věc k ověření na hardwaru: po probuzení musí CO2 spolehlivě naskočit** - to je jediná funkce, která v CESTA nesmí selhat.
  - Druhý největší odběr ve spánku je pak dělič napětí: 220k+100k = 320 kΩ přes baterku = ~12.8 µA trvale. Proti ESP ve spánku (~5 µA) to není nic (0.3 mAh/den), řešit se to nemusí.
- **KALIBRACE TEPLOTY ZAVŘENÁ (srpen 2026, `data/2026-08-22-rest-offset/`).** Konečně měřeno proti referenčnímu teploměru za správných podmínek: **nabíječka i USB odpojené** (během flashování jde XIAO z 5 V USB, na baterce z ~4.1 V, a rozdíl se pálí v LDO - to znečistilo předchozí pokus), DOMA, displej zhasnutý, 49 min na ustálení, tři odečty po pěti minutách, všechny shodně 23.9 °C.
  - SCD41 četl **+1.07 °C** → `temperature_offset` 5.6 → **6.7**
  - BMP180 četl **+0.72 °C** → `REST_OFFSET_BMP180` 1.74 → **2.46**
  - Obě kontroly platnosti prošly: rozdíl mezi senzory 0.35 °C (očekáváno 0.3-0.5) a BMP180 se přes všechny tři odečty pohnul jen o 0.090 °C. Ta druhá je podstatnější, než vypadá - oba senzory za vzduchem zaostávají o svou časovou konstantu (11-15 min), takže drift v místnosti by se započítal jako chyba offsetu. Zbytkový drift značí, že snad 0.1 °C z těch 1.07 je zpoždění - hluboko pod vlastní přesností teploměru (~0.5 °C), nemá smysl to odčítat.
  - **Vedlejší efekt:** změna `temperature_offset` posune i vlhkost, protože SCD41 počítá RH ze své offsetem opravené teploty - vyjde asi o 4 procentní body výš. Správný směr, ale nemáme čím ověřit (vlhkoměr jako reference chybí). **CO2 to neovlivní** - podle Sensirionu offset kondicionuje jen výstupy T a RH.
- Poslední naměřené hodnoty se cachují do flash (`restore_value: true` globals) a displej je hned po zapnutí/probuzení ukazuje, místo loading baru/"--". `esp_sleep_get_wakeup_cause()` bylo kvůli tomu odstraněné (nebylo pro co ho potřebovat), ale **vrátilo se zpátky** s indikátorem zahřívání - teď v `on_boot` prioritě 600 plní globál `cold_boot`, aby šlo odlišit studený start od probuzení. `esp_sleep.h` se do buildu dostává přes header deep_sleep komponenty, žádný extra `includes:` netřeba (ověřeno kompilací).
- `preferences: flash_write_interval: 1s` přidáno, aby se cachovaná hodnota nezralila, pokud deep sleep vypne napájení dřív, než výchozí 1min interval stihne zapsat do flash.
- Mrtvý kód z bodu "Známé drobnosti k úklidu" (níže v tomhle souboru) byl smazaný (button_press_start_ms, long_hold_5s_fired, last_release_held_ms).

**Vyřešeno od minula:**
- Projekt přesunutý z `C:\Users\lagys\Documents\Coding Projects\Air Quality Monitor` (mezera v cestě) na `C:\Users\lagys\air-quality-monitor` (git historie zachovaná, viz git log) - PlatformIO/ESP-IDF toolchain mezery v cestě nesnáší.
- `esphome compile` z nové cesty **prošel úspěšně** (ne jen `esphome config` validace) - RAM 11.4%, Flash 55.5%. Reálný hardwarový test (flash + chování) pořád čeká na uživatele.
- DOMA/CESTA presety a CO2 alarm práh (3000/2700 ppm) uživatel potvrdil - CESTA interval finálně 10 min (ne navrhovaných 5).

**Otevřené položky, na kterých čekáme (potřeba reálný hardware/uživatel):**
1. Reálný hardwarový test celého v2 firmwaru (menu navigace všech 6 položek, deep sleep probuzení tlačítkem i časovačem, CO2 alarm, ASC toggle - viz jeho vlastní pozn. výš o testu s logováním). Nově k tomu: `~` indikátor musí být po studeném startu a **nesmí** být po probuzení z deep sleepu; a v CESTA ověřit, že alarm stihne sepnout ještě ve 30s okně (dýchnout na senzor).
2. Kalibrační konstanty: **teplotní offsety HOTOVO** (viz `2026-08-22-rest-offset` výš, změřeno proti referenci: 6.7 a 2.46). **`CHARGE_OFFSET_*` HOTOVO** - zůstávají 0.0, ale už jako změřené rozhodnutí, teď potvrzené **dvěma** záznamy: nabíjení z prázdné baterky dá vrchol +3.7 °C, dobíjení ze 64 % jen +2.35 °C. Stejná krabička, stejná nabíječka, rozdíl 1.4 °C jen kvůli počátečnímu stavu baterky - žádná konstanta ani časová křivka to nepokryje, značí se to vlnovkou. **Zbývá už jen dělič napětí** (násobič 3.2 ověřený jen v bodě 4.15 V) - chtělo by to multimetr ještě kolem 3.5 a 3.8 V.
2b. **Offset self-heatingu se nejspíš liší mezi DOMA a CESTA** (nezměřeno, nová položka srpen 2026). Klidový offset byl ověřený v DOMA, kde je zařízení pořád vzhůru se zapnutou WiFi; v CESTA většinu času spí, zahřívá se výrazně míň, takže stejný offset tam pravděpodobně odečítá víc než by měl. Potřebuje vlastní záznam v CESTA proti referenčnímu teploměru. Zatím jen zdokumentováno v README Known Issues, firmware s tím nepočítá.
2c. ~~Opravdu studený start~~ **HOTOVO** - viz `data/2026-08-22-cold-start/` výš. `WARMUP_MS` = 45 min je teď změřené.
2d. ~~CESTA transient test~~ **HOTOVO** - viz `data/2026-08-22-cesta-wake-cycles/` výš. Odpověď: ano, opakuje se, ~5.5 °C. Vyřešeno fallbackem SCD41 → BMP180 → cache na stránce TEPLOTA.
2e. ~~Klidový offset bez nabíječky~~ **HOTOVO** - viz `data/2026-08-22-rest-offset/` výš. Obě kontroly platnosti prošly, offsety nastavené na 6.7 a 2.46.
2f. ~~Detekce konce nabíjení~~ **HOTOVO (srpen 2026), ale opravováno dvakrát - přečti si to celé, je to poučné.** Druhé pravidlo vedle trendového: napětí vysoko a přestalo se hýbat → `is_charging = false`.

   První verze (`FULL_V` 4.10, `FULL_FLAT_DELTA` 0.001, `FULL_CONFIRM` 5) byla naladěná prohledáním nad **jedním** záznamem (`charging-from-empty`) a sepnula tam v 18:19, přesně v okně skutečného konce. Vypadalo to solidně - prahy nesedící na hraně, `FULL_V` prý irelevantní v rozsahu 4.00-4.12.

   **Druhý záznam ji celou shodil.** V `data/2026-08-23-charging-warm/` se napětí po dobití usadilo na **4.083 V**, tedy pod prahem 4.10, a pravidlo **nesepnulo ani jednou** za celou hodinu. To tvrzení "`FULL_V` je prakticky jedno" bylo pravdivé jen v tom jednom záznamu, kde napětí náhodou skončilo výš. Skutečnost: obě nabíjení skončila na **jiném** napětí - 4.120 a 4.083 V, 37 mV od sebe na stejném hardwaru.

   Poučení, které stojí za zapamatování: **z jednoho záznamu nejde poznat, který parametr generalizuje.** Plochost napětí ano (v obou záznamech), absolutní hladina ne. Nová verze proto degraduje `FULL_V` na volnou pojistku (4.05, jen aby nabíjení zaseknuté na 3.5 V nešlo splést s hotovým) a nechá rozhodovat plochost, s tolerancí zvednutou na 0.002 V (warm plató má kroky až 0.0019). Přeměřeno přes oba záznamy: sepne v 18:19 (+125 min) a 01:07 (+48 min), `FULL_V` 4.00-4.08 i `FULL_CONFIRM` 4-10 dají shodný výsledek. Když by prahy byly na třetí baterku pořád moc těsné, pravidlo nesepne a převezme to 3h backstop - degradace, ne rozbití.

2g. ~~Procenta baterky nedosáhnou 100 %~~ **HOTOVO (srpen 2026).** Vedlejší nález ze stejných dat: mapa byla lineární 3.0-4.2 V, ale naměřené plno je 4.083-4.120 V, takže dobitá baterka hlásila 90-93 %. Horní konec vzat z měření (4.12 V). Jestli článek opravdu končí na 4.12 V, nebo dělič podhodnocuje 4.2 V o ~2 %, rozhodne až multimetr (bod 5 níž) - procentům je to jedno, berou se z toho, co ADC hlásí při dobití.
3. ASSEMBLY.md pořád popisuje starý (v1) kryt - potřeba přepsat, jakmile budou podklady k novému.
4. Git: lokální repo je klon skutečné historie z `github.com/Spagy69/ESP32-C3-Air-Quality-Monitor` (branch `main`), s v2 změnami jako novými lokálními commity navíc. **Nic není pushnuté** - čeká se, až uživatel řekne, že v2 je hotové.
5. ~~HANDOFF.md v gitu~~ **ROZHODNUTO (srpen 2026): ano**, je teď součástí repa.

---

## Co to je

Bateriový monitor kvality vzduchu na Seeed XIAO ESP32-C3, ESPHome, integrovaný do Home Assistant. Senzory: SCD41 (CO2/teplota/vlhkost), BMP180 (teplota/tlak), OLED displej 128x32, tlačítko pro ovládání. Napájení: recyklovaná LiPo baterie z vapy + TP4056 nabíjecí/ochranný modul.

Podrobný popis hardwaru, zapojení a sestavení je v README.md / WIRING.md / ASSEMBLY.md - tenhle dokument se soustředí na **firmware historii a rozhodnutí**, která nejsou z těch souborů sama o sobě zjevná.

---

## Chronologie a klíčová rozhodnutí

### 1. Původní stav (před touhle sérií změn)
Firmware měl statickou i dynamickou softwarovou korekci self-heatingu teplotních senzorů při nabíjení, detekci nabíjení z trendu napětí baterky, a základní UI (tlačítko: klik = displej on/off na 30s, dvojklik = trvalé zapnutí).

### 2. Objevené a opravené bugy v detekci nabíjení
- **Bug 1:** Debounce fix proti false-positive (z WiFi zátěže) byl nastavený na příliš vysoký práh (0.02V na jeden vzorek) - v reálném testu se `Charging` nespustilo ani jednou za celý 2.5h nabíjecí cyklus, protože skutečné nabíjení rostlo jen ~0.004V/min.
- **Oprava:** přechod na pomalý klouzavý baseline napětí (EWMA, časová konstanta ~10 min), trend = aktuální napětí minus baseline, práh snížen na 0.015V/-0.01V. **Funguje, potvrzeno v praxi.**
- **Vedlejší bug:** korekce self-heatingu se nespustí, pokud firmware nastartuje/restartuje, zatímco je zařízení už nabité/zahřáté (detekce potřebuje vidět skutečný nárůst napětí od bootu). Zdokumentováno, řešeno manuálně (odpojit/znovu připojit nabíječku po restartu).

### 3. Kalibrace self-heatingu - historie pokusů
1. **v1:** fitováno z jednoho ~30min měření, model náběh→pokles k nule. Nejistý `τ_decay` (44 vs 76 min mezi senzory - podezřele rozdílné).
2. **v2:** přeměřeno na kompletním ~4h cyklu (hluboké vybití → plné nabití). Zjištěny mnohem konzistentnější `τ_decay` (~24-25min oba senzory) a nové zjištění: pokud nabíječka zůstává zapojená po dobití, teplota se ustálí na nenulovém plató (~1.1°C), ne klesá k nule.
3. **KRITICKÝ PROBLÉM v praxi:** model v2 (fitovaný z cyklu začínajícího hlubokým vybitím) katastroficky přestřelil při jiné situaci - krátké dobíjení z vysokého SOC (~97%) mělo mnohem menší reálný self-heating, ale model to nevěděl a odečetl příliš mnoho → zobrazená teplota klesla ~4°C **pod** realitu.
4. **Aktuální stav: dynamická korekce je VYPNUTÁ.** Firmware používá jen statický klidový offset (SCD41 5.6°C přes hardwarový registr, BMP180 1.74°C softwarově). Kód dynamického modelu v2 zůstává zakomentovaný v YAML (u obou temperature filtrů) pro případné budoucí obnovení - ale **nedoporučuju ho zapínat bez zásadně lepšího přístupu** (např. model závislý na SOC/nabíjecím proudu, ne jen na uplynulém čase).

### 4. Fyzický redesign krytu
Uživatel přepracoval kryt tak, aby senzory byly **fyzicky oddělené** od zdroje tepla (baterka/TP4056/ESP32). To by mělo zásadně snížit self-heating problém u zdroje, možná natolik, že dynamická korekce nebude vůbec potřeba. **Statický offset po redesignu ještě nebyl přeměřen** - stará hodnota (5.6°C / 1.74°C) je pravděpodobně teď příliš vysoká (redesign snížil teplo, co se k senzorům dostává).

**→ OTEVŘENÝ ÚKOL: přeměřit statický offset po fyzickém redesignu.** Postup: referenční teploměr vedle zařízení v klidu (bez nabíjení, bez hlubokého spánku), nechat ustálit ~15-20 min, porovnat s raw hodnotou v HA.

### 5. Nový UI/power systém (button gestures + menu + deep sleep)
Implementováno na žádost uživatele, iterativně. **Finální (aktuální) chování popsáno v sekci "Aktuální chování tlačítka" níže** - historicky se návrh měnil (např. bylo tam prostřední "hold 2.5-4.5s" gesto pro ruční spuštění hlubokého spánku, které uživatel nakonec **nechtěl** a bylo odstraněno, viz níže).

**Zjištění o deep sleep a SCD41 kalibraci:** Původně jsem (asistent) upozorňoval, že ESP32 deep sleep pravděpodobně vypne napájení SCD41 a resetuje jeho kalibraci/self-heating stav. Uživatel to otestoval a **potvrdil, že se to nestalo** - senzor měří dál i během ESP32 deep sleep (napájení 3V3 pro periferie zůstává aktivní nezávisle na ESP32 spánku), takže kalibrace zůstává v pořádku. (Drobná nejasnost zůstává: první test po probuzení vypadal jako "špatná data, pak se to srovnalo" - buď to byl jen běžný self-heating transient při čtení, nebo ESPHome/SCD41 driver potřebuje čas po `start_periodic_measurement()` volaném při rebootu i když senzor "nezastavil" měření - nebylo definitivně vysvětleno, ale funkčně to podle uživatele teď funguje OK.)

---

## Aktuální chování tlačítka (GPIO3, aktivní LOW, interní pull-up)

Mimo nastavovací menu:
- **Krátký klik:** displej on/off. Když se zapíná, běží 30s countdown (script `display_auto_off`).
- **Dvojklik:** přepnutí trvalého režimu ("stay on" - displej svítí bez countdownu, dokud se znovu nedvojklikne).
- **Drž 5s+:** otevře nastavovací menu.

V nastavovacím menu:
- **Krátký klik:** další položka v seznamu (cyklicky).
- **Dvojklik:** odejít z menu bez dalších změn (změny už provedené 5s-holdem zůstávají uložené).
- **Drž 5s+:** potvrdit/přepnout aktuální položku.

**POZOR - historická změna:** dřív existovalo i "drž 2.5-4.5s" gesto pro okamžité ruční spuštění hlubokého spánku (nezávisle na menu). **Uživatel si tohle gesto nepřál a bylo z kódu odstraněno.** Related globals (`button_press_start_ms`, `long_hold_5s_fired`, `last_release_held_ms`) a `on_press`/`on_release` handlery na tlačítku byly z většiny odstraněny, ale **zbyl tam kus mrtvého kódu**, na který upozorňuji v sekci "Známé drobnosti k úklidu" níže.

### Chování při zhasnutí displeje (30s timeout NEBO ruční klik)
Pokud je v menu zapnutá položka **"SPANEK PO 30s"**, tak PŘI JAKÉMKOLIV zhasnutí displeje (automatický 30s timeout i ruční klik) se zařízení místo pouhého zhasnutí displeje **rovnou uspí do hlubokého spánku** (`deep_sleep.enter`). Trvalý režim (`stay_on`, přes dvojklik) tohle logicky obchází - tam displej záměrně nezhasíná, takže se ani nespustí spánek.

---

## Nastavovací menu - aktuální položky (3, snadno rozšiřitelné)

Implementováno jako `switch/case` podle `id(settings_menu_index)`, stejná struktura na dvou místech v YAML (button 5s-hold handler pro AKCI + display lambda pro VYKRESLENÍ) - **při přidávání nové položky je nutné upravit OBĚ místa** a zvýšit `id(settings_item_count)`.

| Index | Název na displeji | Co dělá | Persistence |
|---|---|---|---|
| 0 | HA PRIPOJENI | Toggle WiFi (`wifi.enable`/`wifi.disable`) | `ha_connection_enabled`, restore_value: true |
| 1 | INTERVAL SPANKU | Cykluje presety [5,10,15,30,60] minut - jak dlouho spí hluboký spánek | `sleep_interval_minutes`, restore_value: true |
| 2 | SPANEK PO 30s | Toggle - jestli zhasnutí displeje (jakékoliv) spustí hluboký spánek | `deep_sleep_mode_enabled`, restore_value: true |

**Vykreslení na displeji (128x32):** název položky (y=0) / stav (y=11) / krátká akční nápověda co dělá 5s-hold (y=22) / tečkový pozice-indikátor vpravo dole (y=27, stejný vizuální styl jako page-indikátor u běžných stránek senzorů).

### Plánovaná další položka (fáze 3, NEIMPLEMENTOVÁNO)
**ASC toggle** (automatic_self_calibration SCD41) za běhu. **Zjištěno při rešerši:** ESPHome's `set_automatic_self_calibration()` metoda jen mění interní flag, needá se posílá I2C příkaz senzoru za běhu (jen jednou při setup()). Aby šlo přepínat opravdu za běhu, je potřeba poslat raw I2C příkaz (SCD4x command 0x2416), a to jen v idle módu senzoru (nutno nejdřív stop_periodic_measurement, počkat, poslat příkaz, pak zase start_periodic_measurement). ESPHome komponenta tohle nevystavuje jako hotovou akci - muselo by se to napsat ručně přes obecné i2c: primitiva. **Označeno jako rizikovější kus, zatím neimplementováno.**

---

## Hluboký spánek (deep_sleep komponenta)

```yaml
deep_sleep:
  id: deep_sleep_1
  sleep_duration: 10min   # fallback, přepisuje se dynamicky před každým usnutím
  wakeup_pin:
    number: GPIO3
    inverted: true
    allow_other_uses: true   # sdílení GPIO3 s button binary_sensor
```

- **Bez `run_duration`** - spánek se NIKDY nespustí automaticky, jen na povel (`deep_sleep.enter` akce). To je záměr.
- **Probuzení:** buď po uplynutí `sleep_interval_minutes` (nastavitelné v menu), nebo okamžitě stiskem tlačítka (`wakeup_pin`).
- **Sdílení GPIO3** mezi button binary_sensor a wakeup_pin vyžaduje `allow_other_uses: true` na OBOU místech (jinak ESPHome config validace hlásí "Pin used in multiple places").
- **`enable_on_boot: false` na `wifi:`** + `reboot_timeout: 0s` na `api:` i `wifi:` - nutné, jinak by ESPHome samo restartovalo zařízení při dlouho vypnuté WiFi (sabotovalo by to úsporný režim). WiFi se po každém probuzení/restartu obnovuje podle `id(ha_connection_enabled)` v `on_boot` kroku.
- **Loading bar při bootu (5 senzorů, 15s timeout) se přeskakuje po probuzení z deep sleep** - detekce přes `esp_sleep_get_wakeup_cause() != ESP_SLEEP_WAKEUP_UNDEFINED`. **NEOVĚŘENO na reálné kompilaci** - je to nízkoúrovňová ESP-IDF funkce, možná bude potřeba `#include <esp_sleep.h>` navíc, pokud kompilace spadne na tomhle řádku.

---

## Známé drobnosti k úklidu (nekritické, ale stojí za zmínku)

1. ~~Mrtvý kód po odstranění medium-hold gesta~~ **HOTOVO** - `button_press_start_ms`, `long_hold_5s_fired` i `last_release_held_ms` jsou pryč, v repu už nejsou ani jednou.
2. ~~`esp_sleep_get_wakeup_cause()` neověřeno na kompilaci~~ **HOTOVO** - kompiluje se, `esp_sleep.h` se do buildu dostane přes `deep_sleep_component.h`, extra include není potřeba. Používá se to teď i v `on_boot` pro `cold_boot` / `wake_was_timer`.
3. **`wakeup_pin` syntaxe pro ESP32-C3** - pořád neověřeno **na reálném hardwaru**. Probouzení časovačem funguje (9 cyklů v `data/2026-08-22-cesta-wake-cycles/`), probuzení **tlačítkem** nikdo nezkusil.

---

## Otevřené úkoly (shrnutí, seřazeno podle priority)

> Tenhle seznam je z dřívější fáze. Většina je hotová - **aktuální stav je v sekci v2 STATUS nahoře**, tohle je tu jen kvůli historii.

1. ~~Přeměřit statický teplotní offset po fyzickém redesignu krytu~~ **HOTOVO** - změřeno proti referenčnímu teploměru, 6.7 / 2.46 (bod 2e v v2 STATUS). Odhad "stará hodnota je moc vysoká" byl mimo, ve skutečnosti byly obě moc **nízké**.
2. ~~Zkompilovat a otestovat aktuální YAML~~ **ČÁSTEČNĚ** - kompiluje se a běží na hardwaru, ale menu, CO2 alarm a probuzení tlačítkem pořád nikdo neproklikal. Viz seznam testů v v2 STATUS.
3. ~~Znovu zapnout dynamickou korekci self-heatingu~~ **ROZHODNUTO: ne.** Dva záznamy nabíjení ukazují, že teplo závisí na stavu baterky (+3.7 °C z prázdné, +2.35 °C ze 64 %), takže model podle času by selhal stejně jako v v1. Značí se to vlnovkou.
4. ~~ASC toggle (fáze 3)~~ **HOTOVO** - implementováno přes raw I2C (`0x2416`), položka **ASC KALIBRACE** v menu. Na hardwaru ale neozkoušené.
5. **Kalibrace děliče napětí přes celý rozsah** - pořád otevřené, jediný ověřený bod je 4.15 V. Poslední nedodělaná kalibrace v projektu.
6. **Notifikace na nízké napětí v HA** - navrženo, neimplementováno (patří to do HA automatizací, ne do firmwaru).
7. ~~Úklid mrtvého kódu~~ **HOTOVO** (viz sekce výš).

---

## Data v tomhle balíčku (`data/` složka)

**Aktualizace srpen 2026:** složka `data/` je teď **součástí repa** (dřív byla v `.gitignore`) - uživatel se rozhodl data zveřejnit, protože z nich přímo vycházejí rozhodnutí ve firmwaru. Záznamy byly přejmenované do struktury `RRRR-MM-DD-co-se-měřilo/veličina.csv` a mají vlastní [`data/README.md`](data/README.md) s popisem podmínek každého měření, co z něj vyšlo, a co ještě chybí změřit. **Ten soubor je jediný zdroj pravdy k datům** - tenhle odstavec ho jen odkazuje.

Historické v1 soubory (`history*.csv`, `after_1800.csv`, `activity.csv`, `tableConvert_com_h6k111.xlsx` - fitování starého křivkového modelu self-heatingu) už ve složce nejsou. Vztahovaly se ke starému fyzickému uspořádání před redesignem krytu, takže by se k nové kalibraci stejně použít nesměly.

**Aktualizace:** `HANDOFF.md` (tenhle soubor) je od srpna 2026 **součástí repa**. Původně byl v `.gitignore` na pokyn uživatele, ten to později změnil.

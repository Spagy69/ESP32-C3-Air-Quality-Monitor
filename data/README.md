# Naměřená data

Syrové exporty z **Home Assistant → History → Download data**. Tyhle záznamy nejsou jen archiv - konkrétní rozhodnutí a opravy ve firmwaru z nich přímo vycházejí, takže je má smysl mít u kódu, ne někde bokem. Kde na ně firmware odkazuje, je to v komentáři u příslušné konstanty/filtru ([`packages/sensors.yaml`](../packages/sensors.yaml)).

## Formát

Každá složka je jedno měření, pojmenované `RRRR-MM-DD-co-se-měřilo` (datum je **UTC**, stejně jako časy v CSV - lokální čas je v létě UTC+2). Jeden CSV = jedna entita, pojmenovaný podle veličiny, ne podle entity v HA.

Sloupce jsou tak, jak je HA exportuje: `entity_id,state,last_changed`.

Dvě věci, které se při čtení dat vyplatí vědět, jinak z nich vyjdou špatné závěry:

- **HA zapisuje jen změny.** Když senzor pošle dvakrát po sobě identickou hodnotu, druhý řádek v exportu není. Mezery v čase tedy neznamenají výpadek - často znamenají pravý opak (hodnota se vůbec nehnula). U `battery-voltage.csv` je to dokonce užitečný signál: opakovaná bit-identická hodnota je podpis mediánového filtru.
- **`state` může být `unavailable`.** Typicky reboot, OTA flash nebo výpadek WiFi. Při parsování se to musí ošetřit, ne přeskočit potichu.

## Co je v jednotlivých složkách

### `2026-08-21-v1-charger-connect/` - 11 min, v1 zapojení děliče

Krátký záznam napětí, ze kterého vypadly **dvě různé věci najednou**:

- **21:57:44Z: jednorázový šumový výkyv** - 3.7241 → **3.5884** → 3.7235 V. Celá jedna 60s perioda o 0.135 V níž, sousedi v klidu. Kvůli tomuhle vznikl medián-ze-3 v lambdě `battery_voltage`.
- **22:02:44Z: skok při připojení nabíječky** - 3.7203 → **4.1122 V** (+0.39 V) během jedné periody. Tohle bylo ještě se starým zapojením děliče (horní noha na BAT+ pinu XIAO, tedy za TP4056 modulem) a vedlo k přepojení horní nohy přímo na B+ baterky - viz [WIRING.md](../WIRING.md).

### `2026-08-21-v2-charging/` - 23 min, už po přepojení, během nabíjení

Napětí v průběhu nabíjení (ne moment připojení - ten v okně není): plynulý nárůst 3.9775 → 4.0766 V, tj. **~0.004 V/min**. To je přesně to číslo, kvůli kterému detekce nabíjení nemůže fungovat na rozdílu dvou po sobě jdoucích vzorků a musí používat pomalý klouzavý baseline - reálný nárůst je menší než šum jednoho čtení.

Několik `unavailable` řádků = OTA flashe během ladění.

### `2026-08-22-doma-baseline/` - 1 h, režim DOMA, displej vypnutý, bez nabíječky

Referenční záznam ustáleného provozu, všech 7 entit. Slouží jako **baseline** - proti němu se dá porovnávat, jestli nějaká změna něco nerozbila. Co se z něj potvrdilo:

| Zjištění | Číslo |
|---|---|
| Teplota SCD41 je ustálená, bez náběhu | 25.09-25.27 °C celou hodinu |
| Teplotní offsety obou senzorů si odpovídají | rozdíl SCD41 vs BMP180 jen 0.44 °C |
| Detekce nabíjení nedělá false-positive | max trend **-0.0003 V** proti prahu +0.015 V |
| Medián na napětí funguje | 22 ze 64 čtení bit-identických s předchozím |
| Vybíjení v DOMA | **-0.08 V/h** |

A jeden bug: v **01:56:54Z** pustil BMP180 jedno úplně vedlejší čtení - teplota 24.409 °C mezi sousedy ~24.70 °C **a zároveň** tlak 956.407 hPa proti ~957.05 hPa. Obě veličiny naráz z jedné špatné I2C konverze. Kvůli tomu má BMP180 teď `median` filtr.

> Pozor: tenhle záznam začíná **až po** tepelném ustálení, takže se z něj nedá zjistit, jak dlouho zahřívání po studeném startu trvá.

### `2026-08-22-power-on-warmup/` - 26 min od zapnutí vypínačem

Záznam pořízený kvůli otázce "jak dlouho po zapnutí trvá, než jsou hodnoty přesné". **Není to studený start** - zařízení bylo vypnuté jen pár minut, což se v datech i pozná: BMP180 vyrostl celkem o 0.37 °C, ale jeho klidový offset je 1.74 °C, takže vychladlý box by musel vyrůst zhruba o těch 1.74. Naměřené doby ustálení jsou proto **spodní mez**.

Boot je vidět jako `unavailable` → `unknown` → první hodnota (02:46:00-02:46:11Z).

Křivka má **dvě fáze**, které spolu nesouvisí:

| fáze | co se děje |
|---|---|
| **0-1.5 min** | SCD41 hlásí **+2.5 °C nad plató** (27.5 vs 25.0), vlhkost **-14 %**, CO2 +56 ppm. Prudce klesá. |
| **1.5-3 min** | Projde správnou hodnotou a **podstřelí o 0.5 °C** dolů. |
| **3-15 min** | Teprve tady se zahřívá krabička - plynulý návrat nahoru, τ ≈ 3.1 min (SCD41) / 5.9 min (BMP180). |

Doby ustálení (odchylka od finální hodnoty): SCD41 do ±0.1 °C od **12.0 min**, BMP180 od **9.0 min**, vlhkost do ±0.5 % od **10.9 min**, CO2 do ±15 ppm od 14.2 min.

Z τ se dá extrapolovat na opravdu studený start (τ je vlastnost soustavy, na amplitudě nezávisí): BMP180 by z plných 1.74 °C potřeboval **20.9 min** na ±0.05 °C. Odtud `WARMUP_MS = 20 min` v [`packages/display.yaml`](../packages/display.yaml).

**A jeden nález, který tam nikdo nehledal:** ta úvodní fáze **není tepelná**. Box byl při zapnutí prakticky na provozní teplotě, ale samotný čip SCD41 musel být *chladnější* než za provozu - vlastním teplem se drží zhruba 5.6 °C nad vzduchem v krabičce (to kompenzuje `temperature_offset`), takže za běhu sedí kolem 30.6 °C a po pár minutách bez proudu už stihl chladnout. A on přesto hlásil hodnotu odpovídající 33.1 °C. Vychladlý čip nemůže hlásit vyšší teplotu než rozehřátý. BMP180 přitom dělá pravý opak: startuje na svém minimu a roste. Vypadá to tedy na chování samotného SCD41 po startu periodického měření, ne na teplotu okolí. Proč to může být problém pro režim CESTA, je v README v Known Issues - a **zatím to není ověřené**.

Vedlejší produkt: potvrzuje, jak ESPHome plánuje první čtení. BMP180 s 60s intervalem publikoval už ~3 s po bootu, SCD41 s 10s až v 11 s (jeho první poll padl dřív, než měl senzor `data_ready`, a přeskočil se).

### `2026-08-22-cold-start/` - 6.5 h, opravdový studený start až do vybití baterky

Zařízení bylo vypnuté ~1 h, pak zapnuté (boot 04:19:33Z) a necháno běžet na baterku, dokud nedošla. Režim DOMA, displej vypnutý. **Nejcennější záznam v téhle složce** - odpověděl na tři otázky najednou.

#### 1. Zahřívání trvá ~45 min, ne 20

BMP180 se ustálí kolem 24.15 °C (plató od 60. minuty). Zbývající chyba v čase:

| čas | 10 min | 20 min | 30 min | 40 min | 50 min |
|---|---|---|---|---|---|
| chyba | −1.11 °C | −0.58 °C | −0.34 °C | −0.18 °C | −0.06 °C |

Časová konstanta vyšla **13-15 min**, ustálení tedy trvá ~3τ. Odtud `WARMUP_MS = 45 min`.

> Předchozí hodnota 20 min byla extrapolace z `power-on-warmup`, který se ukázal být teplý restart. Fitovat exponenciálu na krátký, skoro ustálený ocas dalo τ = 5.9 min, tedy **necelou polovinu skutečné hodnoty**, a extrapolace tím pádem přestřelila o víc než 2×. Poučení: časová konstanta fitovaná přes krátké okno se nedá extrapolovat.

#### 2. Ten úvodní skok SCD41 je prokazatelně artefakt senzoru

Dva nezávislé důkazy z tohohle jednoho záznamu:

- **Ze studeného startu.** V t=6 s hlásí SCD41 o **2.13 °C víc než BMP180**, ve 2. minutě je naopak **pod ním**, a pak se oba srovnají na normální rozdíl +0.49 °C. Studený čip nemůže hlásit vysoko - kdyby šlo o teplo, musel by startovat nízko a růst.
- **Při brownout restartu.** Jak baterka umírala, zařízení se v 10:45:15Z samo restartovalo a SCD41 skočil z 24.04 na **28.42 °C (+4.37 °C) za necelých 38 s**, zatímco BMP180 stál na 23.60 / 23.59 / 23.58. Reálná změna o 4.4 °C při zcela klidném druhém senzoru je fyzikálně nemožná.

Systematická kontrola celého 6.5h záznamu: skoky SCD41 nad 1 °C jsou **přesně dva** a oba sedí na restart (10:45:15 a 10:50:55). Jinde nic. Rozdíl SCD41−BMP180 drží +0.46 až +0.53 °C celých šest hodin.

#### 3. Proč HA po vybití ukazovalo hodnoty, které nikdy nenaměřilo

Konec záznamu krok po kroku:

| čas | napětí | SCD41 | BMP180 | RH | co se stalo |
|---|---|---|---|---|---|
| 10:50:08 | 3.00 V | 24.008 | 23.588 | 64.96 | poslední **správné** čtení |
| 10:50:55 | 2.94 V | **27.434** | 23.575 | **53.70** | brownout restart → transient |
| 10:51:35 | - | - | - | - | `unavailable`, spojení pryč |
| 10:52:45 | 2.94 V | **27.434** | 23.575 | **53.70** | reconnect, **bit-identické** hodnoty |

Ten poslední řádek není nové měření - je to ta samá hodnota znovu. ESPHome si stavy senzorů drží v RAM a při obnovení spojení je pošle znovu; HA to zaloguje jako změnu, protože entita předtím byla `unavailable`. Poznat se to dá podle toho, že jsou to **bit-identické floaty** (2.93834662437439), což u 30× oversamplovaného ADC nemůže vzniknout dvakrát náhodou.

A protože pak baterka došla nadobro, HA zůstalo viset právě na těch hodnotách z brownoutu: **27.43 °C** (realita 23.58, tedy o 3.9 °C vedle) a **53.7 %** vlhkosti (předtím 64.96, o 11 % vedle). Nikdy naměřené nebyly.

Opraveno filtrem v [`packages/sensors.yaml`](../packages/sensors.yaml), který teplotu a vlhkost SCD41 první 3 minuty po bootu zahazuje úplně - nepublikuje ani necachuje.

#### Vedlejší čísla

Vybíjení z 3.79 V na 2.94 V trvalo 6.5 h, tj. **~0.13 V/h** v režimu DOMA (víc než −0.08 V/h z `doma-baseline` - baterka byla níž ve vybíjecí křivce, kde klesá rychleji).

## Nové měření - jak ho sem přidat

1. V HA: **History** → vybrat entitu (nebo víc) → časový rozsah → **Download data**.
2. Nová složka `RRRR-MM-DD-co-se-měřilo`, CSV pojmenovat podle veličiny (`co2.csv`, `temperature-scd41.csv`, `battery-voltage.csv`, …).
3. Přidat sem odstavec: **za jakých podmínek** to běželo (režim DOMA/CESTA, displej, nabíječka, kde krabička ležela) a co z toho vyšlo. Bez podmínek jsou ta čísla skoro k ničemu - hodnota se dá vždycky dopočítat, kontext ne.

### Co ještě chybí změřit

- **Absolutní kontrola teploměrem** - jediné, co pořád chybí k uzavření kalibrace. Všechna dosavadní měření porovnávají oba senzory navzájem (shodnou se na 0.49 °C), ale nikdy proti nezávislé referenci. Stačí položit teploměr vedle ustálené krabičky a zapsat obojí. Bez toho se nedá rozhodnout, jestli sedí `temperature_offset` a `REST_OFFSET_BMP180` jako absolutní hodnoty, nebo jsou oba posunuté stejným směrem.
- **CESTA transient test** - potvrzeno, že úvodní skok je artefakt senzoru (viz `cold-start` výš), ale ještě není ověřené, jestli ho spouští i probuzení z deep sleepu. Rozdíl je v tom, že při brownoutu i studeném startu senzor ztratil napájení, kdežto v deep sleepu 3V3 běží dál a restartuje se jen měření. Přepnout na CESTA, nechat 3-4 cykly probuzení, exportovat teplotu SCD41 a BMP180.
- **Teploty při nabíjení** - obě teploty přes celý nabíjecí cyklus, ideálně s referenčním teploměrem vedle. Z toho se naplní `CHARGE_OFFSET_SCD41` / `CHARGE_OFFSET_BMP180`, dnes obojí `0.0`.
- **CESTA baseline** - totéž co `doma-baseline`, ale v režimu CESTA. V CESTA zařízení většinu času spí, takže se zahřívá míň a klidový offset naměřený v DOMA tam nejspíš odečítá víc, než by měl.

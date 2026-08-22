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

**A jeden nález, který tam nikdo nehledal:** ta úvodní fáze **není tepelná**. Box byl při zapnutí prakticky na provozní teplotě, takže die SCD41 musel být *chladnější* než jeho ustálených 30.6 °C raw - a on přesto hlásil 33.1. Vychladlý die nemůže hlásit vysoko. BMP180 přitom dělá pravý opak: startuje na svém minimu a roste. Vypadá to tedy na chování samotného SCD41 po startu periodického měření, ne na teplotu okolí. Proč to může být problém pro režim CESTA, je v README v Known Issues - a **zatím to není ověřené**.

Vedlejší produkt: potvrzuje, jak ESPHome plánuje první čtení. BMP180 s 60s intervalem publikoval už ~3 s po bootu, SCD41 s 10s až v 11 s (jeho první poll padl dřív, než měl senzor `data_ready`, a přeskočil se).

## Nové měření - jak ho sem přidat

1. V HA: **History** → vybrat entitu (nebo víc) → časový rozsah → **Download data**.
2. Nová složka `RRRR-MM-DD-co-se-měřilo`, CSV pojmenovat podle veličiny (`co2.csv`, `temperature-scd41.csv`, `battery-voltage.csv`, …).
3. Přidat sem odstavec: **za jakých podmínek** to běželo (režim DOMA/CESTA, displej, nabíječka, kde krabička ležela) a co z toho vyšlo. Bez podmínek jsou ta čísla skoro k ničemu - hodnota se dá vždycky dopočítat, kontext ne.

### Co ještě chybí změřit

- **Opravdu studený start** (`RRRR-MM-DD-cold-start/`) - záznam výš byl jen teplý restart. Nechat vypnuté **45-60 min** (τ soustavy je ~6 min, takže 5τ = 30 min stačí, zbytek je rezerva), pak zapnout a nechat běžet 45-60 min v DOMA s vypnutým displejem. Nedržet v ruce, zapsat si čas cvaknutí a položit vedle referenční teploměr. Změní `WARMUP_MS` z extrapolace na měření **a zároveň rozhodne tu otázku s úvodním skokem**: vychladlý die fyzicky nemůže hlásit vysoko, takže když SCD41 i po hodině vypnutí naskočí ~2.5 °C nad plató, je to definitivní důkaz, že jde o chování senzoru, ne o teplotu.
- **CESTA transient test** - jen pokud předchozí bod potvrdí, že jde o senzor: přepnout na CESTA, nechat 3-4 cykly probuzení, exportovat teplotu SCD41. Startuje-li každé probuzení kolem 27 °C, transient se opakuje při každém probuzení a v CESTA (30 s vzhůru) by padlo celé okno doprostřed něj.
- **Teploty při nabíjení** - obě teploty přes celý nabíjecí cyklus, ideálně s referenčním teploměrem vedle. Z toho se naplní `CHARGE_OFFSET_SCD41` / `CHARGE_OFFSET_BMP180`, dnes obojí `0.0`.
- **CESTA baseline** - totéž co `doma-baseline`, ale v režimu CESTA. V CESTA zařízení většinu času spí, takže se zahřívá míň a klidový offset naměřený v DOMA tam nejspíš odečítá víc, než by měl.

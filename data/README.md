# Naměřená data

Syrové exporty z **Home Assistant → History → Download data**. Tyhle záznamy nejsou jen archiv - konkrétní rozhodnutí a opravy ve firmwaru z nich přímo vycházejí, takže je má smysl mít u kódu, ne někde bokem. Kde na ně firmware odkazuje, je to v komentáři u příslušné konstanty/filtru ([`packages/sensors.yaml`](../packages/sensors.yaml)).

## Formát

Každá složka je jedno měření, pojmenované `RRRR-MM-DD-co-se-měřilo` (datum je **UTC**, stejně jako časy v CSV - lokální čas je v létě UTC+2).

Sloupce jsou tak, jak je HA exportuje: `entity_id,state,last_changed`. Export může mít dvě podoby a obě jsou v pořádku:

- **Jeden CSV na veličinu** (`co2.csv`, `temperature-scd41.csv`, …) - pojmenovaný podle veličiny, ne podle entity v HA.
- **Jeden CSV pro všechno** (`all-sensors.csv`) - když se v HA stáhne víc entit najednou; rozlišují se sloupcem `entity_id`.

Cokoliv, co se odečítalo ručně (referenční teploměr, čas cvaknutí vypínače, barva LEDky na nabíječce), patří do `.md` souboru ve stejné složce - v CSV to není a jinak se to nedá obnovit.

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

Z τ se dala extrapolovat doba pro opravdu studený start: BMP180 by z plných 1.74 °C potřeboval 20.9 min na ±0.05 °C, a odtud tehdy vzniklo `WARMUP_MS = 20 min`. **Ta extrapolace byla špatně o víc než dvojnásobek** - viz `cold-start` níž, kde vyšlo 45 min. Fitovat exponenciálu na krátký, skoro ustálený ocas dá časovou konstantu necelou polovinu skutečné.

**A jeden nález, který tam nikdo nehledal:** ta úvodní fáze **není tepelná**. Box byl při zapnutí prakticky na provozní teplotě, ale samotný čip SCD41 musel být *chladnější* než za provozu - vlastním teplem se drží několik °C nad vzduchem v krabičce (to kompenzuje `temperature_offset`, tehdy nastavený na 5.6 - čísla v tomhle odstavci z něj vycházejí), takže za běhu sedí kolem 30.6 °C a po pár minutách bez proudu už stihl chladnout. A on přesto hlásil hodnotu odpovídající 33.1 °C. Vychladlý čip nemůže hlásit vyšší teplotu než rozehřátý. BMP180 přitom dělá pravý opak: startuje na svém minimu a roste. Vypadá to tedy na chování samotného SCD41 po startu periodického měření, ne na teplotu okolí. Proč to může být problém pro režim CESTA, je v README v Known Issues - a **zatím to není ověřené**.

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

### `2026-08-22-charging-from-empty/` - 4 h, nabíjení z úplně vybité baterky, s referenčním teploměrem

Zařízení bylo úplně vybité, v 16:15 (lokálně) zapojena nabíječka, v 16:20 nabootovalo, **nabíječka zapojená po celou dobu**. Vedle položený lihový teploměr, odečty ručně - viz [`reference-thermometer.md`](2026-08-22-charging-from-empty/reference-thermometer.md), **bez toho souboru se z dat nedá zjistit skoro nic**.

Export je tentokrát **jeden soubor pro všechny entity** (`all-sensors.csv`, sloupec `entity_id` rozlišuje), včetně `binary_sensor...charging`.

#### 1. Teplo z nabíjení je +3.7 °C, a žádná konstanta ho neopraví

Průběh proti ustálenému stavu (SCD41; BMP180 dělá totéž s odchylkou do 0.2 °C):

| lokální čas | od bootu | teplota | nad ustáleným |
|---|---|---|---|
| 16:25 | 0 min | 23.78 | +0.0 |
| 16:55 | 30 min | 28.38 | +3.4 |
| **17:05** | **40 min** | **28.61** | **+3.7 (vrchol)** |
| 17:25 | 60 min | 28.54 | +3.6 |
| 18:05 | 100 min | 26.66 | +1.7 |
| 18:55 | 150 min | 25.29 | +0.3 |
| 19:15 | 170 min | 24.99 | +0.0 |

Referenční teploměr se přitom celou dobu držel na 23.8-24.2 °C, takže to není teplota v místnosti.

**Proč to nejde opravit konstantou:** teplo je úměrné nabíjecímu proudu a ten závisí na tom, jak prázdná baterka byla. Nabíjení z nuly dá hodinu plného proudu, dobití z 90 % skoro nic. Jedna konstanta by musela být vedle až o ±3.7 °C podle situace, a průměr přes tenhle cyklus (~1.8 °C) by byl vedle v **obou** směrech. Křivka podle času od začátku nabíjení selže ze stejného důvodu - přesně to zkoušela v1 a v terénu přestřelila o ~4 °C, jakmile se podmínky lišily od dat, na kterých byla nafitovaná.

Firmware to proto **needituje a jen to označí**: `CHARGE_OFFSET_*` zůstávají `0.0` a displej dává během nabíjení před hodnotu `~`.

#### 2. Absolutní kontrola offsetů - poprvé proti nezávislé referenci

Po ustálení (19:15-20:15, nabíjení dokončené) proti lihovému teploměru:

| | senzor | reference | rozdíl |
|---|---|---|---|
| SCD41 | ~24.9 | ~24.1 | **+0.5 až +1.0 °C** |
| BMP180 | ~24.6 | ~24.1 | **+0.3 až +0.7 °C** |

Vypadá to, že oba senzory čtou zhruba **o půl stupně až stupeň víc**, než je skutečnost - tedy že oba offsety (tehdy `temperature_offset` 5.6 a `REST_OFFSET_BMP180` 1.74) jsou o tolik malé. **Potvrzeno a doměřeno** v `rest-offset` níž.

**Ale zatím se podle toho nic nemění**, ze dvou důvodů: (a) lihový teploměr má sám přesnost tak ±0.5 °C a v poslední hodině skočil o 1.1 °C, zatímco senzory se pohnuly o 0.15 - takže část toho rozdílu je chyba odečtu; (b) nabíječka byla pořád zapojená, takže i "ustálený" stav ještě nese trochu zbytkového tepla. Co to uzavře, je v seznamu níž.

#### 3. Detekce nabíjení sepnula správně, ale konec nepozná

`Charging` naskočilo v 16:25, tj. **5 minut po bootu** - detekce funguje. Vyplo se v 19:25, což je ale **přesně 3 h 00 min 03 s** po sepnutí, tedy 3hodinová bezpečnostní pojistka, ne rozpoznání konce.

Skutečné nabíjení skončilo kolem **18:10-18:25** (napětí přestalo růst na 4.150 V a začalo mírně klesat). Detekce to nezachytila, protože pokles po dobití je jen ~0.0009 V/min, což se nikdy nedostane přes práh -0.01 V proti klouzavému baseline. Zůstalo tedy hodinu viset zapnuté. Tady to nevadilo (teplo v tu dobu už bylo skoro pryč), ale znamená to, že se na `Charging` nedá spolehnout jako na indikátor "právě teď teče proud".

> Kvůli tomu vzniklo pravidlo "vysoko a bez pohybu". První verze byla ale naladěná **jen na tenhle jeden záznam** a na dalším neuměla vůbec nic - viz `2026-08-23-charging-warm/` níž.

#### 4. Potvrzení té zamrzlé hodnoty z minula

V 16:15, tedy **před** bootem, HA pořád ukazovalo SCD41 **27.43 °C** a BMP180 23.58 - přesně ty hodnoty z brownoutu při vybití v předchozím záznamu. Přímé potvrzení, že se to bez opravy zaseklo a viselo tam hodiny.

#### 5. Vlhkost a CO2

Vlhkost šla 77 → 60 % zatímco teplota rostla 23.8 → 28.6. Přepočet přes Magnusův vztah dá 58 % - naměřeno 60.5 %. Ta změna vlhkosti tedy **není skutečná**, je to jen důsledek toho, že senzor počítá RH ze své vlastní nadhodnocené teploty. Zároveň je to hezké ověření, že ten Magnusův přepočet v `humidity:` filtru počítá správně.

CO2 spadlo 2400 → 1540 mezi 16:35 a 17:35 a pak znovu 1750 → 1250 kolem 19:45 - otevřené dveře, normální větrání. Nic se senzorem.

### `2026-08-22-cesta-wake-cycles/` - 50 min, 9 cyklů probuzení z deep sleepu

Test s jedinou otázkou: **spouští startovní skok SCD41 i probuzení z deep sleepu?** Nastaveno DEEP SLEEP zapnuto + HA připojení zapnuté (tedy CUSTOM, ne čistá CESTA - v čisté CESTA je WiFi vypnutá a do HA by se nedostalo nic), interval 5 min. Ve 20:42 lokálně odpojena nabíječka.

**Odpověď: ano, opakuje se to při každém probuzení, a je to horší než při studeném startu.**

| probuzení | SCD41 1. čtení | SCD41 2. čtení (+10 s) | BMP180 | SCD41 − BMP180 |
|---|---|---|---|---|
| 20:47 | 29.637 | 28.908 | 24.276 | **+5.36** |
| 20:53 | 29.386 | 28.631 | 23.987 | **+5.40** |
| 20:58 | 29.173 | 28.428 | 23.751 | **+5.42** |
| 21:04 | 28.857 | 28.120 | 23.485 | **+5.37** |
| 21:09 | 28.574 | 27.851 | 23.151 | **+5.42** |
| 21:15 | 28.470 | 27.720 | 22.932 | **+5.54** |
| 21:20 | 28.355 | 27.640 | 22.823 | **+5.53** |
| 21:26 | 28.305 | 27.581 | 22.738 | **+5.57** |
| 21:31 | 28.262 | 27.509 | 22.677 | **+5.59** |

Devět probuzení, pokaždé stejný obrázek: SCD41 startuje **~5.5 °C nad** BMP180 a za 10 s spadne o **0.72-0.76 °C**. Ta konzistence je pozoruhodná - rozptyl prvního rozdílu je 5.36 až 5.59, rozptyl poklesu 0.72 až 0.76.

Pro srovnání první blok v 20:42, ještě než začalo uspávání (zařízení běželo v kuse): SCD41 24.879 vs BMP180 24.572, tedy **rozdíl 0.31 °C** - úplně normální. Takže dokud běží nepřetržitě, oba senzory si odpovídají; jakmile se začne uspávat, je SCD41 o pět stupňů vedle. Vlhkost s tím jde ruku v ruce: 61.8 % v tom prvním bloku, pak 46.7-50.6 % při každém probuzení, tj. o ~13 % míň.

BMP180 přitom klesá naprosto hladce (24.57 → 22.68 za 50 min, jak krabička ve spánku chladne) a **žádný skok nemá**.

#### Co z toho plyne

Mechanismus zapadá do toho, co ukázaly předchozí záznamy: první čtení po `start_periodic_measurement` vypadá, jako by na něj ještě nebyl aplikovaný `temperature_offset` (tehdy 5.6 °C), a ten se "dotáhne" během ~2 minut. Sedí to na obojí - při studeném startu je čip stejně studený jako krabička, takže chybějící offset dělá rozdíl proti BMP180 jen ~1.7-2.1 °C; tady čip celou dobu spánku běžel dál a je proti chladnoucí krabičce rozehřátý, takže totéž dělá ~5.5 °C.

**Prakticky: v režimu s deep sleepem je teplota a vlhkost ze SCD41 nepoužitelná.** 30 s vzhůru je řádově míň, než těch ~2 min, co potřebuje na dotažení. Firmware to od té doby zahazuje (první 3 min po bootu), takže se do HA aspoň nedostane nesmysl - ale znamená to, že v CESTA nemá odkud teplotu brát. Nejnadějnější řešení je **brát ji z BMP180**, který je v těch samých datech čistý.

### `2026-08-22-rest-offset/` - 1 h, klidový offset proti referenčnímu teploměru

**Tímhle se zavřela kalibrace teploty.** Ruční odečty a podmínky jsou v [`reference-thermometer.md`](2026-08-22-rest-offset/reference-thermometer.md).

Nabíječka i USB odpojené, DOMA, displej zhasnutý, 49 min na ustálení, pak tři odečty po pěti minutách - všechny shodně **23.9 °C**.

| | senzor | teploměr | chyba | offset |
|---|---|---|---|---|
| SCD41 | 24.97 | 23.9 | **+1.07 °C** | 5.6 → **6.7** |
| BMP180 | 24.62 | 23.9 | **+0.72 °C** | 1.74 → **2.46** |

Obě kontroly platnosti prošly: rozdíl mezi senzory 0.35 °C (očekáváno 0.3-0.5) a BMP180 se přes všechny tři odečty pohnul jen o 0.090 °C, takže se místnost pod rukama neměnila. Ta druhá kontrola je podstatná - oba senzory za vzduchem zaostávají o svou časovou konstantu (11-15 min), takže drift v místnosti by se započítal jako chyba offsetu.

Proti předchozímu pokusu (`charging-from-empty`, kde vyšlo +0.5 až +1.0 a +0.3 až +0.7) to sedí, jen je to čistší: tehdy byla zapojená nabíječka a teploměr během hodiny skákal o 1.1 °C.

Vedlejší efekt: změna `temperature_offset` posune i vlhkost, protože SCD41 počítá RH ze své offsetem opravené teploty - vyjde asi o 4 procentní body výš. Ověřit to nemáme čím, vlhkoměr jako reference chybí. CO2 to neovlivní.

### `2026-08-22-breath-test/` - 45 min, dýchání do senzoru

První záznam na **novém firmwaru** (nové offsety 6.7 / 2.46). Zařízení v klidu, pak od 23:39 pomalé dýchání do krabičky.

#### Potvrzení, že nové offsety sedí

Před dýcháním je rozdíl **SCD41 − BMP180 = −0.06 až −0.11 °C**. Před překalibrováním to bylo +0.35 °C. Posun je přesně ten očekávaný: SCD41 dostal o 1.07 větší offset, BMP180 o 0.72, rozdíl 0.35 - takže +0.35 → ~0.00. Oba senzory se teď za klidu shodnou na **desetinu stupně**. Po odeznění dýchání (00:06) je rozdíl zpátky na −0.05 °C.

#### Reakce na dech

| | SCD41 | BMP180 |
|---|---|---|
| interval čtení | 5 s | 60 s |
| vrchol | 26.29 °C v 23:40:21 | 28.00 °C v 23:40:56 |
| náběh | 24.03 → 26.29 za 45 s | jen 3 vzorky přes celou událost |

**Rozdíl až −2.57 °C je přechodový jev, ne neshoda senzorů.** BMP180 je holý čip s minimální tepelnou kapacitou a reaguje okamžitě; SCD41 je větší modul a jeho teplotní výstup je navíc interně filtrovaný (ten samý filtr, který dělá ~2min startovní transient). Při pomalé změně dají oba totéž, při prudké ukáže víc ten rychlejší a bližší zdroji tepla.

Zajímavost: publikovaných 28.00 °C u BMP180 je **už zfiltrovaná** hodnota. Median-of-3 vydá prostřední ze tří čtení, takže aby prošlo 28.00, muselo být jedno z předchozích syrových čtení **ještě vyšší** - skutečný vrchol byl nejspíš přes 30 °C. Filtr fungoval, jak má.

#### Ostatní veličiny

- **CO2**: 1253 → **5038 ppm** ve vrcholu, nad 3000 ppm celkem **6.6 min**. Návrat k ~1400 za 25 min.
- **Vlhkost**: 65.7 → **93.8 %**, vrchol ale až v 23:52, tedy **12 min po** vrcholu CO2. Část toho zpoždění je chladnutí (klesající teplota zvedá RH při stejném množství vody), část vlhkost, která v krabičce zůstala - CO2 se provětrá rychleji.

> 93.8 % je blízko rosnému bodu. Dech je nasycený při ~34 °C a když v krabičce zchladne na 24 °C, je hluboko za saturací. Jednorázově nevadí, opakovaně tam dýchat ale znamená riziko skutečné kondenzace na senzorech.

### `2026-08-23-charging-warm/` - 1 h, nabíjení ze 64 % s už ustálenou krabičkou

Protějšek k `charging-from-empty`. Tam byla baterka na nule a krabička studená, takže se startovní transient, zahřívání skříňky i teplo z nabíjení míchaly dohromady. Tady bylo zařízení **hodiny v provozu a plně ustálené**, teprve pak se v 00:19:54 (lokálně) připojila nabíječka - takže jediné, co se v datech hýbe, je teplo z nabíjení. Export je zase jeden soubor (`all-sensors.csv`).

Záznam začíná v ocasu předchozího dýchacího testu, proto ta úvodní vlhkost 82 % a CO2 1342 ppm.

#### 1. Nejlepší dosavadní potvrzení offsetů

Před připojením nabíječky:

| SCD41 | BMP180 | rozdíl |
|---|---|---|
| 24.006 | 24.014 | **−0.009 °C** |

Devět tisícin stupně. Po dýchacím testu (−0.06 až −0.11) je to druhé nezávislé potvrzení, že `temperature_offset 6.7` a `REST_OFFSET_BMP180 2.46` sedí vůči sobě. O absolutní přesnosti to neříká nic - to umí jen teploměr vedle.

#### 2. Teplo z nabíjení je hrb, ne schod - a jeho výška závisí na stavu baterky

| od připojení | SCD41 | nad klidem |
|---|---|---|
| 0 min | 24.01 | +0.0 |
| 2 min | 24.07 | +0.1 (začíná se hýbat) |
| 10 min | 25.28 | +1.3 |
| 20 min | 26.12 | +2.1 |
| **28 min** | **26.32** | **+2.31 (vrchol)** |
| 40 min | 26.09 | +2.1 |
| 50 min | 25.63 | +1.6 |
| 62 min | 25.38 | **+1.37 (a pořád klesá)** |

BMP180 dělá totéž, vrchol +2.41 °C v 27 min.

Klíčové srovnání: **z prázdné baterky to bylo +3.7 °C, ze 64 % jen +2.35 °C.** Stejná krabička, stejná nabíječka, stejná místnost - rozdíl 1.4 °C způsobil jen jiný počáteční stav baterky. Tím se argument "žádná konstanta to neopraví" mění z úvahy na **změřený fakt**: jedna konstanta je vedle o 1.4 °C už jen mezi těmito dvěma případy.

A `~` na displeji je tím pádem správná volba i proto, že teplo po ~28 min zase samo klesá - i "správná" konstanta by po chvíli přepravovala.

#### 3. Který senzor cítí teplo dřív

Rozdíl SCD41 − BMP180 se během hrbu mění: při náběhu je SCD41 **výš** (až +0.087 °C), při klesání **níž** (až −0.22 °C). Obojí znamená totéž - SCD41 se hýbe dřív, tedy leží tepelně blíž zdroji (baterka / TP4056).

Není to v rozporu s dýchacím testem, kde byl rychlejší naopak BMP180 o 1.7 °C. Tam šlo teplo **vzduchem** za desítky sekund a rozhodovala tepelná kapacita čipu; tady jde **materiálem** desítky minut a rozhoduje vzdálenost od zdroje. Jiný mechanismus, jiné pořadí.

#### 4. Detekce konce nabíjení: pravidlo z minule tady neuděla vůbec nic

Napětí vyrostlo 3.77 → 4.118 V a v 01:00:55 **v jednom kroku spadlo o 0.022 V** na 4.095, pak se ustálilo na ~4.083 a dvacet minut se drželo. Ten skok odpovídá konci nabíjení - zmizí úbytek na vnitřním odporu článku (0.022 V ≈ 500 mA × 44 mΩ).

Jenže tehdejší práh byl `FULL_V = 4.10`. **Ta hranice už nikdy nebyla překročena, takže pravidlo nesepnulo ani jednou** a `Charging Duration` běželo dál až do konce záznamu (60 min).

Proč: obě nabíjení skončila na **jiném napětí** - 4.120 V (z prázdné) a 4.083 V (odsud). 37 mV od sebe na stejném hardwaru. Absolutní hladina tedy nic negeneralizuje, generalizuje jen **plochost**. Pravidlo se proto přeladilo: `FULL_V` je teď jen volná pojistka na 4.05 a rozhoduje `FULL_FLAT_DELTA` (0.001 → 0.002, protože zdejší plató má kroky až 0.0019 V).

Přeměřeno přes oba záznamy:

| | z prázdné | zahřáté |
|---|---|---|
| staré 4.10 / 0.001 / 5 | 18:19 (+125 min) ✓ | **nikdy** ✗ |
| nové 4.05 / 0.002 / 5 | 18:19 (+125 min) ✓ | 01:07 (+48 min) ✓ |

`FULL_V` 4.00-4.08 dává stejný výsledek a `FULL_CONFIRM` 4-10 taky - obojí sedí v ploché části parametrů, ne na hraně.

#### 5. Plná baterka ukazovala 90 %

Vedlejší nález ze stejného napětí. Mapa procent byla lineární 3.0-4.2 V, ale plno je naměřeno na 4.083-4.120 V, takže **dobitá baterka hlásila 90-93 % a stovky se nedalo dosáhnout nikdy**. Horní konec se proto vzal z měření (4.12 V), ne z katalogového 4.2.

Otevřené zůstává, jestli článek opravdu končí na 4.12 V, nebo jestli dělič podhodnocuje skutečných 4.2 V o ~2 %. Rozhodne multimetr (viz TODO u děliče v `sensors.yaml`) - pro procenta je to ale jedno, protože se teď berou z toho, co ADC reálně hlásí při dobití.

#### 6. Ostatní veličiny

- **Vlhkost** 81.9 → 64.0 %. Zhruba 10 bodů z toho vysvětlí ohřátí o 2.3 °C (stejná voda ve vzduchu, vyšší teplota = nižší RH), zbytek je odeznívající vlhkost z dýchacího testu.
- **CO2** 1342 → 1247 (00:46) → 1318. Doznívání dýchacího testu a pak normální nárůst v zavřené místnosti.
- **Tlak** 966.2-966.6 hPa přes celou hodinu, žádný výstřel - median-of-3 dělá svoje.

## Nové měření - jak ho sem přidat

1. V HA: **History** → vybrat entitu (nebo víc) → časový rozsah → **Download data**.
2. Nová složka `RRRR-MM-DD-co-se-měřilo`, CSV pojmenovat podle veličiny (`co2.csv`, `temperature-scd41.csv`, `battery-voltage.csv`, …).
3. Přidat sem odstavec: **za jakých podmínek** to běželo (režim DOMA/CESTA, displej, nabíječka, kde krabička ležela) a co z toho vyšlo. Bez podmínek jsou ta čísla skoro k ničemu - hodnota se dá vždycky dopočítat, kontext ne.

### Co ještě chybí změřit

- ~~Klidový offset bez nabíječky~~ **HOTOVO**, viz `2026-08-22-rest-offset/` výš - oba offsety jsou teď změřené proti referenci.
- ~~CESTA transient test~~ **HOTOVO**, viz `2026-08-22-cesta-wake-cycles/` výš - skok se opakuje při každém probuzení a je ~5.5 °C.
- ~~Teploty při nabíjení~~ **HOTOVO**, dvakrát: `2026-08-22-charging-from-empty/` (+3.7 °C) a `2026-08-23-charging-warm/` (+2.35 °C). `CHARGE_OFFSET_*` zůstávají `0.0` **záměrně** - ty dva záznamy dokazují, že konstanta neexistuje.
- **Napětí děliče multimetrem** - dnes je násobič 3.2 ověřený v jediném bodě (4.15 V). Chce to odečty kolem 3.5 a 3.8 V. Zároveň to rozhodne, jestli plná baterka opravdu končí na 4.12 V, nebo jestli dělič podhodnocuje.
- **CESTA baseline** - totéž co `doma-baseline`, ale v režimu CESTA. V CESTA zařízení většinu času spí, takže se zahřívá míň a klidový offset naměřený v DOMA tam nejspíš odečítá víc, než by měl.

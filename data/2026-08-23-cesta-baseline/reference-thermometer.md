# Referenční teploměr - ruční odečet

Zapsáno ručně, **v CSV to není**. Jediný odečet, na konci záznamu.

| Lokální čas | Reference | Poznámka |
|---|---|---|
| 15:50 | **22.5** | 4 min po posledním řádku v CSV (15:46:41 lokálně) |

## Co o tom odečtu víme a co ne

- Že jde o **externí referenci**, ne o zařízení, je jisté: v tu chvíli publikovalo BMP180 `18.90` a `Temperature (SCD41)` bylo `unknown`. Displej v tomhle režimu bere teplotu z BMP180 (viz `packages/display.yaml`), takže 22.5 nemohlo přijít odnikud ze zařízení.
- Přístroj a jeho umístění **nejsou zaznamenané**. V předchozích měřeních (`2026-08-22-rest-offset/`, `2026-08-22-charging-from-empty/`) to byl lihový skleněný teploměr s modrou kapalinou položený vedle krabičky; předpoklad je, že tenhle odečet je z něj taky, ale potvrzené to není.
- Vlastní přesnost toho teploměru je odhadem **±0.5 °C**.

## Proč jeden odečet stačí na hlavní závěr, ale ne na kalibraci

Odchylka, kterou tenhle bod odhaluje, je **−3.55 °C** - řádově víc než jakákoliv nejistota v odečtu. Na závěr "v CESTA se odečítá offset, který tam není" to bohatě stačí.

Na **novou konstantu** to nestačí. Klidový offset v DOMA (`2026-08-22-rest-offset/`) se dělal ze tří odečtů po pěti minutách plus dvou kontrol platnosti (rozdíl SCD41 − BMP180, a drift BMP180 přes celé měření). Tady je jeden bod, jeden teploměr, neznámé umístění. Zbytkových **−1.09 °C** proti syrovému čtení proto nejde rozhodnout: může to být vlastní chyba BMP180 (datasheet ±1 °C), chyba teploměru, nebo skutečný rozdíl mezi místem krabičky a místem teploměru.

Co pro to udělat příště: **stejný protokol jako u `rest-offset`, ale v režimu s uspáváním** - tři odečty po pěti minutách, teploměr prokazatelně vedle krabičky, a krabička aspoň 3 h v tom režimu (viz odstavec o chladnutí v `data/README.md`).

## Podmínky

- Režim s **deep sleepem**, interval **10 min** (jako preset CESTA), ale **HA připojení zapnuté** - jinak by se do Home Assistantu nedostalo nic a záznam by neexistoval. V menu se tohle hlásí jako `CUSTOM`, ne `CESTA`.
- Krabička byla na začátku **nahřátá** (předtím běžela/nabíjela se), BMP180 startuje na 25.28 °C publikovaných.
- Baterka **plná a odpojená od nabíječky**, start na 4.152 V / 100 %.
- Přes noc, 12.4 h, bez zásahu - všech 72 probuzení je časovaných, ani jedno tlačítkem.

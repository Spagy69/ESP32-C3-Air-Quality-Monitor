# Referenční teploměr - 28. 8. 2026

Odečty hlásil uživatel ručně, teploměr ležel vedle krabičky. Časy jsou
lokální (UTC+2), hodnoty ve `all-sensors.csv` jsou v UTC.

**Který teploměr to byl, není zapsané.** Je to stejná mezera jako
u `2026-08-23-cesta-po-oprave/` a znovu se kvůli ní nedá rozhodnout, čí
ta zbytková chyba je. Příště to patří do prvního řádku.

## Odečty

| čas | teploměr | BMP180 (poslední publikovaná) | rozdíl |
|---|---|---|---|
| 22:41 | 23.4 °C | 22.440 °C (22:38:31) | **−0.96** |
| 22:51 | 23.4 °C | 22.471 °C (22:48:54) | **−0.93** |
| 23:07 | 23.4 °C | 22.477 °C (22:59:21) | **−0.92** |

Průměr **−0.94 °C**, směrodatná odchylka **0.02**.

## Proč se tomuhle měření dá věřit víc než minulému

Krabička byla v době odečtů **prokazatelně ustálená**. Po odpojení
nabíječky ve 20:34 klesala teplota z 26.44 °C a od 21:56 se drží v pásmu
22.434-22.477, tedy **rozptyl 0.043 °C přes celou hodinu**. Všechny tři
odečty padly do toho pásma. U záznamu z 23. 8. byla krabička v době
odečtů ještě v pohybu a část rozdílu tím pádem šla na vrub chladnutí.

Odečty **nejsou po pěti minutách**, jak protokol chce - jsou 10 a 16 minut
od sebe. Tady to ale nevadí z jiného důvodu: teploměr ukázal třikrát
totéž číslo a zařízení se za tu dobu pohnulo o 0.037 °C. Rozestup měl
odhalit drift; žádný drift není.

## Co to rozhoduje

**Zbytková chyba je reprodukovatelná.** Dva nezávislé záznamy, jiný den,
jiný stav baterky, jiná výchozí teplota: −0.90 °C (23. 8., sd 0.18) a
−0.94 °C (28. 8., sd 0.02). To už není šum jednoho měření.

## Co to pořád nerozhoduje

**Čí ta chyba je.** Pořád sedí uvnitř součtu katalogových nejistot -
BMP180 má ±1 °C, lihový teploměr ±0.5 °C. Reprodukovatelnost mezi dvěma
záznamy nevylučuje ani jednu z nich, protože je to nejspíš pokaždé ten
samý teploměr na tom samém místě. Na novou konstantu by bylo potřeba
buď druhý referenční teploměr, nebo prohodit místa krabičky a teploměru
a podívat se, jestli se znaménko otočí.

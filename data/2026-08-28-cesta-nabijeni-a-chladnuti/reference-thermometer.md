# Referenční teploměr - 28. 8. 2026

Odečty hlásil uživatel ručně, teploměr ležel vedle krabičky. Časy jsou
lokální (UTC+2), hodnoty ve `all-sensors.csv` jsou v UTC.

**Teploměr:** starší lihový, modrá kapalina. Je to **ten samý kus**, proti
kterému se dělaly všechny referenční odečty v projektu, včetně kalibrace
klidových offsetů v `2026-08-22-rest-offset/`. To je pro výklad podstatné -
viz "Co to rozhoduje" níž.

Katalogová tolerance u tohohle typu bývá **±1 °C**, ne ±0.5, jak se v
dokumentaci projektu dosud psalo. Dělení stupnice bývá po 1 °C, takže
odečet na desetinu je odhad mezi ryskami.

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

**A protože je to prokazatelně ten samý teploměr jako při kalibraci
offsetů, dá se z toho dopočítat něco, co dosud nešlo.**

Označme `t` skutečnou teplotu, `m` odečet teploměru (`m = t + e`, kde `e`
je chyba teploměru), `b` vlastní chybu BMP180 a `h` skutečné self-heating
v režimu DOMA. Pak:

- **Kalibrace v DOMA** (`2026-08-22-rest-offset/`) nastavila konstantu jako
  `O = raw − m = (t + h + b) − (t + e) = h + b − e = 2.46`.
- **V CESTA** se konstanta neodečítá a self-heating tam podle duty cyklu
  není (4 % času vzhůru, spočtený příspěvek ~0.02 °C), takže
  `published − m = (t + b) − (t + e) = b − e = −0.94`.

Odečtením vypadne `e` i `b` a zůstane:

> **`h = 2.46 + 0.94 = 3.40 °C`** - skutečné self-heating krabičky
> v nepřetržitém provozu, **nezávisle na tom, jak přesný ten teploměr je.**

Konstanta 2.46 tedy nikdy nebyla čisté self-heating. Je to **rozdíl dvou
věcí**: ohřevu 3.40 °C a chyby BMP180 proti referenci −0.94 °C. Dokud se
odečítala v obou režimech, na tom nezáleželo. Od chvíle, kdy se odečítá jen
při studeném startu, ano.

**Praktický důsledek: DOMA a CESTA se o sebe rozcházejí o 0.94 °C.**
DOMA čte `t + b + 0.94`, CESTA čte `t + b`. Stejná místnost, stejná
krabička, o 0.9 °C jiné číslo podle režimu. Tohle je fakt o zařízení, ne
o teploměru - platí, ať už je `e` jakékoliv.

## Co to pořád nerozhoduje

**Který z těch dvou režimů je ten správný.** Rozdělit `b − e = −0.94` na
vlastní chybu senzoru a chybu teploměru z těchhle dat nejde:

- Když je teploměr přesný (`e = 0`), čte BMP180 o 0.94 °C nízko a správně
  je **DOMA**.
- Když je přesný senzor (`b = 0`), ukazuje teploměr o 0.94 °C vysoko a
  správně je **CESTA**.

Obě varianty sedí do tolerancí (BMP180 ±1 °C podle datasheetu, tenhle typ
teploměru ±1 °C). **Další odečty tím samým teploměrem už nic nerozhodnou** -
ať jich bude kolik chce, `e` se z nich nevydělí. Rozhodne jedině:

1. **druhý referenční teploměr** (nejlépe jiného typu - digitální s
   certifikátem, nebo aspoň druhý kus), nebo
2. **prohození míst** krabičky a teploměru: kdyby ten rozdíl dělalo místo
   v pokoji a ne přístroje, musí se znaménko otočit.

Do té doby je správný postoj nechat to být a **vědět o tom kroku 0.94 °C
mezi režimy** - je zapsaný tady i v Known Issues v `README.md`.

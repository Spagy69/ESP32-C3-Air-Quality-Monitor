# Referenční teploměr - ruční odečty

Zapsáno ručně, **v CSV to není**. Čtyři odečty rozložené přes celý záznam.

| Lokální čas | Reference | BMP180 publikoval | Rozdíl | Poznámka |
|---|---|---|---|---|
| 17:40 | 23.0 | 19.746 | (−3.25) | okamžik flashe, ještě `cold_boot` - offset se pořád odečítá, nesrovnatelné |
| 17:53 | 23.1 | 22.395 | −0.71 | interpolováno mezi 17:50:00 a 18:00:24 |
| 18:00 | 23.4 | 22.332 | −1.07 | odečet z 18:00:24, 24 s po referenci |
| 20:00 | 23.0 | 22.067 | −0.93 | interpolováno mezi 19:54:56 a 20:05:21 |

Ze tří srovnatelných bodů: **průměr −0.90 °C, sd 0.18**.

## Který z těch tří bodů je nejdůvěryhodnější

**Ten z 20:00.** Krabička se po flashi ~50 min chladla (na USB běžela nepřetržitě
během kompilace a nahrávání, což ji nahřálo) a body 17:53 a 18:00 padnou doprostřed
toho chladnutí. Vidět je to na tom, že přístroj v tom úseku klesá (22.42 → 22.33),
zatímco reference stoupá (23.1 → 23.4) - to nemůže být obojí pravda o té samé
místnosti. V 20:00 už je od flashe 2 h 20 min a přístroj je na plochém konci křivky.

Odečet **23.4 v 18:00 je navíc vybočující i ve své vlastní řadě** - nahoru o 0.3 a
za dvě hodiny zpátky dolů o 0.4, přičemž přístroj se mezitím pohnul jen o 0.27 dolů.

## Co to rozhoduje a co ne

**Rozhoduje** to hlavní otázku toho testu: opravená verze měří v uspávaném režimu
**−0.90 °C** proti referenci, kde předtím měřila **−3.55 °C**. Kdyby se offset
2.46 pořád odečítal, vyšlo by z těchhle stejných dat **−3.36 °C**. Oprava tedy sedí
na změřené hodnotě, ne na odhadu.

**Nerozhoduje** to, jestli se má zavést nová konstanta pro uspávaný režim. Zbytkových
−0.90 °C je pořád **dvojnásobek deklarované přesnosti ±0.5 °C**, ale tenhle záznam
neumí říct, čí ta chyba je: vlastní chyba BMP180 (datasheet ±1 °C), chyba teploměru
(±0.5 °C), nebo skutečný rozdíl mezi místem krabičky a místem teploměru. Tři body
rozházené přes 2 h nejsou totéž co protokol z `2026-08-22-rest-offset/`.

Co pro to udělat příště, se od minula nemění: **tři odečty po pěti minutách** na
konci aspoň tříhodinového běhu v uspávaném režimu, teploměr prokazatelně vedle
krabičky, a zaznamenat **který** teploměr to je.

## Podmínky

- Firmware z větve `v2-deep-sleep-fixes` (7 commitů), nahraný v **17:40** lokálně.
- Režim s **deep sleepem**, interval **10 min**, ale **HA připojení zapnuté** - jinak
  by se do Home Assistantu nedostalo nic. V menu se tohle hlásí jako `CUSTOM`,
  ne `CESTA`.
- Krabička **nahřátá od flashování** (viz výš), baterka **odpojená od nabíječky**,
  start na 3.975 V / 87 %.
- Bez zásahu, 2 h 46 min, všech 16 probuzení je časovaných - **tlačítko nebylo ani
  jednou zmáčknuté**, takže tenhle záznam neověřuje nic, co je vidět jen na displeji
  (vlnovka).

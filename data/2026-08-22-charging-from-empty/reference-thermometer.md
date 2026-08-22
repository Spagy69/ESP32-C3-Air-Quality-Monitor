# Referenční teploměr - ruční odečty

Zapsáno ručně během měření, **v CSV to není** - bez tohohle souboru se ta čísla nedají obnovit.

Dva teploměry položené vedle krabičky:

- **Lihový** (skleněný, modrá kapalina) - referenční
- **Mobil** (vestavěný senzor) - ukázal se jako nepoužitelný, viz níž

Časy jsou **lokální** (UTC+2), tj. o 2 h napřed proti časům v CSV.

| Lokální čas | Lihový | Mobil | Poznámka |
|---|---|---|---|
| 16:15 | 23.8 | 23.4 | zapojena nabíječka |
| 16:20 | 23.8 | 23.4 | nabootovalo |
| 16:30 | 23.8 | 22.7 | |
| 16:37 | 23.8 | 22.4 | |
| 16:45 | 23.8 | 22.0 | |
| 16:51 | 23.8 | 22.0 | |
| 17:24 | 24.0 | 22.0 | |
| 18:07 | 24.2 | 22.0 | |
| 18:57 | 24.2 | - | |
| 19:11 | 24.1 | - | |
| 19:56 | 23.8 | - | |
| 20:17 | 24.9 | - | viz upozornění níž |

## K čemu se to dá a nedá použít

**Mobilní teploměr zahoď.** Za 30 minut ukázal pokles 23.4 → 22.0 °C, zatímco lihový stál na 23.8 a oba senzory v krabičce v tu dobu naopak prudce **rostly**. Telefony neměří vzduch, ale vlastní čip, který se po odložení ochlazuje - přesně tenhle tvar to má. Jako reference je nepoužitelný.

**Lihový teploměr ber s rezervou ±0.5 °C.** Během poslední hodiny ukázal 24.1 → 23.8 → **24.9**, zatímco oba senzory se za tu dobu pohnuly o pouhých 0.15 °C. Ten skok o 1.1 °C mezi 19:56 a 20:17 je skoro jistě chyba odečtu (parallaxa / hrubá stupnice), ne skutečná změna v místnosti. Rozlišení stupnice na tomhle typu bývá 1 °C a odečítá se okem mezi ryskami.

Pro **rozdíly v čase** (o kolik se krabička ohřála od nabíjení) je to dost dobré, protože chyba odečtu se z velké části odečte. Pro **absolutní kalibraci offsetů** to stačí jen na řádové ověření (±0.5 °C), ne na doladění.

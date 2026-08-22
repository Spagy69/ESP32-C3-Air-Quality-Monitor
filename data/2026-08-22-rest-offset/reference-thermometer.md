# Referenční teploměr - ruční odečty

Zapsáno ručně, **v CSV to není**. Lihový teploměr (skleněný, modrá kapalina) položený vedle krabičky. Časy jsou **lokální** (UTC+2), tj. o 2 h napřed proti CSV.

| Lokální čas | Lihový teploměr | Poznámka |
|---|---|---|
| 22:06 | - | flashnuto, napájení z baterky, **nabíječka odpojená** |
| 22:55 | **23.9** | 49 min po startu, ustáleno |
| 23:00 | **23.9** | |
| 23:05 | **23.9** | |

Tři odečty po pěti minutách, všechny shodně 23.9 - žádný rozptyl, na rozdíl od minulého pokusu (`2026-08-22-charging-from-empty/`), kde stejný teploměr během hodiny skočil o 1.1 °C.

## Podmínky

- Režim **DOMA** (bez uspávání) - SCD41 potřebuje >3 min souvislého běhu, aby jeho teplota vůbec něco znamenala
- **Displej zhasnutý**, hodnoty odečítané z Home Assistantu (displej topí)
- **Nabíječka i USB odpojené** - během flashování jde XIAO z 5 V USB, na baterce z ~4.1 V, a ten rozdíl se pálí v LDO jako teplo. Tohle byl důvod, proč předchozí pokus s teploměrem otázku neuzavřel.
- Napětí kleslo 4.016 → 3.899 V za tu hodinu

## Výsledek

| | senzor | teploměr | chyba |
|---|---|---|---|
| SCD41 | 24.97 | 23.9 | **+1.07 °C** |
| BMP180 | 24.62 | 23.9 | **+0.72 °C** |

Odtud `temperature_offset` 5.6 → **6.7** a `REST_OFFSET_BMP180` 1.74 → **2.46**.

## Kontroly platnosti

Obě prošly:

1. **Rozdíl SCD41 − BMP180 = 0.35 °C** (očekáváno 0.3-0.5 za klidu) ✓
2. **BMP180 se přes všechny tři odečty pohnul o 0.090 °C** (limit 0.1) ✓

Ta druhá kontrola je důležitější, než vypadá. Oba senzory za teplotou vzduchu zaostávají o svou časovou konstantu (11-15 min), takže kdyby se místnost během měření znatelně měnila, to zpoždění by se započítalo jako chyba offsetu. Zbytkový drift, který tam byl, znamená, že snad 0.1 °C z těch 1.07 je zpoždění a ne offset - to je ale hluboko pod vlastní přesností teploměru (~0.5 °C), takže nemá smysl to odečítat.

## Co to ještě ovlivní

Změna `temperature_offset` **posune i vlhkost**, protože SCD41 počítá RH ze své vlastní offsetem opravené teploty. Korekce o 1.1 °C dolů znamená, že RH vyjde zhruba o 4 procentní body výš. Je to správný směr, ale nemáme čím to ověřit - vlhkoměr jako reference chybí.

**CO2 to neovlivní.** Podle Sensirionu offset kondicionuje jen výstupy teploty a vlhkosti, do přesnosti CO2 nemluví.

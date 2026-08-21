# Zapojení

## GPIO pinout (Seeed XIAO ESP32-C3)

| Pin | Funkce | Poznámka |
|---|---|---|
| GPIO6 | I2C SDA | Sdílená sběrnice: SCD41, BMP180, SSD1306 |
| GPIO7 | I2C SCL | Sdílená sběrnice: SCD41, BMP180, SSD1306 |
| GPIO4 | Snímání napětí baterky | Odbočka na děliči 220kΩ/100kΩ |
| GPIO3 | Vstup tlačítka OLED | Interní pull-up zapnutý, invertovaná logika |

## v2: hlavní vypínač baterie

Ve v2 přibyl **mechanický vypínač mezi baterií a TP4056 modulem** (v sérii na kladné větvi, mezi B+ baterky a B+ vstupem TP4056). Je to čistě hardwarová záležitost - úplně odpojí napájení celého zařízení (stejný efekt jako vytažení baterky), firmware o něm nijak neví a nepotřebuje s ním nic dělat. Slouží k tomu, aby zařízení mohlo ležet delší dobu úplně bez odběru (žádný "vampire drain" ani při zapnutém hlubokém spánku), např. při skladování.

I2C sběrnice běží na 100kHz. Interní pull-upy ESP jsou vypnuté (`sda_pullup_enabled: false`, `scl_pullup_enabled: false`), takže sběrnice běží čistě na externích 4.7kΩ pull-up rezistorech na SDA i SCL.

## Dělič napětí baterky

```
B+ (baterka, přímo) ──[220kΩ]──┬──[100kΩ]── BAT- (XIAO) / GND
                                │
                              GPIO4
```

**v2 změna:** horní noha děliče (220kΩ) je teď zapojená **přímo na kladnou svorku baterky (B+)**, ne na BAT+ pin XIAO desky/OUT+ TP4056 jako v v1 - obchází tak jakýkoli (byť malý) úbytek na trase přes modul a jeho konektory. Dolní noha (100kΩ) a referenční GND pro GPIO4 zůstávají beze změny na **XIAO GND** (= OUT- TP4056), takže záporná reference děliče je pořád za ochranným obvodem TP4056 (DW01A + FS8205A), stejně jako v v1.

Za normálního provozu (ochranný FET sepnutý) je XIAO GND prakticky totožný s B- (rozdíl jen jednotky mV), takže tahle změna nemění běžné měření ani detekci nabíjení - jen dělá horní nohu o chlup přesnější (méně sériové impedance mezi děličem a skutečnou svorkou článku).

**Co se NEmění:** při zásahu ochrany (hluboké vybití, FET rozpojí OUT-/B-) ztrácí celé XIAO napájení úplně (jde přes stejnou OUT+/OUT- cestu jako napájení ESP32) a zařízení spadne - to platilo v v1 a platí i teď, protože GND noha děliče pořád sedí za ochranným obvodem. Firmware v tu chvíli prostě neběží a nic neměří, žádná "plovoucí" chybná hodnota se do HA nedostane.

**Skok napětí při zapojení nabíječky** (viz [README Known Issues](README.md#known-issues)) se po tomhle přepojení v praxi výrazně zmenšil/zmizel. To ukazuje, že v1 zapojení (dělič na BAT+ pinu XIAO, tedy až za trasou/kontakty TP4056 modulu) neslo víc sériového odporu, než jen ten vnitřní odpor samotného článku - stačilo pár desítek/stovek mΩ navíc z konektorů/drážky modulu při průchodu nabíjecího proudu, aby se to na skoku znatelně projevilo. Přímé zapojení na svorku článku tuhle přidanou impedanci obchází.

- Poměr děliče: (220k + 100k) / 100k = 3.2
- Firmware udělá 30 rychlých čtení `analogReadMilliVolts()` na GPIO4, zprůměruje je a pak vynásobí 3.2, aby dopočítal napětí baterky
- Aktuální přesnost kalibrace viz [README.md, Known Issues](README.md#known-issues)

## Kompletní schéma zapojení

Každý jednotlivý vodič, vedený přes sdílené bus/rail uzly, aby se čáry nezamotávaly:

```mermaid
graph LR
  subgraph XIAO["Seeed XIAO ESP32-C3"]
    P3V3["3V3"]
    PGND["GND"]
    G3["GPIO3"]
    G4["GPIO4"]
    G6["GPIO6 (SDA)"]
    G7["GPIO7 (SCL)"]
    BATP["BAT+"]
    BATN["BAT-"]
  end

  G6 --> SDA_BUS(("SDA sběrnice"))
  G7 --> SCL_BUS(("SCL sběrnice"))
  P3V3 --> RAIL_3V3(("3V3 rozvod"))
  PGND --> RAIL_GND(("GND rozvod"))

  RAIL_3V3 --> RSDA["4.7kΩ"] --> SDA_BUS
  RAIL_3V3 --> RSCL["4.7kΩ"] --> SCL_BUS

  subgraph SCD41["SCD41 (adresa 0x62)"]
    S_SDA["SDA"]
    S_SCL["SCL"]
    S_VCC["VCC"]
    S_GND["GND"]
  end
  SDA_BUS --> S_SDA
  SCL_BUS --> S_SCL
  RAIL_3V3 --> S_VCC
  RAIL_GND --> S_GND

  subgraph BMP180["BMP180 (adresa 0x77)"]
    B_SDA["SDA"]
    B_SCL["SCL"]
    B_VCC["VCC"]
    B_GND["GND"]
  end
  SDA_BUS --> B_SDA
  SCL_BUS --> B_SCL
  RAIL_3V3 --> B_VCC
  RAIL_GND --> B_GND

  subgraph OLED["SSD1306 OLED (adresa 0x3C)"]
    O_SDA["SDA"]
    O_SCL["SCL"]
    O_VCC["VCC"]
    O_GND["GND"]
  end
  SDA_BUS --> O_SDA
  SCL_BUS --> O_SCL
  RAIL_3V3 --> O_VCC
  RAIL_GND --> O_GND

  subgraph BTN["Tlačítko"]
    BTN1["Vývod 1"]
    BTN2["Vývod 2"]
  end
  G3 --> BTN1
  BTN2 --> RAIL_GND

  subgraph DIVIDER["Dělič napětí baterky"]
    R1["220kΩ"]
    TAP(("Odbočka"))
    R2["100kΩ"]
  end
  R1 --> TAP --> R2
  TAP --> G4

  subgraph TP4056["TP4056 nabíjecí/ochranný modul"]
    T_OUTP["OUT+"]
    T_OUTN["OUT-"]
    T_BP["B+"]
    T_BN["B-"]
  end
  BATP --> T_OUTP
  BATN --> T_OUTN

  subgraph BATTERY["LiPo baterie ~500mAh"]
    BP["+"]
    BN["-"]
  end
  subgraph PWRSW["Hlavní vypínač (v2)"]
    SW1["Vývod 1"]
    SW2["Vývod 2"]
  end
  BP --> SW1
  SW2 --> T_BP
  T_BN --> BN
  BP --> R1
  BATN --> R2
  BATN --> RAIL_GND

  classDef bus fill:#2b2b2b,stroke:#888,color:#fff;
  class SDA_BUS,SCL_BUS,RAIL_3V3,RAIL_GND,TAP bus;
```

Poznámky ke schématu:
- `SDA sběrnice`, `SCL sběrnice`, `3V3 rozvod` a `GND rozvod` nejsou fyzické součástky, reprezentují sdílené vodiče, aby schéma nemuselo mít samostatnou křížící se čáru z XIAO ke každýmu jednotlivýmu pinu zařízení.
- SDA a SCL vedou z XIAO každá jedním vodičem, který se rozvětví ke všem třem I2C zařízením, plus pull-up rezistor na 3V3 na každé lince. Je tam jeden 4.7kΩ na SDA a jeden na SCL celkem, ne jeden na senzor.
- Všechny tři I2C zařízení sdílí stejný 3V3 a GND rozvod z XIAO.
- Tlačítko má jeden vývod na GPIO3 a druhý na GND. Interní pull-up na GPIO3 je zapnutý ve firmware a signál je invertovaný, takže pin čte vysokou hodnotu v klidu a nízkou při zmáčknutí.
- Kladný pól baterky jde přes hlavní vypínač (v2) do B+ TP4056 modulu, záporný pól jde do B- přímo. TP4056 OUT+/OUT- jde na BAT+/BAT- na XIAO, takže nabíjení řeší TP4056 modul, ne přímo XIAO deska.
- **Dělič napětí (220kΩ/100kΩ): horní konec (220kΩ) je od v2 zapojený přímo na B+ baterky**, ne na BAT+ pin XIAO desky jako v v1. Spodní konec (100kΩ) zůstává na BAT- (stejný uzel jako GND rozvod celého XIAO) - viz vysvětlení a důsledky výš v sekci "Dělič napětí baterky".
- Odbočka děliče mezi rezistory 220kΩ a 100kΩ je jediné místo připojené na GPIO4.

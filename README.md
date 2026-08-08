# ESP32-C3 Air Quality Monitor

Bateriový monitor kvality vzduchu postavený na Seeed XIAO ESP32-C3, běžící na [ESPHome](https://esphome.io/) a integrovaný do Home Assistant. Měří CO₂, teplotu, vlhkost a tlak, s malým OLED displejem pro stav a tlačítkem pro probuzení / trvalé zapnutí.

<p align="center">
  <img src="images/final.webp" width="400">
</p>


## Funkce

- CO₂, teplota a vlhkost přes Sensirion SCD41
- Sekundární teplota + barometrický tlak přes BMP180
- 128x32 I2C OLED displej, střídá 5 stránek po 3s
- Ovládání tlačítkem: jedno kliknutí probudí displej na 30s, dvojklik přepíná trvalý režim "stay on"
- Sledování napětí/procenta baterky přes odporový dělič, s 30x přeexponovaným (oversampled) čtením ADC pro potlačení šumu
- Automatické vypnutí displeje kvůli úspoře baterky
- WiFi záložní AP + captive portal, pokud je nakonfigurovaná síť nedostupná

## Hardware / BOM

| Součástka | Poznámka |
|---|---|
| Seeed XIAO ESP32-C3 | Hlavní MCU |
| Sensirion SCD41 | CO₂ / teplota / vlhkost, I2C adresa `0x62` |
| BMP180 | Teplota / tlak, I2C adresa `0x77` |
| SSD1306 128x32 OLED | I2C adresa `0x3C` |
| LiPo baterie ~500mAh | Napájí zařízení. Recyklovaná z jednorázové vapy, viz sekce Baterie níže |
| TP4056 nabíjecí/ochranný modul (s DW01A + FS8205A) | Mezi XIAO BAT+/BAT- a baterkou, viz sekce Baterie níže |
| Externí flat/nálepková WiFi anténa (u.FL) | Nahrazuje vestavěnou PCB anténu na desce, na kabelu, viz [ASSEMBLY.md](ASSEMBLY.md) |
| Tlačítko | Připojeno na GPIO3 |
| Rezistory 220kΩ + 100kΩ | Dělič napětí baterky (BAT+ → GPIO4 → GND) |
| Rezistory 4.7kΩ x2 | Externí I2C pull-upy na SDA a SCL |
| 3D tištěný kryt (PLA) | Viz [`enclosure/README.md`](enclosure/README.md) |

## Zapojení

Kompletní GPIO pinout a schéma zapojení viz [WIRING.md](WIRING.md).

## Firmware

Kompletní ESPHome konfigurace je v [`air-quality-monitor.yaml`](air-quality-monitor.yaml). Před nahráním zkopíruj `secrets.yaml.example` do `secrets.yaml` a doplň vlastní WiFi údaje, API encryption klíč a OTA heslo.

```yaml
wifi_ssid: "your-ssid"
wifi_password: "your-password"
api_encryption_key: "base64-key"
ota_password: "your-ota-password"
fallback_ap_password: "your-fallback-password"
```

**Nadmořská výška:** v `air-quality-monitor.yaml` je u SCD41 nastavené `altitude_compensation: 435m`. Tohle je výchozí hodnota nastavená podle mojí konkrétní lokace, ovlivňuje přesnost přepočtu CO₂. Pokud si tenhle config používáš jinde, uprav si tu hodnotu na nadmořskou výšku svýho místa.

## Kryt

3D tištěný z PLA. Zdrojový soubor: [`enclosure/README.md`](enclosure/README.md). Postup sestavení viz [ASSEMBLY.md](ASSEMBLY.md).

## Baterie

Baterie se nenabíjí přímo přes vestavěný nabíjecí obvod XIAO. Mezi XIAO a baterkou je zapojený externí **TP4056 modul**: XIAO BAT+ a BAT- jdou do OUT+ a OUT- na TP4056, a B+ a B- na TP4056 jdou do samotné baterky. TP4056 tak dělá nabíjení místo XIAO desky.

Deska má kromě hlavního TP4056 čipu i DW01A a FS8205A, takže jde o variantu **s ochranou**, ne jen o holou nabíječku. To řeší ochranu proti přebití, podvybití a zkratu, což byla dřív otevřená otázka u recyklovaného článku z vapu bez známého vlastního ochranného obvodu.

Než na to spolehneš dlouhodobě, stojí za to ověřit:
- **Napětí naprázdno a pod zátěží** multimetrem, ať vidíš, jestli se chová jako zdravý článek (viz Known Issues níže pro kalibraci čtení)
- **Fyzický stav článku** (nabobtnání, poškození obalu) před zabudováním do krytu
- **Přítomnost/nepřítomnost ochranného obvodu** - pokud článek nemá vlastní BMS/protection PCB, spoléháš čistě na nabíjecí obvod na XIAO desce

## Known Issues

- **Napětí/procento baterky není přesné.** Čtení teď vychází o pár procent výš než multimetr (~+2.6 % pozorováno zatím). Hodnoty děliče a čtení ADC jsou principiálně správně, ale přesný multiplikátor ještě nebyl pořádně zkalibrovaný napříč celým rozsahem napětí. Ber procenta baterky jako orientační, ne přesný údaj.
- **Riziko driftu CO₂ auto-kalibrace (ASC).** `automatic_self_calibration` je na SCD41 zapnutá. ASC předpokládá, že senzor pravidelně vidí čerstvý venkovní vzduch (~400ppm) a podle toho si upravuje baseline. Pokud senzor sedí v místnosti, která se málokdy pořádně vyvětrá, ASC si může posunout baseline vůči špatné referenci a časem podhodnocovat CO₂. Pokud se prostor pravidelně nevětrá, zvaž vypnutí ASC a manuální kalibraci místo toho.

## Licence

MIT

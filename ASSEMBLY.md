# Sestavení (kryt v2)

<p align="center">
  <img src="images/v2.webp" width="400">
</p>

Postup platí pro **kryt v2** ([`enclosure/case v2.3mf`](enclosure/README.md)). Zapojení komponent se proti v1 nemění, to je pořád v [WIRING.md](WIRING.md) - jiné je jen fyzické uspořádání a pořadí kroků.

Lepí se tavnou pistolí. Text níž používá "natavit" i "nalepit" ve stejném významu, kromě kroku 4, kde jde opravdu o **zatavení otvoru** (spára musí být zadělaná, ne jen přichycená).

## Co se změnilo proti v1

| | v1 | v2 |
|---|---|---|
| Materiál | Bambu PLA Basic | **Aurapol PETG** - tvrdší a odolnější |
| Velikost | menší | o něco větší |
| Teplotní senzory | nalepené na strop krytu | **vlastní kompartment dole**, zatavený zvlášť |
| Tlačítko | nalepené na stranu s baterií, do předního dílu jen zapadlo | **natavené přímo na přední kryt**, s pružinkou pod ním |
| Ikonka na tlačítku | žádná | **symbol napájení** ⏻ |
| Displej | na přední stěnu těla | **na přední kryt** (spolu s tlačítkem) |
| Anténa | dole, pod celou sestavou | **nahoře na krabičce**, co nejvíc vepředu |
| TP4056 | pod baterkou | **podél baterky**, na protilehlé straně než ESP32 |

Ten kompartment dole je hlavní změna, která má vliv na měření: senzory jsou teď oddělené vlastní přepážkou od baterky, TP4056 modulu i ESP32, tedy od všeho, co v krabičce topí.

## 1. Sestava baterky, nabíjení a desky

1. Natavit **baterku a TP4056 modul na sebe**. Modul jde **podél baterky**, takže na ní sedí a nepřesahuje její obrys.
2. Natavit **ESP32-C3 (XIAO)** na **druhou stranu baterky**, tedy na protilehlou plochu než TP4056 - **ne přímo na modul**. Baterka zůstává mezi nimi. Deska musí sedět tak, aby **USB-C vyčnívalo** ven přes okraj baterky.

Pořadí vrstev je tedy:

```
  ┌─────────────────────────────────────┐
  │              ESP32-C3               │  ← USB-C vyčnívá přes okraj
  ├─────────────────────────────────────┤
  │               baterka               │  ← uprostřed, drží obě desky
  ├─────────────────────────────────────┤
  │        TP4056 (podél baterky)       │
  └─────────────────────────────────────┘
```

Vznikne z toho jeden kompaktní blok, dál v textu **stack**. Ten se do krabičky vkládá až na konci (krok 10), protože by jinak překážel u všeho ostatního.

## 2. Teplotní senzory do spodního kompartmentu

3. **Jako úplně první věc** do krabičky přijdou **oba teplotní senzory** - SCD41 i BMP180. Natavit je na **strop spodního kompartmentu**.

Proč jako první: až se otvor zataví (krok 4), není se tam kudy dostat.

## 3. Zatavit spodek

4. Nasadit **novou záklopku na spodek krabičky** - zakrývá kompartment i spodní stěnu krabičky. **Zatavit.** Výsledkem musí být **celý otvor zadělaný**, ne jen přichycená destička.

## 4. Tlačítko do předního krytu

5. Vložit **tlačítko do předního krytu** a přidat pod něj **malou pružinku** - vrací tlačítko zpátky a zlepšuje odezvu.
6. **Natavit tlačítko na přední kryt.** (Ve v1 se lepilo naopak na stranu s baterií a do předního dílu jen zapadlo.)

**Pružinka:** tlačná, drát **0.016" (0.4 mm)**, vnější průměr **0.2" (5.10 mm)**, délka **0.39" (~10 mm)** - běžný rozměr z krabičky s asortimentem pružinek. **Přestřihnout zhruba v půlce**, celá je moc dlouhá; instalovaná je pak asi 5 mm.

## 5. Displej

7. Natavit **displej na přední kryt**.

> Na předním krytu tak sedí **displej i tlačítko**, a prochází jím i vypínač (krok 8). Displej je kabelem svázaný s deskou, která je vzadu v krabičce - přední díl proto po sestavení **nejde volně odložit**, visí na kabelech. Při každém rozebírání s tím počítej a netahej za ně.

## 6. Vypínač

8. Natavit **hlavní vypínač na baterku, vlevo dole** - tedy na stack, ne do krabičky. Pozice musí sedět na **díru v předním krytu**, kterou vypínač prochází ven.

## 7. Stack do krabičky

9. Vzít celý **stack (ESP32 + baterka + TP4056 + vypínač)** a nalepit ho **dozadu do krabičky**. **USB-C musí trefit díru vzadu.**

Tohle je jediné místo, kde se pozice po zaschnutí neopraví, a musí vyjít **dvě věci naráz** - USB-C vzadu a vypínač do díry v předním krytu. Stojí za to složit to nejdřív nasucho a přiložit přední kryt, jestli obojí sedí.

## 8. Anténa

10. Nalepit **anténu nahoru na krabičku**, ideálně **co nejvíc dopředu**.

Anténa je externí flat/nálepková WiFi anténa na u.FL kabelu, ne vestavěná PCB anténa na desce. Ve v1 ležela dole **pod** baterkou a TP4056 modulem, takže signál procházel skrz celou sestavu; nová pozice nahoře a vepředu tenhle problém obchází.

I tak se vyplatí to před nalepením natrvalo zkontrolovat - anténa je na kabelu, takže jde posunout bez rozebírání zbytku:

- Poskládat zařízení volně (bez lepení) a podívat se do logu na `[wifi:xxxx] Signal strength: -XX dB`.
- Orientačně: -50 až -60 dB je dobré, -60 až -70 dB v pořádku pro běžný provoz, -70 až -80 dB slabé, ale funkční, pod -80 dB už hrozí časté výpadky.

## 9. Hotovo

Nasadit přední kryt. Tím je sestavení kompletní.

### Riziko: prasknutí při secvaknutí

Pořád platí z v1 - při secvakávání předního krytu **hrozí prasknutí**. Díly musí jít spojit lehce, bez síly. Když to nejde, něco uvnitř překáží; rozebrat a zkontrolovat, ne to domáčknout. PETG je proti PLA houževnatější a spíš se ohne, než praskne, ale spoléhat se na to nedá.

---

## Poznámky k tisku

Detaily jsou v [`enclosure/README.md`](enclosure/README.md). Ve zkratce: tištěno na **Bambu Lab X1C s AMS** (stejná tiskárna jako v1), materiál **Aurapol PETG**, celý model na **0.2mm** vrstvě, podpory jen u tlačítka a u předního krytu.

**Bez AMS to jde taky.** Jediný díl, kde se barvy míchají, je **přední tlačítko** se symbolem napájení - kdo nemá AMS, vytiskne ho jednobarevně. Ikonka je pak reliéf místo barevného kontrastu, funkčně se nemění nic.

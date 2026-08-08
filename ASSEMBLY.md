# Sestavení

Sestavuje se pomocí tavné pistole (hot glue). Postup níže je v pořadí, v jakém dává smysl jej provádět, včetně dvou rizikových míst, na která je třeba dát pozor.

## 1. Sestava baterie, nabíjení a desky

1. Natavit **TP4056 modul** na spodek baterie.
2. Natavit **ESP32-C3 (XIAO) vzhůru nohama** navrch baterie. Konec s USB-C musí vyčnívat přes okraj baterie (baterie a deska pak dohromady tvoří tvar písmene L, viz náčrt níže).

Tvar půdorysu (pohled shora): deska je nahoře přes celou šířku, konektor USB-C vyčnívá z jejího pravého konce a přesahuje i přes okraj desky, baterie je dole a je užší než deska, takže nezasahuje pod USB-C.

```
┌───────────────────────────────────────────────┐
│                     ESP32-C3                  │
└───────────────────────────────────────────────┘
┌───────────────────────────────┐┌──────────────────────┐
│                               ││        USB-C         │
│                               ││                      │
│            BATERIE            │└──────────────────────┘
│                               │
│                               │
│                               │
└───────────────────────────────┘
```

Skutečné pořadí vrstev odspodu nahoru (od dna krytu):

```
  ┌─────────────────────────────────────┐
  │            ESP32-C3 (vzhůru nohama) │  ← nahoře, USB-C vyčnívá ven
  ├─────────────────────────────────────┤
  │               baterie               │
  ├─────────────────────────────────────┤
  │            nabíjecí modul (TP4056)  │
  ├─────────────────────────────────────┤
  │            anténová deska           │  ← dole, na dně krytu
  └─────────────────────────────────────┘
```

### Anténa: externí, na kabelu

Anténa není vestavěná do desky XIAO, ale jde o samostatnou externí flat/nálepkovou WiFi anténu připojenou kabelem (u.FL) k desce, umístěnou jako spodní vrstva sestavy na dně krytu. Protože je na kabelu, lze s ní hýbat nezávisle na desce, což je oproti vestavěné anténě výhoda: pokud by v této poloze byl signál slabý, není nutné přemísťovat celou sestavu, stačí přesměrovat jen anténu.

I tak anténa leží přímo pod nabíjecím modulem a baterií, takže mírný útlum signálu skrz sestavu je stále možný. Než se to nalepí natrvalo:
- Zkusit zařízení nejdřív poskládat volně (bez lepení) v plánované orientaci a zkontrolovat `Signal strength` v logu (`[wifi:xxxx] Signal strength: -XX dB`).
- Orientačně: -50 až -60 dB je dobré, -60 až -70 dB je v pořádku pro běžný provoz, -70 až -80 dB je slabé, ale funkční, pod -80 dB už hrozí časté výpadky.
- Pokud je signál slabý, zkusit anténu (díky kabelu) posunout blíž ke stěně krytu nebo dál od baterie a nabíjecího modulu, než se natrvalo přilepí ke dnu.

## 2. Vložení sestavy do krytu

3. Natavit tuto celou sestavu (TP4056, baterie, deska) do krytu, na stranu s plochou anténou.

## 3. Senzory a displej

4. Nalepit **SCD41 a BMP180** na strop dílu.
5. Nalepit **displej** na přední část dílu.

## 4. Tlačítko (na sucho, pak natrvalo)

6. **Zkusit oba díly krytu secvaknout na sucho** (bez tlačítka), aby bylo vidět, kam přesně tlačítko sedí vůči spínači/pinu na desce uvnitř.
7. Kryt znovu rozevřít.
8. **Nalepit tlačítko na stranu krytu s baterií** (ne na přední díl).
9. Vložit tlačítko do předního dílku a **nasadit přední kus na kryt najednou, v jednom kroku** (ne postupně po částech).

### Riziko: prasknutí při secvaknutí

Při secvakávání dílů dohromady (jak na sucho v kroku 6, tak natrvalo v kroku 9) hrozí mírné riziko prasknutí krytu. Díly by měly jít spojit lehce, bez použití síly. Pokud spoj nejde snadno, je vhodné zkontrolovat, zda něco uvnitř nepřekáží, a pokus zopakovat.

## 5. Hotovo

Po nasazení předního dílu je sestavení kompletní.

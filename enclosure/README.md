# Kryt

| Verze | Soubor | Materiál |
|---|---|---|
| **v2 (aktuální)** | [`case v2.3mf`](case%20v2.3mf) | **Aurapol PETG** |
| v1 (historická) | [`case.3mf`](case.3mf) | Bambu PLA Basic |

Postup sestavení je v [ASSEMBLY.md](../ASSEMBLY.md) a **platí pro v2**.

## Tisková nastavení

Tištěno na **Bambu Lab X1C + AMS** (stejná tiskárna u obou verzí). Materiál se změnil na **Aurapol PETG** - kryt je proti v1 tvrdší a odolnější. Není to Bambu filament, takže profil je potřeba vybrat ručně (generický PETG), ne podle RFID z AMS.

| Parametr | Hodnota |
|---|---|
| Výška vrstvy | 0.2mm |
| Výška vrstvy (tlačítko) | 0.2mm |
| Podpory | Jen u tlačítka a u předního krytu |

Proti v1 se tisklo tlačítko na 0.16mm, ve v2 jde celý model na jednotných **0.2mm**.

Model má zapracované tolerance, díly by měly sedět bez dodatečného úpravování.

## Tisk bez AMS

Vícebarevný je jediný díl - **přední tlačítko** se symbolem napájení. Bez AMS ho stačí vytisknout jednobarevně, ikonka pak zůstane jako reliéf. Na funkci to nemá vliv.

## Co se změnilo ve v2

- **PETG místo PLA**, o něco větší kryt
- **Spodní kompartment pro teplotní senzory** - oddělený přepážkou od baterky, TP4056 modulu i ESP32, tedy od všeho, co uvnitř topí. Zavírá ho vlastní záklopka, která se zatavuje.
- **Symbol napájení** ⏻ na tlačítku
- **Tlačítko se natavuje přímo na přední kryt** (ve v1 na stranu s baterií)
- **Jiné rozmístění stacku** - TP4056 podél baterky místo pod ní, anténa nahoře vepředu místo dole pod sestavou

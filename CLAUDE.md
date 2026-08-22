# Pokyny pro Claude Code

## Commity

**Nepřidávej se do commitů.** Žádné `Co-Authored-By: Claude`, žádný
`Claude-Session:` trailer, žádná zmínka o asistentovi v těle zprávy.
V historii má být vidět jen autor repa. Platí to i zpětně - kdyby se
takový trailer někde objevil, patří pryč.

**Nepushuj.** Commituj jen lokálně. `git push` až na výslovné vyžádání.

## Soubory mimo repo

`HANDOFF.md` je lokální kontext pro asistenta, **nikdy nepatří do gitu**
(je v `.gitignore`).

## Data

`data/` je součástí repa. Každý nový záznam patří do složky
`RRRR-MM-DD-co-se-měřilo/` a musí mít v [`data/README.md`](data/README.md)
odstavec s **podmínkami měření** (režim, displej, nabíječka, kde to
leželo) - hodnota se dá vždycky dopočítat, kontext ne.

## Přístup k práci

Čísla ve firmwaru i v dokumentaci se opírají o naměřená data, ne o odhady.
Když se něco odhaduje nebo extrapoluje, musí to být u toho napsané. Když
data odporují dřívějšímu závěru, opraví se závěr - včetně komentářů v kódu,
které to tvrdily.

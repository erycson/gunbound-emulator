# Níveis (patentes)

Valor gravado em `Game.TotalGrade` / `SeasonGrade` / `CountryGrade` e mandado nos blocos de jogador (0x1012, 0x2001,
0x2111...). Menor = melhor. Quem recalcula é `gunbound/repository/ranking.py` (job diário, como o do servidor original).

| Grade | Nome | Imagem | Regra do emulador |
|---|---|---|---|
| -4 | Silver Dragon | ![](Play/img/grades/silver-dragon.gif) | 1º colocado (entre quem tem ≥ 6900 GP) |
| -3 | Red Dragon | ![](Play/img/grades/red-dragon.gif) | próximos 4 |
| -2 | Blue Dragon | ![](Play/img/grades/blue-dragon.gif) | próximos 16 |
| -1 | Diamond Wand | ![](Play/img/grades/diamond-hole.gif) | ≥ 6900 GP, até 1% |
| 0 | Ruby Wand | ![](Play/img/grades/red-ruby-hole.gif) | até 3% |
| 1 | Sapphire Wand | ![](Play/img/grades/sapphire-hole.gif) | até 6% |
| 2 | Amethyst Wand | ![](Play/img/grades/violet-hole.gif) | até 10% |
| 3 | Gold Double Sided Axe+ | ![](Play/img/grades/gold-double-sided-axe-+.gif) | até 15% |
| 4 | Gold Double Sided Axe | ![](Play/img/grades/gold-double-sided-axe.gif) | até 22% |
| 5 | Silver Double Sided Axe+ | ![](Play/img/grades/silver-double-sided-axe-+.gif) | até 30% |
| 6 | Silver Double Sided Axe | ![](Play/img/grades/silver-double-sided-axe.gif) | até 40% |
| 7 | Metal Double Sided Axe+ | ![](Play/img/grades/metal-double-sided-axe-+.gif) | até 55% |
| 8 | Metal Double Sided Axe | ![](Play/img/grades/metal-double-sided-axe.gif) | resto de quem tem ≥ 6900 GP |
| 9 | Double Gold Axe | ![](Play/img/grades/double-gold-axe.gif) | ≥ 6000 GP |
| 10 | Gold Axe | (sem imagem) | ≥ 5100 GP |
| 11 | Double Silver Axe | ![](Play/img/grades/double-silver-axe.gif) | ≥ 4200 GP |
| 12 | Silver Axe | ![](Play/img/grades/silver-axe.gif) | ≥ 3500 GP |
| 13 | Double Metal Axe | ![](Play/img/grades/double-metal-axe.gif) | ≥ 2800 GP |
| 14 | Metal Axe | ![](Play/img/grades/metal-axe.gif) | ≥ 2300 GP |
| 15 | Double Stone Hammer | ![](Play/img/grades/double-stone-axe.gif) | ≥ 1800 GP |
| 16 | Stone Hammer | ![](Play/img/grades/stone-axe.gif) | ≥ 1500 GP |
| 17 | Double Wood Hammer | ![](Play/img/grades/double-wood-hammer.gif) | ≥ 1200 GP |
| 18 | Wood Hammer | ![](Play/img/grades/wood-hammer.gif) | ≥ 1100 GP |
| 19 | Chick | ![](Play/img/grades/chick.gif) | abaixo de 1100 GP (conta nova começa com 1000) |
| 20 | GM | | fixo; o recálculo não mexe em quem tem 20 |

- Os percentis (-1 a 8) são acumulados entre os jogadores com ≥ 6900 GP, depois dos dragões. **[INCERTO]**: valores
  aproximados (`PCT_GRADES`); não achamos a tabela exata do original.
- Servidor de um país só: `CountryGrade`/`CountryRank` copiam `TotalGrade`/`TotalRank`.
- `grade_min` / `grade_max` do `config.yml` usam esta escala (19 = Chick, -4 = Silver Dragon).

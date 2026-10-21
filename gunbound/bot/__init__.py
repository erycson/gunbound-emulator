"""
Bots de sala (acoplável: só existe no servidor com `bots.enabled` no config.yml).
- skill.py: curva de acerto pela patente e penalidades de cada tiro (vento, distância, ângulo, clima, parede...).
- profiles.py: o que cada mobile tem de especial, por fase (TH, WCS1, WCS2).
A partida em si (turno, tiro, dano) passa pelo túnel 0x4500 entre clientes; o bot só joga quando esse protocolo
estiver mapeado (docs/Bots.md).
"""

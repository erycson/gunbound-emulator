"""Dá cartas do Jack Pot Booster Card (WCS2) a um usuário no gbwc.db. Uso: python tools/give_jackpot_cards.py test 5
Cartas: item 0xAAEBF + carta (700095 Normal, 700096 Rare, 700097 Epic, 700098 Legend). Relogar para o cliente ver."""
import sqlite3
import sys

user, qty = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 5
db = sqlite3.connect('gbwc.db')
for item in range(0xAAEBF, 0xAAEBF + 4):
    db.execute("INSERT INTO Chest (Owner, Item, Acquisition, Volume, ExpireType) VALUES (?, ?, 'T', ?, 'I')", (user, item, qty))
db.commit()
print(f"{user}: +{qty} de cada carta (700095..700098)")

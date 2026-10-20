"""
Smoke test da camada de banco. Cria o schema (init_db) e exercita os repositórios.

Uso (a partir da pasta do servidor):
    python -m tests.smoke_db sqlite+aiosqlite:///smoke.db
    python -m tests.smoke_db mysql+asyncmy://gbuser:gbpass@127.0.0.1:3306/gbwc
    python -m tests.smoke_db postgresql+asyncpg://gbuser:gbpass@127.0.0.1:5432/gbwc
"""
import sys
import asyncio
import init_db
from gunbound.base.database import Database
from gunbound.base.enums import AcquisitionType, ExpireType, ReceiptBuyType, ReceiptGiftResult, GiftMsgType
from gunbound.repository import UserRepository, InventoryRepository, ServerRepository, RecordsRepository


async def main(uri: str):
    await init_db.main(uri, init_db.VERSIONS[-1])
    db = Database(uri)
    await db.connect()
    try:
        await run(db)
    finally:
        await db.disconnect()
    print(f"OK: {db.dialect}")


async def run(db: Database):
    users, inv, srv, rec = UserRepository(db), InventoryRepository(db), ServerRepository(db), RecordsRepository(db)

    profile = await users.get_profile('test')
    assert profile['User'] == 'test' and profile['Password'] == 'test' and 'Nickname' in profile, profile
    assert await users.get_gender('test') == 0
    assert [(u['Id'], u['Nickname']) for u in await users.find_by_nickname('test')] == [('test', 'test')]
    game = await users.get_game('test')
    assert isinstance(game['ClientData'], bytes) and game['TotalGrade'] is not None, game
    assert await users.update_clientdata('test', game['ClientData'])
    assert (await rec.get_stage('alison'))[0]['Stage'] == 10 and (await rec.get_mobile('alison'))[0]['Win'] == 1

    # Sessão: segundo login do mesmo usuário deve falhar
    await srv.delete_current_user('test')
    assert await srv.insert_current_user('test', 1, '127.0.0.1', 8360) is True
    assert await srv.insert_current_user('test', 2, '127.0.0.1', 8360) is False
    await srv.delete_all_users('127.0.0.1', 8360)
    assert await srv.insert_current_user('test', 3, '127.0.0.1', 8360) is True
    await srv.delete_current_user('test')
    assert await srv.is_ip_blocked('127.0.0.1') is False
    await srv.insert_login_log('test', '127.0.0.1', 8360, '127.0.0.1', 5000, '127.0.0.1', 5000)
    await srv.insert_service_status(8452169, '127.0.0.1', 8360, 'S')
    await srv.insert_user_count(8452169, '255.255.255.255', 8360, 3)

    # Compra: preço da loja, baú, débito com rowcount real
    menu = await inv.get_menu(204805, AcquisitionType.Gold, ExpireType.Week)
    assert menu['Item1'] == 204805 and menu['PriceByGoldForW'] > 0, menu
    money = await inv.get_money('test')
    assert await inv.update_money('test', -100) is True
    assert await inv.get_money('test') == money - 100
    assert await inv.update_money('test', -(10 ** 12)) is False
    assert await inv.update_money('test', 100) is True
    chest_id = await inv.insert_chest('test', 204805, AcquisitionType.Gold, ExpireType.Week, 86400, 1)
    chest_inf = await inv.insert_chest('test', 204806, AcquisitionType.Gold, ExpireType.Infinite, None, 3)
    assert isinstance(chest_id, int) and chest_inf == chest_id + 1, (chest_id, chest_inf)
    chest = {c['No']: c for c in await inv.get_chest('test')}
    assert 0 < chest[chest_id]['Expire'] <= 86400 and chest[chest_inf]['Expire'] is None, chest
    assert int(chest[chest_id]['Wearing']) == 0 and int(chest[chest_id]['Recovered']) == 0
    await inv.set_seal(chest_id, 1234)
    await inv.set_enchant_level(chest_id, 3)  # nível e selo na mesma linha do ChestEnchant
    row = {c['No']: c for c in await inv.get_chest('test')}[chest_id]
    assert (int(row['EnchantLevel']), int(row['Seal'])) == (3, 1234), row
    receipt = await inv.insert_receiptbuy('test', 204805, AcquisitionType.Gold, 100, ReceiptBuyType.Self, ExpireType.Week)
    assert isinstance(receipt, int)
    await inv.insert_buy_info('8452169', 204805, 100, money, AcquisitionType.Gold)

    # Consumo
    item = await inv.get_chest_item('test', chest_inf)
    assert item['Volume'] == 3 and item['Expire'] is None
    assert await inv.chest_consume('test', chest_inf, 1) is True
    assert (await inv.get_chest_item('test', chest_inf))['Volume'] == 2
    refund = await inv.get_refund_value(204806, AcquisitionType.Gold)
    await inv.insert_receiptconsume('test', 204806, 1, False, refund or 0, ExpireType.Infinite, 0)

    # Presente
    gift_id = await inv.insert_giftitem('test', 'Mario', 204805, AcquisitionType.Gold)
    msg_id = await inv.insert_giftmsg('test', 'Mario', 204805, gift_id, 'G', 'oi', ExpireType.Week)
    rg_id = await inv.insert_receiptgift('test', 'Mario', 204805, 'Mario', ReceiptGiftResult.Requested, ExpireType.Week)
    assert all(isinstance(i, int) for i in (gift_id, msg_id, rg_id)), (gift_id, msg_id, rg_id)
    assert await inv.update_giftitem_receiptgift_id(gift_id, rg_id)
    assert await inv.update_receiptbuy_receiptgift_id(receipt, rg_id)
    assert (await inv.get_giftmsg_from_giftitem('Mario', gift_id))['No'] == msg_id
    assert (await inv.get_giftitem('Mario', gift_id))['Sender'] == 'test'
    msgs = await users.get_gift_msgs('Mario')
    assert msgs and msgs[-1]['SentTime'] is not None and msgs[-1]['Msg'] == 'oi'
    assert await inv.update_giftmsg_status(msg_id, 'test', 'Mario', GiftMsgType.Accepted)
    answer = [m for m in await users.get_gift_msgs('Mario') if m['No'] == msg_id]  # Receiver = o 3o argumento
    assert answer and answer[0]['MsgType'] == 'A', answer
    assert await users.delete_gift_msgs([msg_id]) == 1 and not await users.delete_gift_msgs([])
    assert await inv.update_receiptgift_result(rg_id, 'test', ReceiptGiftResult.Accepted)
    assert await inv.delete_giftitem(gift_id) is True
    assert await inv.delete_giftitem(gift_id) is False

    # Transação: rollback desfaz, commit mantém
    before = await inv.get_money('test')
    tx = await db.transaction()
    await inv.update_money('test', -1)
    await tx.rollback()
    assert await inv.get_money('test') == before
    tx = await db.transaction()
    await inv.update_money('test', -1)
    await tx.commit()
    assert await inv.get_money('test') == before - 1


if __name__ == '__main__':
    asyncio.run(main(sys.argv[1]))

SELECT Allow FROM %s WHERE (0x%08X & Mask) = Ip ORDER BY Mask DESC Limit 1
SELECT Reason FROM BanLog WHERE Id = '%s' ORDER BY StartTime DESC LIMIT 1
SELECT Context, ServerIP, ServerPort FROM CurrentUser WHERE Id='%s'
SELECT Score, Rank, RankOld, Win, Lose FROM GrandPrix_Personal WHERE User='%s'
SELECT u.Nickname, g.ScoreOnCalc, g.Rank, g.RankOld, g.Win, g.Lose FROM GrandPrix_Personal AS g INNER JOIN      User AS u ON g.User=u.Id WHERE g.Rank > 0 ORDER BY g.Rank DESC LIMIT %d
SELECT Category, ScoreOnCalc, Rank, RankOld, Win, Lose FROM GrandPrix_Group WHERE Rank > 0 ORDER BY Rank DESC
SELECT ClientData FROM Game WHERE Id='%s'
SELECT Money FROM Game WHERE Id='%s'
SELECT Guild, TotalGrade, SeasonGrade, MemberCount, TotalRank, SeasonRank, GuildRank, AccumShot, AccumDamage, TotalScore, SeasonScore, Money, EventScore0, EventScore1, EventScore2, EventScore3, UNIX_TIMESTAMP(GiftProhibitTime),ClientData, Country, CountryGrade, CountryRank FROM Game WHERE Id='%s'
SELECT Id, Nickname FROM user WHERE Id IN (
SELECT Id, Nickname FROM user WHERE Nickname IN (
SELECT Item FROM Chest WHERE No=%d
INSERT INTO ReceiptGift (Id, Item, Expire, Volume, Receiver, ReceiverNick, Time) SELECT '%s', Item, Expire, Volume, Owner, '%s', NOW() FROM Chest WHERE No=%d
SELECT Refund_%c FROM Item WHERE No=%d
SELECT Item, Acquisition, Volume, Recovered, ExpireType, UNIX_TIMESTAMP(Expire)-UNIX_TIMESTAMP() FROM Chest WHERE No=%d AND Owner='%s'
SELECT Sender,ReceiptGiftNo,Acquisition FROM GiftItem WHERE No=%d and Receiver='%s'
SELECT No,MenuId,ExpireType FROM GiftMsg WHERE Receiver='%s' and GiftItemNo = %d
INSERT INTO ReceiptGift (Id, MenuId, Volume, Receiver, ReceiverNick, Time, Result, ExpireType) SELECT '%s', %d, Volume1, '%s', '%s', NOW(), 'R', '%c' FROM Menu WHERE No=%d
SELECT Item1, Period1, Volume1, Item2, Period2, Volume2, Item3, Period3, Volume3, Item4, Period4, Volume4, Item5, Period5, Volume5, %s%c FROM Menu WHERE No=%d
SELECT Item FROM Chest WHERE Owner='%s' AND Wearing=1 
SELECT No, MenuId, Sender, UNIX_TIMESTAMP(SentTime), Msg, MsgType, ExpireType, GiftItemNo FROM GiftMsg WHERE Receiver='%s'
SELECT No, Item, Wearing, Acquisition, UNIX_TIMESTAMP(Expire)-UNIX_TIMESTAMP(), Volume, PlaceOrder, Recovered FROM Chest WHERE Owner='%s'
SELECT Mobile, Win, Lose FROM MobileRecord WHERE Id='%s'
SELECT Stage, Win, Lose FROM StageRecord WHERE Id='%s'
SELECT Cash FROM Cash WHERE Id='%s'
SELECT g.Authority, UNIX_TIMESTAMP(g.RestrictTime), u.Gender, u.Password, g.Nickname 
SELECT Gender FROM User WHERE Id='%s'
INSERT DELAYED INTO BanLog SET Id='%s', StartTime=NOW(), Duration=%d, Reason=''
INSERT DELAYED INTO Accuse SET Accuse='%s', ServerIp=%u, ServerPort=%u, Accused='%s', Time=NOW(), Complaint=''
INSERT DELAYED INTO EventLog SET Id='%s', Code=%u, AcquiredScore=%d, Time=NOW(), ServerIp=%u, ServerPort=%u
INSERT DELAYED INTO AbnormalUpdate SET Master='%s', Id='%s', ScoreDelta=%d, MoneyDelta=%d, Time=NOW()
INSERT DELAYED INTO PlayLog SET 
INSERT DELAYED INTO DropLog SET Id='%s', Dropper='%s', Time=NOW()
INSERT DELAYED INTO LoginLog (Id, Ip, Ip_v, Port, Port_v, Time, ServerIp, ServerPort) VALUES ('%s', %u, %u, %u, %u, NOW(), %u, %u)
INSERT INTO Collection SET _%d=1, User='%s'
INSERT INTO GrandPrix_Personal SET Score=%d, Lose=1, User='%s'
INSERT INTO GrandPrix_Personal SET Score=%d, Win=1, User='%s'
INSERT INTO CurrentUser SET Id='%s', Context=%d, ServerIP=%d, ServerPort=%d, LoggingTime=NOW()
insert into Game set id='%s', TotalGrade=19, SeasonGrade = 19, TotalScore=1000, Money=200000 
INSERT INTO ReceiptGift (Id, Item, Expire, Volume, Receiver, ReceiverNick, Time) SELECT '%s', Item, Expire, Volume, Owner, '%s', NOW() FROM Chest WHERE No=%d
INSERT INTO GiftMsg SET Receiver='%s', ItemId=%d, Sender='%s', SentTime=NOW(), Msg='%s'
INSERT INTO ReceiptConsume SET Id='%s', Item=%d, Volume=%u, Recovered=%d, Refund=%u, Time=NOW(), ExpireType='%c', Expire=%d
INSERT INTO ReceiptBuy SET Id='%s', MenuId=%d, %sChecked=%d, BuyType='G', Time=NOW(), ExpireType='%c'
INSERT INTO ReceiptGift (Id, MenuId, Volume, Receiver, ReceiverNick, Time, Result, ExpireType) SELECT '%s', %d, Volume1, '%s', '%s', NOW(), 'R', '%c' FROM Menu WHERE No=%d
INSERT INTO GiftMsg SET Receiver='%s', MenuId=%d, GiftItemNo=%d, Sender='%s', ExpireType='%c', SentTime=NOW(), Msg='%s', MsgType='G'
INSERT INTO GiftItem SET 
INSERT INTO ReceiptBuy SET Id='%s', MenuId=%d, %sChecked=%d, Time=NOW(), BuyType='S', ExpireType='%c'
INSERT INTO Chest SET 
INSERT INTO ServiceStatus (SerialNo, Time, ServerIp, ServerPort, Status) VALUES (%u, NOW(), %u, %u, 'T')
INSERT INTO ServiceStatus (SerialNo, Time, ServerIp, ServerPort, Status) VALUES (%u, NOW(), %u, %u, 'S')
INSERT INTO BuyInfo (SerialNo, MenuNo, Price, Asset, BuyType,Time) VALUES (%u, %d, %d, %d, '%c', NOW())
INSERT INTO BuyInfo (SerialNo, MenuNo, Price, Asset, BuyType,Time) VALUES (%u, %d, %d, %d, '%c', '%s')\n
INSERT INTO MobileRecord SET Win=%d, Lose=%d, Id='%s', Mobile=%d
INSERT INTO StageRecord SET Win=%d, Lose=%d, Id='%s', Stage=%d
INSERT DELAYED INTO AbnormalUpdate SET Master='%s', Id='%s', ScoreDelta=%d, MoneyDelta=%d, Time=NOW()
UPDATE Collection SET _%d=_%d+1 WHERE User='%s'
UPDATE GrandPrix_Personal SET Score=Score+%d, Lose=Lose+1 WHERE User='%s'
UPDATE GrandPrix_Personal SET Score=Score+%d, Win=Win+1 WHERE User='%s'
UPDATE GrandPrix_Group SET Score=Score+%d, Lose=Lose+1 WHERE Category=%d
UPDATE GrandPrix_Group SET Score=Score+%d, Win=Win+1 WHERE Category=%d
UPDATE Game SET EventScore%d = EventScore%d + %d WHERE Id='%s'
UPDATE Game SET NoRankUpdate=1 WHERE Id='%s'
UPDATE Game SET Money=Money+%d WHERE Id='%s'
UPDATE Game SET 
UPDATE GunWcUser SET RestrictTime=NOW()+INTERVAL %d SECOND WHERE Id='%s'
UPDATE GunWcUser SET AuthorityBackup=Authority, Authority=%d WHERE Id='%s'
UPDATE Chest SET Owner='%s', Wearing=0, Acquisition='T', PlaceOrder=NULL WHERE No=%d AND Owner='%s' AND (Acquisition='C' OR Acquisition='G') AND Recovered=0
UPDATE Chest SET Volume=Volume-%d WHERE No=%d AND Owner='%s'
UPDATE ReceiptGift Set Result='%c',ConfirmTime=Now() WHERE No=%d and Id='%s'
UPDATE GiftMsg Set MsgType='%c',Receiver='%s',Sender='%s' WHERE No=%d
UPDATE ReceiptBuy Set ReceiptGiftNo=%d where No=%d
UPDATE GiftItem Set ReceiptGiftNo=%d where No=%d
UPDATE Chest SET Wearing=%d WHERE No=%d AND Owner='%s'
UPDATE Chest SET PlaceOrder=%u WHERE No=%d AND Owner='%s'
UPDATE MobileRecord SET Win=Win+%d, Lose=Lose+%d WHERE Id='%s' AND Mobile=%d
UPDATE StageRecord SET Win=Win+%d, Lose=Lose+%d WHERE Id='%s' AND Stage=%d
UPDATE Cash SET Cash=Cash-%d WHERE Id='%s' AND Cash>=%d
DELETE FROM CurrentUser WHERE ServerIP=%d AND ServerPort=%d
DELETE FROM CurrentUser WHERE Id='%s' AND Context=%d
DELETE FROM GiftItem WHERE No=%d
DELETE FROM GiftMsg WHERE No IN (
DELETE FROM Chest WHERE No IN (
INSERT INTO UserCount (SerialNo, ServerIp, ServerPort, Time, UserCount) VALUES (%u, %u, %u, NOW(), %d)
UPDATE user set country='%d' WHERE id='%s'
SELECT Reason FROM BanLog WHERE Id = '%s' ORDER BY StartTime DESC LIMIT 1
SELECT c_num FROM records WHERE (0x%08X & Mask_Decimal) = start_decimal ORDER BY Mask_Decimal DESC Limit 1
SELECT SerialNo, MsgBoxText, MsgBoxType, LinkUrl From Msg WHERE Id = '%s'
SELECT Authority, UNIX_TIMESTAMP(RestrictTime), Password, Nickname FROM User WHERE User = '%s'














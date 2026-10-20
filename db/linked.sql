INSTALL PLUGIN FEDERATED SONAME 'ha_federated';

CREATE SERVER gbwc_linked FOREIGN DATA WRAPPER mysql OPTIONS (HOST '127.0.0.1', PORT 33306, DATABASE 'gbwc', USER 'root', PASSWORD '');

-- ----------------------------
-- Table structure for AbnormalUpdate
-- ----------------------------
DROP TABLE IF EXISTS `AbnormalUpdate`;
CREATE TABLE `AbnormalUpdate`  (
  `Master` varchar(16) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `ID` varchar(16) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `ScoreDelta` smallint(6) NOT NULL DEFAULT 0,
  `MoneyDelta` int(11) NOT NULL DEFAULT 0,
  `Time` datetime NOT NULL DEFAULT '0000-00-00 00:00:00'
) ENGINE = federated CONNECTION = 'gbwc_linked/AbnormalUpdate';

-- ----------------------------
-- Table structure for Accuse
-- ----------------------------
DROP TABLE IF EXISTS `Accuse`;
CREATE TABLE `Accuse`  (
  `Accuse` varchar(16) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `ServerIp` int(11) NOT NULL,
  `ServerPort` smallint(5) UNSIGNED NOT NULL,
  `Accused` varchar(16) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `Complaint` text CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `Time` time NOT NULL
) ENGINE = federated CONNECTION = 'gbwc_linked/Accuse';

-- ----------------------------
-- Table structure for BanLog
-- ----------------------------
DROP TABLE IF EXISTS `BanLog`;
CREATE TABLE `BanLog`  (
  `Id` varchar(16) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `StartTime` datetime NOT NULL DEFAULT '0000-00-00 00:00:00',
  `Duration` smallint(6) NOT NULL DEFAULT 0,
  `Reason` varchar(255) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `Judge` varchar(16) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  INDEX `Id`(`Id`) USING BTREE
) ENGINE = federated CONNECTION = 'gbwc_linked/BanLog';

-- ----------------------------
-- Table structure for BuddyList
-- ----------------------------
DROP TABLE IF EXISTS `BuddyList`;
CREATE TABLE `BuddyList`  (
  `Id` varchar(16) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `Category` varchar(20) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `Buddy` varchar(16) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  INDEX `Id`(`Id`, `Buddy`) USING BTREE
) ENGINE = federated CONNECTION = 'gbwc_linked/BuddyList';

-- ----------------------------
-- Table structure for BuyInfo
-- ----------------------------
DROP TABLE IF EXISTS `BuyInfo`;
CREATE TABLE `BuyInfo`  (
  `No` int(10) UNSIGNED NOT NULL AUTO_INCREMENT,
  `SerialNo` int(10) NOT NULL COMMENT 'ProductVersion do jogo',
  `MenuNo` int(10) NOT NULL COMMENT 'ID do Item',
  `Price` int(10) NOT NULL COMMENT 'Preço de compra',
  `Asset` int(10) NOT NULL COMMENT 'Quantidade de dinheiro que o usuário tinha antes da compra',
  `BuyType` char(1) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL COMMENT 'Duração do item',
  `Time` datetime NOT NULL DEFAULT '0000-00-00 00:00:00',
  PRIMARY KEY (`No`) USING BTREE
) ENGINE = federated CONNECTION = 'gbwc_linked/BuyInfo';

-- ----------------------------
-- Table structure for Cash
-- ----------------------------
DROP TABLE IF EXISTS `Cash`;
CREATE TABLE `Cash`  (
  `ID` varchar(16) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `Cash` int(10) UNSIGNED NOT NULL,
  `OldCash` int(10) UNSIGNED NOT NULL,
  PRIMARY KEY (`ID`) USING BTREE
) ENGINE = federated CONNECTION = 'gbwc_linked/Cash';

-- ----------------------------
-- Table structure for Chest
-- ----------------------------
DROP TABLE IF EXISTS `Chest`;
CREATE TABLE `Chest`  (
  `No` int(10) UNSIGNED NOT NULL AUTO_INCREMENT,
  `Owner` varchar(16) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `Item` int(11) UNSIGNED NOT NULL,
  `Wearing` tinyint(1) UNSIGNED NOT NULL DEFAULT 0 COMMENT '1 = Equipado, 0 = Desequipado',
  `Acquisition` enum('G','C','T') CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL COMMENT 'C = Comprado, G, T',
  `Volume` int(10) UNSIGNED NOT NULL,
  `PlaceOrder` int(10) UNSIGNED NOT NULL DEFAULT 0 COMMENT 'Valor de compra ou revenda?',
  `Recovered` tinyint(1) UNSIGNED NOT NULL DEFAULT 0 COMMENT '1 = Sim, 0 = Não',
  `ExpireType` enum('I','W','M') CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL COMMENT 'I = Para sempre, W = Semana, M = Mês',
  `Expire` datetime NULL DEFAULT '0000-00-00 00:00:00',
  PRIMARY KEY (`No`) USING BTREE,
  INDEX `Chest_Item_index`(`Item`) USING BTREE,
  INDEX `Owner_Item_index`(`Owner`) USING BTREE,
  CONSTRAINT `Chest_Item_foreign` FOREIGN KEY (`Item`) REFERENCES `item` (`No`) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `Chest_Owner_foreign` FOREIGN KEY (`Owner`) REFERENCES `user` (`Id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE = federated CONNECTION = 'gbwc_linked/Chest';

-- ----------------------------
-- Table structure for Collection
-- ----------------------------
DROP TABLE IF EXISTS `Collection`;
CREATE TABLE `Collection`  (
  `User` varchar(50) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `_1` int(11) NULL DEFAULT NULL,
  `_2` int(11) NULL DEFAULT NULL,
  `_3` int(11) NULL DEFAULT NULL,
  `_4` int(11) NULL DEFAULT NULL,
  PRIMARY KEY (`User`) USING BTREE
) ENGINE = federated CONNECTION = 'gbwc_linked/Collection';

-- ----------------------------
-- Table structure for CurrentUser
-- ----------------------------
DROP TABLE IF EXISTS `CurrentUser`;
CREATE TABLE `CurrentUser`  (
  `Id` varchar(16) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL COMMENT 'ID do usuário',
  `Context` int(10) UNSIGNED NOT NULL COMMENT 'ID do servidor',
  `ServerIp` int(10) UNSIGNED NOT NULL,
  `ServerPort` smallint(5) UNSIGNED NOT NULL,
  `LoggingTime` datetime NOT NULL,
  PRIMARY KEY (`Id`) USING BTREE,
  INDEX `CurrentUser_ServerIP_ServerPort_Index`(`ServerIp`, `ServerPort`) USING BTREE,
  INDEX `CurrentUser_Id_Index`(`Id`) USING BTREE,
  CONSTRAINT `CurrentUser_Id_foreign` FOREIGN KEY (`Id`) REFERENCES `user` (`Id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE = federated CONNECTION = 'gbwc_linked/CurrentUser';

-- ----------------------------
-- Table structure for DropLog
-- ----------------------------
DROP TABLE IF EXISTS `DropLog`;
CREATE TABLE `DropLog`  (
  `Id` varchar(16) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `Dropper` varchar(16) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `Time` datetime NOT NULL DEFAULT '0000-00-00 00:00:00',
  INDEX `Id`(`Id`) USING BTREE,
  INDEX `Dropper`(`Dropper`) USING BTREE
) ENGINE = federated CONNECTION = 'gbwc_linked/DropLog';

-- ----------------------------
-- Table structure for EventLog
-- ----------------------------
DROP TABLE IF EXISTS `EventLog`;
CREATE TABLE `EventLog`  (
  `Id` varchar(16) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `Code` smallint(5) UNSIGNED NOT NULL DEFAULT 0,
  `AcquiredScore` smallint(6) NOT NULL DEFAULT 0,
  `Time` datetime NOT NULL DEFAULT '0000-00-00 00:00:00',
  `ServerIp` int(10) UNSIGNED NOT NULL DEFAULT 0,
  `ServerPort` smallint(5) UNSIGNED NOT NULL DEFAULT 0,
  INDEX `Id`(`Id`, `Code`) USING BTREE
) ENGINE = federated CONNECTION = 'gbwc_linked/EventLog';

-- ----------------------------
-- Table structure for Game
-- ----------------------------
DROP TABLE IF EXISTS `Game`;
CREATE TABLE `Game`  (
  `Id` varchar(16) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `Country` int(10) UNSIGNED NULL DEFAULT 28,
  `NickName` varchar(12) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `Guild` varchar(8) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `MemberCount` smallint(6) NOT NULL DEFAULT 0,
  `Money` int(10) UNSIGNED NOT NULL DEFAULT 0,
  `EventScore0` int(11) NOT NULL DEFAULT 0,
  `EventScore1` int(11) NOT NULL DEFAULT 0,
  `EventScore2` int(11) NOT NULL DEFAULT 0,
  `EventScore3` int(11) NOT NULL DEFAULT 0,
  `AvatarWear` bigint(20) NOT NULL DEFAULT 0,
  `Prop1` varchar(201) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `Prop2` varchar(201) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `AdminGift` smallint(6) NOT NULL DEFAULT 0,
  `TotalGrade` tinyint(4) NOT NULL DEFAULT 19,
  `SeasonGrade` tinyint(4) NOT NULL DEFAULT 19,
  `CountryGrade` tinyint(4) NOT NULL DEFAULT 19,
  `TotalScore` int(10) UNSIGNED NOT NULL DEFAULT 1000,
  `SeasonScore` int(10) UNSIGNED NOT NULL DEFAULT 1000,
  `TotalRank` int(10) UNSIGNED NOT NULL DEFAULT 0,
  `SeasonRank` int(10) UNSIGNED NOT NULL DEFAULT 0,
  `CountryRank` int(10) UNSIGNED NOT NULL DEFAULT 0,
  `GuildRank` int(10) UNSIGNED NOT NULL DEFAULT 0,
  `AccumShot` int(10) UNSIGNED NOT NULL DEFAULT 0,
  `AccumDamage` int(10) UNSIGNED NOT NULL DEFAULT 0,
  `NoRankUpdate` tinyint(1) NOT NULL DEFAULT 0,
  `ClientData` varbinary(100) NOT NULL DEFAULT 'xFE' COMMENT 'Se vazio, mandar -2 no primeiro byte para o cliente',
  `StageRecords` varbinary(161) NOT NULL,
  `MobileRecords` varbinary(161) NOT NULL,
  `LastUpdateTime` datetime NULL DEFAULT '0000-00-00 00:00:00',
  `GiftProhibitTime` datetime NULL DEFAULT '0000-00-00 00:00:00',
  `DiscountPoints` int(11) NOT NULL DEFAULT 0 COMMENT 'WCS2 desconto 0x7118',
  `RenaPoints` int(11) NOT NULL DEFAULT 0 COMMENT 'WCS2 Rena 0x7124',
  PRIMARY KEY (`Id`) USING BTREE,
  UNIQUE INDEX `Game_Id_index`(`Id`) USING BTREE,
  INDEX `Game_Guild_index`(`Guild`) USING BTREE,
  CONSTRAINT `Game_Id_foreign` FOREIGN KEY (`Id`) REFERENCES `user` (`Id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE = federated CONNECTION = 'gbwc_linked/Game';

-- ----------------------------
-- Table structure for Gift
-- ----------------------------
DROP TABLE IF EXISTS `Gift`;
CREATE TABLE `Gift`  (
  `SerialNo` int(11) NOT NULL AUTO_INCREMENT,
  `Receiver` varchar(16) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `Sender` varchar(12) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `Prop` int(10) UNSIGNED NOT NULL DEFAULT 0,
  `Msg` varchar(50) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `SentTime` datetime NOT NULL DEFAULT '0000-00-00 00:00:00',
  PRIMARY KEY (`SerialNo`) USING BTREE,
  INDEX `Receiver`(`Receiver`) USING BTREE
) ENGINE = federated CONNECTION = 'gbwc_linked/Gift';

-- ----------------------------
-- Table structure for GiftItem
-- ----------------------------
DROP TABLE IF EXISTS `GiftItem`;
CREATE TABLE `GiftItem`  (
  `No` int(10) UNSIGNED NOT NULL AUTO_INCREMENT,
  `Sender` varchar(16) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `Receiver` varchar(16) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `MenuId` int(10) UNSIGNED NOT NULL DEFAULT 0,
  `Acquisition` char(1) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `ReceiptGiftNo` varchar(16) CHARACTER SET latin1 COLLATE latin1_general_ci NULL DEFAULT NULL,
  PRIMARY KEY (`No`) USING BTREE
) ENGINE = federated CONNECTION = 'gbwc_linked/GiftItem';

-- ----------------------------
-- Table structure for GiftMsg
-- ----------------------------
DROP TABLE IF EXISTS `GiftMsg`;
CREATE TABLE `GiftMsg`  (
  `No` int(10) UNSIGNED NOT NULL AUTO_INCREMENT,
  `Receiver` varchar(16) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL COMMENT 'ID do jogador',
  `Sender` varchar(12) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL COMMENT 'Nickname do jogador',
  `MenuId` int(10) UNSIGNED NOT NULL,
  `MsgType` char(1) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL COMMENT 'G = Presente, S = Pra si mesmo',
  `Msg` varchar(255) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `ExpireType` char(1) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL DEFAULT '0' COMMENT 'I = Infinito, W = Semana, M = Mês',
  `GiftItemNo` int(16) NOT NULL,
  `SentTime` datetime NOT NULL,
  `Acquisition` varchar(255) CHARACTER SET latin1 COLLATE latin1_general_ci NULL DEFAULT NULL,
  `ItemId` int(16) NULL DEFAULT NULL,
  PRIMARY KEY (`No`) USING BTREE
) ENGINE = federated CONNECTION = 'gbwc_linked/GiftMsg';

-- ----------------------------
-- Table structure for GrandPrix_Group
-- ----------------------------
DROP TABLE IF EXISTS `GrandPrix_Group`;
CREATE TABLE `GrandPrix_Group`  (
  `Category` varchar(50) CHARACTER SET latin1 COLLATE latin1_general_ci NULL DEFAULT NULL,
  `ScoreOnCalc` varchar(50) CHARACTER SET latin1 COLLATE latin1_general_ci NULL DEFAULT NULL,
  `Rank` varchar(50) CHARACTER SET latin1 COLLATE latin1_general_ci NULL DEFAULT NULL,
  `RankOld` varchar(50) CHARACTER SET latin1 COLLATE latin1_general_ci NULL DEFAULT NULL,
  `Win` varchar(50) CHARACTER SET latin1 COLLATE latin1_general_ci NULL DEFAULT NULL,
  `Lose` varchar(50) CHARACTER SET latin1 COLLATE latin1_general_ci NULL DEFAULT NULL
) ENGINE = federated CONNECTION = 'gbwc_linked/GrandPrix_Group';

-- ----------------------------
-- Table structure for GrandPrix_Personal
-- ----------------------------
DROP TABLE IF EXISTS `GrandPrix_Personal`;
CREATE TABLE `GrandPrix_Personal`  (
  `User` varchar(16) CHARACTER SET latin1 COLLATE latin1_general_ci NULL DEFAULT NULL,
  `Score` int(11) NULL DEFAULT NULL,
  `Rank` int(11) NULL DEFAULT NULL,
  `RankOld` int(11) NULL DEFAULT NULL,
  `Win` int(11) NULL DEFAULT NULL,
  `Lose` int(11) NULL DEFAULT NULL,
  `ScoreOnCalc` varchar(50) CHARACTER SET latin1 COLLATE latin1_general_ci NULL DEFAULT NULL,
  `Category` varchar(50) CHARACTER SET latin1 COLLATE latin1_general_ci NULL DEFAULT NULL
) ENGINE = federated CONNECTION = 'gbwc_linked/GrandPrix_Personal';

-- ----------------------------
-- Table structure for GunWcUser
-- ----------------------------
DROP TABLE IF EXISTS `GunWcUser`;
CREATE TABLE `GunWcUser`  (
  `Id` varchar(16) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `User` varchar(16) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `Gender` smallint(2) NOT NULL DEFAULT 0,
  `NickName` varchar(12) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `User_Level` varchar(10) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `Authority2` varchar(10) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `Password` varchar(10) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `Status` varchar(10) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `MuteTime` datetime NOT NULL DEFAULT '0000-00-00 00:00:00',
  `RestrictTime` datetime NOT NULL DEFAULT '0000-00-00 00:00:00',
  `Authority` varchar(10) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `E_Mail` varchar(50) CHARACTER SET latin1 COLLATE latin1_general_ci NULL DEFAULT NULL,
  `Country` tinyint(3) UNSIGNED NOT NULL,
  `AuthorityBackup` int(10) NULL DEFAULT NULL,
  PRIMARY KEY (`Id`) USING BTREE,
  INDEX `GunWcUser_Id_index`(`Id`) USING BTREE,
  CONSTRAINT `GunWcUser_Id_foreign` FOREIGN KEY (`Id`) REFERENCES `user` (`Id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE = federated CONNECTION = 'gbwc_linked/GunWcUser';

-- ----------------------------
-- Table structure for IpBlock
-- ----------------------------
DROP TABLE IF EXISTS `IpBlock`;
CREATE TABLE `IpBlock`  (
  `Ip` int(10) UNSIGNED NULL DEFAULT NULL,
  `Mask` int(10) UNSIGNED NULL DEFAULT NULL,
  `Allow` bit(1) NULL DEFAULT NULL,
  INDEX `idx_IpBlock_Mask_Ip`(`Mask`, `Ip`) USING BTREE
) ENGINE = federated CONNECTION = 'gbwc_linked/IpBlock';

-- ----------------------------
-- Table structure for Item
-- ----------------------------
DROP TABLE IF EXISTS `Item`;
CREATE TABLE `Item`  (
  `No` int(11) UNSIGNED NOT NULL DEFAULT 0,
  `Refund_C` int(11) UNSIGNED NOT NULL DEFAULT 0 COMMENT 'Comprado',
  `Refund_G` int(11) UNSIGNED NOT NULL DEFAULT 0,
  `Refund_T` int(11) UNSIGNED NOT NULL DEFAULT 0,
  PRIMARY KEY (`No`) USING BTREE
) ENGINE = federated CONNECTION = 'gbwc_linked/Item';

-- ----------------------------
-- Table structure for LoginLog
-- ----------------------------
DROP TABLE IF EXISTS `LoginLog`;
CREATE TABLE `LoginLog`  (
  `Id` varchar(16) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `Ip` int(10) UNSIGNED NOT NULL DEFAULT 0,
  `Ip_V` bigint(20) UNSIGNED NOT NULL DEFAULT 0,
  `Port` smallint(5) UNSIGNED NOT NULL DEFAULT 0,
  `Port_V` smallint(5) UNSIGNED NOT NULL DEFAULT 0,
  `Time` datetime NOT NULL DEFAULT '0000-00-00 00:00:00',
  `ServerIP` bigint(20) UNSIGNED NOT NULL DEFAULT 0,
  `ServerPort` smallint(5) UNSIGNED NOT NULL DEFAULT 0
) ENGINE = federated CONNECTION = 'gbwc_linked/LoginLog';

-- ----------------------------
-- Table structure for Menu
-- ----------------------------
DROP TABLE IF EXISTS `Menu`;
CREATE TABLE `Menu`  (
  `No` int(10) UNSIGNED NOT NULL,
  `Name` varchar(23) CHARACTER SET latin1 COLLATE latin1_general_ci NULL DEFAULT NULL COMMENT 'Apenas pra ajudar a encontrar, mas não é obrigatório',
  `Item1` int(10) UNSIGNED NOT NULL,
  `Period1` int(10) UNSIGNED NOT NULL DEFAULT 86400,
  `Volume1` int(10) UNSIGNED NOT NULL DEFAULT 1,
  `Item2` int(10) UNSIGNED NULL DEFAULT NULL COMMENT 'Item2 até Item5, provavelmente é do SET',
  `Period2` int(10) UNSIGNED NULL DEFAULT NULL,
  `Volume2` int(10) UNSIGNED NULL DEFAULT NULL,
  `Item3` int(10) UNSIGNED NULL DEFAULT NULL,
  `Period3` int(10) UNSIGNED NULL DEFAULT NULL,
  `Volume3` int(10) UNSIGNED NULL DEFAULT NULL,
  `Item4` int(10) UNSIGNED NULL DEFAULT NULL,
  `Period4` int(10) UNSIGNED NULL DEFAULT NULL,
  `Volume4` int(10) UNSIGNED NULL DEFAULT NULL,
  `Item5` int(10) UNSIGNED NULL DEFAULT NULL,
  `Period5` int(10) UNSIGNED NULL DEFAULT NULL,
  `Volume5` int(10) UNSIGNED NULL DEFAULT NULL,
  `PriceByGoldForW` int(10) UNSIGNED NOT NULL,
  `PriceByCashForW` int(10) UNSIGNED NOT NULL,
  `PriceByGoldForT` int(10) UNSIGNED NOT NULL,
  `PriceByCashForT` int(10) UNSIGNED NOT NULL,
  `PriceByGoldForM` int(10) UNSIGNED NOT NULL,
  `PriceByCashForM` int(10) UNSIGNED NOT NULL,
  `PriceByGoldForY` int(10) UNSIGNED NOT NULL,
  `PriceByCashForY` int(10) UNSIGNED NOT NULL,
  `PriceByGoldForI` int(10) UNSIGNED NOT NULL,
  `PriceByCashForI` int(10) UNSIGNED NOT NULL,
  PRIMARY KEY (`No`) USING BTREE
) ENGINE = federated CONNECTION = 'gbwc_linked/Menu';

-- ----------------------------
-- Table structure for MobileRecord
-- ----------------------------
DROP TABLE IF EXISTS `MobileRecord`;
CREATE TABLE `MobileRecord`  (
  `Id` varchar(16) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `Mobile` int(10) UNSIGNED NOT NULL,
  `Win` int(10) UNSIGNED NOT NULL,
  `Lose` int(10) UNSIGNED NOT NULL,
  PRIMARY KEY (`Id`, `Mobile`) USING BTREE,
  INDEX `MobileRecord_Id_index`(`Id`) USING BTREE,
  CONSTRAINT `IMobileRecord_Id_foreign` FOREIGN KEY (`Id`) REFERENCES `user` (`Id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE = federated CONNECTION = 'gbwc_linked/MobileRecord';

-- ----------------------------
-- Table structure for PlayLog
-- ----------------------------
DROP TABLE IF EXISTS `PlayLog`;
CREATE TABLE `PlayLog`  (
  `ServerIP` int(10) UNSIGNED NOT NULL DEFAULT 0,
  `GameRoomID` smallint(5) UNSIGNED NOT NULL DEFAULT 0,
  `GameRoomTitle` varchar(64) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `StartTime` datetime NULL DEFAULT '0000-00-00 00:00:00',
  `EndTime` datetime NULL DEFAULT '0000-00-00 00:00:00',
  `GameOption` int(10) UNSIGNED NOT NULL DEFAULT 0,
  `WinTeamOrPlayer` tinyint(1) NOT NULL DEFAULT 0,
  `S0_ID` varchar(16) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `S0_TeamID` tinyint(4) NOT NULL DEFAULT 0,
  `S0_DeadTime` datetime NULL DEFAULT '0000-00-00 00:00:00',
  `S0_DeadCause` int(10) UNSIGNED NOT NULL DEFAULT 0,
  `S0_ScoreDelta` smallint(6) NOT NULL DEFAULT 0,
  `S0_MoneyDelta` int(11) NOT NULL DEFAULT 0,
  `S1_ID` varchar(16) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `S1_TeamID` tinyint(4) NOT NULL DEFAULT 0,
  `S1_DeadTime` datetime NULL DEFAULT '0000-00-00 00:00:00',
  `S1_DeadCause` int(10) UNSIGNED NOT NULL DEFAULT 0,
  `S1_ScoreDelta` smallint(6) NOT NULL DEFAULT 0,
  `S1_MoneyDelta` int(11) NOT NULL DEFAULT 0,
  `S2_ID` varchar(16) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `S2_TeamID` tinyint(4) NOT NULL DEFAULT 0,
  `S2_DeadTime` datetime NULL DEFAULT '0000-00-00 00:00:00',
  `S2_DeadCause` int(10) UNSIGNED NOT NULL DEFAULT 0,
  `S2_ScoreDelta` smallint(6) NOT NULL DEFAULT 0,
  `S2_MoneyDelta` int(11) NOT NULL DEFAULT 0,
  `S3_ID` varchar(16) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `S3_TeamID` tinyint(4) NOT NULL DEFAULT 0,
  `S3_DeadTime` datetime NULL DEFAULT '0000-00-00 00:00:00',
  `S3_DeadCause` int(10) UNSIGNED NOT NULL DEFAULT 0,
  `S3_ScoreDelta` smallint(6) NOT NULL DEFAULT 0,
  `S3_MoneyDelta` int(11) NOT NULL DEFAULT 0,
  `S4_ID` varchar(16) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `S4_TeamID` tinyint(4) NOT NULL DEFAULT 0,
  `S4_DeadTime` datetime NULL DEFAULT '0000-00-00 00:00:00',
  `S4_DeadCause` int(10) UNSIGNED NOT NULL DEFAULT 0,
  `S4_ScoreDelta` smallint(6) NOT NULL DEFAULT 0,
  `S4_MoneyDelta` int(11) NOT NULL DEFAULT 0,
  `S5_ID` varchar(16) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `S5_TeamID` tinyint(4) NOT NULL DEFAULT 0,
  `S5_DeadTime` datetime NULL DEFAULT '0000-00-00 00:00:00',
  `S5_DeadCause` int(10) UNSIGNED NOT NULL DEFAULT 0,
  `S5_ScoreDelta` smallint(6) NOT NULL DEFAULT 0,
  `S5_MoneyDelta` int(11) NOT NULL DEFAULT 0,
  `S6_ID` varchar(16) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `S6_TeamID` tinyint(4) NOT NULL DEFAULT 0,
  `S6_DeadTime` datetime NULL DEFAULT '0000-00-00 00:00:00',
  `S6_DeadCause` int(10) UNSIGNED NOT NULL DEFAULT 0,
  `S6_ScoreDelta` smallint(6) NOT NULL DEFAULT 0,
  `S6_MoneyDelta` int(11) NOT NULL DEFAULT 0,
  `S7_ID` varchar(16) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `S7_TeamID` tinyint(4) NOT NULL DEFAULT 0,
  `S7_DeadTime` datetime NULL DEFAULT '0000-00-00 00:00:00',
  `S7_DeadCause` int(10) UNSIGNED NOT NULL DEFAULT 0,
  `S7_ScoreDelta` smallint(6) NOT NULL DEFAULT 0,
  `S7_MoneyDelta` int(11) NOT NULL DEFAULT 0,
  INDEX `S0_ID`(`S0_ID`) USING BTREE,
  INDEX `S1_ID`(`S1_ID`) USING BTREE,
  INDEX `S2_ID`(`S2_ID`) USING BTREE,
  INDEX `S3_ID`(`S3_ID`) USING BTREE,
  INDEX `S4_ID`(`S4_ID`) USING BTREE,
  INDEX `S5_ID`(`S5_ID`) USING BTREE,
  INDEX `S6_ID`(`S6_ID`) USING BTREE,
  INDEX `S7_ID`(`S7_ID`) USING BTREE
) ENGINE = federated CONNECTION = 'gbwc_linked/PlayLog';

-- ----------------------------
-- Table structure for ReceiptBuy
-- ----------------------------
DROP TABLE IF EXISTS `ReceiptBuy`;
CREATE TABLE `ReceiptBuy`  (
  `No` int(10) UNSIGNED NOT NULL AUTO_INCREMENT,
  `Id` varchar(16) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL COMMENT 'ID do usuário',
  `MenuId` int(10) UNSIGNED NOT NULL,
  `CashChecked` int(10) UNSIGNED NULL DEFAULT NULL COMMENT 'Cash consumido',
  `GoldChecked` int(10) UNSIGNED NULL DEFAULT NULL COMMENT 'Gold Consumido',
  `BuyType` enum('S','G') CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL COMMENT 'S = Pra si, G = Presente',
  `ExpireType` enum('I','W','M') CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL COMMENT 'I = Infinito, W = Semana, M = Mês',
  `Time` datetime NOT NULL COMMENT 'Hora da compra',
  `ReceiptGiftNo` int(11) NULL DEFAULT NULL,
  PRIMARY KEY (`No`) USING BTREE,
  INDEX `Id`(`Id`) USING BTREE
) ENGINE = federated CONNECTION = 'gbwc_linked/ReceiptBuy';

-- ----------------------------
-- Table structure for ReceiptConsume
-- ----------------------------
DROP TABLE IF EXISTS `ReceiptConsume`;
CREATE TABLE `ReceiptConsume`  (
  `Id` varchar(16) CHARACTER SET latin1 COLLATE latin1_general_ci NULL DEFAULT NULL,
  `Item` int(16) NULL DEFAULT 0,
  `Volume` int(11) NULL DEFAULT 0,
  `Recovered` varchar(255) CHARACTER SET latin1 COLLATE latin1_general_ci NULL DEFAULT NULL,
  `Refund` varchar(255) CHARACTER SET latin1 COLLATE latin1_general_ci NULL DEFAULT NULL,
  `Time` datetime NULL DEFAULT NULL,
  `ExpireType` varchar(11) CHARACTER SET latin1 COLLATE latin1_general_ci NULL DEFAULT '0',
  `Expire` varchar(11) CHARACTER SET latin1 COLLATE latin1_general_ci NULL DEFAULT '0'
) ENGINE = federated CONNECTION = 'gbwc_linked/ReceiptConsume';

-- ----------------------------
-- Table structure for ReceiptGift
-- ----------------------------
DROP TABLE IF EXISTS `ReceiptGift`;
CREATE TABLE `ReceiptGift`  (
  `Id` varchar(16) CHARACTER SET latin1 COLLATE latin1_general_ci NULL DEFAULT NULL COMMENT 'ID do usuário',
  `MenuId` int(10) UNSIGNED NULL DEFAULT 0,
  `Volume` int(10) UNSIGNED NULL DEFAULT NULL COMMENT 'Quantidade comprada',
  `Receiver` varchar(16) CHARACTER SET latin1 COLLATE latin1_general_ci NULL DEFAULT NULL COMMENT 'ID do usuário',
  `ReceiverNick` varchar(16) CHARACTER SET latin1 COLLATE latin1_general_ci NULL DEFAULT NULL COMMENT 'Nickname do Usuário',
  `Result` char(1) CHARACTER SET latin1 COLLATE latin1_general_ci NULL DEFAULT NULL COMMENT 'R = ???',
  `ExpireType` enum('I','W','M') CHARACTER SET latin1 COLLATE latin1_general_ci NULL DEFAULT NULL COMMENT 'I = Infinito, W = Semana, M = Mês',
  `Time` datetime NULL DEFAULT NULL COMMENT 'Hora da compra',
  INDEX `Id`(`Id`) USING BTREE,
  INDEX `Receiver`(`Receiver`) USING BTREE
) ENGINE = federated CONNECTION = 'gbwc_linked/ReceiptGift';

-- ----------------------------
-- Table structure for ServiceStatus
-- ----------------------------
DROP TABLE IF EXISTS `ServiceStatus`;
CREATE TABLE `ServiceStatus`  (
  `SerialNo` int(10) UNSIGNED NOT NULL,
  `ServerIp` int(10) UNSIGNED NOT NULL,
  `ServerPort` smallint(6) UNSIGNED NOT NULL,
  `Status` enum('S','T') CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `Time` datetime NOT NULL
) ENGINE = federated CONNECTION = 'gbwc_linked/ServiceStatus';

-- ----------------------------
-- Table structure for StageRecord
-- ----------------------------
DROP TABLE IF EXISTS `StageRecord`;
CREATE TABLE `StageRecord`  (
  `Id` varchar(16) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `Stage` int(11) NOT NULL DEFAULT 0,
  `Win` int(11) NOT NULL DEFAULT 0,
  `Lose` int(11) NOT NULL DEFAULT 0,
  PRIMARY KEY (`Id`, `Stage`) USING BTREE,
  INDEX `StageRecord_Id_index`(`Id`) USING BTREE,
  CONSTRAINT `StageRecord_Id_foreign` FOREIGN KEY (`Id`) REFERENCES `user` (`Id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE = federated CONNECTION = 'gbwc_linked/StageRecord';

-- ----------------------------
-- Table structure for User
-- ----------------------------
DROP TABLE IF EXISTS `User`;
CREATE TABLE `User`  (
  `Id` varchar(16) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `User` varchar(16) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `Nickname` varchar(12) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `Password` varchar(20) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `Gender` tinyint(1) NOT NULL DEFAULT 0 COMMENT '0 = Homem, 1 = Mulher',
  `Status` varchar(10) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `MuteTime` datetime NULL DEFAULT '0000-00-00 00:00:00',
  `RestrictTime` datetime NULL DEFAULT '0000-00-00 00:00:00',
  `Authority` tinyint(4) NOT NULL DEFAULT 0,
  `Authority2` tinyint(4) NOT NULL DEFAULT 0,
  `E_Mail` varchar(50) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `Country` tinyint(3) NOT NULL,
  `User_Level` int(3) NOT NULL DEFAULT 0,
  PRIMARY KEY (`Id`) USING BTREE
) ENGINE = federated CONNECTION = 'gbwc_linked/User';

-- ----------------------------
-- Table structure for UserCount
-- ----------------------------
DROP TABLE IF EXISTS `UserCount`;
CREATE TABLE `UserCount`  (
  `SerialNo` int(10) UNSIGNED NOT NULL,
  `ServerIp` int(10) UNSIGNED NOT NULL,
  `ServerPort` smallint(5) UNSIGNED NOT NULL,
  `UserCount` int(11) UNSIGNED NOT NULL,
  `Time` datetime NOT NULL DEFAULT '0000-00-00 00:00:00'
) ENGINE = federated CONNECTION = 'gbwc_linked/UserCount';

-- ----------------------------
-- Table structure for msg
-- ----------------------------
DROP TABLE IF EXISTS `msg`;
CREATE TABLE `msg`  (
  `ID` varchar(16) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `SerialNo` int(11) NULL DEFAULT NULL,
  `MsgBoxText` varchar(50) CHARACTER SET latin1 COLLATE latin1_general_ci NULL DEFAULT '0',
  `MsgBoxType` tinytext CHARACTER SET latin1 COLLATE latin1_general_ci NULL,
  `LinkUrl` tinytext CHARACTER SET latin1 COLLATE latin1_general_ci NULL
) ENGINE = federated CONNECTION = 'gbwc_linked/msg';

-- ----------------------------
-- Table structure for packet
-- ----------------------------
DROP TABLE IF EXISTS `packet`;
CREATE TABLE `packet`  (
  `SerialNo` int(11) UNSIGNED NOT NULL AUTO_INCREMENT,
  `Receiver` varchar(16) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `Sender` varchar(16) CHARACTER SET latin1 COLLATE latin1_general_ci NOT NULL,
  `Code` smallint(5) UNSIGNED NOT NULL DEFAULT 0,
  `Body` tinyblob NOT NULL,
  `Time` datetime NOT NULL DEFAULT '0000-00-00 00:00:00',
  PRIMARY KEY (`SerialNo`) USING BTREE,
  INDEX `Receiver`(`Receiver`) USING BTREE
) ENGINE = federated CONNECTION = 'gbwc_linked/packet';


-- ----------------------------
-- Encantamento do WCS2 (XPEnchantDlg, 0x7115): nível de cada item do baú e chances por nível alvo, em %.
-- Não existem no servidor original. Fail = 100 - Success - Down1 - Down2 - Down3 - Destroy.
-- JewelBonus: % de sucesso a mais por joia além da 1ª (tirado das outras saídas na mesma proporção).
-- ----------------------------
CREATE TABLE `ChestEnchant`  (
  `No` int(11) NOT NULL,
  `Level` smallint(5) NOT NULL DEFAULT 0,
  `Seal` int(11) NOT NULL DEFAULT 0,
  PRIMARY KEY (`No`) USING BTREE
) ENGINE = InnoDB;

CREATE TABLE `EnchantLevel`  (
  `Level` smallint(5) NOT NULL,
  `Success` smallint(5) NOT NULL DEFAULT 0,
  `Down1` smallint(5) NOT NULL DEFAULT 0,
  `Down2` smallint(5) NOT NULL DEFAULT 0,
  `Down3` smallint(5) NOT NULL DEFAULT 0,
  `Destroy` smallint(5) NOT NULL DEFAULT 0,
  `JewelBonus` smallint(5) NOT NULL DEFAULT 0,
  PRIMARY KEY (`Level`) USING BTREE
) ENGINE = InnoDB;

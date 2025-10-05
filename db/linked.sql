INSTALL PLUGIN FEDERATED SONAME 'ha_federated';

CREATE SERVER gbwc_linked FOREIGN DATA WRAPPER mysql OPTIONS (HOST '127.0.0.1', PORT 33306, DATABASE 'gbwc', USER 'root', PASSWORD '');

-- ----------------------------
-- Table structure for abnormalupdate
-- ----------------------------
DROP TABLE IF EXISTS `AbnormalUpdate`;
CREATE TABLE `AbnormalUpdate`  (
  `Master` char(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `ID` char(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `ScoreDelta` smallint(6) NOT NULL DEFAULT 0,
  `MoneyDelta` int(11) NOT NULL DEFAULT 0,
  `Time` datetime NOT NULL DEFAULT '0000-00-00 00:00:00'
) ENGINE = federated CONNECTION = 'gbwc_linked/AbnormalUpdate';

-- ----------------------------
-- Table structure for abnormalupdatelog
-- ----------------------------
DROP TABLE IF EXISTS `AbnormalUpdateLog`;
CREATE TABLE `AbnormalUpdateLog`  (
  `DeadTime` datetime NOT NULL DEFAULT '0000-00-00 00:00:00',
  `MoneyDelta` int(11) NOT NULL DEFAULT 0,
  `ScoreDelta` smallint(6) NOT NULL DEFAULT 0,
  `DeadCause` int(10) NOT NULL DEFAULT 0,
  `TeamID` tinyint(4) NOT NULL DEFAULT 0,
  `ID` varchar(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `WinTeamOrPlayer` tinyint(1) NOT NULL DEFAULT 0,
  `GameOption` int(10) NOT NULL DEFAULT 0,
  `EndTime` datetime NOT NULL DEFAULT '0000-00-00 00:00:00',
  `StartTime` datetime NOT NULL DEFAULT '0000-00-00 00:00:00',
  `GameRoomTitle` varchar(64) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `GameRoomID` smallint(5) NOT NULL DEFAULT 0,
  `ServerIP` int(10) NOT NULL DEFAULT 0
) ENGINE = federated CONNECTION = 'gbwc_linked/AbnormalUpdateLog';

-- ----------------------------
-- Table structure for accuse
-- ----------------------------
DROP TABLE IF EXISTS `Accuse`;
CREATE TABLE `Accuse`  (
  `Accuse` varchar(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT NULL,
  `ServerIp` varchar(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT NULL,
  `ServerPort` varchar(5) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT NULL,
  `Accused` varchar(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT NULL,
  `Time` time NULL DEFAULT NULL,
  `Complaint` text CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL
) ENGINE = federated CONNECTION = 'gbwc_linked/Accuse';

-- ----------------------------
-- Table structure for avatar_table
-- ----------------------------
DROP TABLE IF EXISTS `avatar_table`;
CREATE TABLE `avatar_table`  (
  `Prop_Number` bigint(20) NOT NULL DEFAULT 0,
  `Prop_Name` varchar(30) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `Prop_Count` int(11) NOT NULL DEFAULT 0,
  `Prop_Price` int(11) NOT NULL DEFAULT 0,
  `Prop_Type` varchar(10) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `Prop_Sex` varchar(10) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `Prop_Delay` int(11) NOT NULL DEFAULT 0,
  `Prop_Angle` int(11) NOT NULL DEFAULT 0,
  `Prop_Defence` int(11) NOT NULL DEFAULT 0,
  `Prop_Power` int(11) NOT NULL DEFAULT 0,
  `Prop_Energi` int(11) NOT NULL DEFAULT 0,
  `Prop_MoveMent` int(11) NOT NULL DEFAULT 0,
  `Prop_MountAngle` int(11) NOT NULL DEFAULT 0,
  `Prop_favor` int(11) NOT NULL DEFAULT 0,
  `Prop_Image_Name` varchar(50) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `Prop_Image_Size` int(12) NOT NULL DEFAULT 0,
  `Prop_Note` varchar(100) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT NULL,
  `Prop_image` blob NOT NULL,
  `Prop_Gift` varchar(10) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `Provide_Date` datetime NOT NULL DEFAULT '0000-00-00 00:00:00',
  `Wear_String1` varchar(100) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT NULL,
  `Wear_String2` varchar(100) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT NULL,
  `Wear_String3` varchar(100) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT NULL,
  `Wear_String4` varchar(100) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT NULL,
  `Wear_String5` varchar(100) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT NULL,
  `Wear_String6` varchar(100) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT NULL,
  `Wear_String7` varchar(100) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT NULL,
  `Wear_String8` varchar(100) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT NULL,
  `Wear_String9` varchar(100) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT NULL,
  `Wear_String10` varchar(100) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT NULL,
  PRIMARY KEY (`Prop_Number`) USING BTREE
) ENGINE = federated CONNECTION = 'gbwc_linked/avatar_table';

-- ----------------------------
-- Table structure for ban
-- ----------------------------
DROP TABLE IF EXISTS `Ban`;
CREATE TABLE `Ban`  (
  `ID` char(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `Nickname` char(20) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT ''
) ENGINE = federated CONNECTION = 'gbwc_linked/Ban';

-- ----------------------------
-- Table structure for banlog
-- ----------------------------
DROP TABLE IF EXISTS `BanLog`;
CREATE TABLE `BanLog`  (
  `Id` varchar(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `StartTime` datetime NOT NULL DEFAULT '0000-00-00 00:00:00',
  `Duration` smallint(6) NOT NULL DEFAULT 0,
  `Reason` varchar(255) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `Judge` varchar(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  INDEX `Id`(`Id`) USING BTREE
) ENGINE = federated CONNECTION = 'gbwc_linked/BanLog';

-- ----------------------------
-- Table structure for banreason
-- ----------------------------
DROP TABLE IF EXISTS `BanReason`;
CREATE TABLE `BanReason`  (
  `ID` varchar(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `MuteLog` text CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL
) ENGINE = federated CONNECTION = 'gbwc_linked/BanReason';

-- ----------------------------
-- Table structure for buddylist
-- ----------------------------
DROP TABLE IF EXISTS `BuddyList`;
CREATE TABLE `BuddyList`  (
  `Id` char(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `Category` char(20) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `Buddy` char(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  INDEX `Id`(`Id`, `Buddy`) USING BTREE
) ENGINE = federated CONNECTION = 'gbwc_linked/BuddyList';

-- ----------------------------
-- Table structure for buyinfo
-- ----------------------------
DROP TABLE IF EXISTS `BuyInfo`;
CREATE TABLE `BuyInfo`  (
  `SerialNo` int(11) NULL DEFAULT NULL,
  `MenuNo` int(11) NULL DEFAULT NULL,
  `Price` int(11) NULL DEFAULT NULL,
  `Asset` int(20) NULL DEFAULT NULL,
  `BuyType` varchar(255) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT NULL,
  `Time` datetime NULL DEFAULT '0000-00-00 00:00:00'
) ENGINE = federated CONNECTION = 'gbwc_linked/BuyInfo';

-- ----------------------------
-- Table structure for cash
-- ----------------------------
DROP TABLE IF EXISTS `Cash`;
CREATE TABLE `Cash`  (
  `ID` char(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL,
  `Cash` int(100) NOT NULL DEFAULT 0,
  `OldCash` int(100) NOT NULL DEFAULT 0,
  PRIMARY KEY (`ID`) USING BTREE
) ENGINE = federated CONNECTION = 'gbwc_linked/Cash';

-- ----------------------------
-- Table structure for chest
-- ----------------------------
DROP TABLE IF EXISTS `Chest`;
CREATE TABLE `Chest`  (
  `No` int(10) NOT NULL AUTO_INCREMENT,
  `Item` int(11) NULL DEFAULT NULL,
  `Wearing` varchar(10) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT '0',
  `Acquisition` varchar(10) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT '0',
  `Expire` datetime NULL DEFAULT NULL,
  `Volume` int(10) NULL DEFAULT NULL,
  `PlaceOrder` varchar(50) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT '0',
  `Recovered` varchar(50) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT '0',
  `Owner` varchar(50) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT '',
  `ExpireType` varchar(255) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT NULL,
  PRIMARY KEY (`No`) USING BTREE
) ENGINE = federated CONNECTION = 'gbwc_linked/Chest';

-- ----------------------------
-- Table structure for collection
-- ----------------------------
DROP TABLE IF EXISTS `Collection`;
CREATE TABLE `Collection`  (
  `User` varchar(50) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT ''
) ENGINE = federated CONNECTION = 'gbwc_linked/Collection';

-- ----------------------------
-- Table structure for currentuser
-- ----------------------------
DROP TABLE IF EXISTS `CurrentUser`;
CREATE TABLE `CurrentUser`  (
  `Id` varchar(10) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL,
  `Context` int(10) UNSIGNED NOT NULL,
  `ServerIp` int(10) UNSIGNED NOT NULL,
  `ServerPort` smallint(5) UNSIGNED NOT NULL,
  `LoggingTime` datetime NOT NULL
) ENGINE = federated CONNECTION = 'gbwc_linked/CurrentUser';

-- ----------------------------
-- Table structure for eventlog
-- ----------------------------
DROP TABLE IF EXISTS `EventLog`;
CREATE TABLE `EventLog`  (
  `Id` char(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `Code` smallint(5) UNSIGNED NOT NULL DEFAULT 0,
  `AcquiredScore` smallint(6) NOT NULL DEFAULT 0,
  `Time` datetime NOT NULL DEFAULT '0000-00-00 00:00:00',
  `ServerIp` int(10) UNSIGNED NOT NULL DEFAULT 0,
  `ServerPort` smallint(5) UNSIGNED NOT NULL DEFAULT 0,
  INDEX `Id`(`Id`, `Code`) USING BTREE
) ENGINE = federated CONNECTION = 'gbwc_linked/EventLog';

-- ----------------------------
-- Table structure for game
-- ----------------------------
DROP TABLE IF EXISTS `Game`;
CREATE TABLE `Game`  (
  `Id` varchar(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `Guild` varchar(8) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `MemberCount` smallint(6) NOT NULL DEFAULT 0,
  `Money` int(10) UNSIGNED NOT NULL DEFAULT 0,
  `EventScore0` int(11) NOT NULL DEFAULT 0,
  `EventScore1` int(11) NOT NULL DEFAULT 0,
  `EventScore2` int(11) NOT NULL DEFAULT 0,
  `EventScore3` int(11) NOT NULL DEFAULT 0,
  `AvatarWear` bigint(20) NOT NULL DEFAULT 0,
  `Prop1` varchar(201) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `Prop2` varchar(201) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `AdminGift` smallint(6) NOT NULL DEFAULT 0,
  `TotalScore` int(11) NOT NULL DEFAULT 1000,
  `SeasonScore` int(11) NOT NULL DEFAULT 1000,
  `TotalGrade` smallint(6) NOT NULL DEFAULT 19,
  `SeasonGrade` smallint(6) NOT NULL DEFAULT 19,
  `TotalRank` int(11) NOT NULL DEFAULT 0,
  `SeasonRank` int(11) NOT NULL DEFAULT 0,
  `GuildRank` int(11) NOT NULL DEFAULT 0,
  `AccumShot` int(10) UNSIGNED NOT NULL DEFAULT 0,
  `AccumDamage` int(10) UNSIGNED NOT NULL DEFAULT 0,
  `StageRecords` varchar(161) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `MobileRecords` varchar(161) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `LastUpdateTime` datetime NULL DEFAULT '0000-00-00 00:00:00',
  `NoRankUpdate` tinyint(1) NOT NULL DEFAULT 0,
  `ClientData` varchar(60) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `Country` int(11) NULL DEFAULT 28,
  `CountryGrade` int(11) NOT NULL DEFAULT 19,
  `CountryRank` int(11) NOT NULL DEFAULT 0,
  `GiftProhibitTime` datetime NULL DEFAULT '0000-00-00 00:00:00',
  `NickName` varchar(15) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  PRIMARY KEY (`Id`) USING BTREE,
  INDEX `Guild`(`Guild`) USING BTREE
) ENGINE = federated CONNECTION = 'gbwc_linked/Game';

-- ----------------------------
-- Table structure for gbcomments
-- ----------------------------
DROP TABLE IF EXISTS `GBComments`;
CREATE TABLE `GBComments`  (
  `Id` int(11) NOT NULL AUTO_INCREMENT,
  `Msg_Id` int(11) NOT NULL DEFAULT 0,
  `IP` varchar(25) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `Author` varchar(15) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `Title` text CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL,
  `Comment` text CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL,
  `Date` datetime NOT NULL DEFAULT '0000-00-00 00:00:00',
  PRIMARY KEY (`Id`) USING BTREE
) ENGINE = federated CONNECTION = 'gbwc_linked/GBComments';

-- ----------------------------
-- Table structure for gift
-- ----------------------------
DROP TABLE IF EXISTS `Gift`;
CREATE TABLE `Gift`  (
  `SerialNo` int(11) NOT NULL AUTO_INCREMENT,
  `Receiver` char(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `Sender` char(12) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `Prop` int(10) UNSIGNED NOT NULL DEFAULT 0,
  `Msg` char(50) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `SentTime` datetime NOT NULL DEFAULT '0000-00-00 00:00:00',
  PRIMARY KEY (`SerialNo`) USING BTREE,
  INDEX `Receiver`(`Receiver`) USING BTREE
) ENGINE = federated CONNECTION = 'gbwc_linked/Gift';

-- ----------------------------
-- Table structure for giftitem
-- ----------------------------
DROP TABLE IF EXISTS `GiftItem`;
CREATE TABLE `GiftItem`  (
  `No` int(11) NOT NULL AUTO_INCREMENT,
  `Sender` varchar(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT NULL,
  `MenuId` int(11) NULL DEFAULT 0,
  `ReceiptGiftNo` varchar(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT NULL,
  `Acquisition` varchar(255) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT NULL,
  `Receiver` varchar(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT NULL,
  PRIMARY KEY (`No`) USING BTREE
) ENGINE = federated CONNECTION = 'gbwc_linked/GiftItem';

-- ----------------------------
-- Table structure for giftmsg
-- ----------------------------
DROP TABLE IF EXISTS `GiftMsg`;
CREATE TABLE `GiftMsg`  (
  `No` int(11) NOT NULL AUTO_INCREMENT,
  `MenuId` int(16) NULL DEFAULT NULL,
  `Sender` varchar(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT NULL,
  `SentTime` datetime NULL DEFAULT NULL,
  `Msg` varchar(255) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT NULL,
  `MsgType` varchar(255) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT NULL,
  `ExpireType` varchar(11) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT '0',
  `GiftItemNo` int(16) NULL DEFAULT NULL,
  `Receiver` varchar(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT NULL,
  `ItemId` int(16) NULL DEFAULT NULL,
  `Acquisition` varchar(255) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT NULL,
  PRIMARY KEY (`No`) USING BTREE
) ENGINE = federated CONNECTION = 'gbwc_linked/GiftMsg';

-- ----------------------------
-- Table structure for grandprix_group
-- ----------------------------
DROP TABLE IF EXISTS `GrandPrix_Group`;
CREATE TABLE `grandprix_group`  (
  `Category` varchar(50) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT NULL,
  `ScoreOnCalc` varchar(50) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT NULL,
  `Rank` varchar(50) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT NULL,
  `RankOld` varchar(50) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT NULL,
  `Win` varchar(50) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT NULL,
  `Lose` varchar(50) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT NULL
) ENGINE = federated CONNECTION = 'gbwc_linked/grandprix_group';

-- ----------------------------
-- Table structure for grandprix_personal
-- ----------------------------
DROP TABLE IF EXISTS `GrandPrix_Personal`;
CREATE TABLE `grandprix_personal`  (
  `Score` int(11) NULL DEFAULT NULL,
  `Rank` int(11) NULL DEFAULT NULL,
  `RankOld` int(11) NULL DEFAULT NULL,
  `Win` int(11) NULL DEFAULT NULL,
  `Lose` int(11) NULL DEFAULT NULL,
  `ScoreOnCalc` varchar(50) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT NULL,
  `User` varchar(50) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT NULL,
  `Category` varchar(50) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT NULL
) ENGINE = federated CONNECTION = 'gbwc_linked/grandprix_personal';

-- ----------------------------
-- Table structure for gunwcuser
-- ----------------------------
DROP TABLE IF EXISTS `GunWCUser`;
CREATE TABLE `GunWCUser`  (
  `Id` varchar(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `user` varchar(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `Gender` smallint(2) NOT NULL DEFAULT 0,
  `NickName` varchar(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `User_Level` varchar(10) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `Authority2` varchar(10) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `Password` varchar(10) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `Status` varchar(10) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `MuteTime` datetime NOT NULL DEFAULT '0000-00-00 00:00:00',
  `RestrictTime` datetime NOT NULL DEFAULT '0000-00-00 00:00:00',
  `Authority` varchar(10) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `E_Mail` varchar(50) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT NULL,
  `Country` char(3) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `AuthorityBackup` int(10) NULL DEFAULT NULL,
  PRIMARY KEY (`Id`) USING BTREE
) ENGINE = federated CONNECTION = 'gbwc_linked/GunWCUser';

-- ----------------------------
-- Table structure for IpBlock
-- ----------------------------
DROP TABLE IF EXISTS `IpBlock`;
CREATE TABLE `IpBlock`  (
  `Ip` varchar(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT NULL,
  `Allow` varchar(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT NULL,
  `Mask` varchar(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT NULL
) ENGINE = federated CONNECTION = 'gbwc_linked/IpBlock';

-- ----------------------------
-- Table structure for item
-- ----------------------------
DROP TABLE IF EXISTS `Item`;
CREATE TABLE `Item`  (
  `No` int(11) NOT NULL DEFAULT 0,
  `Refund_C` int(11) NOT NULL DEFAULT 0,
  `Refund_G` int(11) NOT NULL DEFAULT 0,
  `Refund_T` int(11) NOT NULL DEFAULT 0,
  PRIMARY KEY (`No`) USING BTREE
) ENGINE = federated CONNECTION = 'gbwc_linked/Item';

-- ----------------------------
-- Table structure for loginlog
-- ----------------------------
DROP TABLE IF EXISTS `LoginLog`;
CREATE TABLE `LoginLog`  (
  `ID` char(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `Ip` int(10) NOT NULL DEFAULT 0,
  `Ip_V` int(10) NOT NULL DEFAULT 0,
  `Port` smallint(5) NOT NULL DEFAULT 0,
  `Port_V` smallint(5) NOT NULL DEFAULT 0,
  `Time` datetime NOT NULL DEFAULT '0000-00-00 00:00:00',
  `ServerIP` int(10) NOT NULL DEFAULT 0,
  `ServerPort` smallint(5) NOT NULL DEFAULT 0
) ENGINE = federated CONNECTION = 'gbwc_linked/LoginLog';

-- ----------------------------
-- Table structure for menu
-- ----------------------------
DROP TABLE IF EXISTS `Menu`;
CREATE TABLE `Menu`  (
  `No` int(11) NOT NULL DEFAULT 0,
  `Item1` int(11) NOT NULL DEFAULT 0,
  `Period1` int(11) NOT NULL DEFAULT 86400,
  `Volume1` int(11) NOT NULL DEFAULT 1,
  `Item2` int(11) NULL DEFAULT NULL,
  `Period2` int(11) NULL DEFAULT NULL,
  `Volume2` int(11) NULL DEFAULT NULL,
  `Item3` int(11) NULL DEFAULT NULL,
  `Period3` int(11) NULL DEFAULT NULL,
  `Volume3` int(11) NULL DEFAULT NULL,
  `Item4` int(11) UNSIGNED NULL DEFAULT NULL,
  `Period4` int(11) NULL DEFAULT NULL,
  `Volume4` int(11) NULL DEFAULT NULL,
  `Item5` int(11) NULL DEFAULT NULL,
  `Period5` int(11) NULL DEFAULT NULL,
  `Volume5` int(11) NULL DEFAULT NULL,
  `PriceByGoldForW` int(11) NOT NULL DEFAULT 10000,
  `PriceByGoldForM` int(11) NOT NULL DEFAULT 10000,
  `PriceByGoldForI` int(11) NOT NULL DEFAULT 10000,
  `PriceByGoldForT` int(11) NOT NULL DEFAULT 10000,
  `PriceByGoldForY` int(11) NOT NULL DEFAULT 10000,
  `PriceByCashForW` int(11) NOT NULL DEFAULT 10000,
  `PriceByCashForM` int(11) NOT NULL DEFAULT 10000,
  `PriceByCashForI` int(11) NOT NULL DEFAULT 10000,
  `PriceByCashForT` int(11) NOT NULL DEFAULT 10000,
  `PriceByCashForY` int(11) NOT NULL DEFAULT 10000,
  PRIMARY KEY (`No`) USING BTREE
) ENGINE = federated CONNECTION = 'gbwc_linked/Menu';

-- ----------------------------
-- Table structure for mobilerecord
-- ----------------------------
DROP TABLE IF EXISTS `MobileRecord`;
CREATE TABLE `MobileRecord`  (
  `Win` text CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL,
  `Lose` text CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL,
  `Id` varchar(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `Mobile` varchar(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT ''
) ENGINE = federated CONNECTION = 'gbwc_linked/MobileRecord';

-- ----------------------------
-- Table structure for msg
-- ----------------------------
DROP TABLE IF EXISTS `Msg`;
CREATE TABLE `Msg`  (
  `ID` varchar(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `SerialNo` int(11) NULL DEFAULT NULL,
  `MsgBoxText` varchar(50) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT '0',
  `MsgBoxType` tinytext CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL,
  `LinkUrl` tinytext CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL
) ENGINE = federated CONNECTION = 'gbwc_linked/Msg';

-- ----------------------------
-- Table structure for msgqueue
-- ----------------------------
DROP TABLE IF EXISTS `MsgQueue`;
CREATE TABLE `MsgQueue`  (
  `SerialNo` tinytext CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL
) ENGINE = federated CONNECTION = 'gbwc_linked/MsgQueue';

-- ----------------------------
-- Table structure for mutelog
-- ----------------------------
DROP TABLE IF EXISTS `MuteLog`;
CREATE TABLE `MuteLog`  (
  `Id` varchar(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `StartTime` datetime NOT NULL DEFAULT '0000-00-00 00:00:00',
  `Duration` smallint(6) NOT NULL DEFAULT 0,
  `Reason` varchar(255) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `Judge` varchar(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  INDEX `Id`(`Id`) USING BTREE
) ENGINE = federated CONNECTION = 'gbwc_linked/MuteLog';

-- ----------------------------
-- Table structure for packet
-- ----------------------------
DROP TABLE IF EXISTS `Packet`;
CREATE TABLE `Packet`  (
  `SerialNo` int(11) NOT NULL DEFAULT 0,
  `Receiver` varchar(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `Sender` varchar(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `Code` smallint(5) UNSIGNED NOT NULL DEFAULT 0,
  `Body` tinyblob NOT NULL,
  `Time` datetime NOT NULL DEFAULT '0000-00-00 00:00:00',
  INDEX `Receiver`(`Receiver`) USING BTREE
) ENGINE = federated CONNECTION = 'gbwc_linked/Packet';

-- ----------------------------
-- Table structure for playlog
-- ----------------------------
DROP TABLE IF EXISTS `PlayLog`;
CREATE TABLE `PlayLog`  (
  `ServerIP` int(10) UNSIGNED NOT NULL DEFAULT 0,
  `GameRoomID` smallint(5) UNSIGNED NOT NULL DEFAULT 0,
  `GameRoomTitle` varchar(64) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `StartTime` datetime NULL DEFAULT '0000-00-00 00:00:00',
  `EndTime` datetime NULL DEFAULT '0000-00-00 00:00:00',
  `GameOption` int(10) UNSIGNED NOT NULL DEFAULT 0,
  `WinTeamOrPlayer` tinyint(1) NOT NULL DEFAULT 0,
  `S0_ID` varchar(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `S0_TeamID` tinyint(4) NOT NULL DEFAULT 0,
  `S0_DeadTime` datetime NULL DEFAULT '0000-00-00 00:00:00',
  `S0_DeadCause` int(10) UNSIGNED NOT NULL DEFAULT 0,
  `S0_ScoreDelta` smallint(6) NOT NULL DEFAULT 0,
  `S0_MoneyDelta` int(11) NOT NULL DEFAULT 0,
  `S1_ID` varchar(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `S1_TeamID` tinyint(4) NOT NULL DEFAULT 0,
  `S1_DeadTime` datetime NULL DEFAULT '0000-00-00 00:00:00',
  `S1_DeadCause` int(10) UNSIGNED NOT NULL DEFAULT 0,
  `S1_ScoreDelta` smallint(6) NOT NULL DEFAULT 0,
  `S1_MoneyDelta` int(11) NOT NULL DEFAULT 0,
  `S2_ID` varchar(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `S2_TeamID` tinyint(4) NOT NULL DEFAULT 0,
  `S2_DeadTime` datetime NULL DEFAULT '0000-00-00 00:00:00',
  `S2_DeadCause` int(10) UNSIGNED NOT NULL DEFAULT 0,
  `S2_ScoreDelta` smallint(6) NOT NULL DEFAULT 0,
  `S2_MoneyDelta` int(11) NOT NULL DEFAULT 0,
  `S3_ID` varchar(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `S3_TeamID` tinyint(4) NOT NULL DEFAULT 0,
  `S3_DeadTime` datetime NULL DEFAULT '0000-00-00 00:00:00',
  `S3_DeadCause` int(10) UNSIGNED NOT NULL DEFAULT 0,
  `S3_ScoreDelta` smallint(6) NOT NULL DEFAULT 0,
  `S3_MoneyDelta` int(11) NOT NULL DEFAULT 0,
  `S4_ID` varchar(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `S4_TeamID` tinyint(4) NOT NULL DEFAULT 0,
  `S4_DeadTime` datetime NULL DEFAULT '0000-00-00 00:00:00',
  `S4_DeadCause` int(10) UNSIGNED NOT NULL DEFAULT 0,
  `S4_ScoreDelta` smallint(6) NOT NULL DEFAULT 0,
  `S4_MoneyDelta` int(11) NOT NULL DEFAULT 0,
  `S5_ID` varchar(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `S5_TeamID` tinyint(4) NOT NULL DEFAULT 0,
  `S5_DeadTime` datetime NULL DEFAULT '0000-00-00 00:00:00',
  `S5_DeadCause` int(10) UNSIGNED NOT NULL DEFAULT 0,
  `S5_ScoreDelta` smallint(6) NOT NULL DEFAULT 0,
  `S5_MoneyDelta` int(11) NOT NULL DEFAULT 0,
  `S6_ID` varchar(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `S6_TeamID` tinyint(4) NOT NULL DEFAULT 0,
  `S6_DeadTime` datetime NULL DEFAULT '0000-00-00 00:00:00',
  `S6_DeadCause` int(10) UNSIGNED NOT NULL DEFAULT 0,
  `S6_ScoreDelta` smallint(6) NOT NULL DEFAULT 0,
  `S6_MoneyDelta` int(11) NOT NULL DEFAULT 0,
  `S7_ID` varchar(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
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
-- Table structure for receiptbuy
-- ----------------------------
DROP TABLE IF EXISTS `ReceiptBuy`;
CREATE TABLE `ReceiptBuy`  (
  `No` int(11) NOT NULL AUTO_INCREMENT,
  `Id` varchar(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT NULL,
  `MenuId` int(11) NULL DEFAULT NULL,
  `CashChecked` int(11) NULL DEFAULT NULL,
  `GoldChecked` int(11) NULL DEFAULT NULL,
  `Time` datetime NULL DEFAULT NULL,
  `BuyType` varchar(11) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT '',
  `ExpireType` varchar(11) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT NULL,
  `ReceiptGiftNo` int(11) NULL DEFAULT NULL,
  PRIMARY KEY (`No`) USING BTREE,
  INDEX `Id`(`Id`) USING BTREE
) ENGINE = federated CONNECTION = 'gbwc_linked/ReceiptBuy';

-- ----------------------------
-- Table structure for receiptconsume
-- ----------------------------
DROP TABLE IF EXISTS `ReceiptConsume`;
CREATE TABLE `ReceiptConsume`  (
  `Id` varchar(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT NULL,
  `Item` int(16) NULL DEFAULT 0,
  `Volume` int(11) NULL DEFAULT 0,
  `Recovered` varchar(255) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT NULL,
  `Refund` varchar(255) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT NULL,
  `Time` datetime NULL DEFAULT NULL,
  `ExpireType` varchar(11) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT '0',
  `Expire` varchar(11) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT '0'
) ENGINE = federated CONNECTION = 'gbwc_linked/ReceiptConsume';

-- ----------------------------
-- Table structure for receiptgift
-- ----------------------------
DROP TABLE IF EXISTS `ReceiptGift`;
CREATE TABLE `ReceiptGift`  (
  `Id` varchar(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT NULL,
  `MenuId` int(10) UNSIGNED NULL DEFAULT 0,
  `Volume` int(11) NULL DEFAULT NULL,
  `Receiver` varchar(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT NULL,
  `ReceiverNick` varchar(255) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT NULL,
  `Time` datetime NULL DEFAULT NULL,
  `Result` varchar(255) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT NULL,
  `Expiretype` varchar(255) CHARACTER SET latin1 COLLATE latin1_swedish_ci NULL DEFAULT NULL,
  INDEX `Id`(`Id`) USING BTREE,
  INDEX `Receiver`(`Receiver`) USING BTREE
) ENGINE = federated CONNECTION = 'gbwc_linked/ReceiptGift';

-- ----------------------------
-- Table structure for records
-- ----------------------------
DROP TABLE IF EXISTS `Records`;
CREATE TABLE `Records`  (
  `c_num` text CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL,
  `Mask_Decimal` decimal(10, 0) NOT NULL DEFAULT 0
) ENGINE = federated CONNECTION = 'gbwc_linked/Records';

-- ----------------------------
-- Table structure for servicestatus
-- ----------------------------
DROP TABLE IF EXISTS `ServiceStatus`;
CREATE TABLE `ServiceStatus`  (
  `SerialNo` tinytext CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL,
  `ServerIp` int(15) NOT NULL,
  `ServerPort` smallint(5) NOT NULL,
  `Status` enum('S','T') CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL,
  `Time` datetime NOT NULL
) ENGINE = federated CONNECTION = 'gbwc_linked/ServiceStatus';

-- ----------------------------
-- Table structure for stagerecord
-- ----------------------------
DROP TABLE IF EXISTS `StageRecord`;
CREATE TABLE `StageRecord`  (
  `Win` int(11) NOT NULL DEFAULT 0,
  `Lose` int(11) NOT NULL DEFAULT 0,
  `Id` varchar(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `Stage` int(11) NOT NULL DEFAULT 0
) ENGINE = federated CONNECTION = 'gbwc_linked/StageRecord';

-- ----------------------------
-- Table structure for user
-- ----------------------------
DROP TABLE IF EXISTS `User`;
CREATE TABLE `User`  (
  `Id` varchar(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `User` varchar(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `NickName` varchar(12) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `Password` varchar(20) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `Gender` tinyint(1) NOT NULL DEFAULT 0,
  `Status` varchar(10) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `MuteTime` datetime NULL DEFAULT NULL,
  `RestrictTime` datetime NULL DEFAULT NULL,
  `Authority` tinyint NOT NULL DEFAULT 0,
  `Authority2` tinyint NOT NULL DEFAULT 0,
  `E_Mail` varchar(50) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `Country` char(3) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `User_Level` int(3) NOT NULL DEFAULT 0,
  PRIMARY KEY (`Id`) USING BTREE
) ENGINE = federated CONNECTION = 'gbwc_linked/User';

-- ----------------------------
-- Table structure for usercount
-- ----------------------------
DROP TABLE IF EXISTS `UserCount`;
CREATE TABLE `UserCount`  (
  `SerialNo` int(10) UNSIGNED NOT NULL,
  `ServerIp` int(10) UNSIGNED NOT NULL,
  `ServerPort` smallint(5) UNSIGNED NOT NULL,
  `UserCount` int(11) UNSIGNED NOT NULL,
  `Time` datetime NOT NULL,
  PRIMARY KEY (`SerialNo`) USING BTREE
) ENGINE = federated CONNECTION = 'gbwc_linked/UserCount';

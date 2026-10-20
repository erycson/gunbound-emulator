-- Seed do WCS2 (S2: v548/v584), aplicado pelo init_db.py depois do TH e do WCS1.

-- ----------------------------
-- Encantamento do WCS2 (XPEnchantDlg, 0x7115): nível de cada item do baú e chances por nível alvo, em %.
-- Success: ItemEnchantLv1_4..Lv21_30 do Config.json do servidor S3 (60/50/40/30/20/10/5), lido como nível alvo.
-- shortcut: Down1..3 e Destroy são inventados por faixa (o S3 não traz); ajustar aqui.
-- Não existem no servidor original. Fail = 100 - Success - Down1 - Down2 - Down3 - Destroy.
-- JewelBonus: % de sucesso a mais com a Spirit Jewel (tirado da falha). Papéis das joias: wcs2/enchant.py.
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

INSERT INTO `EnchantLevel` VALUES (1, 60, 0, 0, 0, 0, 10);
INSERT INTO `EnchantLevel` VALUES (2, 60, 0, 0, 0, 0, 10);
INSERT INTO `EnchantLevel` VALUES (3, 60, 0, 0, 0, 0, 10);
INSERT INTO `EnchantLevel` VALUES (4, 60, 0, 0, 0, 0, 10);
INSERT INTO `EnchantLevel` VALUES (5, 50, 10, 0, 0, 0, 10);
INSERT INTO `EnchantLevel` VALUES (6, 50, 10, 0, 0, 0, 10);
INSERT INTO `EnchantLevel` VALUES (7, 50, 10, 0, 0, 0, 10);
INSERT INTO `EnchantLevel` VALUES (8, 50, 10, 0, 0, 0, 10);
INSERT INTO `EnchantLevel` VALUES (9, 40, 15, 5, 0, 0, 10);
INSERT INTO `EnchantLevel` VALUES (10, 40, 15, 5, 0, 0, 10);
INSERT INTO `EnchantLevel` VALUES (11, 40, 15, 5, 0, 0, 10);
INSERT INTO `EnchantLevel` VALUES (12, 40, 15, 5, 0, 0, 10);
INSERT INTO `EnchantLevel` VALUES (13, 30, 15, 10, 0, 5, 10);
INSERT INTO `EnchantLevel` VALUES (14, 30, 15, 10, 0, 5, 10);
INSERT INTO `EnchantLevel` VALUES (15, 30, 15, 10, 0, 5, 10);
INSERT INTO `EnchantLevel` VALUES (16, 30, 15, 10, 0, 5, 10);
INSERT INTO `EnchantLevel` VALUES (17, 20, 15, 10, 5, 10, 10);
INSERT INTO `EnchantLevel` VALUES (18, 20, 15, 10, 5, 10, 10);
INSERT INTO `EnchantLevel` VALUES (19, 10, 20, 10, 5, 15, 10);
INSERT INTO `EnchantLevel` VALUES (20, 10, 20, 10, 5, 15, 10);
INSERT INTO `EnchantLevel` VALUES (21, 5, 20, 15, 10, 20, 10);
INSERT INTO `EnchantLevel` VALUES (22, 5, 20, 15, 10, 20, 10);
INSERT INTO `EnchantLevel` VALUES (23, 5, 20, 15, 10, 20, 10);
INSERT INTO `EnchantLevel` VALUES (24, 5, 20, 15, 10, 20, 10);
INSERT INTO `EnchantLevel` VALUES (25, 5, 20, 15, 10, 20, 10);
INSERT INTO `EnchantLevel` VALUES (26, 5, 20, 15, 10, 20, 10);
INSERT INTO `EnchantLevel` VALUES (27, 5, 20, 15, 10, 20, 10);
INSERT INTO `EnchantLevel` VALUES (28, 5, 20, 15, 10, 20, 10);
INSERT INTO `EnchantLevel` VALUES (29, 5, 20, 15, 10, 20, 10);
INSERT INTO `EnchantLevel` VALUES (30, 5, 20, 15, 10, 20, 10);

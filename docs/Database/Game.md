
# Game

## Descrição
A tabela `Game` armazena as informações principais do jogador, incluindo dados de perfil, estatísticas, rankings e configurações de jogo.

## Estrutura da Tabela

```sql
CREATE TABLE `Game`  (
  `Id` varchar(16) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
  `Country` int(10) UNSIGNED NULL DEFAULT 28,
  `NickName` varchar(12) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
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
  `ClientData` varbinary(100) NOT NULL DEFAULT '' COMMENT 'Se vazio, mandar -2 no primeiro byte para o cliente',
  `StageRecords` varbinary(161) NOT NULL DEFAULT '',
  `MobileRecords` varbinary(161) NOT NULL DEFAULT '',
  `LastUpdateTime` datetime NULL DEFAULT '0000-00-00 00:00:00',
  `GiftProhibitTime` datetime NULL DEFAULT '0000-00-00 00:00:00',
  PRIMARY KEY (`Id`) USING BTREE,
  INDEX `Guild`(`Guild`) USING BTREE
) ENGINE = InnoDB CHARACTER SET = latin1 COLLATE = latin1_swedish_ci ROW_FORMAT = Compact;
```

## Campos da Tabela

### Identificação e Perfil

| Campo              | Tipo             | Nulo | Padrão | Descrição                                          |
|--------------------|------------------|------|--------|----------------------------------------------------|
| `Id`               | varchar(16)      |      |        | **Chave primária.** Identificador único do jogador |
| `Country`          | int(10) UNSIGNED |   X  |   28   | Código do país do jogador                          |
| `NickName`         | varchar(12)      |      |        | Nome de exibição do jogador                        |
| `Guild`            | varchar(8)       |      | NULL   | Nome da guild do jogador                           |
| `MemberCount`      | smallint(6)      |      | 0 | Contador de membros (possivelmente relacionado à guild) |
| `Money`            | int(10) UNSIGNED |      | 0 | Dinheiro/moedas do jogador no jogo |
| `EventScore0`      | int(11)          |      | 0 | Pontuação do evento 0 |
| `EventScore1`      | int(11)          |      | 0 | Pontuação do evento 1 |
| `EventScore2`      | int(11)          |      | 0 | Pontuação do evento 2 |
| `EventScore3`      | int(11)          |      | 0 | Pontuação do evento 3 |
| `AvatarWear`       | bigint(20)       |      | 0 | Configuração dos itens equipados no avatar |
| `Prop1`            | varchar(201)     |      | '' | Configurações de propriedades 1 |
| `Prop2`            | varchar(201)     |      | '' | Configurações de propriedades 2 |
| `AdminGift`        | smallint(6)      |      | 0 | Presentes administrativos recebidos |
| `TotalGrade`       | tinyint(4)       |      | 19 | Graduação total do jogador |
| `SeasonGrade`      | tinyint(4)       |      | 19 | Graduação da temporada atual |
| `CountryGrade`     | tinyint(4)       |      | 19 | Graduação no ranking do país |
| `TotalScore`       | int(10) UNSIGNED |      | 1000 | Pontuação total acumulada |
| `SeasonScore`      | int(10) UNSIGNED |      | 1000 | Pontuação da temporada atual |
| `TotalRank`        | int(10) UNSIGNED |      | 0 | Posição no ranking geral |
| `SeasonRank`       | int(10) UNSIGNED |      | 0 | Posição no ranking da temporada |
| `CountryRank`      | int(10) UNSIGNED |      | 0 | Posição no ranking do país |
| `GuildRank`        | int(10) UNSIGNED |      | 0 | Posição no ranking da guild |
| `AccumShot`        | int(10) UNSIGNED |      | 0 | Total de tiros acumulados |
| `AccumDamage`      | int(10) UNSIGNED |      | 0 | Total de dano acumulado |
| `NoRankUpdate`     | tinyint(1)       |      | 0 | Flag para impedir atualizações de ranking (0=permitir, 1=bloquear) |
| `ClientData`       | varbinary(100)   |      | '' | **Dados binários do cliente.** Se vazio, enviar -2 no primeiro byte para o cliente |
| `StageRecords`     | varbinary(161)   |      | '' | Registros de desempenho em fases/mapas |
| `MobileRecords`    | varbinary(161)   |      | '' | Registros específicos para versão mobile |
| `LastUpdateTime`   | datetime         |   X  | '0000-00-00 00:00:00' | Timestamp da última atualização dos dados |
| `GiftProhibitTime` | datetime         |   X  | '0000-00-00 00:00:00' | Timestamp até quando presentes estão proibidos |

## Índices

- **PRIMARY KEY**: `Id` (BTREE) - Chave primária para identificação única
- **INDEX**: `Guild` (BTREE) - Índice para consultas por guild

## Configurações da Tabela

- **Engine**: InnoDB (suporte a transações e integridade referencial)
- **Character Set**: latin1
- **Collation**: latin1_swedish_ci
- **Row Format**: Compact

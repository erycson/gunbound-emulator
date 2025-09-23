https://forum.ragezone.com/threads/gunbound-buddy-packet-identifiers.1253155/
0x1000: SVC_LOGIN - Auth Token request
0x1001: SVC_LOGIN - Auth Token response
0x1010: SVC_LOGIN - Processes the player login (Sends player data and their friend list).
0x2000: SVC_SAVE_PACKET - Saves a message to send to a player who is currently offline.
0x2011: SVC_DELETE_PACKET - Deletes one of the saved messages.
0x2020: SVC_TUNNEL_PACKET - "Tunnel" packet. Used as a fallback for UDP packets (response 0x2021 sent to the recipient).
0x2030: UNKNOWN COMMAND - Response 0x2031
0x3000: SVC_ADD_BUDDY - Request to add a buddy (response 0x3001).
0x3002: SVC_REMOVE_BUDDY - Request to remove a buddy (response 0x3005).
0x3004: SVC_GROUP_BUDDY - Likely moves a buddy to a specific group in the buddy list (response 0x3003).
0x3006: SVC_RENAME_GROUP - Renames a buddy group (response 0x3007).
0x3010: SVC_USER_STATE - Updates or requests the user's status (online, playing, etc.).
0x3FFF: SVC_USER_SYNC - Synchronizes the friend's status (online, playing, etc.).
0x4000: SVC_SEARCH - Searches for a player (response 0x4001).

https://forum.ragezone.com/threads/gunbound-wc-packet-identifiers.1197270/
// 0x1010 -> SVC_LOGIN/ADMIN (Encrypted)
// 0x1016 -> SVC_REP_AUTHDWORD
// 0x1021 -> SVC_USER_NICK
// 0x1020 -> SVC_USER_ID
// 0x1090 -> UNKNOW (probably encrypted)
// 0x1100 -> SVC_GRANDPRIX_LIST (No crypt) < LISTA MUNDIAL
// 0x2020 -> SVC_CHANNEL_MONITOR
// 0x2010 -> SVC_CHANNEL_CHAT (Encrypted)
// 0x2000 -> SVC_CHANNEL_JOIN (No crypt)
// 0x2022 -> SVC_CHANNEL_MONITOR_STOP
// 0x2104 -> SVC_ROOM_DETAIL
// 0x2101 -> SVC_ROOM_SPECIFIC_LIST
// 0x2100 -> SVC_ROOM_SORTED_LIST
// 0x2110 -> SVC_ROOM_JOIN
// 0x2140 -> SVC_ROOM_GRANDPRIX_BEGIN
// 0x2130 -> SVC_QUICKSTART
// 0x2120 -> SVC_ROOM_CREATE
// 0x2141 -> SVC_ROOM_GRANDPRIX_CANCEL
// 0x3101 -> SVC_ROOM_CHANGE_OPTION // MasterOnly
// 0x3100 -> SVC_ROOM_CHANGE_STAGE // MasterOnly
// 0x3001 -> SVC_LEAVE_WAIT_GAMEROOM // Public
// 0x3102 -> SVC_ROOM_CHANGE_USEITEM // MasterOnly
// 0x3150 -> SVC_ROOM_KICK_USER (No crypt) // MasterOnly
// 0x3104 -> SVC_ROOM_CHANGE_TITLE (No crypt) // MasterOnly
// 0x3103 -> SVC_ROOM_CHANGE_MAXMEN (No crypt) // MasterOnly
// 0x3200 -> SVC_ROOM_SELECT_TANK (No crypt) // Public
// 0x3232 -> SVC_ROOM_RETURN_RESULT (No crypt) // MasterOnly
// 0x3230 -> SVC_ROOM_USER_READY (No crypt) // Public
// 0x3210 -> SVC_ROOM_SELECT_TEAM (No crypt) // Public
// 0x3430 -> SVC_START_GAME (Encrypted?)
// 0x4104 -> SVC_PLAY_RESSURECT
// 0x4100 -> SVC_PLAY_USER_DEAD
// 0x4000 -> SVC_PLAY_DROP_USER
// 0x4200 -> SVC_PLAY_END_JEWEL
// 0x5000 -> SVC_POLICE_ACCUSE
// 0x4500 -> SVC_TUNNEL
// 0x4412 -> SVC_PLAY_RESULT
// 0x5010 -> SVC_BCM
// 0x5100 -> SVC_COMMAND
// 0x5110 -> SVC_CMD_STATUS << Admin\GM Only
// 0x5112 -> SVC_CMD_MOTD << Admin\GM Only
// 0x5114 -> SVC_CMD_BCM << Useable by normal users [Used by Double Kill]
// 0x5116 -> SVC_CMD_SETVERSION << Admin\GM Only
// 0x5120 -> SVC_CMD_GRADELIMIT << Admin\GM Only
// 0x5122 -> SVC_CMD_GUILDLIMIT << Admin\GM Only
// 0x5124 -> SVC_FUNCTION_RESTRICT << Admin\GM Only
// 0x512A -> SVC_CMD_SET_PASSABLE_AUTHORITY << Admin\GM Only
// 0x5128 -> SVC_CMD_SET_EVENTACTPROB << Admin\GM Only
// 0x5126 -> SVC_CMD_SET_ALLOWEDGUILD << Admin\GM Only
// 0x512C -> SVC_CMD_SET_FACTOR << Admin\GM Only
// 0x6000 -> SVC_ITEM (No crypt) << Update Items
// 0x6004 -> SVC_ITEM_GIFT_MSG
// 0x6008 -> SVC_ITEM_GIFT_CONFIRM
// 0x600A -> SVC_ITEM_LOCATION
// 0x600E -> SVC_ITEM_WEAR << Change avatar set
// 0x6020 -> SVC_ITEM_BUY (Encrypted) << Buy an avatar
// 0x6024 -> SVC_ITEM_CONSUME
// 0x6030 -> SVC_ITEM_GIFT_BUY
// 0x6028 -> SVC_ITEM_GIFT
// 0x6100 -> SVC_CASH (No crypt) << Update Cash
// 0x6104 -> SVC_GOLD (No crypt) << Update Gold



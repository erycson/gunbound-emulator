# lib/broker/protocol/enums.py
"""Enums para pacotes do cliente e do broker."""
from enum import Enum

"""
Enums para pacotes enviados pelo cliente ao broker.
"""
class ClientPacket(Enum):
    # Solicita a lista de servidores de jogo, ordenada por algum critério.
    CLI_SORTED_SERVER_LIST = 0x1100

    # Solicita informações de servidores específicos.
    CLI_SPECIFIC_SERVER_LIST = 0x1101

    # Requisição de login principal de um jogador.
    CLI_LOGIN = 0x1310

    # Login em um servidor de jogo específico (ou de um administrador).
    CLI_GAME_LOGIN = 0x1311

    # Outra variação de login, provavelmente com privilégios de admin.
    CLI_ADMIN_LOGIN = 0x1320
    
    # Comando administrativo para alterar a versão do servidor em tempo real.
    CLI_CMD_SETVERSION = 0x2000

    # Solicita uma mensagem do sistema (provavelmente "Mensagem do Dia").
    CLI_GET_MSG = 0x3000

"""
Enums para pacotes enviados pelo broker ao cliente.
"""
class ServerPacket(Enum):
    SRV_LOGIN_FAIL = 0x1312 # usado em falha imediata de enfileirar login (DB)
    SRV_SETVERSION = 0x2001 # ack do set version (sucesso/erro)
    SRV_GET_MSG = 0x3001 # ack do get msg (sucesso/erro)

class ServerCode(Enum):
    # Login - SRV_LOGIN_FAIL
    SRV_OK = 0x00
    ERR_GENERIC = 0x04
    ERR_INVALID_SUBTYPE = 0x10
    ERR_WRONG_CREDENTIALS = 0x11    # credenciais inválidas (usuário/senha)
    ERR_OLD_VERSION = 0x19          # versão do cliente abaixo do mínimo
    ERR_IP_BANNED = 0x60            # IP banido

    # Outros
    SRV_ERR_INVALID_SIZE = 0x0007,      # tamanho/framing inválido (Packet_ValidateSize falhou)
    SRV_ERR_NOT_AUTHORIZED = 0x0013,    # provável "não autorizado" em SVC_GET_MSG
    SRV_ERR_VERSION_LOW = 0x0019,       # versão do cliente abaixo do mínimo
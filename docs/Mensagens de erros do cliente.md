# Mensagens de erro do cliente

| Quando | Message Code | Texto (resumo) | Causa / solução |
|---|---|---|---|
| Parado na lista de servidores por muito tempo | 201 (`10053`) | problema na conexão ou tempo de espera excedido | Winsock `WSAECONNABORTED`: a conexão caiu |
| Ao clicar num servidor | 201 (`10061`) | problema na conexão ou tempo de espera excedido | Winsock `WSAECONNREFUSED`: confira firewall e o `accept` do servidor |
| Ao clicar num servidor | 202 | o servidor está com problemas | |
| Ao clicar num servidor | 228 | o servidor selecionado é limitado por níveis | [provável] patente fora de `grade_min`/`grade_max` do servidor |

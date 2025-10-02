import datetime

# O valor hexadecimal do seu log
timestamp_hex = "68DDEF5A"

# 1. Converte para decimal
timestamp_decimal = int(timestamp_hex, 16)
print(f"Valor em decimal: {timestamp_decimal}")

# 2. Converte o timestamp para um objeto de data e hora
data_hora = datetime.datetime.fromtimestamp(timestamp_decimal)

# 3. Formata para uma string legível em português
data_hora_formatada = data_hora.strftime('%d de %B de %Y, %H:%M:%S')

print(f"Data e Hora correspondente: {data_hora_formatada}")
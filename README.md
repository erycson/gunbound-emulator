pip freeze > requirements.txt

python -m venv
pip install -r requirements.txt

## Requisitos
Python 3.11

## Instalando
Se um ambiente virtual do python não existir, execute:

```bash
python -m venv .
```

Depois, ative-o e instale as bibliotecas utilizadas pelo sistema

```
./Scripts/activate
pip install -r requirements.txt
```

# Rodando servidores oficiais em modo debug

Testado no Broker e no Serv. `"%~dp0"`, equivale a pasta onde o servidor está
```cmd
@echo off
GunBoundServ3.exe -debug "%~dp0"
pause
```
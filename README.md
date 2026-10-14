pip freeze > requirements.txt

python -m venv
pip install -r requirements.txt

## Requisitos
Python 3.11+ (testado no 3.13)

Banco de dados: SQLite, MySQL ou PostgreSQL. Configure `database.uri` no `config.yml`:

| Banco      | URI                                                       |
|------------|-----------------------------------------------------------|
| SQLite     | `sqlite+aiosqlite:///gbwc.db`                             |
| MySQL      | `mysql+asyncmy://gbuser:gbpass@127.0.0.1:3306/gbwc`       |
| PostgreSQL | `postgresql+asyncpg://gbuser:gbpass@127.0.0.1:5432/gbwc`  |

Crie as tabelas e importe os dados iniciais (itens, loja e contas de teste) com:

```
python init_db.py
```

Só cria tabelas que não existem e só importa dados em tabelas novas. Para validar a conexão com um banco:

```
python -m tests.smoke_db <uri>
```

## Instalando
Se um ambiente virtual do python não existir, execute:

```bash
python -m venv .venv
```

Depois, ative-o e instale as bibliotecas utilizadas pelo sistema

```
./.venv/Scripts/activate
pip install -r requirements.txt
```

# Rodando servidores oficiais em modo debug

Testado no Broker e no Serv. `"%~dp0"`, equivale a pasta onde o servidor está
```cmd
@echo off
GunBoundServ3.exe -debug "%~dp0"
pause
```
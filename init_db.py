"""
Cria o banco de dados em MySQL, PostgreSQL ou SQLite.

O schema vem de db/linked.sql (estrutura do servidor original) e os dados iniciais (itens, loja, contas de teste)
vêm de db/gbwc.sql. Só cria tabelas que não existem e só importa dados em tabelas vazias, então pode rodar de novo.
Em tabelas que já existem, acrescenta as colunas e os índices que faltam (serve de migração).

Uso:
    python init_db.py                 # usa database.uri do config.yml
    python init_db.py <uri>           # ex.: sqlite+aiosqlite:///gbwc.db
"""
import re
import sys
import asyncio
from datetime import datetime
import yaml
from sqlalchemy import (MetaData, Table, Column, BigInteger, Integer, String, Text, LargeBinary, DateTime, Time,
                        Float, Numeric, PrimaryKeyConstraint, Index, insert, inspect, text)
from sqlalchemy.ext.asyncio import create_async_engine

SCHEMA_FILE = 'db/linked.sql'
DATA_FILE = 'db/gbwc.sql'
SKIP_DATA = {'currentuser', 'servicestatus', 'usercount'}  # Dados de sessão/log, não devem ser importados

# Colunas que o código grava com outro tipo ou que faltam no schema original
TYPE_OVERRIDES = {
    ('receiptconsume', 'recovered'): BigInteger,
    ('receiptconsume', 'refund'): BigInteger,
    ('receiptconsume', 'expire'): BigInteger,
    ('giftitem', 'receiptgiftno'): BigInteger,
}
EXTRA_COLUMNS = {
    'ReceiptGift': [('No', Integer, True), ('ConfirmTime', DateTime, False)],  # (nome, tipo, é a chave primária)
}

# Índices além dos do schema original, para as consultas do emulador (tabela: [(colunas, único)])
EXTRA_INDEXES = {
    'User': [(('Nickname',), True), (('User',), False)],
    'Game': [(('NickName',), True)],
    'BuddyList': [(('Buddy',), False)],
    'GiftMsg': [(('Receiver',), False)],
    'GiftItem': [(('Receiver',), False)],
    'GrandPrix_Personal': [(('User',), True)],
    'LoginLog': [(('Id',), False)],
}
UNIQUE_INDEXES = {('BuddyList', ('Id', 'Buddy'))}  # INDEX do original que deve ser UNIQUE (amizade sem repetição)

COLUMN_RE = re.compile(r"^\s*`(\w+)`\s+(\w+)(?:\(([^)]*)\))?(.*?),?\s*$")
PK_RE = re.compile(r"PRIMARY KEY\s*\(([^)]*)\)")
INDEX_RE = re.compile(r"^\s*(UNIQUE\s+)?(?:INDEX|KEY)\s+`\w+`\s*\(([^)]*)\)", re.I)


def sql_type(name: str, args: str | None):
    name = name.lower()
    if name in ('int', 'bigint', 'smallint', 'tinyint', 'mediumint', 'bit'):
        return BigInteger
    if name in ('float', 'double'):
        return Float
    if name == 'decimal':
        return Numeric
    if name in ('varchar', 'char'):
        return String(int(args))
    if name == 'enum':
        return String(max(len(v) for v in re.findall(r"'([^']*)'", args)))
    if name in ('text', 'tinytext', 'mediumtext', 'longtext'):
        return Text
    if name in ('varbinary', 'binary', 'blob', 'tinyblob', 'mediumblob', 'longblob'):
        return LargeBinary
    if name in ('datetime', 'timestamp'):
        return DateTime
    if name == 'time':
        return Time
    raise ValueError(f"Tipo não suportado: {name}")


def parse_schema(sql: str, metadata: MetaData, lower: bool) -> None:
    """lower: cria nomes em minúsculo (PostgreSQL), para que as consultas sem aspas encontrem tabelas e colunas."""
    fix = str.lower if lower else str
    for name, body in re.findall(r"CREATE TABLE `(\w+)`\s*\((.*?)\n\)", sql, re.S):
        columns, pk, indexes = [], [], []
        for line in body.splitlines():
            if m := COLUMN_RE.match(line):
                col, typ, args, rest = m.groups()
                type_ = TYPE_OVERRIDES.get((name.lower(), col.lower())) or sql_type(typ, args)
                auto = 'AUTO_INCREMENT' in rest.upper()
                default = re.search(r"DEFAULT\s+('[^']*'|-?\d+)", rest, re.I)
                server_default = None
                if default and not auto and type_ not in (LargeBinary, DateTime, Time):
                    value = default.group(1).strip("'")
                    server_default = text(value) if value.lstrip('-').isdigit() else value
                # Inteiro autoincremento precisa ser INTEGER no SQLite
                columns.append(Column(fix(col), Integer if auto else type_, autoincrement=auto, server_default=server_default))
            elif m := PK_RE.search(line):
                pk = [fix(c) for c in re.findall(r"`(\w+)`", m.group(1))]
            elif m := INDEX_RE.match(line):
                cols = tuple(re.findall(r"`(\w+)`", m.group(2)))
                indexes.append((cols, bool(m.group(1)) or (name, cols) in UNIQUE_INDEXES))
        for col, type_, is_pk in EXTRA_COLUMNS.get(name, []):
            columns.append(Column(fix(col), type_, autoincrement=is_pk))
            pk += [fix(col)] if is_pk else []
        table = Table(fix(name), metadata, *columns, *([PrimaryKeyConstraint(*pk)] if pk else []))
        seen = {tuple(pk)}
        for cols, unique in indexes + EXTRA_INDEXES.get(name, []):
            cols = tuple(fix(c) for c in cols)
            if cols not in seen:  # pula o índice igual à chave primária (Game_Id_index)
                seen.add(cols)
                Index(fix(f"ix_{name}_{'_'.join(cols)}"), *(table.c[c] for c in cols), unique=unique)


def split_values(row: str) -> list:
    """Divide '(1, 'a\\'b', NULL)' em [1, "a'b", None], tratando escapes do MySQL."""
    values, i, n = [], 0, len(row)
    escapes = {'0': '\0', 'n': '\n', 'r': '\r', 't': '\t', 'Z': '\x1a'}
    while i < n:
        ch = row[i]
        if ch == "'":
            buf, i = [], i + 1
            while row[i] != "'" or row[i + 1:i + 2] == "'":
                if row[i] == '\\':
                    i += 1
                    buf.append(escapes.get(row[i], row[i]))
                elif row[i] == "'":
                    buf.append("'")
                    i += 1
                else:
                    buf.append(row[i])
                i += 1
            values.append(''.join(buf))
            i += 1
        elif ch in ', ':
            i += 1
        else:
            j = i
            while j < n and row[j] != ',':
                j += 1
            token = row[i:j].strip()
            values.append(None if token.upper() == 'NULL' else (float(token) if '.' in token else int(token)))
            i = j
    return values


def convert(value, column: Column):
    if value is None:
        return None
    if isinstance(column.type, DateTime):
        return None if str(value).startswith('0000') else datetime.fromisoformat(str(value))
    if isinstance(column.type, Time):
        return datetime.strptime(str(value), '%H:%M:%S').time()
    if isinstance(column.type, LargeBinary):
        return str(value).encode('latin-1', errors='replace')
    if isinstance(column.type, (BigInteger, Integer)):
        return int(value) if str(value).lstrip('-').isdigit() else 0
    if isinstance(column.type, (String, Text)):
        return str(value)
    return value


def parse_data(sql: str, metadata: MetaData) -> dict[str, list[dict]]:
    tables = {t.name.lower(): t for t in metadata.tables.values()}
    # As colunas dos INSERTs do dump são posicionais, na ordem do CREATE TABLE do próprio dump
    dump_columns = {name.lower(): re.findall(r"^\s*`(\w+)`", body, re.M)
                    for name, body in re.findall(r"CREATE TABLE `(\w+)`\s*\((.*?)\n\)", sql, re.S)}
    data: dict[str, list[dict]] = {}
    for name, row in re.findall(r"^INSERT INTO `(\w+)` VALUES \((.*)\);$", sql, re.M):
        name = name.lower()
        if name in SKIP_DATA or name not in tables:
            continue
        table = tables[name]
        cols = {c.name.lower(): c for c in table.columns}
        record = {}
        for col, value in zip(dump_columns[name], split_values(row)):
            if (column := cols.get(col.lower())) is not None:
                record[column.name] = convert(value, column)
        data.setdefault(table.name, []).append(record)
    return data


async def main(uri: str) -> None:
    metadata = MetaData()
    engine = create_async_engine(uri)
    with open(SCHEMA_FILE, encoding='utf-8') as f:
        parse_schema(f.read(), metadata, lower=engine.dialect.name == 'postgresql')
    with open(DATA_FILE, encoding='utf-8') as f:
        data = parse_data(f.read(), metadata)

    async with engine.begin() as conn:
        existing = {n.lower() for n in await conn.run_sync(lambda c: c.dialect.get_table_names(c))}
        new_tables = [t for t in metadata.sorted_tables if t.name.lower() not in existing]
        await conn.run_sync(lambda c: metadata.create_all(c, tables=new_tables))
        print(f"Tabelas criadas: {len(new_tables)} (já existiam: {len(metadata.tables) - len(new_tables)})")
        for table in metadata.sorted_tables:
            if table.name.lower() in existing:
                await upgrade(conn, table)

        for table in metadata.sorted_tables:
            rows = data.get(table.name)
            if not rows or table.name.lower() in existing:
                continue
            # Linhas com chave primária repetida no dump quebram em bancos estritos
            pk = [c.name for c in table.primary_key.columns]
            if pk:
                rows = list({tuple(r.get(k) for k in pk): r for r in rows}.values())
            await conn.execute(insert(table), rows)
            print(f"  {table.name}: {len(rows)} linhas importadas")

        if engine.dialect.name == 'postgresql':
            # Ajusta as sequences de autoincremento depois de importar dados com IDs explícitos
            for table in metadata.sorted_tables:
                for col in table.columns:
                    if col.autoincrement is True and data.get(table.name):
                        await conn.execute(text(
                            f"SELECT setval(pg_get_serial_sequence('\"{table.name}\"', '{col.name}'), "
                            f"(SELECT COALESCE(MAX(\"{col.name}\"), 0) + 1 FROM \"{table.name}\"), false)"))
    await engine.dispose()


async def upgrade(conn, table: Table) -> None:
    """Tabela já existente: acrescenta colunas e índices que faltam. Índice UNIQUE com dados repetidos só avisa."""
    have_cols = {c['name'].lower() for c in await conn.run_sync(lambda c: inspect(c).get_columns(table.name))}
    have_ix = {i['name'].lower() for i in await conn.run_sync(lambda c: inspect(c).get_indexes(table.name))}
    quote = conn.dialect.identifier_preparer.quote
    for col in table.columns:
        if col.name.lower() not in have_cols:
            default = f" DEFAULT {col.server_default.arg}" if col.server_default is not None else ''
            await conn.execute(text(f"ALTER TABLE {quote(table.name)} ADD COLUMN {quote(col.name)} "
                                    f"{col.type.compile(dialect=conn.dialect)}{default}"))
            print(f"  {table.name}: coluna {col.name} criada")
    for index in table.indexes:
        if index.name.lower() in have_ix:
            continue
        try:
            async with conn.begin_nested():
                await conn.run_sync(lambda c: index.create(c))
            print(f"  {table.name}: índice {index.name} criado")
        except Exception as e:  # dados repetidos num UNIQUE: o banco segue sem o índice
            print(f"  {table.name}: índice {index.name} NÃO criado ({type(e).__name__}); corrija as linhas repetidas e rode de novo")


if __name__ == '__main__':
    if len(sys.argv) > 1:
        uri = sys.argv[1]
    else:
        with open('config.yml', encoding='utf-8') as f:
            uri = yaml.safe_load(f)['database']['uri']
    asyncio.run(main(uri))

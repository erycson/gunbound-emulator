import re
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import Any, Dict, List, Optional
from sqlalchemy import MetaData, insert, text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

# Conexão da transação aberta na task atual (as consultas da mesma task passam a usá-la)
_transaction_conn: ContextVar[Optional[AsyncConnection]] = ContextVar('transaction_conn', default=None)


class Transaction:
    """Uso: `transaction = await db.transaction()` ... `await transaction.commit()` ou `await transaction.rollback()`."""

    def __init__(self, db: 'Database'):
        self.db = db
        self.conn: Optional[AsyncConnection] = None

    def __await__(self):
        return self._start().__await__()

    async def _start(self) -> 'Transaction':
        self.conn = await self.db.engine.connect()
        await self.conn.begin()
        self._token = _transaction_conn.set(self.conn)
        return self

    async def commit(self) -> None:
        await self._end(commit=True)

    async def rollback(self) -> None:
        await self._end(commit=False)

    async def _end(self, commit: bool) -> None:
        if self.conn is None:  # Já finalizada
            return
        conn, self.conn = self.conn, None
        try:
            await (conn.commit() if commit else conn.rollback())
        finally:
            _transaction_conn.reset(self._token)
            await conn.close()


class Database:
    """
    Camada fina sobre o SQLAlchemy async, compatível com MySQL (asyncmy), PostgreSQL (asyncpg) e SQLite (aiosqlite).

    - fetch_one/fetch_all retornam dicts com as chaves no mesmo "case" usado na consulta (PostgreSQL devolve tudo em minúsculo).
    - execute retorna a quantidade de linhas afetadas (rowcount).
    - insert retorna a chave primária gerada, em qualquer banco.
    """

    def __init__(self, url: str):
        self.engine = create_async_engine(url, pool_pre_ping=True)
        self.dialect = self.engine.dialect.name
        self.metadata = MetaData()

    async def connect(self) -> None:
        # Abre uma conexão apenas para falhar cedo se o banco estiver inacessível
        async with self.engine.connect():
            pass

    async def disconnect(self) -> None:
        await self.engine.dispose()

    def transaction(self) -> Transaction:
        return Transaction(self)

    @asynccontextmanager
    async def _conn(self, write: bool):
        if (conn := _transaction_conn.get()) is not None:
            yield conn
        elif write:
            async with self.engine.begin() as conn:
                yield conn
        else:
            async with self.engine.connect() as conn:
                yield conn

    def _sql(self, query: str):
        if self.dialect == 'postgresql':
            # "user" é palavra reservada no PostgreSQL (tabela User e coluna User)
            query = re.sub(r'(?<![\w:."])user(?![\w"])', '"user"', query, flags=re.IGNORECASE)
        return text(query)

    @staticmethod
    def _row(row, query: str) -> Dict[str, Any]:
        names = {}
        for word in re.findall(r'(?<![:\w])\w+', query):  # sem os parâmetros :x; vale a 1ª grafia (a do SELECT)
            names.setdefault(word.lower(), word)
        return {names.get(key.lower(), key): value for key, value in row.items()}

    async def fetch_one(self, query: str, values: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        async with self._conn(write=False) as conn:
            row = (await conn.execute(self._sql(query), values or {})).mappings().first()
        return self._row(row, query) if row else None

    async def fetch_all(self, query: str, values: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        async with self._conn(write=False) as conn:
            rows = (await conn.execute(self._sql(query), values or {})).mappings().all()
        return [self._row(row, query) for row in rows]

    async def execute(self, query: str, values: Optional[Dict[str, Any]] = None) -> int:
        async with self._conn(write=True) as conn:
            return (await conn.execute(self._sql(query), values or {})).rowcount

    async def insert(self, table: str, values: Dict[str, Any]) -> Optional[int]:
        """Insere uma linha e retorna a chave primária gerada (ou None se a tabela não tiver)."""
        tbl = await self._table(table)
        columns = {c.name.lower(): c.name for c in tbl.columns}
        async with self._conn(write=True) as conn:
            result = await conn.execute(insert(tbl).values({columns[k.lower()]: v for k, v in values.items()}))
        pk = result.inserted_primary_key
        return pk[0] if pk else None

    async def _table(self, name: str):
        name = name.lower()
        found = [t for key, t in self.metadata.tables.items() if key.lower() == name]
        if not found:
            # O nome real pode ter outro "case" (ex.: MySQL no Linux com tabelas CamelCase)
            async with self.engine.connect() as conn:
                await conn.run_sync(lambda c: self.metadata.reflect(c, only=lambda n, _: n.lower() == name))
            found = [t for key, t in self.metadata.tables.items() if key.lower() == name]
        if not found:
            raise LookupError(f"Tabela não encontrada: {name}")
        return found[0]

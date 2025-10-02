from functools import wraps

def synchronized(lock_attr: str = 'lock'):
    """
    Decorator que automaticamente adquire e libera um lock ao redor da função.
    O lock deve ser um atributo da instância (self.lock por padrão).
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            lock = getattr(self, lock_attr)
            async with lock:
                return await func(self, *args, **kwargs)
        return wrapper
    return decorator
# lib/util/class_loader.py
"""
Utilitário para importar e instanciar classes pelo nome completo (ex: 'lib.broker.strategy.login_strategy.DefaultLoginStrategy').
"""
import importlib

def get_class_by_fullname(fullname: str):
    """Importa e retorna a classe pelo nome completo."""
    module_name, class_name = fullname.rsplit('.', 1)
    module = importlib.import_module(module_name)
    return getattr(module, class_name)

def instantiate_by_fullname(fullname: str, *args, **kwargs):
    """Instancia uma classe pelo nome completo, passando argumentos ao construtor."""
    cls = get_class_by_fullname(fullname)
    return cls(*args, **kwargs)

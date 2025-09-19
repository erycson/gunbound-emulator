# lib/broker/managers/config.py
import os
import yaml

"""
Singleton para configurações globais e recursos compartilhados
"""
class ConfigManager:
    _instance = None

    def __new__(cls, config_path=None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config_path=None):
        if self._initialized:
            return
        self._initialized = True
        self.config = self._load_config(config_path)

    def _load_config(self, config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"[ConfigManager] Erro ao carregar config.yml: {e}")
            return {}

    @classmethod
    def initialize(cls, config_path):
        if cls._instance is not None:
            raise RuntimeError("ConfigManager já foi inicializado!")
        cls._instance = ConfigManager(config_path)
        return cls._instance.config

    @classmethod
    def get(cls):
        if cls._instance is None:
            raise RuntimeError("ConfigManager não inicializado. Chame ConfigManager.initialize(config_path) primeiro.")
        return cls._instance.config

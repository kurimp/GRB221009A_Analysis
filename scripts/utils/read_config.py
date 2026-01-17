import yaml
import os

class Config:
  def __init__(self):
    config_path = os.path.join("scripts", "config.yaml")
    
    with open(config_path, 'r', encoding='utf-8') as f:
      self._data = yaml.safe_load(f)

  def __getitem__(self, key):
    return self._data.get(key)

  @property
  def data(self):
    return self._data

# 1回だけインスタンス化しておく
cfg = Config()
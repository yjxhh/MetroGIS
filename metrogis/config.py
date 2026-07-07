from pathlib import Path
import yaml


BASE_DIR = Path(__file__).resolve().parent

CONFIG_FILE = BASE_DIR / "resources" / "default.yaml"


class Config:

    def __init__(self):

        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            self.data = yaml.safe_load(f)


    def get(self, *keys):

        value = self.data

        for key in keys:
            value = value[key]

        return value


settings = Config()

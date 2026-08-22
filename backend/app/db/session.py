import os
from pathlib import Path
from sqlmodel import create_engine, Session

data_dir_env = os.environ.get("DATA_DIR")
if data_dir_env:
    DB_DIR = Path(data_dir_env)
else:
    DB_DIR = Path(__file__).parents[3] / "data"
DB_DIR = DB_DIR / "db"
DB_DIR.mkdir(parents=True, exist_ok=True)

sqlite_url = f"sqlite:///{DB_DIR}/muleguard.sqlite"
engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})


def get_session():
    with Session(engine) as session:
        yield session

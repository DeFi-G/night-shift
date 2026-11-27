# Night Shift - credential-free local evaluation.
# Mock intelligence only. No Sprite holds or Discord delivery.

import os

os.environ["NIGHT_SHIFT_MODE"] = "mock"
os.environ["NIGHT_SHIFT_ALLOW_LIVE"] = "NO"
os.environ.pop("NIGHT_SHIFT_CONNECTION", None)
os.environ.pop("NIGHT_SHIFT_MODEL", None)

import app
from engine import Engine

if __name__ == "__main__":
    app.Engine = Engine
    app.main()

"""Source assets and the default private workspace location."""

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parents[1]
WEB_ROOT = PACKAGE_ROOT / "web"
SOURCE_CHECKOUT = PROJECT_ROOT / "src" / "swing_signal" == PACKAGE_ROOT
DATA_DIR = PROJECT_ROOT / "data" if SOURCE_CHECKOUT else Path.home() / ".swing-signal"

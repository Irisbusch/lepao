"""旧入口。转去 lepao 包，参数保持不变。

    python kernelsu_lsposed.py 127.0.0.1:16416
    python kernelsu_lsposed.py 127.0.0.1:16416 --last
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lepao.cli import main

if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import ast
import re
from pathlib import Path


def test_embedded_python_in_setup_scripts_compiles():
    scripts = Path(__file__).resolve().parents[2] / "scripts"
    for path in scripts.glob("*.sh"):
        text = path.read_text()
        fragments = re.findall(r"-c\s+'([^']+)'", text)
        fragments += re.findall(r"<<'PY'[^\n]*\n(.*?)\nPY", text, re.DOTALL)
        for code in fragments:
            ast.parse(code, filename=str(path))

from pathlib import Path
from unittest.mock import patch
import pytest


@pytest.mark.parametrize('debug,expected', [('false',False),('true',True)])
def test_quick_start_debug_is_opt_in(monkeypatch,debug,expected):
    script = Path(__file__).resolve().parents[1].joinpath('try.sh').read_text()
    python = script.split("<<'PY'\n",1)[1].rsplit('\nPY',1)[0]
    monkeypatch.setattr('sys.argv',['-', '/dev/input/test','true','auto',debug,'true'])
    with patch('touchgesture.cli.main',return_value=0) as main:
        with pytest.raises(SystemExit) as exit_info:
            exec(compile(python,'try.sh embedded Python','exec'),{})
        assert exit_info.value.code == 0
        assert ('--debug' in main.call_args.args[0]) is expected

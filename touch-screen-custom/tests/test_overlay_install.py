import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_extension_staging_install_and_remove_without_session_changes(tmp_path):
    env = dict(os.environ, XDG_DATA_HOME=str(tmp_path))
    other = tmp_path/'gnome-shell/extensions/other@local'
    other.mkdir(parents=True)
    (other/'keep.txt').write_text('keep')
    for _ in range(2):
        subprocess.run([str(ROOT/'install-overlay.sh'),'--no-enable'],env=env,check=True,capture_output=True)
    installed = tmp_path/'gnome-shell/extensions/touchgesture-overlay@local'
    metadata = json.loads((installed/'metadata.json').read_text())
    assert metadata['uuid'] == 'touchgesture-overlay@local'
    assert (installed/'extension.js').read_bytes() == (ROOT/'gnome-extension/touchgesture-overlay@local/extension.js').read_bytes()
    subprocess.run([str(ROOT/'uninstall-overlay.sh'),'--no-disable'],env=env,check=True,capture_output=True)
    assert not installed.exists()
    assert (other/'keep.txt').read_text() == 'keep'


def test_installer_warns_when_shell_still_runs_old_code_on_repeat_install(tmp_path):
    bin_dir = tmp_path/'bin'
    bin_dir.mkdir()
    commands = {
        'gnome-shell': '#!/bin/sh\necho "GNOME Shell 50.1"\n',
        'gnome-extensions': '#!/bin/sh\nif [ "$1" = info ]; then echo "  Version: 1"; fi\n',
    }
    for name, script in commands.items():
        path = bin_dir/name
        path.write_text(script)
        path.chmod(0o755)
    env = dict(os.environ, XDG_DATA_HOME=str(tmp_path/'data'),
               PATH=str(bin_dir)+os.pathsep+os.environ['PATH'])
    for _ in range(2):
        result = subprocess.run([str(ROOT/'install-overlay.sh')],env=env,
                                check=True,capture_output=True,text=True)
        assert '이전 버전(1)' in result.stdout
        assert '프로그램 재실행만으로는 확장이 바뀌지 않습니다.' in result.stdout
        assert '사용 준비 완료' not in result.stdout

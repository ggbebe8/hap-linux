"""Exercise install/update/uninstall using isolated directories and mocked desktop commands."""
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
UUID = 'keyd-visual-mode@local'

with tempfile.TemporaryDirectory(prefix='keyd-visual-test-') as directory:
    base = Path(directory)
    bin_dir = base / 'bin'
    bin_dir.mkdir()
    for name, body in {
        'gnome-shell': "echo 'GNOME Shell 50.1'",
        'gnome-extensions': 'exit 0',
        'keyd': 'exec sleep 30',
    }.items():
        path = bin_dir / name
        path.write_text('#!/bin/sh\n' + body + '\n')
        path.chmod(0o755)
    env = dict(os.environ, PATH=f'{bin_dir}:{os.environ["PATH"]}',
               XDG_DATA_HOME=str(base / 'data'), XDG_CONFIG_HOME=str(base / 'config'),
               GSETTINGS_BACKEND='keyfile')

    def run(*args, check=True):
        return subprocess.run(args, cwd=ROOT, env=env, check=check,
                              capture_output=True, text=True)

    run('gsettings', 'set', 'org.gnome.shell', 'enabled-extensions', "['other@example']")
    run('gsettings', 'set', 'org.gnome.shell', 'disabled-extensions', f"['{UUID}', 'disabled@example']")
    run('gsettings', 'set', 'org.gnome.shell', 'disable-user-extensions', 'true')
    for _ in range(2):
        run('bash', 'install.sh')
    target = base / 'data' / 'gnome-shell' / 'extensions' / UUID
    assert sorted(p.name for p in target.iterdir()) == [
        'extension.js', 'metadata.json', 'monitor.js', 'stylesheet.css']
    enabled = run('gsettings', 'get', 'org.gnome.shell', 'enabled-extensions').stdout
    assert enabled.count(UUID) == 1 and 'other@example' in enabled
    assert run('gsettings', 'get', 'org.gnome.shell', 'disable-user-extensions').stdout.strip() == 'true'
    print('PASS: install/update, preserving unrelated extensions and global switch')
    for _ in range(2):
        run('bash', 'uninstall.sh')
    assert not target.exists()
    assert run('gsettings', 'get', 'org.gnome.shell', 'enabled-extensions').stdout.strip() == "['other@example']"
    assert run('gsettings', 'get', 'org.gnome.shell', 'disabled-extensions').stdout.strip() == "['disabled@example']"
    print('PASS: repeated uninstall and settings cleanup')
    (bin_dir / 'keyd').write_text('#!/bin/sh\nexit 1\n')
    assert run('bash', 'install.sh', check=False).returncode != 0
    assert not target.exists()
    print('PASS: connection failure stops installation before mutation')

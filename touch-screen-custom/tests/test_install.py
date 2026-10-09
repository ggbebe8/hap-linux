import os
from pathlib import Path
import subprocess
import sys

import pytest
from touchgesture.config import load_config

ROOT = Path(__file__).resolve().parents[1]


def configure(target, mode='preserve', service='true'):
    return subprocess.run([sys.executable, str(ROOT/'scripts/configure-install.py'),
                           str(ROOT/'src/touchgesture/default.yaml'), str(target), mode, service],
                          check=True, capture_output=True, text=True)


@pytest.mark.parametrize('mode,service,dry_run', [
    ('preserve','true',False), ('preserve','false',True),
    ('dry-run','true',True), ('execute','true',False),
])
def test_new_install_config_works_without_resolution_setup(tmp_path,mode,service,dry_run):
    path = tmp_path/'config.yaml'
    configure(path,mode,service)
    cfg = load_config(path)
    assert cfg['dry_run'] is dry_run
    assert cfg['recognition']['distance_mode'] == 'normalized'
    assert any(g['name'] == 'previous_tab' for g in cfg['gestures'])
    assert path.stat().st_mode & 0o777 == 0o600


def test_reinstall_preserves_custom_config_and_explicit_mode_backs_up(tmp_path):
    path = tmp_path/'config.yaml'
    original = '# My settings\ndry_run: true\npreview: false\n'
    path.write_text(original)
    configure(path)
    assert path.read_text() == original
    configure(path,'execute')
    assert load_config(path)['dry_run'] is False
    assert load_config(path)['preview'] is False
    assert '# My settings' in path.read_text()
    backups = list(tmp_path.glob('*.bak'))
    assert len(backups) == 1 and backups[0].read_text() == original


def test_uninstall_is_repeatable_and_purge_only_removes_own_config(tmp_path):
    prefix = tmp_path/'prefix'
    config = tmp_path/'config'
    venv = prefix/'share/touchgesture/venv'
    venv.mkdir(parents=True)
    (venv/'installed').write_text('test')
    (prefix/'bin').mkdir()
    (prefix/'bin/touchgesture').symlink_to(venv/'bin/touchgesture')
    settings = config/'touchgesture'
    settings.mkdir(parents=True)
    (settings/'config.yaml').write_text('dry_run: true\n')
    (settings/'config.yaml.20261009-000000-000001.bak').write_text('backup')
    (settings/'notes.txt').write_text('keep')
    service = config/'systemd/user'
    service.mkdir(parents=True)
    (service/'touchgesture.service').write_text('test')
    env = dict(os.environ, TOUCHGESTURE_PREFIX=str(prefix), XDG_CONFIG_HOME=str(config))
    for _ in range(2):
        subprocess.run([str(ROOT/'uninstall.sh'),'--no-systemd'],env=env,check=True,capture_output=True)
    assert not venv.exists()
    assert not (prefix/'bin/touchgesture').is_symlink()
    assert not (service/'touchgesture.service').exists()
    assert (settings/'config.yaml').exists()
    subprocess.run([str(ROOT/'uninstall.sh'),'--no-systemd','--purge'],env=env,check=True,capture_output=True)
    assert list(settings.iterdir()) == [settings/'notes.txt']


def test_device_rules_install_remove_and_refuse_foreign_files(tmp_path):
    # Exercise the privileged helper in a copied script with /etc redirected to
    # a temporary directory and all device operations stubbed out. Never use sudo.
    script = (ROOT/'scripts/device-access.sh').read_text()
    script = script.replace('[[ $EUID == 0 ]]', '[[ 0 == 0 ]]').replace('/etc/', str(tmp_path/'etc')+'/')
    helper = tmp_path/'access.sh'
    helper.write_text(script)
    bin_dir = tmp_path/'bin'
    bin_dir.mkdir()
    log = tmp_path/'calls'
    for name in ['udevadm','modprobe','setfacl']:
        stub = bin_dir/name
        stub.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$TEST_CALLS"\n')
        stub.chmod(0o755)
    env = dict(os.environ, PATH=str(bin_dir)+os.pathsep+os.environ['PATH'], TEST_CALLS=str(log))
    env.pop('SUDO_UID',None)
    def run(action,check=True):
        return subprocess.run(['bash',str(helper),action],env=env,check=check,capture_output=True)
    run('install')
    rules = tmp_path/'etc/udev/rules.d/70-touchgesture-auto.rules'
    module = tmp_path/'etc/modules-load.d/touchgesture-auto.conf'
    assert 'ID_INPUT_TOUCHSCREEN' in rules.read_text()
    assert 'TAG+="uaccess"' in rules.read_text()
    assert 'uinput' in module.read_text()
    run('install')
    run('remove')
    run('remove')
    assert not rules.exists() and not module.exists()
    rules.write_text('# Someone else owns this\n')
    assert run('install',False).returncode != 0
    assert run('remove',False).returncode != 0
    assert rules.read_text() == '# Someone else owns this\n'

"""Create a usable first-install config, or explicitly change its execution mode."""
from datetime import datetime
from pathlib import Path
import shutil
import sys
import yaml

source, target, mode, service = sys.argv[1:]
path = Path(target)
if path.exists():
    if mode == 'preserve':
        raise SystemExit(0)
    text = path.read_text()
    # Update just this scalar so user comments and formatting survive.
    import re
    yaml.safe_load(text)  # Reject malformed YAML before touching the file.
    line = f"dry_run: {'true' if mode == 'dry-run' else 'false'}"
    text, count = re.subn(r'^dry_run:[^\n]*', line, text, flags=re.MULTILINE)
    if not count:
        text = line + '\n' + text
    backup = path.with_name(path.name + '.' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.bak')
    shutil.copy2(path, backup)
    print(f'설정 백업: {backup}')
else:
    cfg = yaml.safe_load(Path(source).read_text())
    cfg['dry_run'] = mode == 'dry-run' or (mode == 'preserve' and service == 'false')
    cfg['recognition'].update(distance_mode='normalized', min_point_distance=.005,
                             simplify_epsilon=.015, min_segment_distance=.08,
                             min_total_distance=.18)
    text = yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False)
path.write_text(text)
path.chmod(0o600)

import math
import pytest
from touchgesture.config import load_config
from touchgesture.recognition import Point, recognize, match


def run(coords, duration=.5):
    cfg = load_config()
    pts = [Point(x, y, i*duration/(len(coords)-1)) for i, (x, y) in enumerate(coords)]
    result = recognize(pts, cfg['recognition'])
    return result, match(result, cfg['gestures'])


@pytest.mark.parametrize('coords,name', [
    ([(500,100),(503,150),(501,220),(502,300),(550,302),(630,303),(720,305)], 'close_tab'),
    ([(500,500),(502,430),(501,350),(503,280),(560,282),(640,280),(720,281)], 'next_tab'),
])
def test_document_samples(coords, name):
    assert run(coords)[1]['name'] == name


@pytest.mark.parametrize('coords', [
    [(500,100),(550,150),(600,200),(650,250)],
    [(0,0),(0,300)], [(0,0),(300,0)],
    [(0,0),(0,40),(40,40)],
    [(0,0),(0,200),(200,200),(200,400),(0,400)],
    [(0,0),(0,120),(200,300)],
    # A smooth quarter circle must not become a right-angled gesture.
    [(300*(1-math.cos(i*math.pi/40)),300*math.sin(i*math.pi/40)) for i in range(21)],
])
def test_rejected(coords):
    assert run(coords)[1] is None


def test_slow():
    assert run([(0,0),(0,200),(200,200)], 1.6)[1] is None


def test_noisy_stroke():
    coords = [(i % 3 - 1, i*5) for i in range(41)]
    coords += [(i*5, 200 + i % 3 - 1) for i in range(1,41)]
    assert run(coords)[1]['name'] == 'close_tab'


def test_custom_three_segments():
    cfg = load_config()
    cfg['gestures'] = [{'name': 'custom', 'sequence': ['DOWN','RIGHT','UP']}]
    result = recognize([Point(0,0,0),Point(0,200,.1),Point(200,200,.2),Point(200,0,.3)], cfg['recognition'])
    assert match(result, cfg['gestures'])['name'] == 'custom'


def test_normalized(tmp_path):
    p = tmp_path/'config.yaml'
    p.write_text('recognition:\n  distance_mode: normalized\n')
    cfg = load_config(p)
    result = recognize([Point(.1,.1,0),Point(.1,.3,.2),Point(.3,.3,.4)], cfg['recognition'])
    assert match(result, cfg['gestures'])['name'] == 'close_tab'


def test_previous_tab_matches_and_sends_shift_ctrl_tab():
    from unittest.mock import Mock
    from touchgesture.actions import ActionExecutor
    result, gesture = run([(500,500),(502,430),(501,350),(503,280),
                           (440,282),(360,280),(280,281)])
    assert gesture['name'] == 'previous_tab'
    assert gesture['label'] == '이전 탭'
    backend = Mock()
    executor = ActionExecutor([gesture], dry_run=False, backend=backend)
    executor.execute(gesture)
    backend.send.assert_called_once_with(['CTRL', 'SHIFT', 'TAB'])

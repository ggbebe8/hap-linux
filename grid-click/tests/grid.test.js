import {Grid} from '../extension/grid.js';
function equal(a, b) {
    if (JSON.stringify(a) !== JSON.stringify(b)) throw new Error(`${JSON.stringify(a)} != ${JSON.stringify(b)}`);
}
const grid = new Grid([{x: 100, y: 40, width: 900, height: 600}, {x: -1200, y: -200, width: 1200, height: 900}]);
equal(grid.point, [550, 340]);
grid.select('Q');
equal(grid.point, [250, 140]);
grid.select('C');
equal(grid.point, [350, 207]);
grid.back();
equal(grid.point, [250, 140]);
grid.reset();
grid.select('S');
equal(grid.point, [550, 340]);
grid.nudge(1, -10);
equal(grid.point, [551, 330]);
grid.back();
equal(grid.point, [550, 340]);
grid.nextMonitor();
equal(grid.point, [-600, 250]);
grid.nudge(-99999, -99999);
equal(grid.point, [-1200, -200]);
grid.nudge(99999, 99999);
equal(grid.point, [-1, 699]);
grid.reset();
for (let i = 0; i < 20; i++) grid.select('C');
if (grid.history.length > 9) throw new Error('Subdivision must stop at pixel precision');
if (grid.point[0] >= 0 || grid.point[1] >= 700) throw new Error('Point outside monitor');
const tiny = new Grid([{x: 0, y: 0, width: 2, height: 2}]);
equal(tiny.select('S'), false);
equal(tiny.select('!'), false);
// Follow a target across odd-sized, fractional cells, independently of any app.
const precise = new Grid([{x: 17, y: 31, width: 1919, height: 1079}]);
const target = [1372, 814];
while (precise.area.width >= 3 && precise.area.height >= 3) {
    const cell = precise.cells().find(c => target[0] >= c.x && target[1] >= c.y && target[0] < c.x + c.width && target[1] < c.y + c.height);
    if (!cell) throw new Error('Gap in grid coverage');
    precise.select(cell.key);
}
if (Math.abs(precise.point[0] - target[0]) > 2 || Math.abs(precise.point[1] - target[1]) > 2)
    throw new Error('Refinement did not converge');
print('PASS: subdivision, undo, reset, pixel nudging, monitor switch, negative origins, fractional cells');

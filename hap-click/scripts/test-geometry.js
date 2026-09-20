// Evaluate the real extension methods without starting a desktop session.
const {GLib} = imports.gi;
const [, bytes] = GLib.file_get_contents('extension/extension.js');
const source = new TextDecoder().decode(bytes).replace(/^import .*;\n/gm, '')
    .replace('export default class', 'class');
const Hap = new Function('Extension', `${source}\nreturn HapExtension;`)(class {});
const hap = new Hap();
const frame = {x: 180, y: 90, width: 920, height: 560};
const buffer = {x: 164, y: 80, width: 952, height: 602};
const win = {get_frame_rect: () => frame, get_buffer_rect: () => buffer};
function check(actual, expected) {
    if (actual.some((n, i) => Math.abs(n - expected[i]) > .001))
        throw new Error(`${actual} != ${expected}`);
}
// VSCode's left toolbar item: account for CSD shadow, without shrinking.
check(hap._hintPoint(hap._coordinateRect(win, {width: 952, height: 602}),
    [42 / 952, 67 / 602]), [206, 147]);
// A toolkit whose accessible root is the visible frame still uses that frame.
check(hap._hintPoint(hap._coordinateRect(win, {width: 920, height: 560}),
    [.25, .5]), [410, 370]);
// Negative monitor origins are valid; normalized coordinates stay bounded.
const left = {...frame, x: -1000};
check(hap._hintPoint(left, [.5, .5]), [-540, 370]);
for (const point of [[48, 51], [NaN, 0], [-.1, .5]]) {
    let rejected = false;
    try { hap._hintPoint(frame, point); } catch { rejected = true; }
    if (!rejected) throw new Error(`Invalid normalized coordinate accepted: ${point}`);
}
print('Shared hint/click geometry regression checks passed');

import GLib from 'gi://GLib';
import {LayerMonitor} from '../extension/monitor.js';

const loop = new GLib.MainLoop(null, false);
const sleep = ms => new Promise(resolve => {
    GLib.timeout_add(GLib.PRIORITY_DEFAULT, ms, () => {
        resolve();
        return GLib.SOURCE_REMOVE;
    });
});
function assert(value, message) {
    if (!value)
        throw new Error(message);
}
async function until(predicate, message, timeout = 4000) {
    const end = GLib.get_monotonic_time() + timeout * 1000;
    while (!predicate()) {
        assert(GLib.get_monotonic_time() < end, message);
        await sleep(20);
    }
}
const command = source => ['python3', '-u', '-c', source];
let current;

async function run() {
    const states = [];
    current = new LayerMonitor(state => states.push(state), {
        command: command(`import time
print('/main')
print('+caps_locked')
print('+caps_d_layer')
print('-caps_d_layer')
print('+caps_nav')
print('-caps_nav')
print('-caps_locked')
time.sleep(30)`),
    });
    current.start();
    await until(() => states.length >= 3, 'Layer events not received');
    assert(JSON.stringify(states) === '["off","on","off"]', 'Nested layer changed the indicator');
    assert(current._timer === 0, 'Connected monitor must have no timer');
    const pid = current._process.get_identifier();
    current.stop();
    await until(() => !GLib.file_test(`/proc/${pid}`, GLib.FileTest.EXISTS), 'Child was not reaped');
    await sleep(50);
    assert(states.length === 3, 'Stale callback changed state after stop');
    print('PASS: initial snapshot, nested layers, deactivation, idle without timer, child cleanup');

    const failures = [];
    current = new LayerMonitor(state => failures.push(state), {
        command: command("print('+caps_locked')"), retryDelays: [1],
    });
    current.start();
    await until(() => failures.filter(state => state === 'error').length === 2, 'Retry did not occur');
    assert(JSON.stringify(failures) === '["off","on","error","off","on","error"]',
        'EOF must clear active state on every connection');
    assert(current._timer === 0 && current._process === null, 'Retry budget not respected');
    current.stop();
    print('PASS: EOF clears state and retry budget is bounded');

    const stopped = [];
    current = new LayerMonitor(state => stopped.push(state), {
        command: ['/definitely/missing/keyd'], retryDelays: [1],
    });
    current.start();
    assert(stopped.includes('error') && current._timer !== 0, 'Spawn error not handled');
    current.stop();
    await sleep(1200);
    assert(stopped.length === 2 && current._timer === 0, 'Stop did not cancel retry');
    print('PASS: spawn failure and retry cancellation');

    const malformed = [];
    current = new LayerMonitor(state => malformed.push(state), {
        command: command("print('Max listeners exceeded')"), retryDelays: [],
    });
    current.start();
    await until(() => malformed.includes('error'), 'Protocol failure not detected');
    current.stop();
    print('PASS: invalid protocol response');
}

let failure = null;
run().catch(error => { failure = error; }).finally(() => {
    current?.stop();
    loop.quit();
});
loop.run();
if (failure)
    throw failure;

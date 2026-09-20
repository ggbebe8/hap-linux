import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

// One blocked asynchronous read, no timer while connected. Retry only on failure.
export class LayerMonitor {
    constructor(onState, {command = ['keyd', 'listen'], layer = 'caps_locked',
        retryDelays = [1, 2, 4, 8, 16]} = {}) {
        this._onState = onState;
        this._command = command;
        this._layer = layer;
        this._retryDelays = retryDelays;
        this._generation = 0;
        this._timer = 0;
        this._running = false;
    }

    start() {
        this.stop();
        this._running = true;
        this._attempt = 0;
        this._connect();
    }

    stop() {
        this._running = false;
        this._generation++;
        if (this._timer) {
            GLib.Source.remove(this._timer);
            this._timer = 0;
        }
        this._cleanup();
    }

    _cleanup() {
        this._cancellable?.cancel();
        this._cancellable = null;
        if (this._process) {
            this._process.force_exit();
            this._process = null;
        }
    }

    _connect() {
        const generation = ++this._generation;
        this._onState('off');
        try {
            this._cancellable = new Gio.Cancellable();
            this._process = Gio.Subprocess.new(this._command,
                Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_SILENCE);
            // Reap every child, including children terminated by disable/retry.
            this._process.wait_async(null, (proc, result) => {
                try { proc.wait_finish(result); } catch (error) { console.error(error); }
            });
            const stream = new Gio.DataInputStream({
                base_stream: this._process.get_stdout_pipe(),
            });
            this._read(stream, generation);
        } catch (error) {
            this._failed(generation, error);
        }
    }

    _read(stream, generation) {
        stream.read_line_async(GLib.PRIORITY_DEFAULT, this._cancellable, (input, result) => {
            let line;
            try {
                [line] = input.read_line_finish_utf8(result);
            } catch (error) {
                if (generation === this._generation && this._running)
                    this._failed(generation, error);
                return;
            }
            if (generation !== this._generation || !this._running)
                return;
            if (line === null) {
                this._failed(generation, new Error('keyd listen disconnected'));
                return;
            }
            if (line === `+${this._layer}`)
                this._onState('on');
            else if (line === `-${this._layer}`)
                this._onState('off');
            else if (!/^[+\-/]/.test(line)) {
                this._failed(generation, new Error(`Unexpected keyd response: ${line}`));
                return;
            }
            this._read(stream, generation);
        });
    }

    _failed(generation, error) {
        if (!this._running || generation !== this._generation)
            return;
        this._generation++;
        this._cleanup();
        console.warn(`Keyd Visual Mode: ${error.message}`);
        this._onState('error');
        // A fixed total budget also prevents an accept/disconnect loop.
        if (this._attempt < this._retryDelays.length) {
            const delay = this._retryDelays[this._attempt++];
            this._timer = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, delay, () => {
                this._timer = 0;
                this._connect();
                return GLib.SOURCE_REMOVE;
            });
        }
    }
}

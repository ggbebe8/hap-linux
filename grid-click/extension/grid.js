export const KEYS = 'QWEASDZXC';

export class Grid {
    constructor(monitors, index = 0) {
        if (!monitors.length || monitors.some(m => ![m.x, m.y, m.width, m.height].every(Number.isFinite) || m.width <= 0 || m.height <= 0))
            throw new Error('사용 가능한 화면이 없습니다.');
        this.monitors = monitors.map(({x, y, width, height}) => ({x, y, width, height}));
        this.index = Math.max(0, Math.min(index, monitors.length - 1));
        this.reset();
    }

    reset() {
        this.history = [{...this.monitors[this.index]}];
        this.dx = this.dy = 0;
    }

    get area() { return this.history[this.history.length - 1]; }

    cells() {
        const {x, y, width, height} = this.area;
        return [...KEYS].map((key, i) => ({key,
            x: x + i % 3 * width / 3, y: y + Math.floor(i / 3) * height / 3,
            width: width / 3, height: height / 3}));
    }

    select(key) {
        if (this.area.width < 3 || this.area.height < 3) return false;
        const cell = this.cells().find(c => c.key === key);
        if (!cell) return false;
        this.history.push(cell);
        this.dx = this.dy = 0;
        return true;
    }

    back() {
        if (this.history.length > 1) this.history.pop();
        this.dx = this.dy = 0;
    }

    nextMonitor() {
        this.index = (this.index + 1) % this.monitors.length;
        this.reset();
    }

    nudge(dx, dy) {
        const [x, y] = this.point;
        const m = this.monitors[this.index];
        const a = this.area;
        this.dx = Math.max(m.x, Math.min(m.x + m.width - 1, x + dx)) - (a.x + a.width / 2);
        this.dy = Math.max(m.y, Math.min(m.y + m.height - 1, y + dy)) - (a.y + a.height / 2);
    }

    get point() {
        const a = this.area;
        const m = this.monitors[this.index];
        return [Math.max(m.x, Math.min(m.x + m.width - 1, Math.round(a.x + a.width / 2 + this.dx))),
            Math.max(m.y, Math.min(m.y + m.height - 1, Math.round(a.y + a.height / 2 + this.dy)))];
    }
}

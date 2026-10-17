// Procedural Cairo scene shared by the GNOME wallpaper and its preview renderer.
import Cairo from 'cairo';

export const DEFAULT_SETTINGS = Object.freeze({
    enabled: true,
    paused: false,
    foreground: true,
    rotation_speed: 0.85,
    glow: 0.82,
    rays: 0.72,
    density: 0.72,
    links: true,
    labels: true,
});

const TAU = Math.PI * 2;

export function advancePhase(phase, elapsed, degreesPerSecond) {
    return (phase - elapsed * degreesPerSecond * Math.PI / 180 + TAU) % TAU;
}

function random(seed) {
    let value = seed >>> 0;
    return () => {
        value = (Math.imul(1664525, value) + 1013904223) >>> 0;
        return value / 4294967296;
    };
}

function color(hex) {
    const clean = /^#[0-9a-fA-F]{6}$/.test(hex ?? '') ? hex.slice(1) : 'a5bde2';
    return [0, 2, 4].map(index => parseInt(clean.slice(index, index + 2), 16) / 255);
}

function source(cr, hex, alpha) {
    const [r, g, b] = color(hex);
    cr.setSourceRGBA(r, g, b, alpha);
}

function circle(cr, x, y, radius, hex, alpha) {
    source(cr, hex, alpha);
    cr.arc(x, y, radius, 0, TAU);
    cr.fill();
}

function glow(cr, x, y, radius, hex, alpha) {
    const [r, g, b] = color(hex);
    const gradient = new Cairo.RadialGradient(x, y, 0, x, y, radius);
    gradient.addColorStopRGBA(0, r, g, b, alpha);
    gradient.addColorStopRGBA(0.18, r, g, b, alpha * 0.48);
    gradient.addColorStopRGBA(1, r, g, b, 0);
    cr.setSource(gradient);
    cr.arc(x, y, radius, 0, TAU);
    cr.fill();
}

function line(cr, x1, y1, x2, y2, hex, alpha, width) {
    source(cr, hex, alpha);
    cr.setLineWidth(width);
    cr.moveTo(x1, y1);
    cr.lineTo(x2, y2);
    cr.stroke();
}

function project(x, y, z, phase, width, height, skyMode) {
    const scale = skyMode ? Math.min(width / 16.9, height / 12.2) : Math.min(width / 15.4, height / 11.8);
    const ca = Math.cos(phase), sa = Math.sin(phase);
    const rx = x * ca - y * sa;
    const ry = x * sa + y * ca;
    return [width * (skyMode ? 0.47 : 0.5) + rx * scale,
        height * (skyMode ? 0.265 : 0.5) + ry * scale * (skyMode ? 0.43 : 0.77) + z * scale * 0.11];
}

export function layoutScene(scene, phase, width, height, skyMode, focus = null) {
    const nodes = scene?.nodes ?? [];
    const bases = new Map(nodes.filter(node => node.id).map(node => [node.id, node]));
    const positions = new Map();
    for (const node of nodes) {
        if (!node.id) continue;
        const parent = bases.get(node.orbit_parent);
        const movingParent = positions.get(node.orbit_parent);
        if (!parent || !movingParent) {
            positions.set(node.id, {x: node.x, y: node.y, z: node.z});
            continue;
        }
        // Integer multiples keep orbits continuous when the scene phase wraps at 2π.
        const speed = node.kind === 'Remembered file' ? 3 :
            node.kind === 'Directory system' ? 0 : 1;
        const angle = phase * speed;
        const dx = node.x - parent.x, dy = node.y - parent.y;
        positions.set(node.id, {
            x: movingParent.x + dx * Math.cos(angle) - dy * Math.sin(angle),
            y: movingParent.y + dx * Math.sin(angle) + dy * Math.cos(angle),
            z: movingParent.z + node.z - parent.z,
        });
    }
    const visible = new Set();
    if (!focus) {
        nodes.forEach((_, index) => visible.add(index));
    } else {
        nodes.forEach((node, index) => {
            if (node.kind === 'Agent') return;
            if (node.root !== focus.root) return;
            if (node.kind === 'Directory system') {
                if (focus.kind === 'Directory system') visible.add(index);
            } else if (focus.kind === 'Directory system' ||
                       node.path === focus.path || node.path?.startsWith(`${focus.path}/`)) {
                visible.add(index);
            }
        });
        for (const link of scene.links ?? []) {
            if (visible.has(link.to)) visible.add(link.from);
        }
    }
    const anchorNode = focus ? nodes.find(node => node.kind === focus.kind &&
        node.root === focus.root && node.path === focus.path) : null;
    const anchor = positions.get(anchorNode?.id) ?? anchorNode;
    const zoom = focus ? (focus.kind === 'Directory system' ? 1.9 : 2.6) : 1;
    const base = project(0, 0, 0, phase, width, height, skyMode);
    const coordinates = nodes.map(node => {
        const position = positions.get(node.id) ?? node;
        const point = project(position.x - (anchor?.x ?? 0), position.y - (anchor?.y ?? 0),
            position.z - (anchor?.z ?? 0), phase, width, height, skyMode);
        return [base[0] + (point[0] - base[0]) * zoom,
            base[1] + (point[1] - base[1]) * zoom];
    });
    return {coordinates, visible, positions};
}

export function hitTest(scene, coordinates, visible, x, y) {
    let best = null;
    for (let i = 0; i < scene.nodes.length; i++) {
        if (!visible.has(i)) continue;
        const node = scene.nodes[i];
        if (!['Host', 'Directory system', 'Remembered directory', 'Remembered file'].includes(node.kind) || !node.path) continue;
        const [px, py] = coordinates[i];
        const radius = node.kind === 'Host' ? 30 : node.kind === 'Directory system' ? 27 : node.kind === 'Remembered directory' ? 16 : 11;
        const distance = Math.hypot(x - px, y - py) / radius;
        if (distance <= 1 && (!best || distance < best.distance)) best = {node, distance};
    }
    return best?.node ?? null;
}

function background(cr, width, height, settings, skyMode) {
    cr.setSourceRGB(0.018, 0.027, 0.049);
    cr.paint();
    const g = Number(settings.glow ?? DEFAULT_SETTINGS.glow);
    const centerY = height * (skyMode ? 0.265 : 0.5);
    glow(cr, width * 0.47, centerY, Math.min(width * 0.42, height * 0.77), '#274e9d', 0.48 * g);
    glow(cr, width * 0.62, centerY - height * 0.12, Math.min(width * 0.28, height * 0.50), '#8840bd', 0.28 * g);
    glow(cr, width * 0.27, centerY + height * 0.12, Math.min(width * 0.25, height * 0.48), '#167da3', 0.29 * g);
    glow(cr, width * 0.47, centerY, Math.min(width * 0.12, height * 0.22), '#f3a6a4', 0.30 * g);
    const rng = random(0x4f425356);
    const count = Math.min(200, Math.max(40, Math.round(width * height / 9500)));
    for (let i = 0; i < count; i++) {
        const x = rng() * width, y = rng() * height, strength = 0.12 + rng() * 0.33;
        circle(cr, x, y, rng() < 0.12 ? 1.15 : 0.55, i % 6 === 0 ? '#9cbffe' : '#dce8ff', strength);
    }
}

function spiralDust(cr, phase, width, height, settings, skyMode) {
    const count = Math.round(1200 * Number(settings.density ?? DEFAULT_SETTINGS.density));
    const rng = random(0xa17ce509);
    for (let i = 0; i < count; i++) {
        const arm = i % 4;
        const radius = 0.45 + Math.sqrt(rng()) * 5.65;
        const theta = arm * TAU / 4 + radius * 0.60 + (rng() - 0.5) * (0.35 + radius * 0.07);
        const x = radius * Math.cos(theta) + (rng() - 0.5) * 0.14;
        const y = radius * Math.sin(theta) + (rng() - 0.5) * 0.14;
        const [px, py] = project(x, y, (rng() - 0.5) * 0.9, phase, width, height, skyMode);
        const palette = ['#8faeff', '#cba4ff', '#77d7e5', '#e8a6bf'];
        const alpha = 0.17 + rng() * 0.54;
        circle(cr, px, py, rng() > 0.96 ? 1.75 : 0.65 + rng() * 0.75, palette[arm], alpha);
    }
    const rayPower = Number(settings.rays ?? DEFAULT_SETTINGS.rays);
    if (rayPower <= 0) return;
    for (let arm = 0; arm < 4; arm++) {
        for (let pass = 0; pass < 2; pass++) {
            cr.newPath();
            for (let step = 0; step <= 65; step++) {
                const r = 0.26 + step / 65 * 5.6;
                const theta = arm * TAU / 4 + r * 0.60 + (pass ? 0.10 : -0.10);
                const [px, py] = project(r * Math.cos(theta), r * Math.sin(theta), 0, phase, width, height, skyMode);
                if (step === 0) cr.moveTo(px, py);
                else cr.lineTo(px, py);
            }
            source(cr, arm % 2 ? '#a77afa' : '#62b7f3', (pass ? 0.095 : 0.044) * rayPower);
            cr.setLineWidth(pass ? 13 : 32);
            cr.stroke();
        }
    }
}

function lightRays(cr, phase, width, height, settings, skyMode) {
    const strength = Number(settings.rays ?? DEFAULT_SETTINGS.rays);
    if (strength <= 0) return;
    const cx = width * (skyMode ? 0.47 : 0.5), cy = height * (skyMode ? 0.265 : 0.5);
    for (let index = 0; index < 14; index++) {
        const angle = phase + index * TAU / 14 + Math.sin(index * 13.1) * 0.18;
        const reach = Math.min(width * 0.43, height * 0.77) * (0.65 + ((index * 7) % 5) * 0.08);
        const x = cx + Math.cos(angle) * reach;
        const y = cy + Math.sin(angle) * reach * (skyMode ? 0.43 : 0.77);
        const gradient = new Cairo.LinearGradient(cx, cy, x, y);
        const tint = color(index % 3 === 0 ? '#f0afca' : '#6bbde8');
        gradient.addColorStopRGBA(0, ...tint, 0.22 * strength);
        gradient.addColorStopRGBA(0.26, ...tint, 0.07 * strength);
        gradient.addColorStopRGBA(1, ...tint, 0);
        cr.setSource(gradient);
        cr.setLineWidth(index % 4 === 0 ? 2.0 : 0.8);
        cr.moveTo(cx, cy);
        cr.lineTo(x, y);
        cr.stroke();
    }
}

function label(cr, x, y, text, hex, size = 11) {
    source(cr, hex, 0.91);
    cr.selectFontFace('Sans', Cairo.FontSlant.NORMAL, Cairo.FontWeight.BOLD);
    cr.setFontSize(size);
    const extents = cr.textExtents(text);
    cr.moveTo(x - extents.width / 2, y);
    cr.showText(text);
}

function paintForeground(cr, width, height, image) {
    if (!image) return;
    const imageWidth = image.getWidth(), imageHeight = image.getHeight();
    const scale = Math.max(width / imageWidth, height / imageHeight);
    cr.save();
    cr.translate((width - imageWidth * scale) / 2, (height - imageHeight * scale) / 2);
    cr.scale(scale, scale);
    cr.setSourceSurface(image, 0, 0);
    cr.paint();
    cr.restore();
}

function attribution(cr, width, height, scene) {
    const title = 'CONSTELLATION BY PROGRETECH';
    const notice = '© 2026 PROGRETECH LLC';
    const stale = scene && (!Number.isFinite(scene.generated_at) || Date.now() / 1000 - scene.generated_at > 360);
    const count = `${scene?.counts?.files ?? 0} REMEMBERED FILES${stale ? '  ·  MEMORY STALE' : ''}`;
    const shortcuts = [
        'CLICK FOLDER · OPEN     ALT+CLICK · FOCUS/RESET',
        'CTRL+HOVER FILE · TARGET     CTRL+CLICK · OPEN',
    ];
    if (['hindsight', 'hindsight-api'].includes(scene?.memory_source?.provider))
        shortcuts.push('CTRL+SHIFT+CLICK FILE · NEWEST MEMORY');
    const rows = [
        ...shortcuts.map(text => ({text, size: 8.5, bold: false, alpha: 0.82, gap: 0})),
        {text: count, size: 9, bold: false, alpha: 0.76, gap: 5},
        {text: title, size: 11, bold: true, alpha: 0.97, gap: 2},
        {text: notice, size: 9, bold: true, alpha: 0.9, gap: 0},
    ];
    cr.save();
    let widest = 0;
    let baseline = 8;
    for (const row of rows) {
        cr.selectFontFace('Sans', Cairo.FontSlant.NORMAL,
            row.bold ? Cairo.FontWeight.BOLD : Cairo.FontWeight.NORMAL);
        cr.setFontSize(row.size);
        widest = Math.max(widest, cr.textExtents(row.text).width);
        baseline += row.gap + row.size + 4;
        row.baseline = baseline;
    }
    const boxWidth = Math.min(width - 16, widest + 24);
    const boxHeight = baseline + 9;
    // Leave the usual right-hand desktop icon column uncovered on wide monitors.
    const rightInset = width >= 1600 ? 140 : 14;
    const left = Math.max(8, width - boxWidth - rightInset);
    const top = Math.max(8, height - boxHeight - 14);
    cr.setSourceRGBA(0.018, 0.027, 0.049, 0.78);
    cr.rectangle(left, top, boxWidth, boxHeight);
    cr.fill();
    for (const row of rows) {
        cr.selectFontFace('Sans', Cairo.FontSlant.NORMAL,
            row.bold ? Cairo.FontWeight.BOLD : Cairo.FontWeight.NORMAL);
        cr.setFontSize(row.size);
        cr.setSourceRGBA(0.85, 0.93, 1, row.alpha);
        cr.moveTo(left + boxWidth - cr.textExtents(row.text).width - 12, top + row.baseline);
        cr.showText(row.text);
    }
    cr.restore();
}

export function renderGalaxy(cr, width, height, scene, settings = DEFAULT_SETTINGS, phase = 0, time = 0, foreground = null, focus = null) {
    const skyMode = settings.foreground !== false && foreground !== null;
    background(cr, width, height, settings, skyMode);
    spiralDust(cr, phase, width, height, settings, skyMode);
    lightRays(cr, phase, width, height, settings, skyMode);
    if (!scene || !Array.isArray(scene.nodes)) {
        if (skyMode) paintForeground(cr, width, height, foreground);
        label(cr, width * 0.5, height - 24, 'MEMORY SCENE UNAVAILABLE', '#ed9a92', 10);
        attribution(cr, width, height, null);
        return;
    }
    const {coordinates, visible} = layoutScene(scene, phase, width, height, skyMode, focus);
    const intensity = Number(settings.glow ?? DEFAULT_SETTINGS.glow);
    if (settings.links !== false && Array.isArray(scene.links)) {
        for (let i = 0; i < scene.links.length; i++) {
            const link = scene.links[i];
            const a = coordinates[link.from], b = coordinates[link.to];
            if (!a || !b || !visible.has(link.from) || !visible.has(link.to)) continue;
            line(cr, ...a, ...b, link.color, 0.22, 0.9);
            const direction = ((time * 0.24 + i * 0.127) % 2);
            const t = direction <= 1 ? direction : 2 - direction;
            const x = a[0] + (b[0] - a[0]) * t, y = a[1] + (b[1] - a[1]) * t;
            glow(cr, x, y, 13, link.color, 0.32 * intensity);
            circle(cr, x, y, 2.25, '#e6f7ff', 0.88);
        }
    }
    for (let i = 0; i < scene.nodes.length; i++) {
        if (!visible.has(i)) continue;
        const node = scene.nodes[i], [x, y] = coordinates[i];
        if (node.kind === 'Host') {
            glow(cr, x, y, 70, node.color, 0.55 * intensity);
            circle(cr, x, y, 10, node.color, 0.98);
            circle(cr, x, y, 3.2, '#fff6de', 0.98);
            source(cr, node.color, 0.42);
            cr.setLineWidth(0.9);
            cr.arc(x, y, 18, 0, TAU);
            cr.stroke();
            if (settings.labels !== false) {
                label(cr, x, y + 31, node.name.toUpperCase(), node.color, 12);
                if (scene.galaxy?.label) label(cr, x, y + 44, scene.galaxy.label.toUpperCase(), '#bdd2ea', 9);
            }
        } else if (node.kind === 'Directory system') {
            glow(cr, x, y, 37, node.color, 0.43 * intensity);
            circle(cr, x, y, 7.3, node.color, 0.94);
            circle(cr, x, y, 2.5, '#ffffff', 0.76);
            if (settings.labels !== false) label(cr, x, y - 17, node.name.toUpperCase(), '#d5e7f7', 10);
        } else if (node.kind === 'Agent') {
            const core = node.action === 'center';
            glow(cr, x, y, core ? 71 : 29, node.color, (core ? 0.61 : 0.43) * intensity * node.alpha);
            circle(cr, x, y, core ? 10 : 5.3, node.color, node.alpha);
            if (core) {
                circle(cr, x, y, 3.2, '#fff6de', 0.98);
                cr.setLineWidth(0.9);
                source(cr, '#ffcb93', 0.42);
                cr.arc(x, y, 18, 0, TAU);
                cr.stroke();
            }
            if (settings.labels !== false)
                label(cr, x, y + (core ? 32 : 19), node.name.toUpperCase(), node.color, core ? 12 : 9);
        } else if (node.kind === 'Remembered directory') {
            glow(cr, x, y, 14, node.color, 0.18 * intensity);
            circle(cr, x, y, 3.2, node.color, 0.74);
        } else {
            const flicker = 0.73 + 0.20 * Math.sin(time * 1.4 + i * 7.13);
            circle(cr, x, y, 1.1 + Math.max(0, node.z + 1) * 0.30, node.color, flicker);
        }
    }
    if (skyMode) paintForeground(cr, width, height, foreground);
    if (focus) label(cr, Math.min(width * 0.47, 410), 44,
        `FOCUS: ${focus.name.toUpperCase()}  ·  ALT+CLICK AGAIN TO RESET`, '#c7dcf4', 10);
    attribution(cr, width, height, scene);
}

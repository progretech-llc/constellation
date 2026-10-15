import {advancePhase, hitTest, layoutScene} from '../gnome-extension/galaxy.js';

const scene = {
    nodes: [
        {id: 'root:Projects', kind: 'Directory system', name: 'Projects', root: 'Projects', path: '/projects', x: -4, y: 0, z: 0},
        {id: 'dir:App', orbit_parent: 'root:Projects', kind: 'Remembered directory', name: 'App', root: 'Projects', path: '/projects/app', x: -3, y: 0, z: 0},
        {id: 'file:main', orbit_parent: 'dir:App', kind: 'Remembered file', name: 'main.py', root: 'Projects', path: '/projects/app/main.py', x: -2.5, y: 0, z: 0},
        {id: 'root:Pictures', kind: 'Directory system', name: 'Pictures', root: 'Pictures', path: '/pictures', x: 4, y: 0, z: 0},
        {id: 'agent:worker', kind: 'Agent', name: 'Worker', root: '', path: '', x: 0, y: 0, z: 0},
    ],
    links: [{from: 4, to: 2}],
};
const focus = {kind: 'Directory system', name: 'Projects', root: 'Projects', path: '/projects'};
const system = layoutScene(scene, 0, 1200, 800, true, focus);
if ([...system.visible].sort().join(',') !== '0,1,2,4') throw new Error('System focus included unrelated nodes');
const directory = layoutScene(scene, 0, 1200, 800, true,
    {kind: 'Remembered directory', name: 'App', root: 'Projects', path: '/projects/app'});
if ([...directory.visible].sort().join(',') !== '1,2,4') throw new Error('Directory focus did not select its files and agent');
if (Math.abs(directory.coordinates[1][0] - 1200 * 0.47) > 1) throw new Error('Focused folder was not centered');
if (hitTest(scene, directory.coordinates, directory.visible, ...directory.coordinates[1])?.name !== 'App')
    throw new Error('Focused folder hit target was not found');
if (hitTest(scene, directory.coordinates, directory.visible, ...directory.coordinates[3]) !== null)
    throw new Error('Hidden solar system still accepted clicks');
const later = layoutScene(scene, 0.6, 1200, 800, true,
    {kind: 'Remembered directory', name: 'App', root: 'Projects', path: '/projects/app'});
const root0 = directory.positions.get('root:Projects'), root1 = later.positions.get('root:Projects');
const dir0 = directory.positions.get('dir:App'), dir1 = later.positions.get('dir:App');
const file0 = directory.positions.get('file:main'), file1 = later.positions.get('file:main');
const distance = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
if (Math.abs(distance(root0, dir0) - distance(root1, dir1)) > 0.0001)
    throw new Error('Folder did not keep its orbit around its system');
if (Math.abs(distance(dir0, file0) - distance(dir1, file1)) > 0.0001 || distance(file0, file1) < 0.1)
    throw new Error('File did not orbit its containing folder');
if (Math.abs(later.coordinates[1][0] - 1200 * 0.47) > 1)
    throw new Error('Focused folder drifted off center while orbiting');
const beforeWrap = layoutScene(scene, 2 * Math.PI - 0.0001, 1200, 800, true);
const afterWrap = layoutScene(scene, 0, 1200, 800, true);
for (const key of ['dir:App', 'file:main']) {
    if (distance(beforeWrap.positions.get(key), afterWrap.positions.get(key)) > 0.01)
        throw new Error(`${key} jumped when the rotation phase wrapped`);
}
const hostScene = {
    nodes: [
        {id: 'host', kind: 'Host', name: 'Machine', path: '/galaxy', x: 0, y: 0, z: 0},
        {id: 'root:Projects', orbit_parent: 'host', kind: 'Directory system', name: 'Projects', root: 'Projects', path: '/galaxy/projects', x: 4, y: 0, z: 0},
        {id: 'agent:worker', orbit_parent: 'host', kind: 'Agent', name: 'Worker', root: '', path: '', x: 1, y: 0, z: 0},
        {id: 'file:main', orbit_parent: 'root:Projects', kind: 'Remembered file', name: 'main.py', root: 'Projects', path: '/galaxy/projects/main.py', x: 4.5, y: 0, z: 0},
    ],
    links: [{from: 2, to: 3}],
};
const start = layoutScene(hostScene, 0, 1200, 800, true);
const phase = advancePhase(0, 1, 90);
const moved = layoutScene(hostScene, phase, 1200, 800, true);
if (Math.abs(phase - 1.5 * Math.PI) > 0.0001) throw new Error('Galaxy did not turn counterclockwise');
if (moved.coordinates[1][1] >= start.coordinates[1][1]) throw new Error('Solar system did not move counterclockwise on screen');
if (distance(start.positions.get('host'), moved.positions.get('host')) > 0.0001)
    throw new Error('Host drifted from the center');
if (distance(start.positions.get('agent:worker'), moved.positions.get('agent:worker')) < 0.1)
    throw new Error('Agent did not roam around the host');
if (hitTest(hostScene, start.coordinates, start.visible, ...start.coordinates[0])?.kind !== 'Host')
    throw new Error('Central galaxy directory cannot be selected');
print('focus layout checks passed');

const movementScene = {
    ...hostScene,
    nodes: [...hostScene.nodes,
        {id: 'root:Other', kind: 'Directory system', root: 'Other', x: -4, y: 1, z: 0},
        {id: 'file:other', kind: 'Remembered file', orbit_parent: 'root:Other', root: 'Other', x: -3.5, y: 1, z: 0}],
    agent_activity: [{agent: 2, targets: [3, 5], last_modified_root: 4, modified_targets: [5, 3]}],
};
const layoutMode = (mode, time, selectedFocus = null, angle = 0.3) =>
    layoutScene(movementScene, angle, 1200, 800, false, selectedFocus, {agent_mode: mode}, time);
const legacy = layoutScene(movementScene, 0.3, 1200, 800, false);
for (const mode of ['orbiting', 'invalid']) {
    const actual = layoutMode(mode, 30);
    if (JSON.stringify(actual.coordinates) !== JSON.stringify(legacy.coordinates))
        throw new Error('Default layout changed');
    if (actual.motionLinks !== movementScene.links) throw new Error('Default links changed');
}
const satellite = layoutMode('satellite', 1);
if (satellite.motionLinks.length !== 1 || satellite.motionLinks[0].to !== 5)
    throw new Error('Satellite links escaped its latest modified system');
const satRadius = distance(satellite.positions.get('agent:worker'), satellite.positions.get('root:Other'));
const satelliteLater = layoutMode('satellite', 5);
if (satRadius < 0.7 || satRadius > 1.5 ||
    Math.abs(satRadius - distance(satelliteLater.positions.get('agent:worker'), satelliteLater.positions.get('root:Other'))) > 1e-6)
    throw new Error('Satellite failed to stay in system orbit');
const unrelatedFocus = {kind: 'Directory system', name: 'Projects', root: 'Projects', path: '/galaxy/projects'};
if (layoutMode('satellite', 5, unrelatedFocus).visible.has(2))
    throw new Error('Satellite appeared in an unrelated focused system');
let touched = new Set();
let previousAgent = null;
for (let i = 0; i < 6400; i++) {
    const actual = layoutMode('asteroid', i * 0.01);
    if (actual.motionLinks.length !== 0) throw new Error('Asteroid retained lines or bouncing lights');
    const point = actual.positions.get('agent:worker');
    if (![point.x, point.y, point.z].every(Number.isFinite)) throw new Error('Non-finite asteroid coordinate');
    if (previousAgent && distance(point, previousAgent) > 0.06) throw new Error('Asteroid jumped across a route boundary');
    for (const id of ['file:main', 'file:other']) {
        if (distance(point, actual.positions.get(id)) < 1e-8) touched.add(id);
    }
    previousAgent = point;
}
if (touched.size !== 2) throw new Error('Asteroid did not touch every remembered target');
for (const mode of ['asteroid', 'satellite']) {
    const before = layoutMode(mode, 4, null, 2 * Math.PI - 1e-6);
    const after = layoutMode(mode, 4, null, 0);
    if (distance(before.positions.get('agent:worker'), after.positions.get('agent:worker')) > 0.001)
        throw new Error('Movement mode jumped when phase wrapped');
    const quietScene = {...movementScene, agent_activity: []};
    const quiet = layoutScene(quietScene, 0.3, 1200, 800, false, null, {agent_mode: mode}, 40);
    if (distance(quiet.positions.get('agent:worker'), legacy.positions.get('agent:worker')) > 1e-8)
        throw new Error('Agent without remembered targets lost its default orbit');
    const single = {...movementScene, agent_activity: [{agent: 2, targets: [3]}]};
    const actual = layoutScene(single, 0.3, 1200, 800, false, null, {agent_mode: mode}, 40);
    if (!actual.coordinates.flat().every(Number.isFinite)) throw new Error('Single-target scene failed');
}
print('agent movement checks passed');

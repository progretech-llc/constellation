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

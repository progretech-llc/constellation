import {advancePhase, clickAction, hitTest, layoutScene} from '../gnome-extension/galaxy.js';

const memoryScene = {
    memory_source: {provider: 'hindsight-api', ui_url: 'http://127.0.0.1:9999'},
    nodes: [
        {id: 'root:Hindsight', kind: 'Directory system', path: ''},
        {id: 'memory:shared-id', kind: 'Memory planet', memory: 'shared-id', path: ''},
        {id: 'agent:quiet', kind: 'Agent', path: ''},
    ],
};
const memoryCoordinates = [[100, 100], [180, 100], [260, 100]];
for (const [index, action] of [[0, 'hindsight'], [1, 'memory']]) {
    const selected = hitTest(memoryScene, memoryCoordinates, new Set([0, 1, 2]), ...memoryCoordinates[index]);
    if (selected !== memoryScene.nodes[index] || clickAction(selected, memoryScene.memory_source) !== action)
        throw new Error('Pathless Hindsight nodes did not route to their web/memory actions');
}
if (hitTest(memoryScene, memoryCoordinates, new Set([0, 2]), 180, 100) !== null)
    throw new Error('A hidden memory planet accepted a click');
if (clickAction({kind: 'Agent', path: ''}, memoryScene.memory_source) !== null)
    throw new Error('Quiet agents tried to open empty folders');
const rememberedFile = {kind: 'Remembered file', path: '/project/file', memory: 'shared-id'};
if (clickAction(rememberedFile, memoryScene.memory_source) !== null ||
    clickAction(rememberedFile, memoryScene.memory_source, true) !== 'folder' ||
    clickAction(rememberedFile, memoryScene.memory_source, true, true) !== 'memory')
    throw new Error('File modifier navigation regressed');
print('Hindsight root, memory planet and file navigation checks passed');

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

// Independent system spin preserves nested geometry, focus and moving targets.
const spinLayout = (speed, time, angle = null, selectedFocus = null, mode = 'orbiting') =>
    layoutScene(movementScene, 0.3, 1200, 800, false, selectedFocus,
        {solar_rotation: true, solar_rotation_speed: speed, agent_mode: mode}, time, angle);
const spun = spinLayout(3, 30);
for (const id of ['host', 'root:Projects', 'root:Other', 'agent:worker']) {
    if (distance(spun.positions.get(id), legacy.positions.get(id)) > 1e-8)
        throw new Error('Local spin moved a system center, host or default agent');
}
if (distance(spun.positions.get('file:main'), legacy.positions.get('file:main')) < 0.1)
    throw new Error('Local spin failed to rotate contents');
const rigid = layoutScene(scene, 0.3, 1200, 800, false, null,
    {solar_rotation: true}, 40);
const rigidBase = layoutScene(scene, 0, 1200, 800, false);
for (const [a,b] of [['dir:App','file:main'],['root:Projects','dir:App']]) {
    if (Math.abs(distance(rigid.positions.get(a),rigid.positions.get(b))-
                 distance(rigidBase.positions.get(a),rigidBase.positions.get(b))) > 1e-8)
        throw new Error('Local spin distorted nested orbits');
}
const zeroSpin=spinLayout(0,30), initialSpin=spinLayout(0,0);
if(JSON.stringify(zeroSpin.coordinates)!==JSON.stringify(initialSpin.coordinates))
    throw new Error('Zero speed moved the initial local angle');
if (JSON.stringify(spinLayout(3, 30).coordinates) !== JSON.stringify(spinLayout(6, 15).coordinates))
    throw new Error('Local spin did not follow degrees per second');
if (JSON.stringify(spinLayout(1, 10, 0.8).coordinates) !== JSON.stringify(spinLayout(8, 90, 0.8).coordinates))
    throw new Error('Speed changes jumped an accumulated angle');
const spinFocus = layoutScene(scene, 0.3, 1200, 800, true,
    {kind:'Remembered directory',root:'Projects',path:'/projects/app'}, {solar_rotation:true}, 40);
if (Math.abs(spinFocus.coordinates[1][0]-1200*0.47)>1e-8 ||
    hitTest(scene,spinFocus.coordinates,spinFocus.visible,...spinFocus.coordinates[1])?.name!=='App')
    throw new Error('Spin broke focused folder placement or hit testing');
let spinTouches = new Set();
for (let i=0;i<6400;i++) {
    const actual=spinLayout(3,i*.01,null,null,'asteroid');
    if (actual.motionLinks.length) throw new Error('Spinning asteroid retained lights');
    for (const id of ['file:main','file:other'])
        if(distance(actual.positions.get('agent:worker'),actual.positions.get(id))<1e-8) spinTouches.add(id);
}
if(spinTouches.size!==2) throw new Error('Asteroid failed to touch rotating targets');
const spinSatellite=spinLayout(3,40,null,null,'satellite');
if(spinSatellite.motionLinks.length!==1 || spinSatellite.motionLinks[0].to!==5)
    throw new Error('Spin changed satellite target selection');
const spinWrapBefore=spinLayout(1,0,2*Math.PI-1e-7),spinWrapAfter=spinLayout(1,0,0);
if(distance(spinWrapBefore.positions.get('file:main'),spinWrapAfter.positions.get('file:main'))>1e-5)
    throw new Error('Local spin jumped on angle wrap');
print('independent solar rotation checks passed');

const sharedScene = {
    ...movementScene,
    nodes: [...movementScene.nodes, {id:'agent:factory-worker',kind:'Agent',root:'',x:2,y:2,z:0,color:'#999999'}],
    links: [...movementScene.links,{from:6,to:3,color:'#999999'}],
    agent_activity: [{agent:2,targets:[3,5],write_targets:[3],last_modified_root:4,modified_targets:[5]},
                     {agent:6,targets:[3,5],write_targets:[5],last_modified_root:4,modified_targets:[5]}],
};
const sharedLayout=(mode,time,phase=0.3,focus=null) => layoutScene(sharedScene,phase,1200,800,false,focus,
    {agent_mode:mode,solar_rotation:true},time);
const fixed=sharedLayout('orbiting',0).coordinates[6];
for (const mode of ['orbiting','asteroid','satellite']) {
    for (const phase of [0,1,4]) {
        const layout=sharedLayout(mode,47,phase,unrelatedFocus);
        if(JSON.stringify(layout.coordinates[6])!==JSON.stringify(fixed)) throw new Error('Shared worker roamed');
        if(layout.motionLinks.some(link=>link.from===6)) throw new Error('Shared worker retained outgoing lines');
        if(!layout.visible.has(6)) throw new Error('Shared worker lost related focus');
    }
}
const {activityLights}=await import('../gnome-extension/galaxy.js');
for (const mode of ['orbiting','asteroid','satellite']) {
    let arrivals=0;
    for(let i=0;i<1200;i++) {
        const time=i*.02,layout=sharedLayout(mode,time);
        const lights=activityLights(sharedScene,layout,{agent_mode:mode,write_lights:true},time);
        if(lights.length>4) throw new Error('Unbounded effects');
        for(const light of lights) {
            if(![light.x,light.y,light.alpha,light.radius].every(Number.isFinite)) throw new Error('Invalid light');
            if(light.kind==='inward' && (light.to!==6 || ![3,5].includes(light.from)))
                throw new Error('Shared worker sent a file outward');
            if(light.kind==='write') {
                if(mode==='satellite' || light.from!==2 || light.to!==3) throw new Error('Write light used a read-only target or wrong mode');
                if(light.arrival>0) arrivals++;
            }
        }
        if(activityLights(sharedScene,layout,{agent_mode:mode,write_lights:false},time).some(l=>l.kind==='write'))
            throw new Error('Disabled write lights still emitted');
    }
    if(mode!=='satellite' && !arrivals) throw new Error('Write light never illuminated a tiny file planet');
}
const hidden=sharedLayout('asteroid',1);
hidden.visible.delete(6);hidden.visible.delete(2);
if(activityLights(sharedScene,hidden,{agent_mode:'asteroid',write_lights:true},1).length)
    throw new Error('Hidden agents emitted lights');
const older={...sharedScene,agent_activity:[{agent:2,targets:[3]}]};
if(activityLights(older,sharedLayout('orbiting',1),{write_lights:true},1).length)
    throw new Error('Legacy read references were invented as writes');
print('shared-worker anchor and one-way recorded-write lights checks passed');

// Solar direction is screen-relative and independent of galaxy rotation speed.
const directionLayout=(clockwise,time,phase=0)=>layoutScene(hostScene,phase,1200,800,false,null,
    {solar_rotation:true,solar_rotation_speed:1,solar_clockwise:clockwise},time);
for(const phase of [0,0.6,2.5]) {
    const ccw=directionLayout(false,45,phase),cw=directionLayout(true,45,phase);
    if(ccw.coordinates[3][1]>=ccw.coordinates[1][1]) throw new Error('Default solar spin is not counterclockwise');
    if(cw.coordinates[3][1]<=cw.coordinates[1][1]) throw new Error('Clockwise spin was overridden by galaxy rotation');
    const held=directionLayout(false,0,phase);
    if(Math.abs(held.coordinates[3][1]-held.coordinates[1][1])>1e-8) throw new Error('Zero local phase inherited galaxy spin');
}
const fixedAngle=(clockwise)=>layoutScene(hostScene,.7,1200,800,false,null,
    {solar_rotation:true,solar_rotation_speed:4,solar_clockwise:clockwise},200,1.2);
if(JSON.stringify(fixedAngle(true).coordinates)!==JSON.stringify(fixedAngle(false).coordinates))
    throw new Error('Changing direction reset the accumulated phase');
print('counterclockwise default and independent direction checks passed');

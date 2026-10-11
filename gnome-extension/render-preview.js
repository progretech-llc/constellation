// Render the exact GNOME Cairo scene without loading GNOME Shell.
import Cairo from 'cairo';
import GLib from 'gi://GLib';
import {renderGalaxy, DEFAULT_SETTINGS} from './galaxy.js';

const [scenePath, outputPath, widthText, heightText, foregroundPath, phaseText, focusText] = ARGV;
if (!scenePath || !outputPath)
    throw new Error('Usage: gjs -m render-preview.js SCENE.json OUTPUT.png [width height foreground.png phase [focus.json]]');
const width = Math.max(320, Number(widthText) || 1920);
const height = Math.max(240, Number(heightText) || 1080);
const [ok, bytes] = GLib.file_get_contents(scenePath);
if (!ok) throw new Error('Unable to read scene');
const scene = JSON.parse(new TextDecoder().decode(bytes));
const foreground = foregroundPath ? Cairo.ImageSurface.createFromPNG(foregroundPath) : null;
const surface = new Cairo.ImageSurface(Cairo.Format.ARGB32, width, height);
const cr = new Cairo.Context(surface);
const phase = phaseText === undefined ? 0.24 : Number(phaseText);
const focus = focusText ? JSON.parse(focusText) : null;
renderGalaxy(cr, width, height, scene, DEFAULT_SETTINGS, phase, 1.8, foreground, focus);
cr.$dispose();
surface.writeToPNG(outputPath);

// Render the exact GNOME Cairo scene without loading GNOME Shell.
import Cairo from 'cairo';
import GLib from 'gi://GLib';
import {renderGalaxy, DEFAULT_SETTINGS} from './galaxy.js';

const [scenePath, outputPath, widthText, heightText] = ARGV;
if (!scenePath || !outputPath)
    throw new Error('Usage: gjs -m render-preview.js SCENE.json OUTPUT.png [width height]');
const width = Math.max(320, Number(widthText) || 1920);
const height = Math.max(240, Number(heightText) || 1080);
const [ok, bytes] = GLib.file_get_contents(scenePath);
if (!ok) throw new Error('Unable to read scene');
const scene = JSON.parse(new TextDecoder().decode(bytes));
const surface = new Cairo.ImageSurface(Cairo.Format.ARGB32, width, height);
const cr = new Cairo.Context(surface);
renderGalaxy(cr, width, height, scene, DEFAULT_SETTINGS, 0.24, 1.8);
cr.$dispose();
surface.writeToPNG(outputPath);

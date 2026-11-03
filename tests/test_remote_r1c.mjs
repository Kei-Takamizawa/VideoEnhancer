import test from 'node:test';
import assert from 'node:assert/strict';
import {platform, previewTile, previewLeft, droppedVideo, downloadMode} from '../src/videoenhancer/remote/web/platform.mjs';

test('Mac desktop and desktop-mode iPad stay distinct', () => {
  assert.equal(platform({userAgent: 'Macintosh Version/26 Safari', maxTouchPoints: 0}), 'mac');
  assert.equal(platform({userAgent: 'Macintosh Version/26 Safari', maxTouchPoints: 5}), 'ipad');
  assert.equal(platform({userAgent: 'iPad Version/26 Safari', maxTouchPoints: 5}), 'ipad');
});
test('preview tile and edge clamp', () => {
  const index = {interval: 3, width: 160, height: 90, frames: 200};
  assert.deepEqual(previewTile(309, index), {sheet: 1, x: 480, y: 0});
  assert.deepEqual(previewTile(900, index), {sheet: 1, x: 1440, y: 810});
  assert.equal(previewLeft(0, 500, 160), 0);
  assert.equal(previewLeft(499, 500, 160), 340);
});
test('one video drop and platform download', () => {
  const file = {type: 'video/mp4', name: 'clip.mp4'};
  assert.equal(droppedVideo([file]), file);
  assert.throws(() => droppedVideo([file, file]));
  assert.throws(() => droppedVideo([{type: 'text/plain', name: 'a.txt'}]));
  assert.equal(downloadMode('mac', 2e9, 9e8), 'attachment');
  assert.equal(downloadMode('ipad', 2e9, 9e8), 'safari');
  assert.equal(downloadMode('ipad', 2e8, 9e8), 'share');
});

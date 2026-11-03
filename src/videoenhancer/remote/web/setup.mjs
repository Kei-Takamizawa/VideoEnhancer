import {platform} from './platform.mjs';

if (platform() === 'mac') {
  const steps = document.querySelector('#setup-steps');
  const address = steps.dataset.address;
  steps.replaceChildren();
  const lines = [
    ['Download the VideoEnhancer CA profile.', '/ca.mobileconfig'],
    ['Open System Settings > General > Device Management (or Profiles), select VideoEnhancer Local CA and install the profile.'],
    ['Confirm that VideoEnhancer opens over HTTPS without a warning.', address],
    ['If Safari still does not trust the certificate, open Keychain Access, find VideoEnhancer Local CA, open Trust and choose Always Trust for Secure Sockets Layer (SSL).'],
    ['Open Settings > Add a new device on a paired device, or run VideoEnhancer - Redo pairing on the PC, then select Pair this device in Safari or Chrome within 2 minutes. Each browser is paired separately.'],
    ['Optional: in Safari, choose File > Add to Dock.'],
  ];
  for (const [text, href] of lines) {
    const li = document.createElement('li');
    const node = document.createElement(href ? 'a' : 'span');
    node.textContent = text; if (href) node.href = href;
    li.append(node); steps.append(li);
  }
}

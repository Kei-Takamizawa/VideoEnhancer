import {pairingStatus} from './logic.mjs';

export function mountPairing({container, element, button, api, session, update}) {
  const card = element('section', undefined, 'add-card');
  const status = element('p', '');
  status.setAttribute('role', 'status');
  const instructions = element('p', 'On the new device, open the setup address and follow the steps, then select Pair this device.');
  const address = element('a', session.setup_address);
  address.href = session.setup_address;
  const copy = button('Copy address', async () => {
    try { await navigator.clipboard.writeText(session.setup_address); copied.textContent = 'Address copied.'; }
    catch { copied.textContent = 'Copy failed. Select and copy the address above.'; }
  });
  const copied = element('p', ''); copied.setAttribute('role', 'status');
  const panel = element('div');
  instructions.replaceChildren('On the new device, open ', address, ' and follow the steps, then select Pair this device.');
  panel.append(status, instructions, copy, copied);
  let original = session.devices || [];
  let watching = false;
  const render = () => {
    status.textContent = pairingStatus(session, original);
    const open = session.pairing_open && Date.parse(session.closes_at) > Date.now();
    instructions.hidden = copy.hidden = !open;
    openButton.disabled = open;
  };
  const watch = async () => {
    if (watching) return;
    watching = true;
    while (card.isConnected) {
      render();
      try {
        const next = await api('/api/session');
        if (!card.isConnected) break;
        if (!next.paired) throw new Error('Pair this device to use VideoEnhancer.');
        session = next;
        update(next);
        render();
        if (!session.pairing_open) break;
      } catch (error) { copied.textContent = error.message; }
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
    watching = false;
  };
  const openButton = button('Add a new device', async () => {
    openButton.disabled = true;
    copied.textContent = '';
    try {
      // Refresh the baseline before opening, so an earlier claim is not mistaken for this one.
      session = await api('/api/session');
      original = session.devices || [];
      const result = await api('/api/pair/open', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'});
      session = {...session, pairing_open: true, closes_at: result.closes_at};
      panel.hidden = false;
      render();
      void watch();
    } catch (error) { panel.hidden = false; copied.textContent = error.message; openButton.disabled = false; }
  }, 'primary');
  card.append(element('h2', 'Add a new device'), openButton, panel);
  container.append(card);
  panel.hidden = !session.pairing_open;
  if (session.pairing_open) { render(); void watch(); }
}

import {platform, droppedVideo} from './platform.mjs';
/** Render the approved Add flow using the existing shell's controls. */
import {entryDescription, selectedEntries, transferUpload, uploadRecord, uploadText, resumeText, keepOpenText} from './add.mjs';

export function mountAdd({main, element, button, api, added}) {
  const post = (path, body = {}) => api(path, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  const card = heading => {
    const section = element('section', undefined, 'add-card');
    section.append(element('h2', heading)); main.append(section); return section;
  };
  const link = card('Paste a link');
  const label = element('label', 'Video URL');
  const input = element('input'); input.type = 'url'; input.id = 'video-url'; input.placeholder = 'https://…'; input.autocomplete = 'off'; label.htmlFor = input.id;
  const linkMessage = element('p', '', 'muted'); linkMessage.setAttribute('role', 'status');
  const linkResults = element('div');
  const paste = button('Paste', async () => {
    try { input.value = await navigator.clipboard.readText(); input.focus(); }
    catch { linkMessage.textContent = 'Touch and hold the Video URL field, then tap Paste.'; input.focus(); }
  });
  const check = button('Check link', checkLink, 'primary');
  const linkActions = element('div', undefined, 'actions'); linkActions.append(paste, check);
  link.append(label, input, linkActions, linkMessage, linkResults);

  async function poll(path, initial, statusNode) {
    let value = initial;
    while (value && !['done', 'completed', 'failed', 'error', 'cancelled'].includes(value.state)) {
      if (value.entries || value.tools_required) return value;
      await new Promise(resolve => setTimeout(resolve, 800));
      if (!statusNode.isConnected) throw new Error('Open Add again to continue.');
      value = await api(path);
    }
    if (value?.error || ['failed', 'error', 'cancelled'].includes(value?.state)) throw new Error(value.error?.message || value.error || 'The request could not be completed. Try again.');
    return value;
  }
  async function tools() {
    linkMessage.textContent = 'Link tools are not installed on the PC.';
    const install = button('Install link tools', async () => {
      install.disabled = true; linkResults.replaceChildren();
      try {
        const started = await post('/api/link-tools/check');
        const checked = await poll(`/api/link-tools/${encodeURIComponent(started.id)}`, started, linkMessage);
        const plan = checked.result || checked;
        const notice = typeof plan.notice === 'object' ? plan.notice.text : plan.notice;
        linkResults.append(element('p', notice || plan.message || 'Review the link tools release plan before installing.'));
        if (plan.tools) {
          for (const tool of plan.tools) linkResults.append(element('p', [tool.name || tool.tool, tool.version, tool.licence, tool.url].filter(Boolean).join(' · ')));
        }
        const consent = button('Install these link tools', async () => {
          consent.disabled = true;
          try {
            const operation = await post('/api/link-tools/install', {consent: true, plan_id: plan.plan_id || plan.id || checked.plan_id});
            linkMessage.textContent = 'Installing link tools…';
            await poll(`/api/link-tools/${encodeURIComponent(operation.id)}`, operation, linkMessage);
            await checkLink();
          } catch (error) { linkMessage.textContent = error.message; consent.disabled = false; }
        }, 'primary');
        linkResults.append(consent);
      } catch (error) { linkMessage.textContent = error.message; install.disabled = false; }
    });
    linkResults.append(install);
  }
  async function checkLink() {
    if (!input.value.trim()) { linkMessage.textContent = 'Paste a video URL first.'; input.focus(); return; }
    check.disabled = true; linkResults.replaceChildren(); linkMessage.textContent = 'Checking the link…';
    try {
      const support = await api('/api/link-tools');
      if (!support.available) { await tools(); return; }
      const started = await post('/api/links/check', {url: input.value.trim()});
      const result = await poll(`/api/links/check/${encodeURIComponent(started.id)}`, started, linkMessage);
      if (result.tools_required) { await tools(); return; }
      if (!link.isConnected) return;
      const entries = result.entries || result.result?.entries || [];
      if (!entries.length) throw new Error('No supported videos were found at this link.');
      linkMessage.textContent = entries.length > 1 ? 'Choose the videos to add.' : 'Review the video before adding.';
      const selected = new Set(selectedEntries(entries));
      const descriptions = new Map();
      for (const entry of entries) {
        const row = element('label', undefined, 'playlist-row');
        const tick = element('input'); tick.type = 'checkbox'; tick.checked = selected.has(entry.key); tick.disabled = Boolean(entry.error);
        const text = element('span'); text.append(element('strong', entry.title));
        const description = element('small', entry.error || entryDescription(entry), entry.error ? 'error' : 'muted');
        descriptions.set(entry.key, description); text.append(description); row.append(tick, text); linkResults.append(row);
        tick.onchange = () => { tick.checked ? selected.add(entry.key) : selected.delete(entry.key); add.disabled = !selected.size; void refreshEstimate(); };
      }
      let estimateVersion = 0;
      async function refreshEstimate() {
        const version = ++estimateVersion;
        if (!selected.size) return;
        add.disabled = true;
        try {
          const estimates = await post('/api/estimate', {check_id: result.id || started.id, entry_keys: selectedEntries(entries, selected)});
          if (version !== estimateVersion || !link.isConnected) return;
          for (const entry of estimates.entries || []) descriptions.get(entry.key)?.replaceChildren(document.createTextNode(entryDescription(entry)));
          add.disabled = !selected.size;
        } catch (error) { if (version === estimateVersion) linkMessage.textContent = error.message; }
      }
      const add = button('Add', async () => {
        add.disabled = true;
        try {
          await post('/api/jobs', {check_id: result.id || started.id, entry_keys: selectedEntries(entries, selected)});
          await added();
        } catch (error) { linkMessage.textContent = error.message; add.disabled = !selected.size; }
      }, 'primary');
      add.disabled = !selected.size; linkResults.append(add);
      await refreshEstimate();
    } catch (error) { if (linkMessage.isConnected) linkMessage.textContent = error.message; }
    finally { check.disabled = false; }
  }

  const upload = card('Upload a video');
  upload.append(element('p', keepOpenText, 'muted'));
  const fileLabel = element('label', 'Choose from Photos or Files');
  const resumeWarning = element('p', '', 'muted');
  const fileInput = element('input'); fileInput.type = 'file'; fileInput.accept = 'video/*'; fileInput.id = 'upload-video'; fileLabel.htmlFor = fileInput.id;
  const uploadMessage = element('p', '', 'muted'); uploadMessage.setAttribute('role', 'status');
  const uploadActions = element('div', undefined, 'actions');
  upload.append(fileLabel, fileInput, resumeWarning, uploadMessage, uploadActions);
  let busy = false;
  let current;
  async function run(record) {
    if (busy) return;
    busy = true; fileInput.disabled = true; uploadActions.replaceChildren();
    try {
      const status = await transferUpload(record.file, record.id, api, (offset, size, speed, message) => {
        uploadMessage.textContent = message || uploadText(offset, size, speed);
      });
      if (!status.ready) throw new Error('The upload is not ready. Try resuming it.');
      const estimate = await post('/api/estimate', {upload_id: record.id});
      uploadMessage.textContent = `${record.name} · ${entryDescription(estimate.entries?.[0] || status.media || {})}`;
      const add = button('Add', async () => {
        add.disabled = true;
        try {
          await post('/api/jobs', {upload_id: record.id});
          await uploadRecord('delete').catch(() => {}); current = null;
          await added();
        } catch (error) { uploadMessage.textContent = error.message; add.disabled = false; }
      }, 'primary');
      uploadActions.append(add);
    } catch (error) {
      uploadMessage.textContent = error.message;
      uploadActions.append(button('Resume upload', () => run(record), 'primary'));
    } finally { busy = false; fileInput.disabled = false; }
  }
  async function chooseFile(file) { if (!file || busy) return;
    if (file.size > 20000000000) { uploadMessage.textContent = 'Choose a video smaller than 20 GB.'; return; }
    if (current && !window.confirm('Replace the saved upload with this video?')) { fileInput.value = ''; return; }
    fileInput.disabled = true; busy = true;
    uploadMessage.textContent = 'Checking available space…';
    try {
      // The PC checks its incoming drive's free space before accepting any bytes.
      const status = await post('/api/uploads', {name: file.name, size: file.size});
      current = {id: status.id, file, name: file.name, size: file.size};
      try { await uploadRecord('put', current); }
      catch { resumeWarning.textContent = 'Keep this app open. This device could not save the video for resuming after reopening.'; }
      busy = false;
      await run(current);
    } catch (error) { uploadMessage.textContent = error.message; }
    finally { busy = false; fileInput.disabled = false; }
  };
  fileInput.onchange = () => chooseFile(fileInput.files?.[0]);
  if (platform() === 'mac') {
    upload.append(element('p', 'Or drop one video file here.', 'muted'));
    upload.ondragover = event => { event.preventDefault(); event.dataTransfer.dropEffect = 'copy'; };
    upload.ondrop = event => {
      event.preventDefault();
      try { void chooseFile(droppedVideo(event.dataTransfer.files)); }
      catch (error) { uploadMessage.textContent = error.message; }
    };
  }
  void uploadRecord('get').then(async record => {
    if (!record || !upload.isConnected || busy || current) return;
    current = record;
    try {
      const status = await api(`/api/uploads/${encodeURIComponent(record.id)}`);
      if (!upload.isConnected || busy) return;
      uploadMessage.textContent = record.name;
      uploadActions.append(button(resumeText(status), () => run(record), 'primary'));
    } catch (error) { uploadMessage.textContent = error.message; }
  }).catch(() => {});
}


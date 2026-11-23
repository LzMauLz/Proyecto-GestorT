document.addEventListener('submit', (event) => {
  const form = event.target.closest('[data-confirm]');
  if (form && !window.confirm(form.dataset.confirm)) event.preventDefault();
});

document.addEventListener('DOMContentLoaded', () => {
  const shell = document.querySelector('[data-docked-chat]');
  if (!shell) return;
  const composer = shell.querySelector('[data-composer]');
  const input = shell.querySelector('[data-input]');
  const messages = shell.querySelector('[data-messages]');
  const panel = shell.querySelector('.docked-chat-panel');
  const launcher = shell.querySelector('[data-chat-toggle]');
  const mode = shell.querySelector('[data-chat-mode]');
  const staff = shell.dataset.scope === 'staff';
  const storageKey = staff ? 'gestortech:staff-chat' : 'gestortech:catalog-chat';
  const thread = shell.dataset.thread;
  const state = {thread, open: false, entries: [], history: []};
  try {
    const saved = JSON.parse(sessionStorage.getItem(storageKey));
    if (saved?.thread === thread) {
      state.open = saved.open === true;
      state.entries = Array.isArray(saved.entries) ? saved.entries.slice(-16) : [];
      state.history = Array.isArray(saved.history) ? saved.history.slice(-10) : [];
    }
  } catch {}
  const save = () => {
    try {
      sessionStorage.setItem(storageKey, JSON.stringify(state));
    } catch {}
  };
  const setOpen = (isOpen, focus = true) => {
    state.open = isOpen;
    panel.hidden = !isOpen;
    launcher.setAttribute('aria-expanded', String(isOpen));
    if (focus) (isOpen ? input : launcher).focus();
    if (isOpen) messages.scrollTop = messages.scrollHeight;
    save();
  };
  launcher.hidden = false;
  launcher.addEventListener('click', () => setOpen(!state.open));
  shell.querySelector('[data-chat-close]').addEventListener('click', () => setOpen(false));
  shell.addEventListener('keydown', event => {
    if (event.key === 'Escape' && state.open) setOpen(false);
  });
  document.querySelectorAll('[data-open-chat]').forEach(button => {
    button.hidden = false;
    button.addEventListener('click', () => setOpen(true));
  });
  if (staff) {
    document.querySelectorAll('form[action="/logout"]').forEach(form => {
      form.addEventListener('submit', () => {
        try { sessionStorage.removeItem(storageKey); } catch {}
      });
    });
  }
  const categories = JSON.parse(shell.dataset.categories);
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
  let sending = false;
  const readResponse = async (response) => {
    const data = (response.headers.get('content-type') || '').includes('application/json')
      ? await response.json() : {error: 'No se pudo completar la solicitud. Intenta nuevamente.'};
    if (!response.ok) throw new Error(data.error || 'No se pudo completar la solicitud.');
    return data;
  };
  const currency = new Intl.NumberFormat('es-CO', {style:'currency', currency:'COP', minimumFractionDigits:0});
  function appendLink(parent, label, href) {
    if (typeof label !== 'string' || typeof href !== 'string' || !href.startsWith('/')) return;
    const url = new URL(href, location.origin);
    if (url.origin !== location.origin || url.protocol !== location.protocol) return;
    const link = document.createElement('a');
    link.href = url.href;
    link.textContent = label;
    parent.append(link);
  }
  const addMessage = (entry) => {
    const {role, text, proposal, links = [], products = []} = entry;
    const item = document.createElement('div');
    item.className = `assistant-message assistant-message-${role}`;
    const title = document.createElement('strong');
    title.textContent = role === 'user' ? 'Tú' : role === 'error' ? 'Revisa la solicitud' : 'GestorTech';
    const paragraph = document.createElement('p');
    paragraph.textContent = text;
    item.append(title, paragraph);
    if (links.length || products.length) {
      const results = document.createElement('div');
      results.className = 'chat-results';
      links.forEach(link => appendLink(results, link.label, link.url));
      products.forEach(product => {
        const price = Number.isSafeInteger(product.price_cents) ? currency.format(product.price_cents / 100) : 'Consulta el precio';
        appendLink(results, `${product.name} · ${price} · ${product.available ? 'Disponible' : 'No disponible'}`, product.url);
      });
      item.append(results);
    }
    if (staff && proposal?.id) {
      const review = document.createElement('form');
      review.className = 'assistant-proposal';
      const products = proposal.operation === 'product_create';
      const entries = products ? (proposal.products || [proposal]) : [proposal];
      const groups = [];
      entries.forEach((entry, index) => {
        const group = document.createElement('fieldset');
        const legend = document.createElement('legend');
        legend.textContent = products ? `Producto ${index + 1}` : 'Movimiento de inventario';
        group.append(legend);
        const fields = products ? [['name','Nombre'],['description','Descripción'],['category','Categoría'],['price','Precio COP'],['stock','Cantidad']]
          : proposal.operation === 'stock_move' ? [['product_id','ID del producto'],['kind','Tipo'],['quantity','Cantidad'],['note','Nota del movimiento']]
          : [['name','Nombre'],['description','Descripción'],['category','Categoría']];
        fields.forEach(([key, labelText]) => {
          const label = document.createElement('label');
          label.textContent = labelText;
          const isCategory = key === 'category';
          const control = document.createElement(key === 'kind' || isCategory ? 'select' : key === 'description' || key === 'note' ? 'textarea' : 'input');
          control.name = key;
          if (key === 'kind') ['entrada','salida'].forEach(value => {
            const option = document.createElement('option'); option.value = value; option.textContent = value === 'entrada' ? 'Entrada' : 'Salida'; control.append(option);
          });
          if (isCategory) {
            const choices = new Set(['', ...categories, entry.category || '']);
            choices.forEach(value => control.add(new Option(value || 'Sin categoría', value)));
          }
          control.value = entry[key] ?? '';
          if (['name','price','stock','product_id','kind','quantity'].includes(key)) control.required = true;
          if (['stock','quantity','product_id'].includes(key)) { control.type = 'number'; control.step = '1'; control.min = key === 'stock' ? '0' : '1'; control.max = '2147483647'; }
          if (key === 'price') control.inputMode = 'decimal';
          if (key === 'name') control.maxLength = 160;
          if (key === 'description') control.maxLength = 2000;
          if (key === 'note') control.maxLength = 500;
          label.append(control); group.append(label);
        });
        groups.push(group); review.append(group);
      });
      const status = document.createElement('p'); status.setAttribute('role','status');
      const actions = document.createElement('div'); actions.className = 'button-row';
      const confirm = document.createElement('button'); confirm.type = 'submit'; confirm.className = 'button primary'; confirm.textContent = products ? `Confirmar ${entries.length} producto${entries.length > 1 ? 's' : ''}` : 'Confirmar propuesta';
      const cancel = document.createElement('button'); cancel.type = 'button'; cancel.className = 'button quiet'; cancel.textContent = 'Cancelar propuesta';
      actions.append(confirm, cancel); review.append(status, actions); item.append(review);
      const resolve = async (approve) => {
        confirm.disabled = cancel.disabled = true; review.setAttribute('aria-busy','true'); status.textContent = 'Guardando tu decisión…';
        const values = groups.map(group => Object.fromEntries(Array.from(group.querySelectorAll('[name]')).map(control => [control.name, control.value])));
        const edits = products && proposal.products ? {products: values} : values[0];
        try {
          const options = {method:'POST', headers:{'X-CSRF-Token':csrf}};
          if (approve) { options.headers['Content-Type'] = 'application/json'; options.body = JSON.stringify({correcciones:edits}); }
          const result = await readResponse(await fetch(`/api/asistente/propuestas/${encodeURIComponent(proposal.id)}/${approve ? 'confirmar' : 'cancelar'}`, options));
          status.textContent = approve ? 'Operación confirmada. Los datos se guardaron.' : 'Propuesta cancelada. No se cambió el inventario.';
          groups.forEach(group => { group.disabled = true; });
          entry.proposal = null;
          if (approve && products) {
            status.textContent = 'Productos guardados sin publicar. Ahora adjunta una imagen local y revisa su disponibilidad antes de publicarlos.';
            const nextSteps = document.createElement('div');
            nextSteps.className = 'button-row';
            const ids = result.product_ids || [result.product_id];
            entry.links = [];
            ids.filter(id => Number.isSafeInteger(id) && id > 0).forEach((id, index) => {
              const link = document.createElement('a');
              link.className = 'button secondary';
              link.href = `/products/${id}/edit`;
              link.textContent = `Adjuntar imagen y revisar: ${values[index]?.name || 'producto ' + id}`;
              nextSteps.append(link);
              entry.links.push({url: link.getAttribute('href'), label: link.textContent});
            });
            review.append(nextSteps);
            nextSteps.querySelector('a')?.focus();
          }
          entry.text = status.textContent;
          save();
        } catch (error) {
          status.textContent = error.message || 'No se pudo guardar la decisión. Puedes reintentar.';
          confirm.disabled = cancel.disabled = false;
        } finally { review.removeAttribute('aria-busy'); }
      };
      review.addEventListener('submit', event => { event.preventDefault(); resolve(true); });
      cancel.addEventListener('click', () => resolve(false));
    }
    messages.append(item); messages.scrollTop = messages.scrollHeight;
  };
  state.entries.forEach(addMessage);
  setOpen(state.open, false);
  const send = async () => {
    const text = input.value.trim();
    if (!text || sending) return;
    sending = true;
    const button = composer.querySelector('button[type="submit"]'); button.disabled = true; composer.setAttribute('aria-busy','true');
    const question = {role:'user', text};
    addMessage(question);
    const pending = document.createElement('p'); pending.className = 'assistant-pending'; pending.textContent = 'Preparando respuesta…'; messages.append(pending);
    try {
      const payload = {mensaje:text};
      if (staff) payload.historial = state.history;
      else payload.mode = mode.checked ? 'model' : 'product';
      const data = await readResponse(await fetch(shell.dataset.endpoint, {
        method:'POST', headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},
        body:JSON.stringify(payload)
      }));
      input.value = '';
      pending.remove();
      const answer = {role:'ai', text:data.message, proposal:data.proposal, links:data.links, products:data.products};
      addMessage(answer);
      if (data.persistent !== false) state.entries = [...state.entries, question, answer].slice(-16);
      if (data.inventory_history) {
        state.history = [...state.history, {role:'user',content:text}, {role:'assistant',content:data.message}].slice(-10);
      }
      save();
    } catch (error) { pending.remove(); addMessage({role:'error', text:error.message || 'No se pudo responder.'}); }
    finally { sending = false; button.disabled = false; composer.removeAttribute('aria-busy'); if (state.open) input.focus(); }
  };
  composer.addEventListener('submit', event => { event.preventDefault(); send(); });
  composer.querySelectorAll('[data-assistant-example]').forEach(example => {
    example.addEventListener('click', () => {
      input.value = example.dataset.assistantExample;
      if (mode) mode.checked = example.hasAttribute('data-model-example');
      input.focus();
    });
  });
  input.addEventListener('keydown', event => { if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); send(); } });
});

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-suggest-description]').forEach(button => {
    button.addEventListener('click', async () => {
      const form = button.form;
      const {name, category, description} = form.elements;
      const status = form.querySelector('[data-description-status]');
      if (!name.value.trim()) {
        status.textContent = 'Escribe el nombre del producto primero.';
        name.focus();
        return;
      }
      const fields = {name: name.value, category: category.value, description: description.value};
      button.disabled = true;
      status.textContent = 'Redactando descripción…';
      try {
        const response = await fetch(button.dataset.suggestDescription, {
          method: 'POST',
          headers: {'Content-Type': 'application/json', 'X-CSRF-Token': form.elements._csrf_token.value},
          body: JSON.stringify(fields)
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error);
        if (Object.keys(fields).some(key => form.elements[key].value !== fields[key])) {
          status.textContent = 'Cambiaste los datos mientras se redactaba. Pulsa el botón para usar la versión actual.';
          return;
        }
        description.value = data.description;
        status.textContent = 'Descripción sugerida. Revísala antes de guardar.';
        description.focus();
      } catch (error) {
        status.textContent = error instanceof SyntaxError ? 'No se pudo redactar. Recarga la página o escribe la descripción.' : error.message || 'No se pudo redactar la descripción.';
      } finally {
        button.disabled = false;
      }
    });
  });
});

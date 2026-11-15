document.addEventListener('submit', (event) => {
  const form = event.target.closest('[data-confirm]');
  if (form && !window.confirm(form.dataset.confirm)) event.preventDefault();
});

document.addEventListener('DOMContentLoaded', () => {
  const shell = document.querySelector('[data-assistant]');
  if (!shell) return;
  const composer = shell.querySelector('[data-composer]');
  const input = shell.querySelector('[data-input]');
  const messages = shell.querySelector('[data-messages]');
  const history = [];
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
  let sending = false;
  const readResponse = async (response) => {
    const data = (response.headers.get('content-type') || '').includes('application/json')
      ? await response.json() : {error: 'No se pudo completar la solicitud. Intenta nuevamente.'};
    if (!response.ok) throw new Error(data.error || 'No se pudo completar la solicitud.');
    return data;
  };
  const addMessage = (role, text, proposal) => {
    const item = document.createElement('div');
    item.className = `assistant-message assistant-message-${role}`;
    const title = document.createElement('strong');
    title.textContent = role === 'user' ? 'Tú' : role === 'error' ? 'Revisa la solicitud' : 'GestorTech';
    const paragraph = document.createElement('p');
    paragraph.textContent = text;
    item.append(title, paragraph);
    if (proposal?.id) {
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
          const control = document.createElement(key === 'kind' ? 'select' : key === 'description' || key === 'note' ? 'textarea' : 'input');
          control.name = key;
          if (key === 'kind') ['entrada','salida'].forEach(value => {
            const option = document.createElement('option'); option.value = value; option.textContent = value === 'entrada' ? 'Entrada' : 'Salida'; control.append(option);
          });
          control.value = entry[key] ?? '';
          if (['name','price','stock','product_id','kind','quantity'].includes(key)) control.required = true;
          if (['stock','quantity','product_id'].includes(key)) { control.type = 'number'; control.step = '1'; control.min = key === 'stock' ? '0' : '1'; control.max = '2147483647'; }
          if (key === 'price') control.inputMode = 'decimal';
          if (key === 'name') control.maxLength = 160;
          if (key === 'description') control.maxLength = 2000;
          if (key === 'category') control.maxLength = 100;
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
          await readResponse(await fetch(`/api/asistente/propuestas/${encodeURIComponent(proposal.id)}/${approve ? 'confirmar' : 'cancelar'}`, options));
          status.textContent = approve ? 'Operación confirmada. Los datos se guardaron.' : 'Propuesta cancelada. No se cambió el inventario.';
          groups.forEach(group => { group.disabled = true; });
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
  const send = async () => {
    const text = input.value.trim();
    if (!text || sending) return;
    sending = true;
    const button = composer.querySelector('button'); button.disabled = true; composer.setAttribute('aria-busy','true');
    addMessage('user', text);
    const pending = document.createElement('p'); pending.className = 'assistant-pending'; pending.textContent = 'Preparando respuesta…'; messages.append(pending);
    try {
      const data = await readResponse(await fetch('/api/asistente/mensaje', {
        method:'POST', headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},
        body:JSON.stringify({mensaje:text,historial:history.slice(-10)})
      }));
      input.value = ''; pending.remove(); addMessage('ai', data.message, data.proposal);
      history.push({role:'user',content:text},{role:'assistant',content:data.message});
    } catch (error) { pending.remove(); addMessage('error', (error.message || 'No se pudo responder.') + ' Puedes usar la revisión manual del archivo o registrar el producto desde Inventario.'); }
    finally { sending = false; button.disabled = false; composer.removeAttribute('aria-busy'); input.focus(); }
  };
  composer.addEventListener('submit', event => { event.preventDefault(); send(); });
  input.addEventListener('keydown', event => { if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); send(); } });
});

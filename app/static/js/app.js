document.addEventListener('submit', (event) => {
  const form = event.target.closest('[data-confirm]');
  if (form && !window.confirm(form.dataset.confirm)) event.preventDefault();
});

document.addEventListener('DOMContentLoaded', () => {
  const shell = document.querySelector('[data-assistant]');
  if (!shell) return;
  const form = shell.querySelector('[data-composer]');
  const input = shell.querySelector('[data-input]');
  const messages = shell.querySelector('[data-messages]');
  const history = [];
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
  const addMessage = (role, text, proposal) => {
    const item = document.createElement('div');
    item.className = `assistant-message assistant-message-${role}`;
    const title = document.createElement('strong');
    title.textContent = role === 'user' ? 'Tú' : 'GestorTech IA';
    const paragraph = document.createElement('p');
    paragraph.textContent = text;
    item.append(title, paragraph);
    if (proposal) {
      const box = document.createElement('div');
      box.className = 'assistant-proposal';
      box.textContent = JSON.stringify(proposal, null, 2);
      if (proposal.id) {
        const actions = document.createElement('div');
        actions.className = 'button-row';
        const confirm = document.createElement('button');
        confirm.className = 'button primary small';
        confirm.type = 'button';
        confirm.textContent = Array.isArray(proposal.products)
          ? `Confirmar ${proposal.products.length} productos`
          : 'Confirmar propuesta';
        confirm.dataset.proposal = proposal.id;
        const cancel = document.createElement('button');
        cancel.className = 'button quiet small';
        cancel.type = 'button';
        cancel.textContent = 'Cancelar';
        cancel.dataset.cancelProposal = proposal.id;
        actions.append(confirm, cancel);
        box.append(actions);
      }
      item.append(box);
    }
    messages.append(item);
    messages.scrollTop = messages.scrollHeight;
  };
  const send = async () => {
    const text = input.value.trim();
    if (!text) return;
    input.value = '';
    addMessage('user', text);
    history.push({role: 'user', content: text});
    const pending = document.createElement('p');
    pending.className = 'assistant-pending';
    pending.textContent = 'Procesando solicitud…';
    messages.append(pending);
    try {
      const response = await fetch('/api/asistente/mensaje', {
        method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf},
        body: JSON.stringify({mensaje: text, historial: history.slice(-10)})
      });
      const contentType = response.headers.get('content-type') || '';
      const data = contentType.includes('application/json')
        ? await response.json()
        : {error: 'El servidor devolvió una respuesta inesperada. Revisa la terminal de GestorTech.'};
      pending.remove();
      if (!response.ok) throw new Error(data.error || 'El asistente no pudo responder.');
      addMessage('ai', data.message, data.proposal);
      history.push({role: 'assistant', content: data.message});
    } catch (error) {
      pending.remove();
      addMessage('error', error.message);
    }
  };
  form.addEventListener('submit', (event) => { event.preventDefault(); send(); });
  input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); send(); }
  });
  messages.addEventListener('click', async (event) => {
    const button = event.target.closest('[data-proposal], [data-cancel-proposal]');
    if (!button) return;
    const action = button.dataset.proposal ? 'confirmar' : 'cancelar';
    button.disabled = true;
    const response = await fetch(`/api/asistente/propuestas/${button.dataset.proposal || button.dataset.cancelProposal}/${action}`, {
      method: 'POST', headers: {'X-CSRF-Token': csrf}
    });
    const contentType = response.headers.get('content-type') || '';
    const data = contentType.includes('application/json')
      ? await response.json()
      : {error: 'El servidor devolvió una respuesta inesperada. Revisa la terminal de GestorTech.'};
    addMessage(response.ok ? 'ai' : 'error', response.ok ? (action === 'confirmar' ? 'Operación confirmada y registrada.' : 'Propuesta cancelada.') : (data.error || 'No se pudo resolver la propuesta.'));
  });
});

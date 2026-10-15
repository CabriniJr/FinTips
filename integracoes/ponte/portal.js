// O browser só acompanha a aprovação OAuth. Nunca recebe contexto do telefone.
const el = document.querySelector('#oauth');
const status = document.querySelector('#status');
if (el) {
  const poll = async () => {
    try {
      const response = await fetch('/api/poll', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ poll: el.dataset.poll }) });
      if (!response.ok) { status.textContent = 'Autorização expirada. Inicie novamente na IA.'; return; }
      const data = await response.json();
      if (data.redirect) { location.assign(data.redirect); return; }
      setTimeout(poll, 2000);
    } catch { status.textContent = 'Não foi possível acompanhar a autorização. Confira a conexão e tente novamente.'; }
  };
  poll();
}

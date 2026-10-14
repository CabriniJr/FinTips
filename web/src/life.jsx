import React, { useCallback, useEffect, useRef, useState } from "react";
import { AREAS, STORAGE_KEY, dailyProgress, emptyLife, isDone, localDay, newId,
  readLife, removeTask, shiftDay, tasksForDay, toggleTask, validateLife } from "./life-store.js";
import { Icon } from "./icons.jsx";
import { ReadingTracker } from "./reading.jsx";

export function useLocalLife() {
  const [initial] = useState(() => {
    try { return { data: readLife(localStorage), blocked: false }; }
    catch { return { data: emptyLife(), blocked: true }; }
  });
  const [state, setState] = useState(initial.data);
  const [blocked, setBlocked] = useState(initial.blocked);
  const [issue, setIssue] = useState(initial.blocked ? "Não foi possível ler seus dados locais. Eles foram preservados; faça uma cópia antes de tentar recuperá-los." : "");
  const update = useCallback((transform) => {
    if (blocked) return false;
    try {
      const next = transform(readLife(localStorage));
      if (!validateLife(next)) throw new Error("estado inválido");
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      setState(next); setIssue(""); return true;
    } catch {
      setIssue("Não foi possível salvar no aparelho. Sua alteração não foi gravada. Verifique o espaço e tente novamente.");
      return false;
    }
  }, [blocked]);
  useEffect(() => {
    const refresh = (event) => {
      if (event.key !== STORAGE_KEY && event.key !== null) return;
      try { setState(readLife(localStorage)); setBlocked(false); setIssue(""); }
      catch { setBlocked(true); setIssue("Os dados locais não puderam ser lidos. A edição foi pausada para preservar seus registros."); }
    };
    addEventListener("storage", refresh);
    return () => removeEventListener("storage", refresh);
  }, []);
  return { state, update, blocked, issue };
}

export function PageHeading({ code = "01", overline, title, description, action }) {
  return <div className="life-heading"><div><div className="heading-code" aria-hidden="true"><span>FIN / {code}</span><span className="heading-ruler"/></div><div className="eyebrow">{overline}</div><h1>{title}</h1>
    {description && <p>{description}</p>}</div>{action}</div>;
}

export function AreaBadge({ id, small = false }) {
  const area = AREAS.find((a) => a.id === id);
  return <span className={`area-badge ${small ? "small" : ""}`} style={{ "--area": area.cor }}>
    <Icon name={area.icone} size={small ? 16 : 22}/>{!small && area.nome}</span>;
}

function Empty({ icon = "life", title, children, action }) {
  return <div className="life-empty"><span className="empty-icon"><Icon name={icon} size={28}/></span>
    <h3>{title}</h3><p>{children}</p>{action}</div>;
}

export function Sheet({ title, close, children }) {
  const ref = useRef(null);
  useEffect(() => {
    const dialog = ref.current;
    dialog.showModal();
    return () => dialog.close();
  }, []);
  return <dialog ref={ref} className="life-sheet" aria-label={title} onCancel={close}
    onClick={(e) => { if (e.target === ref.current) close(); }}>
    <div className="sheet-head"><h2>{title}</h2><button className="icon-button" aria-label="Fechar" onClick={close}><Icon name="close"/></button></div>
    {children}
  </dialog>;
}

export function TaskForm({ life, selectedDay, area = "FOC", close, toast }) {
  const [title, setTitle] = useState("");
  const [attribute, setAttribute] = useState(area);
  const [repeat, setRepeat] = useState(false);
  return <Sheet title="Uma coisa de cada vez" close={close}>
    <p className="sheet-description">Escolha algo que cabe no seu dia.</p>
    <form onSubmit={(e) => {
      e.preventDefault();
      const trimmed = title.trim();
      if (!trimmed) return;
      if (life.update((s) => ({ ...s, tarefas: [...s.tarefas, { id: newId(), titulo: trimmed,
        atributo: attribute, inicio: selectedDay, repetir: repeat }] }))) { toast("Tarefa salva no aparelho"); close(); }
    }}>
      <label className="life-field">O que você quer fazer?<input autoFocus required maxLength={180} value={title}
        onChange={(e) => setTitle(e.target.value)} placeholder="Ex.: ler por 20 minutos"/></label>
      <label className="life-field">Área da vida<select value={attribute} onChange={(e) => setAttribute(e.target.value)}>
        {AREAS.map((a) => <option key={a.id} value={a.id}>{a.nome}</option>)}</select></label>
      <label className="check-field"><input type="checkbox" checked={repeat} onChange={(e) => setRepeat(e.target.checked)}/>
        <span>Repetir todos os dias<small>A partir de {new Date(`${selectedDay}T12:00:00`).toLocaleDateString("pt-BR")}</small></span></label>
      {life.issue && <p role="alert" className="form-error">{life.issue}</p>}
      <button className="life-button primary full" disabled={life.blocked}>Adicionar tarefa <Icon name="plus" size={18}/></button>
    </form>
  </Sheet>;
}

function Tasks({ life, selectedDay, area, add, toast }) {
  const [filter, setFilter] = useState("todas");
  const [undo, setUndo] = useState(null);
  const tasks = tasksForDay(life.state, selectedDay).filter((t) => !area || t.atributo === area);
  const visible = tasks.filter((t) => filter === "todas" || (filter === "feitas") === isDone(life.state, t.id, selectedDay));
  return <section className="life-card task-card">
    <div className="section-head"><h2>Tarefas do dia</h2><button className="text-button" onClick={add} disabled={life.blocked}><Icon name="plus" size={18}/> Nova</button></div>
    <div className="segmented" aria-label="Filtrar tarefas">{[["todas", "Todas"], ["pendentes", "A fazer"], ["feitas", "Feitas"]].map(([id, label]) =>
      <button key={id} aria-pressed={filter === id} onClick={() => setFilter(id)}>{label}</button>)}</div>
    {tasks.length === 0 ? <Empty icon="today" title="Seu dia começa aqui" action={<button className="life-button" onClick={add} disabled={life.blocked}>Adicionar primeira tarefa</button>}>
      Uma tarefa pequena já dá um próximo passo à sua rotina.</Empty>
      : visible.length === 0 ? <p className="quiet-state">{filter === "feitas" ? "Ainda não há tarefas concluídas neste dia." : "Tudo feito por aqui. Um espaço para respirar."}</p>
      : <ul className="task-list">{visible.map((t) => {
        const done = isDone(life.state, t.id, selectedDay);
        return <li key={t.id} className={done ? "done" : ""}>
          <label className="task-check"><input type="checkbox" checked={done} disabled={life.blocked}
            onChange={() => life.update((s) => toggleTask(s, t.id, selectedDay))}/><span className="check-visual"><Icon name="check" size={17}/></span>
            <span className="task-title">{t.titulo}<small>{AREAS.find((a) => a.id === t.atributo).nome} · {t.repetir ? "Todos os dias" : "Neste dia"} · Você registrou</small></span></label>
          <button className="icon-button delete-task" disabled={life.blocked} aria-label={`Excluir tarefa ${t.titulo}`} onClick={() => {
            const records = life.state.registros.filter((r) => r.tarefaId === t.id);
            if (life.update((s) => removeTask(s, t.id))) setUndo({ task: t, records });
          }}><Icon name="trash" size={17}/></button>
        </li>;
      })}</ul>}
    {undo && <div className="undo-row" role="status"><span>Tarefa removida.</span><button className="text-button" onClick={() => {
      if (life.update((s) => ({ ...s, tarefas: [...s.tarefas.filter((t) => t.id !== undo.task.id), undo.task],
        registros: [...s.registros.filter((r) => r.tarefaId !== undo.task.id), ...undo.records] }))) {
        setUndo(null); toast("Tarefa restaurada");
      }
    }}>Desfazer</button></div>}
  </section>;
}

function AreaCards({ life, selectedDay, openArea }) {
  return <div className="area-grid">{AREAS.map((a) => {
    const progress = dailyProgress(life.state, selectedDay, a.id);
    return <button className="area-card" key={a.id} onClick={() => openArea(a.id)} style={{ "--area": a.cor }}>
      <span className="area-card-top"><span className="area-icon"><Icon name={a.icone}/></span><span className="area-code" aria-hidden="true">{a.id}</span></span>
      <strong>{a.nome}</strong><span className="area-reading" aria-hidden="true">{progress.total ? `${progress.done}/${progress.total}` : "—"}</span><small>{progress.total ? `${progress.done} de ${progress.total} tarefas` : "Sem tarefas ainda"}</small>
      <span className="area-progress"><i style={{ width: `${progress.pct}%` }}/></span>
    </button>;
  })}</div>;
}

export function Today({ life, selectedDay, setDay, ir, openArea, toast }) {
  const [form, setForm] = useState(false);
  const progress = dailyProgress(life.state, selectedDay);
  const weekday = new Date(`${selectedDay}T12:00:00`).getDay();
  const start = shiftDay(selectedDay, -((weekday + 6) % 7));
  const isToday = selectedDay === localDay();
  return <>
    <PageHeading overline={isToday ? "Rotina diária" : "Histórico da rotina"} title={isToday ? "Hoje" : "Seu dia"}
      description="Seu dia, em seis áreas da vida."/>
    <div className="week-strip" aria-label="Selecionar dia da semana">{Array.from({ length: 7 }, (_, i) => {
      const d = shiftDay(start, i), date = new Date(`${d}T12:00:00`);
      return <button key={d} aria-pressed={d === selectedDay} aria-label={date.toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" })}
        className={d === localDay() ? "actual-day" : ""} onClick={() => setDay(d)}>
        <small>{["D", "S", "T", "Q", "Q", "S", "S"][date.getDay()]}</small><strong>{date.getDate()}</strong><span className="day-dot"/>
      </button>;
    })}</div>
    <div className="date-controls"><button className="icon-button" aria-label="Semana anterior" onClick={() => setDay(shiftDay(selectedDay, -7))}><Icon name="back" size={18}/></button>
      <label>Dia <input type="date" aria-label="Data das tarefas" value={selectedDay} onChange={(e) => e.target.value && setDay(e.target.value)}/></label>
      <button className="icon-button" aria-label="Próxima semana" onClick={() => setDay(shiftDay(selectedDay, 7))}><Icon name="arrow" size={18}/></button>
      {!isToday && <button className="text-button" onClick={() => setDay(localDay())}>Hoje</button>}</div>
    <section className="day-summary"><div><div className="eyebrow">Progresso registrado</div><h2>{progress.total ? `${progress.done} de ${progress.total} tarefas feitas` : "Pronto para começar"}</h2>
      {!progress.total && <p>Adicione uma tarefa para acompanhar o dia.</p>}</div>
      <div className="daily-gauge"><div className="daily-value" aria-label={`${progress.pct}% das tarefas concluídas`}>{progress.total ? <>{progress.pct}<small>%</small></> : "—"}</div><div className="daily-track" aria-hidden="true"><i style={{ width: `${progress.pct}%` }}/></div><small>{progress.total ? "tarefas concluídas" : "sem tarefas ainda"}</small></div>
    </section>
    <Tasks life={life} selectedDay={selectedDay} add={() => setForm(true)} toast={toast}/>
    <div className="section-head outside"><h2>Suas áreas de vida</h2><button className="text-button" onClick={() => ir("vida")}>Explorar <Icon name="arrow" size={16}/></button></div>
    <AreaCards life={life} selectedDay={selectedDay} openArea={openArea}/>
    <button className="context-prompt" onClick={() => ir("contexto")}><span className="area-icon"><Icon name="context"/></span><span><strong>O celular também pode contar uma história</strong><small>Descubra quais sinais podem ajudar a entender sua rotina.</small></span><Icon name="arrow" size={18}/></button>
    {form && <TaskForm life={life} selectedDay={selectedDay} close={() => setForm(false)} toast={toast}/>}
  </>;
}

export function LifeAreas({ life, selectedDay, areaId, setArea, toast, ir }) {
  const [form, setForm] = useState(false);
  const tabs = useRef(null);
  const area = AREAS.find((a) => a.id === areaId) || AREAS[0];
  useEffect(() => {
    const row = tabs.current, active = row?.querySelector('[aria-pressed="true"]');
    if (active) row.scrollTo({ left: row.scrollLeft + active.getBoundingClientRect().left - row.getBoundingClientRect().left - (row.clientWidth - active.offsetWidth) / 2 });
  }, [area.id]);
  const plans = life.state.planos.filter((p) => p.atributo === area.id && !p.concluido);
  return <>
    <PageHeading code="02" overline="Seis áreas · uma vida" title="Vida" description="Você escolhe o que cultivar em cada uma."/>
    <div ref={tabs} className="area-tabs" aria-label="Áreas da vida">{AREAS.map((a) => <button key={a.id} aria-pressed={area.id === a.id} onClick={() => setArea(a.id)}><Icon name={a.icone} size={18}/>{a.nome}</button>)}</div>
    <section className="area-feature" style={{ "--area": area.cor }}><AreaBadge id={area.id}/><h2>{area.detalhe}</h2><p>{area.id === "OURO" ? "Suas escolhas financeiras também fazem parte da vida que você está construindo." : "Defina a sua intenção. Transforme-a em um passo possível para hoje."}</p>
      <div className="area-feature-stats"><span><b>{dailyProgress(life.state, selectedDay, area.id).total}</b> tarefas neste dia</span><span><b>{plans.length}</b> planos em andamento</span></div>
      {area.id === "OURO" && <button className="life-button" onClick={() => ir("visao")}>Abrir finanças <Icon name="arrow" size={17}/></button>}
    </section>
    {area.id === "INT" && <ReadingTracker toast={toast}/>}
    <Tasks key={area.id} life={life} area={area.id} selectedDay={selectedDay} add={() => setForm(true)} toast={toast}/>
    <section className="life-card"><div className="section-head"><h2>Para onde você quer ir</h2><button className="text-button" onClick={() => ir("projetos")}>Planos <Icon name="arrow" size={16}/></button></div>
      {plans.length ? plans.map((p) => <div className="area-plan" key={p.id}><strong>{p.titulo}</strong><small>{p.proximoPasso || "Escolha seu próximo passo na aba Planos."}</small></div>) : <p className="quiet-state">Um plano dá direção às pequenas escolhas. Crie o seu na aba Planos.</p>}
    </section>
    {form && <TaskForm life={life} area={area.id} selectedDay={selectedDay} close={() => setForm(false)} toast={toast}/>}
  </>;
}

function PlanForm({ life, plan, close, toast }) {
  const [draft, setDraft] = useState(plan || { id: newId(), titulo: "", atributo: "INT", porque: "", proximoPasso: "", prazo: "", concluido: false });
  const field = (key) => ({ value: draft[key], onChange: (e) => setDraft({ ...draft, [key]: e.target.value }) });
  return <Sheet title={plan ? "Seu plano, do seu jeito" : "Dê direção ao próximo capítulo"} close={close}>
    <form onSubmit={(e) => {
      e.preventDefault();
      if (!draft.titulo.trim() || !draft.porque.trim()) return;
      const value = { ...draft, titulo: draft.titulo.trim(), porque: draft.porque.trim(), proximoPasso: draft.proximoPasso.trim() };
      if (life.update((s) => ({ ...s, planos: plan ? s.planos.map((p) => p.id === plan.id ? value : p) : [...s.planos, value] }))) { toast("Plano salvo no aparelho"); close(); }
    }}>
      <label className="life-field">O que você quer realizar?<input required maxLength={180} autoFocus placeholder="Ex.: aprender um novo idioma" {...field("titulo")}/></label>
      <label className="life-field">Área<select {...field("atributo")}>{AREAS.map((a) => <option key={a.id} value={a.id}>{a.nome}</option>)}</select></label>
      <label className="life-field">Por que isso importa para você?<textarea required rows={3} maxLength={1000} placeholder="O motivo é seu. Guarde-o nas suas palavras." {...field("porque")}/></label>
      <label className="life-field">Qual é o próximo passo?<input maxLength={180} placeholder="Um passo pequeno e concreto" {...field("proximoPasso")}/></label>
      <label className="life-field">Um prazo, se fizer sentido<input type="date" {...field("prazo")}/></label>
      {life.issue && <p role="alert" className="form-error">{life.issue}</p>}
      <button className="life-button primary full" disabled={life.blocked}>Salvar plano <Icon name="check" size={18}/></button>
    </form>
  </Sheet>;
}

export function LifePlans({ life, toast, ir }) {
  const [editing, setEditing] = useState(null);
  const [filter, setFilter] = useState("ativos");
  const active = life.state.planos.filter((p) => !p.concluido);
  const shown = life.state.planos.filter((p) => filter === "todos" || !p.concluido);
  return <>
    <PageHeading code="04" overline="Direção e próximos passos" title="Planos" description="Um motivo para começar. Um próximo passo para continuar."
      action={<button className="life-button primary" onClick={() => setEditing("novo")} disabled={life.blocked}><Icon name="plus" size={18}/> Novo plano</button>}/>
    <div className="plan-summary"><Icon name="plans" size={24}/><span><b>{active.length}</b> {active.length === 1 ? "plano em andamento" : "planos em andamento"}</span><small>Sem precisar transformar tudo em dinheiro.</small></div>
    <div className="segmented plan-filter">{[["ativos", "Em andamento"], ["todos", "Todos os planos"]].map(([id, label]) => <button key={id} aria-pressed={filter === id} onClick={() => setFilter(id)}>{label}</button>)}</div>
    {shown.length === 0 ? <section className="life-card"><Empty icon="plans" title="O que você quer construir?"
      action={<button className="life-button" onClick={() => setEditing("novo")} disabled={life.blocked}>Criar meu primeiro plano</button>}>Pode ser uma viagem, um novo hábito ou uma mudança de carreira. O primeiro passo é dar um nome.</Empty></section>
      : <div className="plans-grid">{shown.map((p) => <article className={`life-card life-plan ${p.concluido ? "finished" : ""}`} key={p.id}>
        <div className="section-head"><AreaBadge id={p.atributo}/><span className="plan-status">{p.concluido ? "Concluído" : "Em andamento"}</span></div>
        <h2>{p.titulo}</h2><p>{p.porque}</p>
        {p.proximoPasso && <div className="next-step"><span className="eyebrow">Próximo passo</span><strong>{p.proximoPasso}</strong></div>}
        {p.prazo && <div className="plan-deadline"><Icon name="today" size={16}/> Até {new Date(`${p.prazo}T12:00:00`).toLocaleDateString("pt-BR")}</div>}
        <div className="plan-actions"><button className="text-button" disabled={life.blocked} onClick={() => setEditing(p)}>Editar</button><button className="life-button" disabled={life.blocked} onClick={() => life.update((s) => ({ ...s, planos: s.planos.map((v) => v.id === p.id ? { ...v, concluido: !v.concluido } : v) }))}>{p.concluido ? "Reabrir" : "Concluir"}<Icon name="check" size={16}/></button></div>
      </article>)}</div>}
    <button className="context-prompt" onClick={() => ir("planos")}><span className="area-icon"><Icon name="wallet"/></span><span><strong>Esse plano também envolve dinheiro?</strong><small>Cadastre a meta financeira para calcular aportes e prazos.</small></span><Icon name="arrow" size={18}/></button>
    {editing && <PlanForm life={life} plan={editing === "novo" ? null : editing} close={() => setEditing(null)} toast={toast}/>}
  </>;
}

const SOURCES = [
  { id: "uso", icon: "context", title: "Tempo por aplicativo", detail: "Quanto tempo vai para cada app e para a tela.", android: "Disponível em app nativo, com acesso a estatísticas de uso nas configurações.", ios: "Relatórios protegidos de Tempo de Uso. Acesso depende de autorização e recursos aprovados pela Apple." },
  { id: "saude", icon: "heart", title: "Passos, sono e atividade", detail: "Sinais para suas áreas de movimento e saúde.", android: "Health Connect ou sensor de passos, com permissão. Sono depende de uma fonte que registre esses dados.", ios: "HealthKit, com autorização por tipo de dado. Apple Watch e outros apps podem fornecer registros." },
  { id: "agenda", icon: "today", title: "Agenda e rotina", detail: "Tempo ocupado e janelas possíveis para os planos.", android: "Calendário com permissão de leitura, ou seleção manual.", ios: "Para ler eventos, EventKit exige acesso completo à agenda. Permissão apenas de escrita não permite consultar eventos." },
];

function UsageForm({ life, close, toast }) {
  const [app, setApp] = useState("");
  const [minutes, setMinutes] = useState("");
  const [date, setDate] = useState(localDay());
  return <Sheet title="Registrar tempo de uso" close={close}><p className="sheet-description">Consulte o Tempo de Uso ou Bem-estar Digital e registre o que você viu. A origem será manual.</p>
    <form onSubmit={(e) => {
      e.preventDefault();
      const number = Number(minutes);
      if (!app.trim() || !date || minutes === "" || !Number.isInteger(number) || number < 0 || number > 1440) return;
      // Um app por dia: corrigir o valor substitui a anotação anterior.
      if (life.update((s) => ({ ...s, medidas: [...s.medidas.filter((m) => !(m.dia === date && m.app.toLocaleLowerCase() === app.trim().toLocaleLowerCase())),
        { id: newId(), dia: date, app: app.trim(), minutos: number, origem: "usuario" }] }))) { toast("Tempo registrado no aparelho"); close(); }
    }}>
      <label className="life-field">Aplicativo<input required autoFocus maxLength={100} placeholder="Nome do app" value={app} onChange={(e) => setApp(e.target.value)}/></label>
      <label className="life-field">Minutos de uso<input type="number" inputMode="numeric" min="0" max="1440" step="1" required value={minutes} onChange={(e) => setMinutes(e.target.value)}/></label>
      <label className="life-field">Dia<input type="date" required value={date} onChange={(e) => setDate(e.target.value)}/></label>
      {life.issue && <p role="alert" className="form-error">{life.issue}</p>}
      <button className="life-button primary full" disabled={life.blocked}>Salvar registro <Icon name="check" size={18}/></button>
    </form></Sheet>;
}

export function PhoneContext({ life, toast }) {
  const [platform, setPlatform] = useState("android");
  const [form, setForm] = useState(false);
  const [date, setDate] = useState(localDay());
  const data = life.state.medidas.filter((m) => m.dia === date).sort((a, b) => b.minutos - a.minutos);
  const largest = Math.max(...data.map((m) => m.minutos), 1);
  const backup = () => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY) || JSON.stringify(life.state);
      const url = URL.createObjectURL(new Blob([raw], { type: "application/json" }));
      const link = document.createElement("a"); link.href = url; link.download = `fintips-vida-${localDay()}.json`; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      toast("Cópia local criada. Guarde-a com cuidado.");
    } catch { toast("Não foi possível criar a cópia local."); }
  };
  return <>
    <PageHeading code="05" overline="Sinais da rotina" title="Contexto" description="O que seu celular pode contar, sob seu controle."/>
    <section className="privacy-card"><span className="privacy-icon"><Icon name="lock" size={24}/></span><div><h2>Seus dados ficam com você</h2><p>Tarefas, planos e registros desta tela ficam neste navegador. A coleta automática e a conexão com ChatGPT ainda não estão ativas.</p></div></section>
    <section className="life-card"><div className="section-head"><h2>Seu tempo de tela</h2><span className="manual-tag">Registro manual</span></div>
      <label className="usage-date">Dia do registro<input type="date" value={date} onChange={(e) => e.target.value && setDate(e.target.value)}/></label>
      {!data.length ? <Empty icon="clock" title="Antes de concluir, observe">Registre o tempo que aparece nas configurações do celular. Não temos acesso automático aos seus apps nesta versão.</Empty>
        : <div className="usage-list">{data.map((m) => <div className="usage-row" key={m.id}><div><strong>{m.app}</strong><span>{m.minutos} min</span></div><div className="usage-track"><i style={{ width: `${m.minutos / largest * 100}%` }}/></div><small>Informado por você</small><button className="icon-button" disabled={life.blocked} aria-label={`Excluir registro de ${m.app}`} onClick={() => life.update((s) => ({ ...s, medidas: s.medidas.filter((v) => v.id !== m.id) }))}><Icon name="trash" size={16}/></button></div>)}</div>}
      <button className="life-button full" disabled={life.blocked} onClick={() => setForm(true)}><Icon name="plus" size={18}/> Registrar tempo de uso</button>
    </section>
    <div className="section-head outside"><h2>Fontes que podemos conectar</h2><span className="small-note">Em estudo</span></div>
    <div className="segmented platform-switch">{[["android", "Android"], ["ios", "iPhone"]].map(([id, label]) => <button key={id} aria-pressed={platform === id} onClick={() => setPlatform(id)}>{label}</button>)}</div>
    <div className="source-grid">{SOURCES.map((s) => <article key={s.id} className="life-card source-card"><div className="section-head"><span className="area-icon"><Icon name={s.icon}/></span><span className="manual-tag">Ainda não conectado</span></div><h3>{s.title}</h3><p>{s.detail}</p><div className="source-detail">{s[platform]}</div></article>)}</div>
    <section className="life-card backup-card"><div><h2>Uma cópia dos seus registros</h2><p>O arquivo contém seus dados pessoais. Guarde-o no aparelho. Limpar os dados do navegador pode apagar seus registros.</p></div><button className="life-button" onClick={backup}>Baixar cópia local</button></section>
    {form && <UsageForm life={life} close={() => setForm(false)} toast={toast}/>}
  </>;
}

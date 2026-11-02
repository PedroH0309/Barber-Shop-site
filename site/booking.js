(() => {
  'use strict';
  const $ = s => document.querySelector(s);
  const fmt = v => new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(v);
  const nowSP = () => {
    const p = new Intl.DateTimeFormat('en-US',{timeZone:'America/Sao_Paulo',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date());
    const obj = Object.fromEntries(p.map(x=>[x.type,x.value]));
    return `${obj.year}-${obj.month}-${obj.day}`;
  };
  const fromISO = str => new Date(`${str}T12:00:00Z`);
  const niceDate = str => new Intl.DateTimeFormat('pt-BR',{timeZone:'UTC',weekday:'long',day:'numeric',month:'long'}).format(fromISO(str));
  const isoDate = d => d.toISOString().slice(0,10);
  async function api(path,options={}) {
    let response;
    try {response=await fetch('/api/public/'+path,{headers:{'Content-Type':'application/json'},cache:'no-store',...options});}
    catch {throw new Error('Não foi possível conectar ao servidor. Tente novamente.');}
    const data=await response.json().catch(()=>({}));
    if (!response.ok) {const err=new Error(typeof data.detail==='string'?data.detail:'Ocorreu um erro.');err.status=response.status;throw err;}
    return data;
  }
  const state={services:[],plans:[],service:null,day:null,time:null,step:0,config:null,month:null,maxDays:45,slotRequest:0,bookingToken:null,pollTimer:null};
  function notify(text){const notice=$('#demo-notice');notice.textContent=text;notice.hidden=false;}
  function step(n){
    state.step=n;
    ['service','calendar','details','success'].forEach((name,i)=>$('#panel-'+name).hidden!==undefined && ($('#panel-'+name).hidden=i!==n));
    document.querySelectorAll('.step-indicator').forEach((btn,i)=>{btn.classList.toggle('current',i===n);btn.classList.toggle('past',i<n);btn.disabled=i>n||n===3;});
    if(n===2) updateSummary();
    window.scrollTo({top:0,behavior:'smooth'});
  }
  function renderServices(){
    const grid=$('#service-grid');grid.replaceChildren();
    if(!state.services.length){grid.innerHTML='<p class="empty">Nenhum serviço disponível no momento.</p>';return;}
    state.services.forEach(service=>{
      const button=document.createElement('button');button.type='button';button.className='service-option';button.setAttribute('aria-pressed',String(state.service?.id===service.id));
      button.innerHTML=`<img src="${safeImage(service.image)}" alt="" loading="lazy"><span class="service-text"><h3></h3><p></p><span class="service-foot"><span class="service-price"></span><span class="duration"></span></span></span><span class="selected-dot">✓</span>`;
      button.querySelector('h3').textContent=service.name;
      button.querySelector('p').textContent=service.description;
      button.querySelector('.service-price').textContent=fmt(service.price);
      button.querySelector('.duration').textContent=`${service.duration_min} MIN`;
      button.classList.toggle('selected',state.service?.id===service.id);
      button.addEventListener('click',()=>{
        if(state.service?.id!==service.id){state.day=null;state.time=null;}
        state.service=service;renderServices();$('#to-calendar').disabled=false;
        $('#chosen-service').textContent=`${service.name} · ${service.duration_min} min · ${fmt(service.price)}`;
      });
      grid.append(button);
    });
  }
  function safeImage(path){return /^\/(?:assets|uploads)\/[\w.\-\/]+$/.test(path||'')?path:'/assets/section-standard.jpg';}
  function renderPlans(){
    const wrap=$('#plans-wrap'), grid=$('#plans-grid');grid.replaceChildren();wrap.hidden=!state.plans.length;
    for (const plan of state.plans){
      const el=document.createElement('article');el.className='plan-card';
      const title=document.createElement('strong');title.textContent=plan.name;
      const price=document.createElement('b');price.textContent=`${fmt(plan.price)} / ${plan.period}`;
      const desc=document.createElement('p');desc.textContent=plan.description;
      el.append(title,price,desc);
      if(plan.benefits){const ul=document.createElement('ul');for(const benefit of plan.benefits.split('\n').filter(Boolean)){const li=document.createElement('li');li.textContent=benefit;ul.append(li);}el.append(ul);}
      grid.append(el);
    }
  }
  function renderCalendar(){
    const today=nowSP();if(!state.month)state.month=today.slice(0,7);
    const [yr,month]=state.month.split('-').map(Number);
    const first=new Date(Date.UTC(yr,month-1,1));
    const grid=$('#date-grid');grid.replaceChildren();
    $('#month-label').textContent=new Intl.DateTimeFormat('pt-BR',{timeZone:'UTC',month:'long',year:'numeric'}).format(first);
    const startOffset=first.getUTCDay();
    const days=new Date(Date.UTC(yr,month,0)).getUTCDate();
    const max=isoDate(new Date(fromISO(today).getTime()+state.maxDays*86400000));
    for(let i=0;i<startOffset;i++) grid.append(document.createElement('span'));
    for(let d=1;d<=days;d++){
      const day=isoDate(new Date(Date.UTC(yr,month-1,d)));
      const btn=document.createElement('button');btn.type='button';btn.textContent=String(d);btn.setAttribute('aria-label',niceDate(day));
      btn.disabled=day<today||day>max;
      btn.classList.toggle('selected',day===state.day);
      btn.classList.toggle('today',day===today);
      btn.addEventListener('click',()=>selectDay(day));grid.append(btn);
    }
    const minMonth=today.slice(0,7),maxMonth=max.slice(0,7);
    $('#month-prev').disabled=state.month<=minMonth;$('#month-next').disabled=state.month>=maxMonth;
    $('#to-details').disabled=!state.time;
  }
  async function selectDay(day){
    state.day=day;const previousTime=state.time;state.time=null;renderCalendar();
    $('#refresh-slots').hidden=false;
    $('#selected-day-label').textContent=niceDate(day);
    $('#to-details').disabled=true;
    const grid=$('#times-grid');grid.innerHTML='<p class="empty">Consultando horários disponíveis…</p>';
    const req=++state.slotRequest;
    try{
      const data=await api(`slots?service_id=${state.service.id}&day=${encodeURIComponent(day)}`);
      if(req!==state.slotRequest)return;
      grid.replaceChildren();
      if(!data.slots.length){grid.innerHTML=data.published?'<p class="empty">Nenhum horário disponível nesta data. Escolha outro dia ou confira o expediente da barbearia.</p>':'<p class="empty">Agenda ainda não publicada pelo barbeiro. Não é possível reservar horários.</p>';return;}
      for(const hour of data.slots){
        const btn=document.createElement('button');btn.type='button';btn.textContent=hour;
        btn.addEventListener('click',()=>{state.time=hour;grid.querySelectorAll('button').forEach(x=>x.classList.toggle('selected',x===btn));$('#to-details').disabled=false;});
        if(hour===previousTime){state.time=hour;btn.classList.add('selected');$('#to-details').disabled=false;}
        grid.append(btn);
      }
    }catch(err){if(req===state.slotRequest){grid.textContent=err.message;}}
  }
  function changeMonth(diff){
    const [y,m]=state.month.split('-').map(Number);
    const d=new Date(Date.UTC(y,m-1+diff,1));state.month=d.toISOString().slice(0,7);renderCalendar();
  }
  function updateSummary(){const s=state.service;
    $('#summary-service').textContent=s.name;$('#summary-date').textContent=niceDate(state.day);
    $('#summary-time').textContent=state.time;$('#summary-duration').textContent=`${s.duration_min} min`;
    $('#summary-price').textContent=fmt(s.price);
  }
  async function submit(event){
    event.preventDefault();const error=$('#booking-error');error.hidden=true;
    const name=$('#full-name').value.trim().replace(/\s+/g,' '),phone=$('#phone').value.trim();
    if(name.split(' ').length<2||name.length<5){error.textContent='Informe seu nome completo.';error.hidden=false;return;}
    if(phone.replace(/\D/g,'').length<10){error.textContent='Informe o número de WhatsApp com DDD.';error.hidden=false;return;}
    const btn=$('#confirm-booking');btn.disabled=true;btn.textContent='RESERVANDO…';
    try{
      const data=await api('bookings',{method:'POST',body:JSON.stringify({service_id:state.service.id,day:state.day,time:state.time,name,phone,consent_whatsapp:$('#consent').checked})});
      $('#done-service').textContent=data.service;$('#done-date').textContent=niceDate(state.day);
      $('#done-time').textContent=`${state.time} · ${state.service.duration_min} minutos · ${fmt(data.price)}`;
      state.bookingToken=data.token;
      history.replaceState(null,'','/agendar?reserva='+encodeURIComponent(data.token));
      step(3);
      await refreshBookingStatus();
      startPolling();
    }catch(err){
      error.hidden=false;error.textContent=err.message;
      if(err.status===409){setTimeout(()=>{step(1);selectDay(state.day);},2200);}
    }finally{btn.disabled=false;btn.innerHTML='SOLICITAR HORÁRIO <span>↗</span>';}
  }
  const statusText={pendente:'PENDENTE DE APROVAÇÃO',aprovado:'APROVADO PELO BARBEIRO',confirmado:'PRESENÇA CONFIRMADA',recusado:'SOLICITAÇÃO RECUSADA',cancelado:'AGENDAMENTO CANCELADO',concluido:'ATENDIMENTO CONCLUÍDO',nao_compareceu:'NÃO COMPARECEU'};
  const statusCopy={
    pendente:'Sua solicitação chegou ao barbeiro. O horário está bloqueado para outras pessoas até que ele aprove ou recuse. Volte a este link para conferir.',
    aprovado:'O barbeiro aprovou o horário! Agora você pode adicioná-lo ao Google Agenda ou ao calendário do iPhone.',
    confirmado:'Seu horário foi aprovado e sua presença foi confirmada. Você pode salvar o evento na agenda.',
    recusado:'O barbeiro não pôde aceitar este pedido. O horário foi liberado e você pode solicitar outro.',
    cancelado:'Esta reserva foi cancelada e o horário foi liberado. Você pode solicitar outro.',
    concluido:'Seu atendimento foi concluído.',
    nao_compareceu:'Este atendimento foi registrado como não comparecimento.'
  };
  async function refreshBookingStatus(){
    if(!state.bookingToken)return;
    const status=await api('bookings/'+encodeURIComponent(state.bookingToken));
    const can=status.can_add_calendar;
    $('#result-title').innerHTML=can?'HORÁRIO <em>APROVADO.</em>':
      status.status==='pendente'?'AGUARDANDO <em>APROVAÇÃO.</em>':'SITUAÇÃO <em>ATUALIZADA.</em>';
    $('#result-message').textContent=statusCopy[status.status]||'Situação atualizada.';
    $('#booking-status-badge').textContent=statusText[status.status]||status.status;
    $('#done-service').textContent=status.service;
    $('#done-date').textContent=niceDate(status.start.slice(0,10));
    $('#done-time').textContent=`${status.start.slice(11,16)} · ${status.duration_min} minutos · ${fmt(status.price)}`;
    $('#calendar-actions').hidden=!can;
    $('#calendar-note').hidden=!can;
    if(can){$('#google-calendar').href=status.google_url;$('#apple-calendar').href=status.ics_url;}
    else{$('#google-calendar').removeAttribute('href');$('#apple-calendar').removeAttribute('href');}
    return status;
  }
  function startPolling(){
    clearInterval(state.pollTimer);
    state.pollTimer=setInterval(async()=>{
      if(state.step!==3||document.hidden)return;
      try{await refreshBookingStatus();}catch(e){console.warn('Não foi possível atualizar a situação da reserva.');}
    },30000);
  }
  async function loadTrackedBooking(){
    const token=new URLSearchParams(location.search).get('reserva');
    if(!token)return;
    state.bookingToken=token;
    try{await refreshBookingStatus();step(3);startPolling();}
    catch(e){state.bookingToken=null;notify('Não foi possível consultar essa reserva. Verifique se o link está completo.');}
  }
  async function init(){
    try{state.config=await api('config');state.services=state.config.services;state.plans=state.config.plans;
      state.maxDays=state.config.advance_days;document.title=`Agendar — ${state.config.business_name}`;
      renderServices();renderPlans();if(!state.config.published)notify('Agenda em configuração. Os preços exibidos são exemplos e novos agendamentos ainda estão desativados.');
    }catch(e){notify(e.message);$('#service-grid').textContent='Não foi possível carregar os serviços.';}
    document.querySelectorAll('[data-step-nav]').forEach(b=>b.addEventListener('click',()=>{const n=Number(b.dataset.stepNav);if(n<3&&n<state.step)step(n);}));
    $('#to-calendar').addEventListener('click',()=>{if(!state.service)return;step(1);renderCalendar();if(state.day)selectDay(state.day);});
    $('#to-details').addEventListener('click',()=>{if(state.day&&state.time)step(2);});
    $('#back-to-service').addEventListener('click',()=>step(0));$('#back-to-calendar').addEventListener('click',()=>step(1));
    $('#month-prev').addEventListener('click',()=>changeMonth(-1));$('#month-next').addEventListener('click',()=>changeMonth(1));
    $('#refresh-slots').addEventListener('click',()=>{if(state.day&&state.service)selectDay(state.day);});
    $('#booking-form').addEventListener('submit',submit);
    $('#refresh-booking').addEventListener('click',async()=>{try{await refreshBookingStatus();}catch(e){notify(e.message);}});
    $('#copy-booking-link').addEventListener('click',async()=>{try{await navigator.clipboard.writeText(location.href);$('#copy-booking-link').textContent='LINK COPIADO ✓';}catch{notify('Copie o endereço do navegador para guardar sua reserva.');}});
    await loadTrackedBooking();
  }
  init();
})();

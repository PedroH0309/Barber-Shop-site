(() => {
  'use strict';
  const $=s=>document.querySelector(s);
  const state={csrf:'',services:[],plans:[],tab:'dashboard',mode:null,editId:null,bookings:[],clients:[],username:''};
  const money=n=>new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(n/100);
  const escapeHtml=s=>String(s??'').replace(/[&<>"']/g,x=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[x]));
  const dateSP=()=>{const p=new Intl.DateTimeFormat('en-US',{timeZone:'America/Sao_Paulo',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date());const o=Object.fromEntries(p.map(x=>[x.type,x.value]));return `${o.year}-${o.month}-${o.day}`;};
  const addDays=(str,n)=>{const d=new Date(str+'T12:00:00Z');d.setUTCDate(d.getUTCDate()+n);return d.toISOString().slice(0,10);};
  const weekdayNames=['Dom','Seg','Ter','Qua','Qui','Sex','Sáb'];
  const dateLabel=v=>new Intl.DateTimeFormat('pt-BR',{day:'2-digit',month:'2-digit',year:'numeric',timeZone:'UTC'}).format(new Date(v+'T12:00:00Z'));
  async function api(path,opts={}){
    let response;
    const headers={...opts.headers};
    if(!(opts.body instanceof FormData) && opts.body)headers['Content-Type']='application/json';
    if(opts.method && opts.method!=='GET' && state.csrf)headers['X-CSRF-Token']=state.csrf;
    try{response=await fetch('/api/admin/'+path,{credentials:'same-origin',cache:'no-store',...opts,headers});}
    catch {throw new Error('Falha de conexão com o servidor.');}
    const data=await response.json().catch(()=>({}));
    if(!response.ok){if(response.status===401)showLogin();throw new Error(typeof data.detail==='string'?data.detail:'Não foi possível completar a operação.');}
    return data;
  }
  function flash(msg,error=false){const box=$('#flash');box.hidden=false;box.textContent=msg;box.classList.toggle('error',error);clearTimeout(flash.timer);flash.timer=setTimeout(()=>box.hidden=true,7000);}
  function showLogin(){$('#login-screen').hidden=false;$('#workspace').hidden=true;state.csrf='';state.bookings=[];state.clients=[];}
  function showApp(){$('#login-screen').hidden=true;$('#workspace').hidden=false;}
  async function boot(){
    $('#dashboard-date').value=dateSP();$('#bookings-from').value=dateSP();$('#bookings-to').value=addDays(dateSP(),30);$('#block-day').min=dateSP();$('#block-day').value=dateSP();
    try{const session=await api('me');state.csrf=session.csrf;state.username=session.username||'barbeiro';showApp();await changeTab('dashboard');}catch{showLogin();}
  }
  async function login(event){event.preventDefault();$('#login-error').textContent='';
    const btn=$('#login-form button');btn.disabled=true;$('#login-error').classList.remove('success');
    try{const result=await api('login',{method:'POST',body:JSON.stringify({username:$('#login-user').value.trim(),password:$('#login-pass').value})});state.csrf=result.csrf;state.username=$('#login-user').value.trim();$('#login-pass').value='';showApp();await changeTab('dashboard');}
    catch(err){$('#login-error').textContent=err.message;}
    finally{btn.disabled=false;}
  }
  async function changeTab(name){
    state.tab=name;
    document.querySelectorAll('.tab-view').forEach(x=>x.hidden=x.id!=='tab-'+name);
    document.querySelectorAll('[data-tab]').forEach(x=>x.classList.toggle('active',x.dataset.tab===name));
    $('#section-name').textContent=({dashboard:'Visão geral',bookings:'Agendamentos',clients:'Clientes',services:'Serviços e fotos',plans:'Planos',schedule:'Meus horários',settings:'Configurações'})[name];
    try{
      if(name==='dashboard')await loadDashboard();
      if(name==='bookings')await loadBookings();
      if(name==='clients')await loadClients();
      if(name==='services')await loadServices();
      if(name==='plans')await loadPlans();
      if(name==='schedule')await loadSchedule();
      if(name==='settings')await loadSettings();
    }catch(err){flash(err.message,true);}
    window.scrollTo({top:0,behavior:'auto'});
  }
  const statusNames={pendente:'Pendente',aprovado:'Aprovado',confirmado:'Presença confirmada',recusado:'Recusado',cancelado:'Cancelado',concluido:'Concluído',nao_compareceu:'Não compareceu'};
  function statusLabel(s){return statusNames[s]||s;}
  async function setBookingStatus(b,next){
    if(next==='recusado'&&!confirm(`Recusar a solicitação de ${b.name}? O horário ficará livre novamente.`))return;
    if(next==='cancelado'&&!confirm(`Cancelar a reserva de ${b.name}?`))return;
    try{
      await api(`bookings/${b.id}`,{method:'PATCH',body:JSON.stringify({status:next})});
      flash(next==='aprovado'?'Reserva aprovada. O cliente já pode consultar e adicionar ao calendário.':
            next==='recusado'?'Solicitação recusada; horário liberado.':'Situação atualizada.');
      if(state.tab==='bookings')await loadBookings();
      else if(state.tab==='dashboard')await loadDashboard();
    }catch(e){flash(e.message,true);if(state.tab==='bookings')await loadBookings();}
  }
  async function copyCustomerNotice(b){
    const date=dateLabel(b.start.slice(0,10));
    const hour=b.start.slice(11,16);
    const first=b.name.split(' ')[0];
    const base=`Olá, ${first}! Aqui é da barbearia. `;
    const msg=b.status==='aprovado'||b.status==='confirmado'
      ?base+`Seu pedido para ${b.service} no dia ${date} às ${hour} foi aprovado. Até lá!`
      :base+`Sobre o pedido de ${b.service} para ${date} às ${hour}: não foi possível confirmar esse horário. Você pode solicitar outro pela nossa agenda online.`;
    try{await navigator.clipboard.writeText(msg);flash('Mensagem copiada. Cole e envie manualmente pelo seu WhatsApp, se apropriado.');}
    catch{window.prompt('Copie esta mensagem para enviar manualmente:',msg);}
  }
  function approvalActions(b){
    const wrap=document.createElement('div');wrap.className='approval-actions';
    if(b.status==='pendente'){
      const approve=button('✓ APROVAR',()=>setBookingStatus(b,'aprovado'));approve.className='small-btn approve-btn';
      const reject=button('✕ RECUSAR',()=>setBookingStatus(b,'recusado'));reject.className='small-btn reject-btn';
      wrap.append(approve,reject);
    }else if(['aprovado','confirmado'].includes(b.status)){
      const select=document.createElement('select');select.setAttribute('aria-label','Atualizar '+b.name);
      for(const [value,label] of [['','OUTRA AÇÃO'],['confirmado','Presença confirmada'],['concluido','Concluído'],['nao_compareceu','Não compareceu'],['cancelado','Cancelar']]){
        if(value===b.status)continue;
        const option=document.createElement('option');option.value=value;option.textContent=label;select.append(option);
      }
      select.addEventListener('change',()=>{if(select.value)setBookingStatus(b,select.value);});wrap.append(select);
    }else{
      const tag=document.createElement('span');tag.className='muted-note';tag.textContent='Finalizado';wrap.append(tag);
    }
    if(['aprovado','confirmado','recusado'].includes(b.status)){
      const copy=button('COPIAR AVISO',()=>copyCustomerNotice(b));copy.className='small-btn';wrap.append(copy);
    }
    return wrap;
  }
  async function loadPending(){
    const data=await api('pending');const list=$('#pending-bookings');list.replaceChildren();
    $('#pending-side-count').textContent=data.bookings.length?String(data.bookings.length):'';
    if(!data.bookings.length){list.innerHTML='<p class="helper">Nenhuma solicitação aguardando aprovação.</p>';return;}
    for(const b of data.bookings){
      const item=document.createElement('article');item.className='pending-card';
      const info=document.createElement('div');
      const when=document.createElement('strong');when.textContent=`${dateLabel(b.start.slice(0,10))} · ${b.start.slice(11,16)}`;
      const name=document.createElement('p');name.textContent=`${b.name} — ${b.service}`;
      const phone=document.createElement('small');phone.textContent=b.phone;
      info.append(when,name,phone);item.append(info,approvalActions(b));list.append(item);
    }
  }
  async function loadDashboard(){
    const data=await api('overview?day='+encodeURIComponent($('#dashboard-date').value));
    $('#stat-today').textContent=data.day_count;$('#stat-future').textContent=data.all_future;
    $('#stat-pending').textContent=data.pending_count;await loadPending();
    $('#stat-revenue').textContent=new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(data.day_revenue);
    const list=$('#dashboard-bookings');list.replaceChildren();
    if(!data.bookings.length){list.innerHTML='<p class="helper">Nenhum agendamento neste dia.</p>';return;}
    for(const b of data.bookings){const item=document.createElement('div');item.className='booking-item';
      item.innerHTML=`<div class="booking-hour">${escapeHtml(b.start.slice(11,16))}</div><div><b>${escapeHtml(b.name)}</b><small>${escapeHtml(b.service)} · ${escapeHtml(b.phone)}</small></div><span class="pill ${escapeHtml(b.status)}">${escapeHtml(statusLabel(b.status))}</span>`;
      list.append(item);
    }
  }
  async function loadBookings(){
    const result=await api(`bookings?from_date=${encodeURIComponent($('#bookings-from').value)}&to_date=${encodeURIComponent($('#bookings-to').value)}`);
    state.bookings=result.bookings;renderBookings();
  }
  function filteredBookings(){
    const term=$('#bookings-search').value.trim().toLocaleLowerCase('pt-BR');
    const status=$('#bookings-status').value;
    return state.bookings.filter(b=>(!status||b.status===status)&&(!term||`${b.name} ${b.phone} ${b.service}`.toLocaleLowerCase('pt-BR').includes(term)));
  }
  function renderBookings(){
    const data=filteredBookings();const tbody=$('#bookings-body');tbody.replaceChildren();
    $('#bookings-count').textContent=`${data.length} de ${state.bookings.length} agendamento(s) no período selecionado.`;
    if(!data.length){tbody.innerHTML='<tr><td colspan="6">Nenhuma reserva encontrada com os filtros atuais.</td></tr>';return;}
    for (const b of data){
      const tr=document.createElement('tr');
      tr.innerHTML=`<td><b>${dateLabel(b.start.slice(0,10))}</b><small>${escapeHtml(b.start.slice(11,16))}–${escapeHtml(b.end.slice(11,16))}</small></td><td><b>${escapeHtml(b.name)}</b><small>${escapeHtml(b.phone)}</small></td><td>${escapeHtml(b.service)}</td><td>${money(Math.round(b.price*100))}</td><td><span class="pill ${escapeHtml(b.status)}">${escapeHtml(statusLabel(b.status))}</span></td>`;
      const td=document.createElement('td');td.append(approvalActions(b));const hist=button('HISTÓRICO',()=>showBookingHistory(b.id));hist.className='small-btn';td.append(hist);tr.append(td);tbody.append(tr);
    }
  }
  async function showBookingHistory(id){
    try{
      const data=await api(`bookings/${id}/history`);
      const box=$('#history-content');box.replaceChildren();
      const info=document.createElement('p');info.className='helper';info.textContent=`${data.booking.name} · ${data.booking.service} · ${dateLabel(data.booking.start.slice(0,10))} às ${data.booking.start.slice(11,16)}`;box.append(info);
      if(!data.events.length){const empty=document.createElement('p');empty.className='helper';empty.textContent='Ainda não há mudanças de status registradas para esta solicitação.';box.append(empty);}
      for(const ev of data.events){const row=document.createElement('div');row.className='audit-item';const when=document.createElement('small');when.textContent=ev.occurred_at.replace('T',' ').slice(0,19);const label=document.createElement('strong');label.textContent=`${statusLabel(ev.old_status)} → ${statusLabel(ev.new_status)}`;const who=document.createElement('span');who.textContent=`Alterado por: ${ev.actor==='barbeiro'?'Barbeiro':ev.actor==='whatsapp'?'Confirmação via WhatsApp':'Sistema'}`;row.append(when,label,who);box.append(row);}
      $('#history-dialog').showModal();
    }catch(e){flash(e.message,true);}
  }
  function csvCell(value){const v=String(value??'');const safe=/^[\s]*[=+@-]/.test(v)?"'"+v:v;return '"'+safe.replace(/"/g,'""')+'"';}
  function exportBookings(){
    const rows=filteredBookings();if(!rows.length){flash('Não existem agendamentos para exportar.',true);return;}
    const header=['Data','Início','Fim','Cliente','Telefone','Serviço','Valor (R$)','Situação'];
    const csv=[header,...rows.map(b=>[b.start.slice(0,10),b.start.slice(11,16),b.end.slice(11,16),b.name,b.phone,b.service,b.price.toFixed(2).replace('.',','),statusLabel(b.status)])].map(x=>x.map(csvCell).join(';')).join('\r\n');
    const blob=new Blob(['\ufeff'+csv],{type:'text/csv;charset=utf-8'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=`precision-agenda-${$('#bookings-from').value}-${$('#bookings-to').value}.csv`;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
    flash('Arquivo CSV exportado. Ele contém dados pessoais: mantenha-o privado.');
  }
  async function changeCredentials(e){
    e.preventDefault();const password=$('#credentials-new').value;
    if(password!==$('#credentials-confirm').value){flash('As novas senhas não coincidem.',true);return;}
    try{
      const result=await api('credentials',{method:'PUT',body:JSON.stringify({username:$('#credentials-username').value.trim(),current_password:$('#credentials-current').value,new_password:password})});
      $('#credentials-form').reset();showLogin();$('#login-user').value='';$('#login-error').textContent=result.message;$('#login-error').classList.add('success');
    }catch(err){flash(err.message,true);}
  }
  async function loadClients(){
    const data=await api('clients');state.clients=data.clients;
    $('#clients-total').textContent=data.total;
    $('#clients-returning').textContent=data.returning;
    $('#clients-attendances').textContent=data.attendances;
    renderClients();
  }
  function renderClients(){
    const term=$('#clients-search').value.trim().toLocaleLowerCase('pt-BR');
    const clients=state.clients.filter(c=>!term||`${c.name} ${c.phone}`.toLocaleLowerCase('pt-BR').includes(term));
    $('#clients-count').textContent=`${clients.length} de ${state.clients.length} cliente(s).`;
    const body=$('#clients-body');body.replaceChildren();
    if(!clients.length){body.innerHTML='<tr><td colspan="6">Nenhum cliente encontrado.</td></tr>';return;}
    for(const c of clients){
      const tr=document.createElement('tr');
      const last=c.last_service?dateLabel(c.last_service.slice(0,10)):'—';
      const next=c.next_service?`${dateLabel(c.next_service.slice(0,10))} · ${c.next_service.slice(11,16)}`:'—';
      tr.innerHTML=`<td><b>${escapeHtml(c.name)}</b></td><td>${escapeHtml(c.phone)}</td><td>${c.reservations}</td><td>${c.completed}</td><td>${escapeHtml(last)}</td><td>${escapeHtml(next)}</td>`;
      body.append(tr);
    }
  }
  async function loadServices(){
    const data=await api('services');state.services=data.services;const grid=$('#service-admin-grid');grid.replaceChildren();
    for(const s of data.services){
      const card=document.createElement('article');card.className='editable-card';
      const image=s.image&&/^\/(?:assets|uploads)\/[-\w./]+$/.test(s.image)?s.image:'/assets/section-standard.jpg';
      card.innerHTML=`<img src="${image}" alt=""><div class="editable-content"><h3>${escapeHtml(s.name)}</h3><p>${escapeHtml(s.description)}</p><div class="editable-meta"><b>${money(s.price_cents)}</b><span>${s.duration_min} MIN · ${s.active?'ATIVO':'OCULTO'}</span></div><div class="editable-buttons"></div></div>`;
      const actions=card.querySelector('.editable-buttons');
      const edit=button('EDITAR',()=>openEditor('service',s.id));
      const photo=button('ALTERAR FOTO',()=>uploadPrompt(s.id));
      const toggle=button(s.active?'OCULTAR':'ATIVAR',async()=>{try{await api(`services/${s.id}`,{method:'PUT',body:JSON.stringify({...s,active:!s.active})});await loadServices();flash('Serviço atualizado.');}catch(e){flash(e.message,true);}});
      actions.append(edit,photo,toggle);grid.append(card);
    }
  }
  const button=(text,fn)=>{const b=document.createElement('button');b.type='button';b.textContent=text;b.addEventListener('click',fn);return b;};
  async function uploadPrompt(id){
    const picker=document.createElement('input');picker.type='file';picker.accept='image/png,image/jpeg,image/webp';
    picker.addEventListener('change',async()=>{
      if(!picker.files?.[0])return;
      const data=new FormData();data.append('image',picker.files[0]);
      try{await api(`services/${id}/photo`,{method:'POST',body:data});flash('Foto atualizada.');await loadServices();}
      catch(e){flash(e.message,true);}
    });picker.click();
  }
  async function loadPlans(){
    const data=await api('plans');state.plans=data.plans;const grid=$('#plan-admin-grid');grid.replaceChildren();
    if(!data.plans.length){grid.innerHTML='<p class="helper">Ainda não há planos cadastrados. Clique em “Novo plano”.</p>';return;}
    for(const p of data.plans){const card=document.createElement('article');card.className='editable-card';
      card.innerHTML=`<div class="editable-content"><div class="tiny">${escapeHtml(p.period)} · ${p.active?'VISÍVEL':'OCULTO'}</div><h3 style="margin-top:13px">${escapeHtml(p.name)}</h3><p>${escapeHtml(p.description)}</p><div class="editable-meta"><b>${money(p.price_cents)}</b><span>${escapeHtml(p.period)}</span></div><div class="editable-buttons"></div></div>`;
      const actions=card.querySelector('.editable-buttons');
      actions.append(button('EDITAR',()=>openEditor('plan',p.id)),button(p.active?'OCULTAR':'ATIVAR',async()=>{try{await api(`plans/${p.id}`,{method:'PUT',body:JSON.stringify({...p,active:!p.active})});await loadPlans();flash('Plano atualizado.');}catch(e){flash(e.message,true);}}));grid.append(card);
    }
  }
  function openEditor(type,id=null){state.mode=type;state.editId=id;
    const existing=type==='service'?state.services.find(x=>x.id===id):state.plans.find(x=>x.id===id);
    $('#dialog-title').textContent=`${id?'EDITAR':'NOVO'} ${type==='service'?'SERVIÇO':'PLANO'}`;
    const fields=$('#dialog-fields');fields.replaceChildren();
    const add=(key,label,value,kind='text',opts={})=>{
      const box=document.createElement('div');box.className='field';const l=document.createElement('label');l.textContent=label;l.htmlFor='edit-'+key;
      const i=kind==='textarea'?document.createElement('textarea'):document.createElement('input');i.id='edit-'+key;i.name=key;
      if(kind!=='textarea')i.type=kind;
      if(kind==='number'){i.min='0';i.step='0.01';}
      if(opts.maxLength)i.maxLength=opts.maxLength;
      i.value=value??'';if(opts.required)i.required=true;
      box.append(l,i);fields.append(box);
    };
    add('name','NOME',existing?.name||'','text',{required:true,maxLength:90});
    add('description','DESCRIÇÃO',existing?.description||'','textarea',{maxLength:300});
    add('price','PREÇO EM R$',existing?existing.price.toFixed(2):'', 'number',{required:true});
    if(type==='service')add('duration','DURAÇÃO (MINUTOS)',existing?.duration_min||45,'number',{required:true});
    else{add('period','PERIODICIDADE',existing?.period||'mensal','text');add('benefits','BENEFÍCIOS (UM POR LINHA)',existing?.benefits||'','textarea');}
    const row=document.createElement('label');row.className='check-field';const inp=document.createElement('input');inp.type='checkbox';inp.id='edit-active';inp.checked=existing?.active??true;
    const lbl=document.createElement('span');lbl.textContent='VISÍVEL PARA CLIENTES';row.append(inp,lbl);fields.append(row);
    $('#edit-dialog').showModal();
  }
  async function saveEditor(event){event.preventDefault();const type=state.mode,id=state.editId;
    const name=$('#edit-name').value.trim(),description=$('#edit-description').value.trim();
    const priceNumber=Number($('#edit-price').value);
    if(!name||!Number.isFinite(priceNumber)||priceNumber<0){flash('Preencha um nome e preço válido.',true);return;}
    const payload={name,description,price_cents:Math.round(priceNumber*100),active:$('#edit-active').checked};
    if(type==='service'){payload.duration_min=Number($('#edit-duration').value);}
    else{payload.period=$('#edit-period').value.trim()||'mensal';payload.benefits=$('#edit-benefits').value.trim();}
    const suffix=type==='service'?'services':'plans';
    try{await api(`${suffix}${id?'/'+id:''}`,{method:id?'PUT':'POST',body:JSON.stringify(payload)});
      $('#edit-dialog').close();flash('Alterações salvas com sucesso.');await (type==='service'?loadServices():loadPlans());}
    catch(e){flash(e.message,true);}
  }
  async function loadSchedule(){const data=await api('schedule');const shifts=$('#shift-list'),blocks=$('#block-list');shifts.replaceChildren();blocks.replaceChildren();
    $('#schedule-public-status').textContent=data.published?'✓ AGENDA PUBLICADA — turnos futuros já aparecem para clientes, respeitando folgas e reservas.':'⚠ AGENDA NÃO PUBLICADA — ative em Configurações → Publicar agenda e salve para os clientes verem horários.';
    $('#schedule-public-status').classList.toggle('active',data.published);
    if(!data.shifts.length)shifts.innerHTML='<p class="helper">Nenhum expediente cadastrado.</p>';
    for(const s of data.shifts){const row=chip(`${weekdayNames[s.weekday]} · ${s.start}–${s.end}`,async()=>{try{await api(`shifts/${s.id}`,{method:'DELETE'});await loadSchedule();}catch(e){flash(e.message,true);}});shifts.append(row);}
    if(!data.blocks.length)blocks.innerHTML='<p class="helper">Não há bloqueios futuros.</p>';
    for(const b of data.blocks)blocks.append(chip(`${dateLabel(b.day)} · ${b.start}–${b.end} ${b.reason?'· '+b.reason:''}`,async()=>{try{await api(`blocks/${b.id}`,{method:'DELETE'});await loadSchedule();}catch(e){flash(e.message,true);}}));
  }
  function chip(text,onDelete){const row=document.createElement('div');row.className='chip';const s=document.createElement('span');s.textContent=text;const del=button('×',onDelete);del.setAttribute('aria-label','Remover '+text);row.append(s,del);return row;}
  async function saveShift(e){e.preventDefault();try{await api('shifts',{method:'POST',body:JSON.stringify({weekday:Number($('#shift-day').value),start:$('#shift-start').value,end:$('#shift-end').value})});flash('Turno cadastrado.');await loadSchedule();}catch(err){flash(err.message,true);}}
  async function changeWeekdaySchedule(closeDay=false){
    const weekday=Number($('#shift-day').value), day=weekdayNames[weekday];
    const start=$('#shift-start').value, end=$('#shift-end').value;
    const msg=closeDay
      ?`Fechar todos os horários de ${day}? As reservas existentes não serão canceladas.`
      :`Substituir TODOS os turnos de ${day} por ${start}–${end}? As reservas existentes serão mantidas.`;
    if(!confirm(msg))return;
    try{
      if(closeDay)await api(`shifts/day/${weekday}`,{method:'DELETE'});
      else await api(`shifts/day/${weekday}`,{method:'PUT',body:JSON.stringify({weekday,start,end})});
      flash(closeDay?`Dia ${day} fechado para novas reservas.`:`Horários de ${day} substituídos. Confira na agenda pública.`);
      await loadSchedule();
    }catch(e){flash(e.message,true);}
  }
  async function saveBlock(e){e.preventDefault();try{await api('blocks',{method:'POST',body:JSON.stringify({day:$('#block-day').value,start:$('#block-start').value,end:$('#block-end').value,reason:$('#block-reason').value})});flash('Período bloqueado.');await loadSchedule();}catch(err){flash(err.message,true);}}
  async function loadSettings(){const [data,feed,integrations]=await Promise.all([api('settings'),api('calendar-feed'),api('integrations')]);
    const wa=integrations.whatsapp;
    $('#whatsapp-integration-status').textContent=wa.automatic_reminders_active
      ?'ATIVO — lembretes automáticos configurados no servidor via WhatsApp Business Cloud API.'
      :wa.configured?'CREDENCIAIS PRESENTES — envio automático desativado no servidor.'
      :'NÃO CONFIGURADO — nenhuma mensagem automática será enviada pelo sistema.';
    $('#credentials-username').value=state.username;
    $('#set-name').value=data.business_name;$('#set-address').value=data.address;$('#set-whatsapp').value=data.whatsapp;$('#set-lead').value=data.lead_hours;
    $('#set-days').value=data.advance_days;$('#set-reminder').value=data.reminder_hours;$('#set-published').checked=data.published;
    $('#publish-status').textContent=data.published?'● PUBLICADA':'● RASCUNHO';$('#publish-status').classList.toggle('published',data.published);
    $('#calendar-url').value=location.origin+feed.path;
  }
  async function saveSettings(e){e.preventDefault();const p={business_name:$('#set-name').value,address:$('#set-address').value,
    whatsapp:$('#set-whatsapp').value,published:$('#set-published').checked,lead_hours:Number($('#set-lead').value),
    advance_days:Number($('#set-days').value),reminder_hours:Number($('#set-reminder').value)};
    try{await api('settings',{method:'PUT',body:JSON.stringify(p)});flash('Configurações salvas.');await loadSettings();}
    catch(err){flash(err.message,true);}
  }
  async function rotateFeed(){if(!confirm('O link antigo deixará de funcionar nos calendários conectados. Continuar?'))return;
    try{const data=await api('calendar-feed/rotate',{method:'POST'});$('#calendar-url').value=location.origin+data.path;flash('Link privado atualizado.');}catch(e){flash(e.message,true);}
  }
  document.querySelectorAll('[data-tab]').forEach(x=>x.addEventListener('click',()=>changeTab(x.dataset.tab)));
  $('#login-form').addEventListener('submit',login);$('#dashboard-date').addEventListener('change',loadDashboard);
  $('#refresh-bookings').addEventListener('click',loadBookings);
  $('#bookings-search').addEventListener('input',renderBookings);
  $('#bookings-status').addEventListener('change',renderBookings);
  $('#export-bookings').addEventListener('click',exportBookings);
  $('#refresh-clients').addEventListener('click',loadClients);
  $('#clients-search').addEventListener('input',renderClients);
  $('#credentials-form').addEventListener('submit',changeCredentials);
  $('#close-history').addEventListener('click',()=>$('#history-dialog').close());
  $('#dismiss-history').addEventListener('click',()=>$('#history-dialog').close());
  $('#new-service').addEventListener('click',()=>openEditor('service'));
  $('#new-plan').addEventListener('click',()=>openEditor('plan'));
  $('#close-dialog').addEventListener('click',()=>$('#edit-dialog').close());
  $('#cancel-dialog').addEventListener('click',()=>$('#edit-dialog').close());
  $('#edit-form').addEventListener('submit',saveEditor);
  $('#shift-form').addEventListener('submit',saveShift);$('#block-form').addEventListener('submit',saveBlock);
  $('#replace-shift-day').addEventListener('click',()=>changeWeekdaySchedule(false));
  $('#close-shift-day').addEventListener('click',()=>changeWeekdaySchedule(true));
  $('#settings-form').addEventListener('submit',saveSettings);
  $('#copy-calendar').addEventListener('click',async()=>{try{await navigator.clipboard.writeText($('#calendar-url').value);flash('Link copiado. Guarde-o em segurança.');}catch{flash('Selecione o link e copie manualmente.',true);}});
  $('#rotate-calendar').addEventListener('click',rotateFeed);
  $('#logout').addEventListener('click',async()=>{try{await api('logout',{method:'POST'});}finally{showLogin();}});
  boot();
})();

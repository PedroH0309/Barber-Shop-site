/* Precision Admin: installable, online-first management experience. No client data is cached. */
(() => {
  'use strict';
  const $ = (selector) => document.querySelector(selector);
  const items = [
    ['dashboard', '▦', 'Início'],
    ['bookings', '▤', 'Agenda'],
    ['clients', '♙', 'Clientes'],
    ['schedule', '◷', 'Horários'],
    ['services', '✂', 'Serviços'],
    ['plans', '♢', 'Planos'],
    ['settings', '⚙', 'Ajustes'],
  ];
  const make = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  };

  // Original desktop tabs remain the single source of truth for navigation.
  const navigate = (tab) => {
    const target = document.querySelector(`.side-nav [data-tab="${tab}"]`);
    if (target) target.click();
    closeMenu();
  };

  const dock = make('nav', 'mobile-dock');
  dock.setAttribute('aria-label', 'Navegação rápida do barbeiro');
  const quickTabs = items.slice(0, 2).concat(items.slice(3, 4));
  for (const [tab, symbol, title] of quickTabs) {
    const button = make('button', 'dock-tab', `${symbol}\n${title}`);
    button.type = 'button';
    button.dataset.destination = tab;
    button.setAttribute('aria-label', title);
    button.addEventListener('click', () => navigate(tab));
    dock.append(button);
  }
  const more = make('button', 'dock-tab dock-more-trigger', '☰\nMais');
  more.type = 'button';
  more.setAttribute('aria-label', 'Mais opções do painel');
  more.setAttribute('aria-expanded', 'false');
  dock.append(more);
  $('#workspace').append(dock);

  const veil = make('div', 'mobile-menu-veil');
  veil.hidden = true;
  const menu = make('section', 'mobile-menu');
  menu.hidden = true;
  menu.setAttribute('role', 'dialog');
  menu.setAttribute('aria-modal', 'true');
  menu.setAttribute('aria-label', 'Mais opções do painel');
  const header = make('div', 'mobile-menu-title');
  header.append(make('strong', '', 'GERENCIAR BARBEARIA'));
  const close = make('button', 'mobile-menu-close', '✕');
  close.type = 'button';
  close.setAttribute('aria-label', 'Fechar menu');
  header.append(close);
  menu.append(header);
  for (const [tab, symbol, title] of items) {
    const button = make('button', 'mobile-menu-item', `${symbol}  ${title}`);
    button.type = 'button';
    button.dataset.destination = tab;
    button.addEventListener('click', () => navigate(tab));
    menu.append(button);
  }
  const siteLink = make('a', 'mobile-menu-item', '↗  Abrir agenda pública');
  siteLink.href = '/agendar';
  siteLink.target = '_blank';
  siteLink.rel = 'noopener';
  menu.append(siteLink);
  const logout = make('button', 'mobile-menu-item', '⎋  Sair da conta');
  logout.type = 'button';
  logout.addEventListener('click', () => { closeMenu(); $('#logout').click(); });
  menu.append(logout);
  document.body.append(veil, menu);
  function closeMenu() {
    menu.hidden = true;
    veil.hidden = true;
    more.setAttribute('aria-expanded', 'false');
    document.body.classList.remove('mobile-menu-open');
  }
  function openMenu() {
    menu.hidden = false;
    veil.hidden = false;
    more.setAttribute('aria-expanded', 'true');
    document.body.classList.add('mobile-menu-open');
    close.focus();
  }
  more.addEventListener('click', () => menu.hidden ? openMenu() : closeMenu());
  close.addEventListener('click', closeMenu);
  veil.addEventListener('click', closeMenu);
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') closeMenu();
    if (event.key === 'Tab' && !menu.hidden) {
      const controls = Array.from(menu.querySelectorAll('button, a'));
      const first = controls[0], last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
  });

  // The mobile and desktop navigation reflect the current section.
  const syncNavigation = () => {
    const current = document.querySelector('.side-nav [data-tab].active')?.dataset.tab;
    dock.querySelectorAll('[data-destination]').forEach((button) => {
      const selected = button.dataset.destination === current;
      button.classList.toggle('active', selected);
      if (selected) button.setAttribute('aria-current', 'page');
      else button.removeAttribute('aria-current');
    });
  };
  new MutationObserver(syncNavigation).observe($('.side-nav'), {subtree: true, attributes: true, attributeFilter: ['class']});
  syncNavigation();

  // Install instructions are public UI only; credentials stay in HttpOnly cookies.
  let installEvent = null;
  const installButton = make('button', 'install-app-button', '↧  INSTALAR APP');
  installButton.type = 'button';
  installButton.setAttribute('aria-label', 'Instalar Precision Admin');
  $('.top-actions').prepend(installButton);
  const loginInstall = make('button', 'login-install-button', '↧  INSTALAR NO CELULAR / PC');
  loginInstall.type = 'button';
  $('#login-form').insertAdjacentElement('afterend', loginInstall);

  const installDialog = document.createElement('dialog');
  installDialog.className = 'pwa-install-dialog';
  installDialog.innerHTML = `
    <div class="pwa-dialog-top"><div><span class="tiny">PRECISION ADMIN</span><h2>INSTALE SEU PAINEL.</h2></div><button type="button" class="pwa-dialog-close" aria-label="Fechar">✕</button></div>
    <p>O painel funciona no iPhone, Android e computador. A agenda fica no servidor e é atualizada pela internet.</p>
    <div class="pwa-device"><b>iPhone / iPad (Safari)</b><span>Toque em Compartilhar → Adicionar à Tela de Início → Adicionar.</span></div>
    <div class="pwa-device"><b>Android (Chrome)</b><span>Menu ⋮ → Instalar app ou Adicionar à tela inicial.</span></div>
    <div class="pwa-device"><b>Windows (Chrome ou Edge)</b><span>Abra o menu do navegador e escolha Instalar Precision Admin.</span></div>
    <p class="pwa-install-warning">Necessário endereço HTTPS público (ou localhost para testes). O app precisa de internet para consultar e aprovar reservas; dados de clientes não são salvos offline.</p>
    <button type="button" class="primary pwa-install-now" hidden>INSTALAR AGORA ↗</button>
  `;
  document.body.append(installDialog);
  const installNow = $('.pwa-install-now');
  const openInstall = () => {
    installNow.hidden = !installEvent;
    if (!installDialog.open) installDialog.showModal();
  };
  installButton.addEventListener('click', openInstall);
  loginInstall.addEventListener('click', openInstall);
  installDialog.querySelector('.pwa-dialog-close').addEventListener('click', () => installDialog.close());
  installNow.addEventListener('click', async () => {
    if (!installEvent) return;
    const prompt = installEvent;
    installEvent = null;
    installNow.hidden = true;
    installDialog.close();
    await prompt.prompt();
  });
  window.addEventListener('beforeinstallprompt', (event) => {
    event.preventDefault();
    installEvent = event;
  });
  window.addEventListener('appinstalled', () => {
    installEvent = null;
    installNow.hidden = true;
  });

  // Never cache admin responses or personal data. All API calls are network-only.
  if ('serviceWorker' in navigator && window.isSecureContext) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/admin-sw.js', {scope: '/'}).catch(() => {});
    });
  }

  const networkStatus = make('div', 'pwa-network-status', 'Sem conexão: a agenda não pode ser atualizada ou consultada.');
  networkStatus.hidden = navigator.onLine;
  networkStatus.setAttribute('role', 'status');
  document.body.append(networkStatus);
  window.addEventListener('offline', () => { networkStatus.hidden = false; });
  window.addEventListener('online', () => { networkStatus.hidden = true; });

  // Refetch open section after returning to the installed app (no background polling of private data).
  let lastRefresh = Date.now();
  const refreshVisible = () => {
    if (document.hidden || !navigator.onLine || $('#workspace').hidden || Date.now() - lastRefresh < 45000) return;
    lastRefresh = Date.now();
    const tab = $('.side-nav [data-tab].active')?.dataset.tab;
    if (tab === 'dashboard' || tab === 'bookings') navigate(tab);
  };
  document.addEventListener('visibilitychange', refreshVisible);
  window.addEventListener('focus', refreshVisible);
})();


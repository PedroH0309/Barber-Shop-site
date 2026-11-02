(() => {
  'use strict';

  const $ = (selector, context = document) => context.querySelector(selector);
  const menuToggle = $('#menu-toggle');
  const mobileNav = $('#mobile-nav');

  const closeMenu = (returnFocus = false) => {
    if (!menuToggle || !mobileNav) return;
    const wasOpen = menuToggle.getAttribute('aria-expanded') === 'true';
    menuToggle.setAttribute('aria-expanded', 'false');
    menuToggle.setAttribute('aria-label', 'Abrir menu');
    mobileNav.hidden = true;
    document.body.classList.remove('menu-open');
    if (returnFocus && wasOpen) menuToggle.focus();
  };

  if (menuToggle && mobileNav) {
    menuToggle.addEventListener('click', () => {
      const opening = menuToggle.getAttribute('aria-expanded') !== 'true';
      menuToggle.setAttribute('aria-expanded', String(opening));
      menuToggle.setAttribute('aria-label', opening ? 'Fechar menu' : 'Abrir menu');
      mobileNav.hidden = !opening;
      document.body.classList.toggle('menu-open', opening);
      if (opening) mobileNav.querySelector('a')?.focus();
    });
    mobileNav.querySelectorAll('a').forEach(link => link.addEventListener('click', () => closeMenu()));
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && !mobileNav.hidden) closeMenu(true);
    });
    document.addEventListener('click', event => {
      if (!mobileNav.hidden && !event.target.closest('.site-header')) closeMenu();
    });
    window.addEventListener('resize', () => {
      if (window.innerWidth > 820 && !mobileNav.hidden) closeMenu();
    });
  }

  // Decorative section reveals. The content remains visible when JS is disabled.
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if ('IntersectionObserver' in window && !prefersReducedMotion) {
    const items = document.querySelectorAll('.reveal');
    const observer = new IntersectionObserver((entries, obs) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          obs.unobserve(entry.target);
        }
      });
    }, {threshold: 0.07, rootMargin: '0px 0px 30px 0px'});
    items.forEach(item => observer.observe(item));
    // Only turn on pre-reveal styling after the observer is ready.
    document.documentElement.classList.add('js-ready');
    // Elements above fold can be revealed immediately.
    items.forEach(item => { if (item.getBoundingClientRect().top < innerHeight) item.classList.add('is-visible'); });
  }

  const year = $('#year');
  if (year) year.textContent = String(new Date().getFullYear());
})();

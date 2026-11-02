/* Installable shell; deliberately network-only to keep private booking data off device caches. */
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()));
// No fetch interception. Private API responses, authenticated pages and session state are never cached by this worker.


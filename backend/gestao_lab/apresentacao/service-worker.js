const PREFIXO_CACHE = "poodev-publico-";
const CACHE_PUBLICO = PREFIXO_CACHE + "6-__REVISAO_ESTILO__";
const URL_ESTILO = "__URL_ESTILO__";
const PAGINA_OFFLINE = "/offline";
const ARQUIVOS_OFFLINE = new Set([
    PAGINA_OFFLINE,
    "/ajuda",
    URL_ESTILO,
    "/icones-menu.png",
    "/manifest.webmanifest",
    "/registrar-pwa.js",
    "/pwa/icone-192.png",
    "/pwa/icone-512.png",
]);

self.addEventListener("install", (evento) => {
    // O cache contém somente respostas públicas, buscadas sem o cookie de sessão.
    const requisicoes = [...ARQUIVOS_OFFLINE].map((caminho) =>
        new Request(new URL(caminho, self.location.origin), {
            cache: "reload",
            credentials: "omit",
            redirect: "error",
        })
    );
    evento.waitUntil(caches.open(CACHE_PUBLICO).then((cache) => cache.addAll(requisicoes)));
});

self.addEventListener("activate", (evento) => {
    evento.waitUntil((async () => {
        const nomes = await caches.keys();
        await Promise.all(nomes
            .filter((nome) => nome.startsWith(PREFIXO_CACHE) && nome !== CACHE_PUBLICO)
            .map((nome) => caches.delete(nome)));
        await self.clients.claim();
    })());
});

self.addEventListener("fetch", (evento) => {
    const pedido = evento.request;
    const url = new URL(pedido.url);
    if (pedido.method !== "GET" || url.origin !== self.location.origin) return;

    const endereco = url.pathname + url.search;
    if (ARQUIVOS_OFFLINE.has(endereco)) {
        evento.respondWith(
            caches.open(CACHE_PUBLICO)
                .then((cache) => cache.match(endereco))
                .then((resposta) => resposta || fetch(pedido))
        );
    } else if (pedido.mode === "navigate") {
        evento.respondWith(fetch(pedido).catch(async () => {
            const cache = await caches.open(CACHE_PUBLICO);
            return (await cache.match(PAGINA_OFFLINE)) || Response.error();
        }));
    }
});

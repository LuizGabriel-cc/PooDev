if ("serviceWorker" in navigator && window.isSecureContext) {
    navigator.serviceWorker.register("/service-worker.js").catch((erro) => {
        console.warn("Não foi possível preparar o acesso offline do sistema.", erro);
    });
}

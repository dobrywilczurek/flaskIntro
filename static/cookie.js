document.addEventListener('DOMContentLoaded', function() {
    const acceptBtn = document.getElementById('accept-cookies');
    const rejectBtn = document.getElementById('reject-cookies');

    if (acceptBtn && rejectBtn) {
        acceptBtn.addEventListener('click', function() {
            fetch('/accept_cookies', { method: 'POST' })
                .then(() => document.getElementById('cookie-banner').remove());
        });

        rejectBtn.addEventListener('click', function() {
            fetch('/reject_cookies', { method: 'POST' })
                .then(() => document.getElementById('cookie-banner').remove());
        });
    }
});
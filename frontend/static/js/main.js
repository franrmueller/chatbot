document.addEventListener('DOMContentLoaded', function () {
    console.log('Chatbot application initialized');

    // AUTH
    function checkAuth() {
        const sessionToken = localStorage.getItem('accessToken');
        if (!sessionToken &&
            !window.location.pathname.includes('/login') &&
            !window.location.pathname.includes('/register') &&
            window.location.pathname !== '/') {
            window.location.href = '/login';
        }
    }

    checkAuth();

    document.querySelectorAll('.logout-button').forEach(button => {
        button.addEventListener('click', async function (e) {
            e.preventDefault();
            try {
                // Clear all chat histories on logout
                const keys = Object.keys(sessionStorage);
                keys.forEach(key => {
                    if (key.startsWith('chat-history-') || key.startsWith('visible-chat-')) {
                        sessionStorage.removeItem(key);
                    }
                });
                
                await fetch('/api/auth/logout', { method: 'POST' });
                localStorage.removeItem('accessToken');
                window.location.href = '/';
            } catch (error) {
                console.error('Logout error:', error);
            }
        });
    });
});
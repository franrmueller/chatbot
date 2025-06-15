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
                await fetch('/api/auth/logout', { method: 'POST' });
                localStorage.removeItem('accessToken');
                window.location.href = '/';
            } catch (error) {
                console.error('Logout error:', error);
            }
        });
    });

    // CHAT
    const form = document.getElementById('chat-form');
    const chatWindow = document.getElementById('chat-window');
    const userInput = document.getElementById('user-input');

    function appendMessage(sender, html) {
        const msg = document.createElement('div');
        msg.classList.add('chat-message', sender);
        msg.style.margin = '0.5rem 0';
        msg.innerHTML = `<strong>${sender === 'user' ? 'Du' : 'Vorlesungschatbot'}:</strong> ${html}`;
        chatWindow.appendChild(msg);
        chatWindow.scrollTop = chatWindow.scrollHeight;
    }

    function showSpinnerMessage() {
        const msg = document.createElement('div');
        msg.classList.add('chat-message', 'bot');
        msg.id = 'loading-message';
        msg.style.margin = '0.5rem 0';
        msg.innerHTML = `
            <strong>Vorlesungschatbot:</strong> Antwort wird generiert...
            <div class="spinner"></div>
        `;
        chatWindow.appendChild(msg);
        chatWindow.scrollTop = chatWindow.scrollHeight;
    }

    function removeSpinnerMessage() {
        const spinner = document.getElementById('loading-message');
        if (spinner) {
            spinner.remove();
        }
    }

    form?.addEventListener('submit', async function (e) {
        e.preventDefault();
        const question = userInput.value.trim();
        if (!question) return;

        appendMessage('user', question);
        userInput.value = '';

        showSpinnerMessage(); // Spinner im Chat anzeigen

        try {
            const classId = form.dataset.classId || "{{ class.id }}";
            const response = await fetch(`/chat/${classId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ prompt: question })
            });

            const data = await response.json();
            removeSpinnerMessage(); // Spinner entfernen
            appendMessage('bot', data.answer);
        } catch (error) {
            removeSpinnerMessage();
            appendMessage('bot', 'Fehler beim Abrufen der Antwort.');
            console.error(error);
        }
    });
});

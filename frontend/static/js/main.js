document.addEventListener('DOMContentLoaded', function() {
    console.log('Chatbot application initialized');
    
    // Check authentication status
    function checkAuth() {
        const sessionToken = localStorage.getItem('accessToken');
        if (!sessionToken && !window.location.pathname.includes('/login') && 
            !window.location.pathname.includes('/register') && 
            window.location.pathname !== '/') {
            // Redirect to login if not authenticated and trying to access protected page
            window.location.href = '/login';
        }
    }
    
    // Run auth check
    checkAuth();
    
    // Add logout functionality to all logout buttons
    const logoutButtons = document.querySelectorAll('.logout-button');
    if (logoutButtons) {
        logoutButtons.forEach(button => {
            button.addEventListener('click', async function(e) {
                e.preventDefault();
                
                try {
                    await fetch('/api/auth/logout', {
                        method: 'POST',
                    });
                    
                    // Clear local storage
                    localStorage.removeItem('accessToken');
                    
                    // Redirect to home page
                    window.location.href = '/';
                } catch (error) {
                    console.error('Logout error:', error);
                }
            });
        });
    }
});
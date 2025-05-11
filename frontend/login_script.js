document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('loginForm');
    const errorMessageElement = document.getElementById('errorMessage');

    // Function to get the redirect URL from query parameters or default to index.html
    function getRedirectUrl() {
        const urlParams = new URLSearchParams(window.location.search);
        return urlParams.get('redirect') || '../index.html';
    }

    if (loginForm) {
        loginForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            errorMessageElement.style.display = 'none';
            errorMessageElement.textContent = '';

            const username = loginForm.username.value;
            const password = loginForm.password.value;

            // FastAPI's OAuth2PasswordRequestForm expects form data
            const formData = new FormData();
            formData.append('username', username);
            formData.append('password', password);

            try {
                // 1. Get the access token
                const tokenResponse = await fetch('/api/v1/auth/token', {
                    method: 'POST',
                    body: formData, // Sending as form-data
                });

                if (!tokenResponse.ok) {
                    const errorData = await tokenResponse.json().catch(() => ({ detail: 'Login failed. Please check your credentials.' }));
                    throw new Error(errorData.detail || 'Login failed. Please check your credentials.');
                }

                const tokenData = await tokenResponse.json();
                localStorage.setItem('authToken', tokenData.access_token);

                // 2. Get user details using the new token
                const userResponse = await fetch('/api/v1/auth/users/me', {
                    method: 'GET',
                    headers: {
                        'Authorization': `Bearer ${tokenData.access_token}`
                    }
                });

                if (!userResponse.ok) {
                    // If users/me fails, token might be invalid or user inactive. Clean up.
                    localStorage.removeItem('authToken');
                    const errorData = await userResponse.json().catch(() => ({ detail: 'Failed to fetch user details after login.' }));
                    throw new Error(errorData.detail || 'Failed to fetch user details.');
                }

                const userData = await userResponse.json();
                localStorage.setItem('username', userData.username);
                localStorage.setItem('userRole', userData.role); // Store user role

                // Redirect to the main page or previous page
                window.location.href = getRedirectUrl();

            } catch (error) {
                console.error('Login error:', error);
                errorMessageElement.textContent = error.message;
                errorMessageElement.style.display = 'block';
                localStorage.removeItem('authToken'); // Clean up token on any error
                localStorage.removeItem('username');
                localStorage.removeItem('userRole');
            }
        });
    }
});

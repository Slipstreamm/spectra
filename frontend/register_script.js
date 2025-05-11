document.addEventListener('DOMContentLoaded', () => {
    const registerForm = document.getElementById('registerForm');
    const errorMessageElement = document.getElementById('errorMessage');
    const successMessageElement = document.getElementById('successMessage');

    if (registerForm) {
        registerForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            errorMessageElement.style.display = 'none';
            errorMessageElement.textContent = '';
            successMessageElement.style.display = 'none';
            successMessageElement.textContent = '';

            const username = registerForm.username.value;
            const email = registerForm.email.value;
            const password = registerForm.password.value;
            const confirmPassword = registerForm.confirmPassword.value;

            if (password !== confirmPassword) {
                errorMessageElement.textContent = 'Passwords do not match.';
                errorMessageElement.style.display = 'block';
                return;
            }

            // Basic email validation (more robust validation can be added)
            if (!email.includes('@') || !email.includes('.')) {
                errorMessageElement.textContent = 'Please enter a valid email address.';
                errorMessageElement.style.display = 'block';
                return;
            }
            
            // Password length check (already in HTML minlength, but good for JS backup)
            if (password.length < 8) {
                errorMessageElement.textContent = 'Password must be at least 8 characters long.';
                errorMessageElement.style.display = 'block';
                return;
            }


            try {
                const response = await fetch('/api/v1/auth/register', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        username: username,
                        email: email,
                        password: password,
                        // role will be defaulted to 'user' by the backend
                    }),
                });

                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({ detail: 'Registration failed. Please try again.' }));
                    throw new Error(errorData.detail || 'Registration failed. Please try again.');
                }

                // const responseData = await response.json(); // User data returned on successful registration
                successMessageElement.textContent = 'Registration successful! Redirecting to login...';
                successMessageElement.style.display = 'block';

                // Redirect to login page after a short delay
                setTimeout(() => {
                    window.location.href = 'login.html?registration=success';
                }, 2000);

            } catch (error) {
                console.error('Registration error:', error);
                errorMessageElement.textContent = error.message;
                errorMessageElement.style.display = 'block';
            }
        });
    }
});

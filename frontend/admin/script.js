document.addEventListener('DOMContentLoaded', () => {
    const loginSection = document.getElementById('loginSection');
    const dashboardSection = document.getElementById('dashboardSection');
    const loginForm = document.getElementById('loginForm');
    const loginStatus = document.getElementById('loginStatus');
    const logoutButton = document.getElementById('logoutButton');
    const imageListDiv = document.getElementById('imageList');

    const API_BASE_URL = '/api/v1'; // Adjust if your API prefix is different

    function getToken() {
        return localStorage.getItem('adminToken');
    }

    function setToken(token) {
        localStorage.setItem('adminToken', token);
    }

    function removeToken() {
        localStorage.removeItem('adminToken');
    }

    function showLogin() {
        loginSection.style.display = 'block';
        dashboardSection.style.display = 'none';
        logoutButton.style.display = 'none';
    }

    function showDashboard() {
        loginSection.style.display = 'none';
        dashboardSection.style.display = 'block';
        logoutButton.style.display = 'block';
        fetchAdminImages();
    }

    // Handle Login
    if (loginForm) {
        loginForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            loginStatus.textContent = 'Logging in...';
            const username = loginForm.username.value;
            const password = loginForm.password.value;

            const formData = new FormData();
            formData.append('username', username);
            formData.append('password', password);

            try {
                const response = await fetch(`${API_BASE_URL}/auth/token`, {
                    method: 'POST',
                    body: formData, // FastAPI expects form data for OAuth2PasswordRequestForm
                });

                const result = await response.json();

                if (response.ok) {
                    setToken(result.access_token);
                    loginStatus.textContent = 'Login successful!';
                    loginForm.reset();
                    showDashboard();
                } else {
                    loginStatus.textContent = `Login failed: ${result.detail || response.statusText}`;
                    removeToken();
                }
            } catch (error) {
                console.error('Login error:', error);
                loginStatus.textContent = `Login error: ${error.message}`;
                removeToken();
            }
        });
    }

    // Handle Logout
    if (logoutButton) {
        logoutButton.addEventListener('click', () => {
            removeToken();
            showLogin();
            imageListDiv.innerHTML = '<p>Please log in to see images.</p>'; // Clear images
        });
    }

    // Fetch and display images for admin
    async function fetchAdminImages() {
        const token = getToken();
        if (!token) {
            showLogin();
            return;
        }

        imageListDiv.innerHTML = '<p>Loading images...</p>';

        try {
            const response = await fetch(`${API_BASE_URL}/admin/images`, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (response.status === 401 || response.status === 403) {
                removeToken();
                showLogin();
                loginStatus.textContent = 'Session expired or unauthorized. Please log in again.';
                return;
            }
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json(); // Expecting PaginatedImages model

            imageListDiv.innerHTML = ''; // Clear previous content

            if (result.data && result.data.length > 0) {
                result.data.forEach(image => {
                    const itemDiv = document.createElement('div');
                    itemDiv.className = 'image-item';

                    const imgElement = document.createElement('img');
                    imgElement.src = image.image_url || `${API_BASE_URL}/static/uploads/${image.filename}`;
                    imgElement.alt = image.filename;

                    const nameP = document.createElement('p');
                    nameP.textContent = `Filename: ${image.filename}`;
                    
                    const id_P = document.createElement('p');
                    id_P.textContent = `ID: ${image.id}`;

                    const tagsP = document.createElement('p');
                    tagsP.textContent = `Tags: ${image.tags.map(tag => tag.name).join(', ') || 'None'}`;
                    
                    const uploadedAtP = document.createElement('p');
                    uploadedAtP.textContent = `Uploaded: ${new Date(image.uploaded_at).toLocaleString()}`;


                    const deleteButton = document.createElement('button');
                    deleteButton.className = 'delete-button action-button';
                    deleteButton.textContent = 'Delete';
                    deleteButton.dataset.imageId = image.id;
                    deleteButton.addEventListener('click', handleDeleteImage);

                    itemDiv.appendChild(imgElement);
                    itemDiv.appendChild(nameP);
                    itemDiv.appendChild(id_P);
                    itemDiv.appendChild(tagsP);
                    itemDiv.appendChild(uploadedAtP);
                    itemDiv.appendChild(deleteButton);
                    imageListDiv.appendChild(itemDiv);
                });
            } else {
                imageListDiv.innerHTML = '<p>No images found.</p>';
            }
        } catch (error) {
            console.error('Error fetching admin images:', error);
            imageListDiv.innerHTML = `<p>Error loading images: ${error.message}</p>`;
            if (error.message.includes("401") || error.message.includes("403")) {
                removeToken();
                showLogin();
            }
        }
    }

    // Handle image deletion
    async function handleDeleteImage(event) {
        const imageId = event.target.dataset.imageId;
        const token = getToken();

        if (!token) {
            showLogin();
            alert('Authentication token not found. Please log in.');
            return;
        }

        if (!confirm(`Are you sure you want to delete image ID: ${imageId}?`)) {
            return;
        }

        try {
            const response = await fetch(`${API_BASE_URL}/admin/images/${imageId}`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (response.status === 401 || response.status === 403) {
                removeToken();
                showLogin();
                loginStatus.textContent = 'Session expired or unauthorized. Please log in again.';
                return;
            }

            if (response.ok) { // Status 204 No Content is also "ok"
                alert(`Image ID: ${imageId} deleted successfully.`);
                fetchAdminImages(); // Refresh the list
            } else {
                const errorResult = await response.json().catch(() => ({ detail: 'Unknown error during deletion.' }));
                alert(`Failed to delete image: ${errorResult.detail || response.statusText}`);
            }
        } catch (error) {
            console.error('Error deleting image:', error);
            alert(`Error deleting image: ${error.message}`);
        }
    }


    // Initial check: if token exists, try to show dashboard, else show login
    if (getToken()) {
        // Optionally, you could add a quick check here to see if the token is still valid
        // e.g., by fetching /users/me. For simplicity, we'll just show the dashboard.
        showDashboard();
    } else {
        showLogin();
    }
});

document.addEventListener('DOMContentLoaded', () => {
    const loginSection = document.getElementById('loginSection');
    const dashboardSection = document.getElementById('dashboardSection');
    const loginForm = document.getElementById('loginForm');
    const loginStatus = document.getElementById('loginStatus');
    const logoutButton = document.getElementById('logoutButton');
    const imageListDiv = document.getElementById('imageList');

    // New elements for mass upload
    const massUploadForm = document.getElementById('massUploadForm');
    const massUploadFilesInput = document.getElementById('massUploadFiles');
    const massUploadTagsInput = document.getElementById('massUploadTags');
    const massUploadStatus = document.getElementById('massUploadStatus');

    // New elements for batch tag update
    const batchTagUpdateForm = document.getElementById('batchTagUpdateForm');
    const batchTagUpdatePostIdsInput = document.getElementById('batchTagUpdatePostIds');
    const batchTagUpdateTagsInput = document.getElementById('batchTagUpdateTags');
    const batchTagUpdateActionButton = document.getElementById('batchTagUpdateButton');
    const batchTagUpdateStatus = document.getElementById('batchTagUpdateStatus');
    
    let selectedPostIdsForTagging = new Set();

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
            selectedPostIdsForTagging.clear(); // Clear selection on refresh
            updateBatchTagPostIdsDisplay();


            if (result.data && result.data.length > 0) {
                result.data.forEach(image => {
                    const itemDiv = document.createElement('div');
                    itemDiv.className = 'image-item';

                    // Checkbox for batch selection
                    const checkbox = document.createElement('input');
                    checkbox.type = 'checkbox';
                    checkbox.className = 'image-select-checkbox';
                    checkbox.dataset.postId = image.id;
                    checkbox.addEventListener('change', handleImageSelectionForTagging);
                    itemDiv.appendChild(checkbox);

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

    // --- Mass Image Upload Logic ---
    if (massUploadForm) {
        massUploadForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            const token = getToken();
            if (!token) {
                massUploadStatus.textContent = 'Authentication error. Please log in.';
                showLogin();
                return;
            }

            const files = massUploadFilesInput.files;
            const tagsStr = massUploadTagsInput.value;

            if (!files || files.length === 0) {
                massUploadStatus.textContent = 'Please select at least one file to upload.';
                return;
            }

            massUploadStatus.textContent = `Uploading ${files.length} file(s)...`;

            const formData = new FormData();
            for (let i = 0; i < files.length; i++) {
                formData.append('files', files[i]);
            }
            if (tagsStr) {
                formData.append('tags_str', tagsStr);
            }

            try {
                const response = await fetch(`${API_BASE_URL}/admin/posts/batch-upload`, {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${token}`
                    },
                    body: formData
                });

                const result = await response.json();

                if (response.ok || response.status === 201 || response.status === 207) { // 207 for Multi-Status
                    let message = `Batch upload process completed.\n`;
                    message += `Successful uploads: ${result.successful ? result.successful.length : 0}\n`;
                    if (result.failed && result.failed.length > 0) {
                        message += `Failed uploads: ${result.failed.length}\n`;
                        result.failed.forEach(fail => {
                            message += `- ${fail.filename}: ${fail.error}\n`;
                        });
                    }
                    massUploadStatus.textContent = message;
                    massUploadForm.reset();
                    fetchAdminImages(); // Refresh image list
                } else {
                    massUploadStatus.textContent = `Upload failed: ${result.detail?.message || result.detail || response.statusText}`;
                }
            } catch (error) {
                console.error('Mass upload error:', error);
                massUploadStatus.textContent = `Upload error: ${error.message}`;
            }
        });
    }

    // --- Batch Tag Update Logic ---
    function handleImageSelectionForTagging(event) {
        const postId = parseInt(event.target.dataset.postId, 10);
        if (event.target.checked) {
            selectedPostIdsForTagging.add(postId);
        } else {
            selectedPostIdsForTagging.delete(postId);
        }
        updateBatchTagPostIdsDisplay();
    }

    function updateBatchTagPostIdsDisplay() {
        const idsArray = Array.from(selectedPostIdsForTagging);
        batchTagUpdatePostIdsInput.value = idsArray.join(', ');
        batchTagUpdateActionButton.disabled = idsArray.length === 0;
    }

    if (batchTagUpdateForm) {
        batchTagUpdateForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            const token = getToken();
            if (!token) {
                batchTagUpdateStatus.textContent = 'Authentication error. Please log in.';
                showLogin();
                return;
            }

            const postIds = Array.from(selectedPostIdsForTagging);
            const tags = batchTagUpdateTagsInput.value.split(',').map(t => t.trim()).filter(t => t);
            const action = batchTagUpdateForm.querySelector('input[name="action"]:checked').value;

            if (postIds.length === 0) {
                batchTagUpdateStatus.textContent = 'Please select at least one image to update.';
                return;
            }
            if (tags.length === 0 && action !== 'set') { // 'set' can have empty tags to clear
                batchTagUpdateStatus.textContent = 'Please enter tags for the action.';
                return;
            }
            
            batchTagUpdateStatus.textContent = 'Updating tags...';

            const payload = {
                post_ids: postIds,
                tags: tags,
                action: action
            };

            try {
                const response = await fetch(`${API_BASE_URL}/admin/posts/batch-tags`, {
                    method: 'PUT',
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(payload)
                });

                const result = await response.json();

                if (response.ok) {
                    batchTagUpdateStatus.textContent = `Tag update successful: ${result.message || 'Completed.'} Affected posts: ${result.updated_posts_count || 0}.`;
                    fetchAdminImages(); // Refresh image list to show updated tags
                    // Clear selection and form
                    selectedPostIdsForTagging.clear();
                    updateBatchTagPostIdsDisplay();
                    batchTagUpdateTagsInput.value = '';

                } else {
                    batchTagUpdateStatus.textContent = `Tag update failed: ${result.detail || response.statusText}`;
                }
            } catch (error) {
                console.error('Batch tag update error:', error);
                batchTagUpdateStatus.textContent = `Tag update error: ${error.message}`;
            }
        });
    }
});

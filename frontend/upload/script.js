document.addEventListener('DOMContentLoaded', () => {
    const uploadForm = document.getElementById('uploadForm');
    const imageFileIn = document.getElementById('imageFile');
    const imageTagsIn = document.getElementById('imageTags');
    const uploadStatusDiv = document.getElementById('uploadStatus');
    const submitUploadButton = document.getElementById('submitUploadButton');

    const API_BASE_URL = '/api/v1'; // Adjust if your API prefix is different

    function getAuthToken() {
        return localStorage.getItem('authToken');
    }

    // Apply theme from localStorage (copied from main page for consistency)
    // This script block is also in upload/index.html, but good to have here if that's removed.
    const savedTheme = localStorage.getItem('spectraTheme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);

    // Optional: Theme toggle button logic (if you make the button visible and functional)
    const themeToggleButton = document.getElementById('themeToggle');
    if (themeToggleButton) { // Check if it exists
        themeToggleButton.style.visibility = 'visible'; // Make it visible if you want it
        themeToggleButton.addEventListener('click', () => {
            const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            document.documentElement.setAttribute('data-theme', newTheme);
            localStorage.setItem('spectraTheme', newTheme);
        });
    }


    if (uploadForm) {
        uploadForm.addEventListener('submit', async (event) => {
            event.preventDefault();

            const token = getAuthToken();
            if (!token) {
                uploadStatusDiv.textContent = 'You must be logged in to upload. Please login and try again.';
                uploadStatusDiv.className = 'upload-status error';
                // Optionally redirect to login page: window.location.href = '/login.html';
                return;
            }

            if (!imageFileIn.files || imageFileIn.files.length === 0) {
                uploadStatusDiv.textContent = 'Please select an image file.';
                uploadStatusDiv.className = 'upload-status error';
                return;
            }

            uploadStatusDiv.textContent = 'Uploading...';
            uploadStatusDiv.className = 'upload-status'; // Reset class
            submitUploadButton.disabled = true;

            const formData = new FormData();
            formData.append('file', imageFileIn.files[0]);
            
            // Tags are sent as a comma-separated string.
            // The backend /upload/ endpoint should be prepared to parse this.
            formData.append('tags_str', imageTagsIn.value.trim());

            try {
                // The endpoint for creating posts (which includes upload) is /api/v1/posts/
                const headers = {};
                if (token) {
                    headers['Authorization'] = `Bearer ${token}`;
                }

                const response = await fetch(`${API_BASE_URL}/posts/`, {
                    method: 'POST',
                    body: formData,
                    headers: headers
                    // 'Content-Type': 'multipart/form-data' is automatically set by browser for FormData
                });

                const result = await response.json();

                if (response.ok) {
                    uploadStatusDiv.textContent = `Upload successful! Image ID: ${result.id} (${result.filename})`;
                    uploadStatusDiv.className = 'upload-status success';
                    uploadForm.reset(); 
                } else {
                    uploadStatusDiv.textContent = `Upload failed: ${result.detail || response.statusText || 'Unknown error'}`;
                    uploadStatusDiv.className = 'upload-status error';
                }
            } catch (error) {
                console.error('Error uploading image:', error);
                uploadStatusDiv.textContent = `Upload error: ${error.message || 'Network error or server unavailable'}`;
                uploadStatusDiv.className = 'upload-status error';
            } finally {
                submitUploadButton.disabled = false;
            }
        });
    }
});

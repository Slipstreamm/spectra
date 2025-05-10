document.addEventListener('DOMContentLoaded', () => {
    const uploadForm = document.getElementById('uploadForm');
    const imageFileIn = document.getElementById('imageFile');
    const imageTagsIn = document.getElementById('imageTags');
    const uploadStatusDiv = document.getElementById('uploadStatus');
    const galleryContainer = document.getElementById('galleryContainer');

    // Define API base URL - adjust if your FastAPI runs elsewhere or has a prefix
    const API_BASE_URL = 'http://localhost:8000/api/v1'; // FastAPI runs on port 8000 with /api/v1 prefix

    // Function to fetch and display images
    async function fetchImages() {
        try {
            // Adjust the endpoint if your API has a version prefix like /api/v1
            const response = await fetch(`${API_BASE_URL}/images/`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const result = await response.json(); // Expecting PaginatedImages model
            
            galleryContainer.innerHTML = ''; // Clear previous content

            if (result.data && result.data.length > 0) {
                result.data.forEach(image => {
                    const imageDiv = document.createElement('div');
                    imageDiv.className = 'gallery-item';

                    const imgElement = document.createElement('img');
                    // Use image.image_url if populated by backend, otherwise construct from filepath
                    imgElement.src = image.image_url || `${API_BASE_URL}/static/uploads/${image.filename}`; // Adjust if API serves static files differently
                    imgElement.alt = image.filename;

                    const tagsDiv = document.createElement('div');
                    tagsDiv.className = 'tags';
                    tagsDiv.textContent = `Tags: ${image.tags.map(tag => tag.name).join(', ') || 'None'}`;
                    
                    const detailsDiv = document.createElement('div');
                    detailsDiv.className = 'details';
                    detailsDiv.innerHTML = `
                        <p>Filename: ${image.filename}</p>
                        <p>Uploaded: ${new Date(image.uploaded_at).toLocaleString()}</p>
                    `;

                    imageDiv.appendChild(imgElement);
                    imageDiv.appendChild(tagsDiv);
                    imageDiv.appendChild(detailsDiv);
                    galleryContainer.appendChild(imageDiv);
                });
            } else {
                galleryContainer.innerHTML = '<p>No images found.</p>';
            }
        } catch (error) {
            console.error('Error fetching images:', error);
            galleryContainer.innerHTML = `<p>Error loading images: ${error.message}</p>`;
        }
    }

    // Handle form submission
    if (uploadForm) {
        uploadForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            uploadStatusDiv.textContent = 'Uploading...';

            const formData = new FormData();
            formData.append('file', imageFileIn.files[0]);
            
            // Tags are sent as a comma-separated string in a form field,
            // which FastAPI can then parse.
            // Or, you can send it as 'tags' multiple times if your backend expects a list.
            // For simplicity, sending as a single string that the backend splits.
            formData.append('tags_str', imageTagsIn.value);


            try {
                // Adjust the endpoint if your API has a version prefix like /api/v1
                const response = await fetch(`${API_BASE_URL}/upload/`, {
                    method: 'POST',
                    body: formData,
                    // 'Content-Type': 'multipart/form-data' is automatically set by browser for FormData
                });

                const result = await response.json();

                if (response.ok) {
                    uploadStatusDiv.textContent = `Upload successful! Image ID: ${result.id} (${result.filename})`;
                    uploadForm.reset(); // Clear the form
                    fetchImages(); // Refresh gallery
                } else {
                    uploadStatusDiv.textContent = `Upload failed: ${result.detail || response.statusText}`;
                }
            } catch (error) {
                console.error('Error uploading image:', error);
                uploadStatusDiv.textContent = `Upload error: ${error.message}`;
            }
        });
    }

    // Initial load of images
    fetchImages();
});

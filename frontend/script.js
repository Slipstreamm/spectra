document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const galleryContainer = document.getElementById('galleryContainer');
    const paginationControls = document.getElementById('paginationControls');
    const tagSearchInput = document.getElementById('tagSearchInput');
    const searchButton = document.getElementById('searchButton');
    const imageModal = document.getElementById('imageModal');
    const modalImage = document.getElementById('modalImage');
    const modalFilename = document.getElementById('modalFilename');
    const modalUploadedAt = document.getElementById('modalUploadedAt');
    const modalTagsContainer = document.getElementById('modalTags');
    const closeModalButton = imageModal.querySelector('.close-button');
    const tagDisplayArea = document.getElementById('tag-display-area'); // Added for sidebar tags
    // Auth-related DOM Elements
    const loginLink = document.getElementById('loginLink');
    const registerLink = document.getElementById('registerLink');
    const logoutLink = document.getElementById('logoutLink');
    const userInfoDisplay = document.getElementById('userInfo');
    const usernameDisplay = document.getElementById('usernameDisplay');
    // const accountLink = document.getElementById('accountLink');


    // API and App State
    const API_BASE_URL = '/api/v1'; // Assuming backend is served from the same host
    const IMAGES_PER_PAGE = 20; // Or get from backend if configurable
    let currentPage = 1;
    let currentTags = '';
    // serverThemeConfig is removed as theme logic is now in theme.js

    // --- Authentication Handling ---
    // Theme related functions (applyServerThemeColors, loadAndApplyThemePreference, applyLocalThemePreference)
    // and the themeToggleButton event listener have been moved to frontend/theme.js
    function getAuthToken() {
        return localStorage.getItem('authToken');
    }

    function getUsername() {
        return localStorage.getItem('username');
    }

    function getUserRole() {
        return localStorage.getItem('userRole');
    }

    function updateAuthUI() {
        const token = getAuthToken();
        const username = getUsername();
        const role = getUserRole();

        if (token && username) {
            loginLink.style.display = 'none';
            registerLink.style.display = 'none';
            logoutLink.style.display = 'inline-block';
            userInfoDisplay.style.display = 'inline';
            usernameDisplay.textContent = `${username} (${role || 'user'})`; // Display role
            // Example: Show admin link if user is admin or owner
            // const adminDashboardLink = document.getElementById('adminDashboardLink'); // Assuming you add this link
            // if (adminDashboardLink) {
            //     if (role === 'admin' || role === 'owner') {
            //         adminDashboardLink.style.display = 'inline-block';
            //     } else {
            //         adminDashboardLink.style.display = 'none';
            //     }
            // }
        } else {
            loginLink.style.display = 'inline-block';
            registerLink.style.display = 'inline-block';
            logoutLink.style.display = 'none';
            userInfoDisplay.style.display = 'none';
            usernameDisplay.textContent = '';
            // const adminDashboardLink = document.getElementById('adminDashboardLink');
            // if (adminDashboardLink) adminDashboardLink.style.display = 'none';
        }
    }

    function handleLogout() {
        localStorage.removeItem('authToken');
        localStorage.removeItem('username');
        localStorage.removeItem('userRole'); // Remove role on logout
        // Potentially call a backend logout endpoint
        updateAuthUI();
        window.location.reload(); // Reload to clear any user-specific state or redirect
    }

    if (logoutLink) {
        logoutLink.addEventListener('click', (event) => {
            event.preventDefault();
            handleLogout();
        });
    }

    // --- Image Fetching and Rendering ---
    async function fetchImages(tags = '', page = 1) {
        currentTags = tags;
        currentPage = page;
        galleryContainer.innerHTML = '<p class="status-message">Loading images...</p>';
        paginationControls.innerHTML = ''; // Clear old pagination

        let queryParams = `?page=${page}&limit=${IMAGES_PER_PAGE}`;
        if (tags) {
            queryParams += `&tags=${encodeURIComponent(tags.trim().split(/\s+/).join(','))}`; // Split by space, join by comma for API
        }

        try {
            const response = await fetch(`${API_BASE_URL}/posts/${queryParams}`); // Changed from /images/ to /posts/
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const result = await response.json(); // Expecting { data: [], total_items: N, total_pages: N, current_page: N }

            renderGallery(result.data || []);
            renderPagination(result.total_pages || 0, result.current_page || 1);

        } catch (error) {
            console.error('Error fetching images:', error);
            galleryContainer.innerHTML = `<p class="status-message">Error loading images: ${error.message}</p>`;
        }
    }

    function renderGallery(images) {
        galleryContainer.innerHTML = ''; // Clear previous content
        if (images.length === 0) {
            galleryContainer.innerHTML = '<p class="status-message">No images found for the current filter.</p>';
            return;
        }

        images.forEach(post => { // Renamed 'image' to 'post' for clarity
            const itemDiv = document.createElement('div');
            itemDiv.className = 'gallery-item';

            // Add classes for video/gif based on mimetype
            if (post.mimetype) {
                if (post.mimetype.startsWith('video/')) {
                    itemDiv.classList.add('video-post');
                } else if (post.mimetype === 'image/gif') {
                    itemDiv.classList.add('gif-post');
                }
            }
            
            // Click navigates to post detail page
            itemDiv.addEventListener('click', () => {
                window.location.href = `post.html?id=${post.id}`;
            });

            const imgElement = document.createElement('img');
            imgElement.src = post.thumbnail_url || post.image_url || `${API_BASE_URL}/static/uploads/${post.filename}`; // Prefer thumbnail
            imgElement.alt = post.title || post.filename; // Use title for alt text if available
            imgElement.loading = 'lazy'; // Lazy load images

            const infoDiv = document.createElement('div');
            infoDiv.className = 'gallery-item-info';
            
            // Comment Count
            const commentsElement = document.createElement('p');
            commentsElement.className = 'post-comments';
            commentsElement.textContent = `Comments: ${post.comment_count !== undefined ? post.comment_count : 'N/A'}`;
            infoDiv.appendChild(commentsElement);

            // Vote Score
            const votesElement = document.createElement('p');
            votesElement.className = 'post-votes';
            const voteScore = (post.upvotes !== undefined && post.downvotes !== undefined) ? (post.upvotes - post.downvotes) : 'N/A';
            votesElement.textContent = `Score: ${voteScore}`;
            infoDiv.appendChild(votesElement);

            // Tags (similar to before, but using 'post' object)
            // const tagsDiv = document.createElement('div');
            // tagsDiv.className = 'tags';
            // if (post.tags && post.tags.length > 0) {
            //     post.tags.slice(0, 3).forEach(tag => { // Show a few tags
            //         const tagSpan = document.createElement('span');
            //         tagSpan.textContent = tag.name;
            //         tagsDiv.appendChild(tagSpan);
            //     });
            //     if (post.tags.length > 3) {
            //         const moreSpan = document.createElement('span');
            //         moreSpan.textContent = `+${post.tags.length - 3}`;
            //         tagsDiv.appendChild(moreSpan);
            //     }
            // } else {
            //     tagsDiv.textContent = 'No tags';
            // }
            // infoDiv.appendChild(tagsDiv);
            
            itemDiv.appendChild(imgElement);
            itemDiv.appendChild(infoDiv);
            galleryContainer.appendChild(itemDiv);
        });
    }

    function renderPagination(totalPages, page) {
        paginationControls.innerHTML = '';
        if (totalPages <= 1) return;

        const prevButton = document.createElement('button');
        prevButton.id = 'prevPage';
        prevButton.textContent = 'Previous';
        prevButton.disabled = page <= 1;
        prevButton.addEventListener('click', () => fetchImages(currentTags, page - 1));
        paginationControls.appendChild(prevButton);

        const pageInfo = document.createElement('span');
        pageInfo.className = 'current-page';
        pageInfo.textContent = `Page ${page} of ${totalPages}`;
        paginationControls.appendChild(pageInfo);

        const nextButton = document.createElement('button');
        nextButton.id = 'nextPage';
        nextButton.textContent = 'Next';
        nextButton.disabled = page >= totalPages;
        nextButton.addEventListener('click', () => fetchImages(currentTags, page + 1));
        paginationControls.appendChild(nextButton);
    }

    // --- Modal Logic ---
    function openModal(image) {
        modalImage.src = image.image_url || `${API_BASE_URL}/static/uploads/${image.filename}`;
        modalFilename.textContent = image.filename;
        modalUploadedAt.textContent = new Date(image.uploaded_at).toLocaleString();
        
        modalTagsContainer.innerHTML = '';
        if (image.tags && image.tags.length > 0) {
            image.tags.forEach(tag => {
                const tagSpan = document.createElement('span');
                tagSpan.textContent = tag.name;
                tagSpan.addEventListener('click', () => {
                    tagSearchInput.value = tag.name; // Set search to this tag
                    handleSearch();
                    closeModal();
                });
                modalTagsContainer.appendChild(tagSpan);
            });
        } else {
            modalTagsContainer.textContent = 'None';
        }
        imageModal.style.display = 'block';
    }

    function closeModal() {
        imageModal.style.display = 'none';
        modalImage.src = ''; // Clear image to free memory
    }

    closeModalButton.addEventListener('click', closeModal);
    window.addEventListener('click', (event) => { // Close if clicked outside modal content
        if (event.target === imageModal) {
            closeModal();
        }
    });
    window.addEventListener('keydown', (event) => { // Close with Escape key
        if (event.key === 'Escape' && imageModal.style.display === 'block') {
            closeModal();
        }
    });

    // --- Search Logic ---
    function handleSearch() {
        const tags = tagSearchInput.value.trim();
        fetchImages(tags, 1); // Reset to page 1 for new search
    }

    searchButton.addEventListener('click', handleSearch);
    tagSearchInput.addEventListener('keypress', (event) => {
        if (event.key === 'Enter') {
            handleSearch();
        }
    });
    
    // --- Tag Sidebar Logic ---
    async function fetchAndDisplayTags() {
        if (!tagDisplayArea) return; // Sidebar might not be on all pages

        try {
            const response = await fetch(`${API_BASE_URL}/tags/`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const tagsWithCounts = await response.json(); // Expecting List[models.TagWithCount]

            renderSidebarTags(tagsWithCounts);

        } catch (error) {
            console.error('Error fetching tags for sidebar:', error);
            tagDisplayArea.innerHTML = '<p class="status-message">Error loading tags.</p>';
        }
    }

    function renderSidebarTags(tagsWithCounts) {
        tagDisplayArea.innerHTML = '<h3>Tags</h3>'; // Reset and add title

        if (!tagsWithCounts || tagsWithCounts.length === 0) {
            tagDisplayArea.innerHTML += '<p>No tags available.</p>';
            return;
        }

        // Define categories and their prefixes
        const categories = {
            "Copyright": "copyright:",
            "Character": "character:",
            "Artist": "artist:",
            // Add more specific categories if needed
            // "Meta": "meta:", 
        };
        const generalTags = [];
        const categorizedTags = {};

        for (const categoryName in categories) {
            categorizedTags[categoryName] = [];
        }

        tagsWithCounts.forEach(tag => {
            let categorized = false;
            for (const categoryName in categories) {
                const prefix = categories[categoryName];
                if (tag.name.startsWith(prefix)) {
                    categorizedTags[categoryName].push({
                        ...tag,
                        displayName: tag.name.substring(prefix.length).replace(/_/g, ' ') // Clean display name
                    });
                    categorized = true;
                    break;
                }
            }
            if (!categorized) {
                generalTags.push({ ...tag, displayName: tag.name.replace(/_/g, ' ') });
            }
        });

        // Render categorized tags
        for (const categoryName in categories) {
            if (categorizedTags[categoryName].length > 0) {
                const categoryDiv = document.createElement('div');
                categoryDiv.className = 'tag-category';
                const categoryTitle = document.createElement('h4');
                categoryTitle.textContent = categoryName;
                categoryDiv.appendChild(categoryTitle);

                const ul = document.createElement('ul');
                categorizedTags[categoryName]
                    .sort((a, b) => b.post_count - a.post_count) // Sort by count within category
                    .forEach(tag => {
                        const li = document.createElement('li');
                        const a = document.createElement('a');
                        a.href = '#'; // Prevent page jump
                        a.textContent = `${tag.displayName} (${tag.post_count})`;
                        a.addEventListener('click', (e) => {
                            e.preventDefault();
                            tagSearchInput.value = tag.name; // Use original tag name for search
                            handleSearch();
                        });
                        li.appendChild(a);
                        ul.appendChild(li);
                    });
                categoryDiv.appendChild(ul);
                tagDisplayArea.appendChild(categoryDiv);
            }
        }

        // Render general tags
        if (generalTags.length > 0) {
            const generalCategoryDiv = document.createElement('div');
            generalCategoryDiv.className = 'tag-category';
            const generalTitle = document.createElement('h4');
            generalTitle.textContent = 'General';
            generalCategoryDiv.appendChild(generalTitle);

            const ul = document.createElement('ul');
            generalTags
                .sort((a, b) => b.post_count - a.post_count) // Sort by count
                .forEach(tag => {
                    const li = document.createElement('li');
                    const a = document.createElement('a');
                    a.href = '#';
                    a.textContent = `${tag.displayName} (${tag.post_count})`;
                    a.addEventListener('click', (e) => {
                        e.preventDefault();
                        tagSearchInput.value = tag.name;
                        handleSearch();
                    });
                    li.appendChild(a);
                    ul.appendChild(li);
                });
            generalCategoryDiv.appendChild(ul);
            tagDisplayArea.appendChild(generalCategoryDiv);
        }
    }

    // --- Initial Load ---
    const urlParams = new URLSearchParams(window.location.search);
    const initialTagsFromURL = urlParams.get('tags');
    if (initialTagsFromURL) {
        tagSearchInput.value = initialTagsFromURL.replace(/,/g, ' '); // Convert comma to space for input
        fetchImages(tagSearchInput.value, 1);
    } else {
        fetchImages('', 1); // Load all images on page 1 initially
    }
    fetchAndDisplayTags(); // Load tags for the sidebar

    // The old upload form logic is removed as per the new design focus.
    // If upload functionality is needed on this page, it would need to be re-integrated.

    // --- Initialize Auth UI ---
    updateAuthUI(); 
});

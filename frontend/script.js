document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const galleryContainer = document.getElementById('galleryContainer');
    const paginationControls = document.getElementById('paginationControls');
    const tagSearchInput = document.getElementById('tagSearchInput');
    const searchButton = document.getElementById('searchButton');
    const themeToggleButton = document.getElementById('themeToggle');
    const imageModal = document.getElementById('imageModal');
    const modalImage = document.getElementById('modalImage');
    const modalFilename = document.getElementById('modalFilename');
    const modalUploadedAt = document.getElementById('modalUploadedAt');
    const modalTagsContainer = document.getElementById('modalTags');
    const closeModalButton = imageModal.querySelector('.close-button');

    // API and App State
    const API_BASE_URL = '/api/v1'; // Assuming backend is served from the same host
    const IMAGES_PER_PAGE = 20; // Or get from backend if configurable
    let currentPage = 1;
    let currentTags = '';
    let serverThemeConfig = null; // To store fetched theme config

    // --- Theme Configuration and Toggling ---
    function applyServerThemeColors(themeName, themeData) {
        let styleSheet = document.getElementById('dynamic-theme-styles');
        if (!styleSheet) {
            styleSheet = document.createElement('style');
            styleSheet.id = 'dynamic-theme-styles';
            document.head.appendChild(styleSheet);
        }

        const themeColors = themeData[themeName];
        if (!themeColors) {
            console.warn(`Theme "${themeName}" not found in server configuration.`);
            return;
        }

        const cssVariables = Object.entries(themeColors)
            .map(([key, value]) => `--${key.replace(/_/g, '-')}: ${value};`)
            .join('\n');
        
        styleSheet.innerHTML = `
            html[data-theme="${themeName}"] {
                ${cssVariables}
            }
        `;
        // console.log(`Applied ${themeName} theme from server config.`);
    }

    async function loadAndApplyThemePreference() {
        try {
            const response = await fetch(`${API_BASE_URL}/theme-config`);
            if (!response.ok) {
                console.error('Failed to fetch theme configuration from server.');
                // Fallback to local theme application without server colors
                applyLocalThemePreference();
                return;
            }
            serverThemeConfig = await response.json();
            // console.log('Server theme config loaded:', serverThemeConfig);
            
            const preferredTheme = localStorage.getItem('spectraTheme') || 'dark'; // Or server default from config.site.default_theme if exposed
            applyServerThemeColors(preferredTheme, serverThemeConfig);
            document.documentElement.setAttribute('data-theme', preferredTheme);

        } catch (error) {
            console.error('Error fetching or applying server theme configuration:', error);
            applyLocalThemePreference(); // Fallback
        }
    }
    
    function applyLocalThemePreference() {
        // This is a fallback if server config fails, uses CSS defaults
        const preferredTheme = localStorage.getItem('spectraTheme') || 'dark';
        document.documentElement.setAttribute('data-theme', preferredTheme);
        // console.log(`Applied ${preferredTheme} theme using local preference (server config failed or not used).`);
    }


    themeToggleButton.addEventListener('click', () => {
        const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        
        if (serverThemeConfig) {
            applyServerThemeColors(newTheme, serverThemeConfig);
        }
        // Always set data-theme for CSS selectors and save preference
        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('spectraTheme', newTheme);
    });

    // Initial theme load
    loadAndApplyThemePreference();


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

        images.forEach(image => {
            const itemDiv = document.createElement('div');
            itemDiv.className = 'gallery-item';
            itemDiv.addEventListener('click', () => openModal(image));

            const imgElement = document.createElement('img');
            imgElement.src = image.thumbnail_url || image.image_url || `${API_BASE_URL}/static/uploads/${image.filename}`; // Prefer thumbnail
            imgElement.alt = image.filename;
            imgElement.loading = 'lazy'; // Lazy load images

            const infoDiv = document.createElement('div');
            infoDiv.className = 'gallery-item-info';

            const tagsDiv = document.createElement('div');
            tagsDiv.className = 'tags';
            if (image.tags && image.tags.length > 0) {
                image.tags.slice(0, 3).forEach(tag => { // Show a few tags
                    const tagSpan = document.createElement('span');
                    tagSpan.textContent = tag.name;
                    tagsDiv.appendChild(tagSpan);
                });
                if (image.tags.length > 3) {
                    const moreSpan = document.createElement('span');
                    moreSpan.textContent = `+${image.tags.length - 3}`;
                    tagsDiv.appendChild(moreSpan);
                }
            } else {
                tagsDiv.textContent = 'No tags';
            }
            
            infoDiv.appendChild(tagsDiv);
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
    
    // --- Initial Load ---
    // Check for tags in URL query params (e.g., ?tags=nature,sky)
    const urlParams = new URLSearchParams(window.location.search);
    const initialTagsFromURL = urlParams.get('tags');
    if (initialTagsFromURL) {
        tagSearchInput.value = initialTagsFromURL.replace(/,/g, ' '); // Convert comma to space for input
        fetchImages(tagSearchInput.value, 1);
    } else {
        fetchImages('', 1); // Load all images on page 1 initially
    }

    // The old upload form logic is removed as per the new design focus.
    // If upload functionality is needed on this page, it would need to be re-integrated.
});

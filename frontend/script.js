document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const galleryContainer = document.getElementById('galleryContainer');
    const paginationControls = document.getElementById('paginationControls');
    const tagSearchInput = document.getElementById('tagSearchInput');
    const searchButton = document.getElementById('searchButton'); // For tag search
    const imageModal = document.getElementById('imageModal');
    const modalImage = document.getElementById('modalImage');
    const modalFilename = document.getElementById('modalFilename');
    const modalUploadedAt = document.getElementById('modalUploadedAt');
    const modalTagsContainer = document.getElementById('modalTags');
    const closeModalButton = imageModal.querySelector('.close-button');
    const tagDisplayArea = document.getElementById('tag-display-area'); // Added for sidebar tags
    const sidebarTagFilterInput = document.getElementById('sidebarTagFilter'); // Added for the new filter input

    // Advanced Search DOM Elements
    const filterDateAfterInput = document.getElementById('filterDateAfter');
    const filterDateBeforeInput = document.getElementById('filterDateBefore');
    const filterMinScoreInput = document.getElementById('filterMinScore');
    const filterMinWidthInput = document.getElementById('filterMinWidth');
    const filterMinHeightInput = document.getElementById('filterMinHeight');
    const filterUploaderInput = document.getElementById('filterUploader');
    const applyAdvancedSearchButton = document.getElementById('applyAdvancedSearchButton');

    // Auth-related DOM Elements
    const loginLink = document.getElementById('loginLink');
    const registerLink = document.getElementById('registerLink');
    const logoutLink = document.getElementById('logoutLink');
    const userInfoDisplay = document.getElementById('userInfo');
    const usernameDisplay = document.getElementById('usernameDisplay');
    const itemsPerPageSelect = document.getElementById('itemsPerPageSelect');
    const controlsBar = document.getElementById('controlsBar');
    const galleryContainerElement = document.getElementById('galleryContainer'); // Ensure this is the one we modify
    // const accountLink = document.getElementById('accountLink');


    // API and App State
    const API_BASE_URL = '/api/v1'; // Assuming backend is served from the same host
    let IMAGES_PER_PAGE = 20; // Default, will be updated by select
    let currentPage = 1;
    let currentTags = '';
    let currentSortBy = 'date'; // Default sort: 'date', 'score', 'id', 'random'
    let currentOrder = 'desc'; // Default order: 'asc', 'desc'
    let currentAdvancedFilters = {}; // To store advanced filter values
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
    async function fetchImages(tags = '', page = 1, sort_by = currentSortBy, order = currentOrder, limit = IMAGES_PER_PAGE, advancedFilters = currentAdvancedFilters) {
        currentTags = tags; // Basic tag search
        currentPage = page;
        currentSortBy = sort_by;
        currentOrder = order;
        IMAGES_PER_PAGE = parseInt(limit, 10);
        currentAdvancedFilters = advancedFilters; // Store current advanced filters

        galleryContainer.innerHTML = '<p class="status-message">Loading images...</p>';
        paginationControls.innerHTML = ''; // Clear old pagination

        let queryParams = new URLSearchParams({
            page: page,
            limit: IMAGES_PER_PAGE,
            sort_by: sort_by,
            order: order
        });

        if (tags) {
            queryParams.set('tags', tags.trim().split(/\s+/).join(','));
        }

        // Append advanced filters
        for (const key in advancedFilters) {
            if (advancedFilters[key]) { // Only add if value is present
                queryParams.set(key, advancedFilters[key]);
            }
        }
        
        const queryString = queryParams.toString();

        try {
            const response = await fetch(`${API_BASE_URL}/posts/?${queryString}`); // Changed from /images/ to /posts/
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

    function renderPagination(totalPages, currentPage) {
        paginationControls.innerHTML = '';
        if (totalPages <= 1) return;

        const createPageButton = (text, targetPage, isDisabled = false, isCurrent = false, isEllipsis = false) => {
            const button = document.createElement(isEllipsis ? 'span' : 'button');
            button.textContent = text;
            if (isEllipsis) {
                button.className = 'pagination-ellipsis';
            } else {
                button.className = 'pagination-button';
                if (isCurrent) {
                    button.classList.add('active');
                    button.disabled = true; // Disable current page button
                }
                if (isDisabled && !isCurrent) { // Don't re-disable if already current
                    button.disabled = true;
                }
                if (!isDisabled && !isEllipsis) {
                    // Pass currentAdvancedFilters to pagination clicks
                    button.addEventListener('click', () => fetchImages(currentTags, targetPage, currentSortBy, currentOrder, IMAGES_PER_PAGE, currentAdvancedFilters));
                }
            }
            return button;
        };

        // First Button
        paginationControls.appendChild(createPageButton('First', 1, currentPage === 1));

        // Previous Button
        paginationControls.appendChild(createPageButton('Previous', currentPage - 1, currentPage === 1));

        // Page Number Buttons
        const contextPages = 2; // Number of pages to show around the current page
        let pagesToShow = new Set();

        // Add first page
        pagesToShow.add(1);

        // Add pages around current page
        for (let i = Math.max(1, currentPage - contextPages); i <= Math.min(totalPages, currentPage + contextPages); i++) {
            pagesToShow.add(i);
        }

        // Add last page
        pagesToShow.add(totalPages);

        const sortedPages = Array.from(pagesToShow).sort((a, b) => a - b);
        let lastPageShown = 0;

        sortedPages.forEach(p => {
            if (p > lastPageShown + 1 && lastPageShown > 0) { // Check lastPageShown > 0 to avoid ellipsis before page 1 if 1 isn't in contextPages
                paginationControls.appendChild(createPageButton('...', 0, true, false, true)); // Ellipsis
            }
            if (p > 0) { // Ensure page number is valid
                 paginationControls.appendChild(createPageButton(p.toString(), p, false, p === currentPage));
            }
            lastPageShown = p;
        });
        
        // Next Button
        paginationControls.appendChild(createPageButton('Next', currentPage + 1, currentPage === totalPages));

        // Last Button
        paginationControls.appendChild(createPageButton('Last', totalPages, currentPage === totalPages));
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
    function handleTagSearch() { // Renamed from handleSearch
        const tags = tagSearchInput.value.trim();
        currentAdvancedFilters = {}; // Clear advanced filters when doing a new tag search
        clearAdvancedFilterInputs();
        fetchImages(tags, 1, currentSortBy, currentOrder, IMAGES_PER_PAGE, {}); // Reset to page 1, clear advanced filters
    }

    if (searchButton) { // For tag search
        searchButton.addEventListener('click', handleTagSearch);
    }
    if (tagSearchInput) {
        tagSearchInput.addEventListener('keypress', (event) => {
            if (event.key === 'Enter') {
                handleTagSearch();
            }
        });
    }

    function handleAdvancedSearch() {
        const filters = {
            uploaded_after: filterDateAfterInput.value,
            uploaded_before: filterDateBeforeInput.value,
            min_score: filterMinScoreInput.value ? parseInt(filterMinScoreInput.value, 10) : '',
            min_width: filterMinWidthInput.value ? parseInt(filterMinWidthInput.value, 10) : '',
            min_height: filterMinHeightInput.value ? parseInt(filterMinHeightInput.value, 10) : '',
            uploader_name: filterUploaderInput.value.trim()
        };
        // When applying advanced search, we might want to use current tags from tagSearchInput or clear them.
        // For now, let's assume advanced search can be combined with tags in the main search bar.
        const tags = tagSearchInput.value.trim(); 
        fetchImages(tags, 1, currentSortBy, currentOrder, IMAGES_PER_PAGE, filters);
    }

    if (applyAdvancedSearchButton) {
        applyAdvancedSearchButton.addEventListener('click', handleAdvancedSearch);
    }
    
    function clearAdvancedFilterInputs() {
        if(filterDateAfterInput) filterDateAfterInput.value = '';
        if(filterDateBeforeInput) filterDateBeforeInput.value = '';
        if(filterMinScoreInput) filterMinScoreInput.value = '';
        if(filterMinWidthInput) filterMinWidthInput.value = '';
        if(filterMinHeightInput) filterMinHeightInput.value = '';
        if(filterUploaderInput) filterUploaderInput.value = '';
    }

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
        const popularTagsLimit = 10; // Number of popular tags to show

        for (const categoryName in categories) {
            categorizedTags[categoryName] = [];
        }

        // Sort all tags by post_count to easily get popular tags
        const sortedAllTags = [...tagsWithCounts].sort((a, b) => b.post_count - a.post_count);

        // Populate categorized tags and general tags
        // Iterate over a copy for categorization, so sortedAllTags remains for "Most Popular"
        [...tagsWithCounts].forEach(tag => {
            let categorized = false;
            for (const categoryName in categories) {
                const prefix = categories[categoryName];
                if (tag.name.startsWith(prefix)) {
                    categorizedTags[categoryName].push({
                        ...tag,
                        displayName: tag.name.substring(prefix.length).replace(/_/g, ' ')
                    });
                    categorized = true;
                    break;
                }
            }
            if (!categorized) {
                generalTags.push({ ...tag, displayName: tag.name.replace(/_/g, ' ') });
            }
        });
        
        // Render "Most Popular Tags" section
        if (sortedAllTags.length > 0) {
            const popularCategoryDiv = document.createElement('div');
            popularCategoryDiv.className = 'tag-category popular-tags-category';
            const popularTitle = document.createElement('h4');
            popularTitle.textContent = 'Most Popular';
            popularCategoryDiv.appendChild(popularTitle);
            const popularUl = document.createElement('ul');
            sortedAllTags.slice(0, popularTagsLimit).forEach(tag => {
                const li = document.createElement('li');
                const a = document.createElement('a');
                a.href = '#';
                // For popular tags, display the original name (with underscores) and count
                a.textContent = `${tag.name.replace(/_/g, ' ')} (${tag.post_count})`; 
                a.addEventListener('click', (e) => {
                    e.preventDefault();
                    tagSearchInput.value = tag.name; // Use original tag name for search
                    handleTagSearch(); // Use new tag search handler
                });
                li.appendChild(a);
                popularUl.appendChild(li);
            });
            popularCategoryDiv.appendChild(popularUl);
            tagDisplayArea.appendChild(popularCategoryDiv);
        }

        // Render other categorized tags
        for (const categoryName in categories) {
            if (categorizedTags[categoryName].length > 0) {
                // Sort within specific categories as well
                categorizedTags[categoryName].sort((a,b) => b.post_count - a.post_count);
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
                            handleTagSearch(); // Use new tag search handler
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
                        handleTagSearch(); // Use new tag search handler
                    });
                    li.appendChild(a);
                    ul.appendChild(li);
                });
            generalCategoryDiv.appendChild(ul);
            tagDisplayArea.appendChild(generalCategoryDiv);
        }
    }

    if (sidebarTagFilterInput && tagDisplayArea) {
        sidebarTagFilterInput.addEventListener('input', () => {
            const filterText = sidebarTagFilterInput.value.toLowerCase().trim();
            const tagLinks = tagDisplayArea.querySelectorAll('.tag-category ul li a');
            tagLinks.forEach(link => {
                const tagName = link.textContent.toLowerCase();
                const listItem = link.closest('li'); // Get the parent <li>
                if (tagName.includes(filterText)) {
                    listItem.style.display = '';
                } else {
                    listItem.style.display = 'none';
                }
            });

            // Also show/hide category titles if all their tags are hidden
            const categories = tagDisplayArea.querySelectorAll('.tag-category');
            categories.forEach(category => {
                const visibleItems = category.querySelectorAll('ul li[style*="display: initial"], ul li:not([style*="display: none"])');
                const title = category.querySelector('h4');
                if (title) { // Ensure title exists
                    if (visibleItems.length > 0) {
                        title.style.display = '';
                        category.style.display = ''; // Show the category div itself
                    } else {
                        // If the category is "Most Popular" and it's empty due to filter, hide it.
                        // Otherwise, for normal categories, if all items are filtered out, hide the category.
                        // This prevents hiding "Most Popular" if it was empty to begin with.
                        if (!category.classList.contains('popular-tags-category') || filterText) {
                             title.style.display = 'none';
                             category.style.display = 'none'; // Hide the category div itself
                        } else if (category.classList.contains('popular-tags-category') && visibleItems.length === 0 && filterText) {
                            // Specifically hide popular if it has items but all are filtered out
                            title.style.display = 'none';
                            category.style.display = 'none';
                        } else {
                            // Keep popular visible if it was initially empty and no filter text
                             title.style.display = '';
                             category.style.display = '';
                        }
                    }
                }
            });
        });
    }

    // --- Site Info Fetching and Applying ---
    async function fetchAndApplySiteInfo() {
        try {
            const response = await fetch(`${API_BASE_URL}/site-info`);
            if (!response.ok) {
                console.error(`HTTP error fetching site info! status: ${response.status}`);
                return;
            }
            const siteInfo = await response.json(); // Expecting { name: "...", description: "..." }

            // Update document title
            document.title = siteInfo.name || 'Image Gallery';

            // Update meta description tag
            let metaDescription = document.querySelector('meta[name="description"]');
            if (!metaDescription) {
                metaDescription = document.createElement('meta');
                metaDescription.setAttribute('name', 'description');
                document.head.appendChild(metaDescription);
            }
            metaDescription.setAttribute('content', siteInfo.description || 'Browse and enjoy images.');

            // Update Open Graph title
            let ogTitle = document.querySelector('meta[property="og:title"]');
            if (ogTitle) {
                ogTitle.setAttribute('content', siteInfo.name || 'Image Gallery');
            }

            // Update Open Graph description
            let ogDescription = document.querySelector('meta[property="og:description"]');
            if (ogDescription) {
                ogDescription.setAttribute('content', siteInfo.description || 'Browse and enjoy images.');
            }

            // Update visible site title in header
            const siteTitleElement = document.querySelector('.site-title');
            if (siteTitleElement) {
                siteTitleElement.textContent = siteInfo.name || 'Image Gallery';
            }

            // Update footer copyright (if it exists and follows a pattern)
            const footerParagraphs = document.querySelectorAll('footer p');
            footerParagraphs.forEach(p => {
                if (p.textContent.includes('Spectra Gallery')) { // Simple check
                    p.textContent = p.textContent.replace('Spectra Gallery', siteInfo.name || 'The Gallery');
                }
                // More robust: if footer has a specific ID/class for copyright text
                // const copyrightElement = document.getElementById('copyrightSiteName');
                // if (copyrightElement) copyrightElement.textContent = siteInfo.name;
            });

        } catch (error) {
            console.error('Error fetching or applying site info:', error);
        }
    }

    // --- Initial Load ---
    const urlParams = new URLSearchParams(window.location.search);
    const initialTagsFromURL = urlParams.get('tags');

    // Initialize items per page from select, or default
    if (itemsPerPageSelect) {
        IMAGES_PER_PAGE = parseInt(itemsPerPageSelect.value, 10); // Set initial based on HTML selected
        itemsPerPageSelect.addEventListener('change', (event) => {
            const newLimit = parseInt(event.target.value, 10);
            // Pass currentAdvancedFilters when changing items per page
            fetchImages(currentTags, 1, currentSortBy, currentOrder, newLimit, currentAdvancedFilters); 
        });
    }

    // Initialize sort buttons
    if (controlsBar) {
        const sortButtons = controlsBar.querySelectorAll('.sort-button');
        sortButtons.forEach(button => {
            if (button.dataset.sort === currentSortBy && (currentSortBy === 'random' || button.dataset.order === currentOrder)) {
                button.classList.add('active');
            }
            button.addEventListener('click', () => {
                sortButtons.forEach(btn => btn.classList.remove('active'));
                button.classList.add('active');
                const sortBy = button.dataset.sort;
                const sortOrder = button.dataset.order || 'desc';
                // Pass currentAdvancedFilters when changing sort
                fetchImages(currentTags, 1, sortBy, sortOrder, IMAGES_PER_PAGE, currentAdvancedFilters);
            });
        });

        // Initialize Thumbnail Size Controls
        const thumbnailSizeButtons = controlsBar.querySelectorAll('.thumbnail-size-button');
        let currentThumbnailSize = localStorage.getItem('thumbnailSize') || 'medium'; // Default to medium

        function applyThumbnailSize(size) {
            if (galleryContainerElement) {
                galleryContainerElement.classList.remove('size-small', 'size-medium', 'size-large');
                galleryContainerElement.classList.add(`size-${size}`);
            }
            thumbnailSizeButtons.forEach(btn => {
                btn.classList.toggle('active', btn.dataset.size === size);
            });
            localStorage.setItem('thumbnailSize', size);
            currentThumbnailSize = size; // Update state variable
        }

        thumbnailSizeButtons.forEach(button => {
            button.addEventListener('click', () => {
                applyThumbnailSize(button.dataset.size);
            });
        });
        applyThumbnailSize(currentThumbnailSize); // Apply initial size on load
    }


    if (initialTagsFromURL) {
        tagSearchInput.value = initialTagsFromURL.replace(/,/g, ' '); // Convert comma to space for input
        // Initial load with URL tags, no advanced filters initially
        fetchImages(tagSearchInput.value, 1, currentSortBy, currentOrder, IMAGES_PER_PAGE, {}); 
    } else {
        // Initial load, no tags, no advanced filters
        fetchImages('', 1, currentSortBy, currentOrder, IMAGES_PER_PAGE, {}); 
    }
    fetchAndDisplayTags(); // Load tags for the sidebar
    fetchAndApplySiteInfo(); // Load and apply site name and description

    // The old upload form logic is removed as per the new design focus.
    // If upload functionality is needed on this page, it would need to be re-integrated.

    // --- Initialize Auth UI ---
    updateAuthUI(); 
});

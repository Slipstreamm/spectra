import asyncpg
import redis.asyncio as redis_async
import json
from typing import List, Dict, Any, Optional # Added Optional
from . import models # Using models directly as Pydantic models for API and DB representation for now
# from .core.config import settings # May not be needed directly in crud

# Cache constants
IMAGE_CACHE_PREFIX = "image:"
IMAGE_LIST_CACHE_PREFIX = "images_list:"
IMAGE_COUNT_CACHE_PREFIX = "images_count:"
CACHE_EXPIRY_SECONDS = 300 # 5 minutes, adjust as needed


async def get_or_create_tag(db: asyncpg.Connection, tag_name: str) -> models.Tag:
    """
    Retrieves a tag by name if it exists, otherwise creates it.
    Returns the tag object (Pydantic model).
    """
    tag_name_cleaned = tag_name.strip().lower()
    if not tag_name_cleaned:
        # Should not happen if input is validated, but as a safeguard
        raise ValueError("Tag name cannot be empty.")

    async with db.transaction():
        # Try to fetch the existing tag
        tag_record = await db.fetchrow("SELECT id, name FROM tags WHERE name = $1", tag_name_cleaned)
        if tag_record:
            return models.Tag(id=tag_record['id'], name=tag_record['name'])
        
        # If not found, create it
        # RETURNING id, name ensures we get the created record back
        created_tag_record = await db.fetchrow(
            "INSERT INTO tags (name) VALUES ($1) RETURNING id, name",
            tag_name_cleaned
        )
        if not created_tag_record:
            # This should ideally not happen if INSERT is successful
            raise Exception(f"Failed to create tag: {tag_name_cleaned}")
        return models.Tag(id=created_tag_record['id'], name=created_tag_record['name'])

async def create_image_with_tags(
    db: asyncpg.Connection,
    redis: redis_async.Redis, # Added redis client for cache invalidation
    image_data: models.ImageCreate, # Contains filename, mimetype, filesize, and list of tag names
    filepath_on_disk: str # The actual path stored in the DB, e.g., "backend/uploads/uuid.jpg"
) -> models.Image:
    """
    Creates an image record in the database and associates it with the given tags.
    Handles finding or creating tags as needed.
    Returns the created image object (Pydantic model) including its tags.
    """
    async with db.transaction():
        # 1. Insert the image metadata
        image_insert_query = """
            INSERT INTO images (filename, filepath, mimetype, filesize)
            VALUES ($1, $2, $3, $4)
            RETURNING id, filename, filepath, mimetype, filesize, uploaded_at
        """
        image_record = await db.fetchrow(
            image_insert_query,
            image_data.filename,
            filepath_on_disk, # Use the passed filepath_on_disk
            image_data.mimetype,
            image_data.filesize
        )

        if not image_record:
            raise Exception("Failed to create image record in database.")

        created_image_id = image_record['id']
        processed_tags: List[models.Tag] = []

        # 2. Process tags: get or create each tag and associate with the image
        if image_data.tags:
            for tag_name in image_data.tags:
                tag_name_cleaned = tag_name.strip().lower()
                if not tag_name_cleaned:
                    continue # Skip empty tags that might result from "tag1,,tag2"

                tag_obj = await get_or_create_tag(db, tag_name_cleaned)
                processed_tags.append(tag_obj)

                # 3. Link image to tag in the image_tags junction table
                await db.execute(
                    "INSERT INTO image_tags (image_id, tag_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                    created_image_id,
                    tag_obj.id
                )
        
        # Construct the Pydantic model for the response
        # The image_record is an asyncpg.Record, which is dict-like
        response_image = models.Image(
            id=image_record['id'],
            filename=image_record['filename'],
            filepath=image_record['filepath'],
            mimetype=image_record['mimetype'],
            filesize=image_record['filesize'],
            uploaded_at=image_record['uploaded_at'],
            tags=processed_tags,
            image_url=None # URL will be populated in the router
        )
        
        # Cache invalidation:
        # Clear any general list caches and count caches.
        # More specific invalidation (e.g., by tags) can be complex.
        # For now, a simpler approach: delete all list and count caches.
        # A more advanced strategy might involve deleting caches that *could* include this new image.
        
        # Delete all keys matching IMAGE_LIST_CACHE_PREFIX and IMAGE_COUNT_CACHE_PREFIX
        # This is a broad invalidation. For high-traffic sites, more granular invalidation is needed.
        list_cache_keys = [key async for key in redis.scan_iter(match=f"{IMAGE_LIST_CACHE_PREFIX}*")]
        if list_cache_keys:
            await redis.delete(*list_cache_keys)
            print(f"Invalidated {len(list_cache_keys)} list caches.")

        count_cache_keys = [key async for key in redis.scan_iter(match=f"{IMAGE_COUNT_CACHE_PREFIX}*")]
        if count_cache_keys:
            await redis.delete(*count_cache_keys)
            print(f"Invalidated {len(count_cache_keys)} count caches.")

        # The individual image cache (IMAGE_CACHE_PREFIX:{created_image_id}) doesn't need invalidation
        # here as it's a new image, it won't be cached yet.

        return response_image


async def get_image(db: asyncpg.Connection, redis: redis_async.Redis, image_id: int) -> Optional[models.Image]:
    """
    Retrieves a single image by its ID, along with its tags.
    Checks cache first.
    """
    cache_key = f"{IMAGE_CACHE_PREFIX}{image_id}"
    cached_image_json = await redis.get(cache_key)

    if cached_image_json:
        try:
            image_dict = json.loads(cached_image_json)
            # Ensure tags are correctly parsed if stored as list of dicts
            image_dict['tags'] = [models.Tag(**tag_data) for tag_data in image_dict.get('tags', [])]
            print(f"Cache HIT for image ID: {image_id}")
            return models.Image(**image_dict)
        except json.JSONDecodeError:
            print(f"Error decoding cached image for ID: {image_id}. Fetching from DB.")
            # Fall through to DB fetch if cache is corrupted

    # If not in cache or cache error, fetch from DB
    print(f"Cache MISS for image ID: {image_id}. Fetching from DB.")
    query = """
        SELECT
            i.id, i.filename, i.filepath, i.mimetype, i.filesize, i.uploaded_at,
            COALESCE(
                (SELECT json_agg(json_build_object('id', t.id, 'name', t.name))
                 FROM tags t JOIN image_tags it ON t.id = it.tag_id
                 WHERE it.image_id = i.id),
                '[]'::json
            ) AS tags
        FROM images i
        WHERE i.id = $1;
    """
    image_record = await db.fetchrow(query, image_id)
    if not image_record:
        return None

    # image_record['tags'] will be a list of dicts from json_agg
    # Pydantic should handle this conversion for the List[models.Tag]
    db_image_model = models.Image(
        id=image_record['id'],
        filename=image_record['filename'],
        filepath=image_record['filepath'],
        mimetype=image_record['mimetype'],
        filesize=image_record['filesize'],
        uploaded_at=image_record['uploaded_at'],
        tags=[models.Tag(**tag_data) for tag_data in image_record['tags']], # Explicitly map if needed
        image_url=None # URL to be populated in router
    )
    
    # Store in cache before returning
    # Pydantic's model_dump_json (v2) or .json() (v1) is useful here
    await redis.set(cache_key, db_image_model.model_dump_json(), ex=CACHE_EXPIRY_SECONDS)
    print(f"DB HIT for image ID: {image_id}. Stored in cache.")
    return db_image_model


async def get_images(
    db: asyncpg.Connection,
    redis: redis_async.Redis, # Added redis client
    skip: int = 0,
    limit: int = 10,
    tags_filter: Optional[List[str]] = None
) -> List[models.Image]:
    """
    Retrieves a list of images, optionally filtered by tags, with pagination.
    Checks cache first.
    """
    # Create a cache key based on parameters
    # Normalize tags_filter for consistent cache key
    normalized_tags_key_part = "_".join(sorted([tag.strip().lower() for tag in tags_filter])) if tags_filter else "all"
    cache_key = f"{IMAGE_LIST_CACHE_PREFIX}skip_{skip}_limit_{limit}_tags_{normalized_tags_key_part}"

    cached_images_json = await redis.get(cache_key)
    if cached_images_json:
        try:
            images_dict_list = json.loads(cached_images_json)
            response_images = []
            for img_dict in images_dict_list:
                img_dict['tags'] = [
                    models.Tag(**tag_data) if isinstance(tag_data, dict) else models.Tag(id=0, name=tag_data)
                    for tag_data in img_dict.get('tags', [])
                ]
                response_images.append(models.Image(**img_dict))
            print(f"Cache HIT for image list: {cache_key}")
            return response_images
        except json.JSONDecodeError:
            print(f"Error decoding cached image list for key: {cache_key}. Fetching from DB.")
            # Fall through

    print(f"Cache MISS for image list: {cache_key}. Fetching from DB.")
    # Base query
    base_query = """
        SELECT
            i.id, i.filename, i.filepath, i.mimetype, i.filesize, i.uploaded_at,
            COALESCE(
                (SELECT json_agg(json_build_object('id', t.id, 'name', t.name) ORDER BY t.name)
                 FROM tags t JOIN image_tags it ON t.id = it.tag_id
                 WHERE it.image_id = i.id),
                '[]'::json
            ) AS tags
        FROM images i
    """
    
    conditions = []
    query_params: List[Any] = []
    param_idx = 1

    if tags_filter:
        # Normalize tags_filter
        normalized_tags_filter = [tag.strip().lower() for tag in tags_filter if tag.strip()]
        if normalized_tags_filter:
            # This subquery ensures the image has ALL the specified tags
            conditions.append(f"""
                EXISTS (
                    SELECT 1
                    FROM image_tags it_filter
                    JOIN tags t_filter ON it_filter.tag_id = t_filter.id
                    WHERE it_filter.image_id = i.id AND t_filter.name = ANY(${param_idx}::text[])
                    GROUP BY it_filter.image_id
                    HAVING COUNT(DISTINCT t_filter.name) = CARDINALITY(${param_idx}::text[])
                )
            """)
            # Note: CARDINALITY(${param_idx}::text[]) might not work directly if param_idx refers to the same list for both.
            # A better way for "has all tags":
            # For each tag in tags_filter, add an EXISTS clause.
            # Or, use array operations if tags are stored as an array on the image (not our current schema).
            # For now, let's simplify to "has ANY of the tags" for this example,
            # or stick to a more complex "has ALL" if required.
            # For "has ALL tags":
            # We need to ensure that for each tag in tags_filter, there's a match.
            # A common way is to count matching tags and ensure it equals the number of filter tags.
            # Let's refine the tag filtering part.
            # For now, this is a placeholder for potentially complex tag filtering.
            # A simpler "has any tag in list" would be:
            # conditions.append(f"EXISTS (SELECT 1 FROM image_tags it_f JOIN tags t_f ON it_f.tag_id = t_f.id WHERE it_f.image_id = i.id AND t_f.name = ANY(${param_idx}))")
            # query_params.append(normalized_tags_filter)
            # param_idx +=1
            
            # For "has ALL tags" (more complex, might need multiple joins or a subquery with count)
            # This is a common SQL challenge. Let's use a subquery that counts distinct matching tags.
            tag_placeholders = ', '.join([f'${i+param_idx}' for i in range(len(normalized_tags_filter))])
            conditions.append(f"""
                (
                    SELECT COUNT(DISTINCT t_filter.id)
                    FROM image_tags it_filter
                    JOIN tags t_filter ON it_filter.tag_id = t_filter.id
                    WHERE it_filter.image_id = i.id AND t_filter.name IN ({tag_placeholders})
                ) = {len(normalized_tags_filter)}
            """)
            query_params.extend(normalized_tags_filter)
            param_idx += len(normalized_tags_filter)


    if conditions:
        base_query += " WHERE " + " AND ".join(conditions)

    base_query += f" ORDER BY i.uploaded_at DESC, i.id DESC LIMIT ${param_idx} OFFSET ${param_idx + 1}"
    query_params.extend([limit, skip])

    image_records = await db.fetch(base_query, *query_params)
    
    images_list = []
    for record in image_records:
        images_list.append(models.Image(
            id=record['id'],
            filename=record['filename'],
            filepath=record['filepath'],
            mimetype=record['mimetype'],
            filesize=record['filesize'],
            uploaded_at=record['uploaded_at'],
        tags=[
            models.Tag(**tag_data) if isinstance(tag_data, dict) else models.Tag(id=0, name=tag_data)
            for tag_data in record['tags']
        ],
            image_url=None # URL to be populated in router
        ))
    return images_list


async def count_images(
    db: asyncpg.Connection,
    redis: redis_async.Redis, # Added redis client
    tags_filter: Optional[List[str]] = None
) -> int:
    """
    Counts the total number of images, optionally filtered by tags.
    Checks cache first.
    """
    normalized_tags_key_part = "_".join(sorted([tag.strip().lower() for tag in tags_filter])) if tags_filter else "all"
    cache_key = f"{IMAGE_COUNT_CACHE_PREFIX}tags_{normalized_tags_key_part}"

    cached_count = await redis.get(cache_key)
    if cached_count is not None:
        try:
            print(f"Cache HIT for image count: {cache_key}")
            return int(cached_count)
        except ValueError:
            print(f"Error decoding cached image count for key: {cache_key}. Fetching from DB.")
            # Fall through

    print(f"Cache MISS for image count: {cache_key}. Fetching from DB.")
    base_query = "SELECT COUNT(DISTINCT i.id) FROM images i"
    conditions = []
    query_params: List[Any] = []
    param_idx = 1

    if tags_filter:
        normalized_tags_filter = [tag.strip().lower() for tag in tags_filter if tag.strip()]
        if normalized_tags_filter:
            tag_placeholders = ', '.join([f'${i+param_idx}' for i in range(len(normalized_tags_filter))])
            # This join is needed to filter by tags
            base_query = """
                SELECT COUNT(DISTINCT i.id)
                FROM images i
                JOIN image_tags it_count ON i.id = it_count.image_id
                JOIN tags t_count ON it_count.tag_id = t_count.id
            """
            conditions.append(f"""
                (
                    SELECT COUNT(DISTINCT t_inner.id)
                    FROM image_tags it_inner
                    JOIN tags t_inner ON it_inner.tag_id = t_inner.id
                    WHERE it_inner.image_id = i.id AND t_inner.name IN ({tag_placeholders})
                ) = {len(normalized_tags_filter)}
            """)
            query_params.extend(normalized_tags_filter)
            # param_idx += len(normalized_tags_filter) # Not needed for count if placeholders are directly in string

    if conditions:
        base_query += " WHERE " + " AND ".join(conditions)
        
    count_record = await db.fetchval(base_query, *query_params)
    db_count = count_record if count_record is not None else 0
    
    await redis.set(cache_key, db_count, ex=CACHE_EXPIRY_SECONDS)
    print(f"DB HIT for image count. Stored in cache: {cache_key}")
    return db_count

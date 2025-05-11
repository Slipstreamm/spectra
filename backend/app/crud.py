import asyncpg
import redis.asyncio as redis_async
import json
from typing import List, Dict, Any, Optional
from . import models
from .core.config import settings
from .core import security
from .core.json_utils import json_dumps

# Helper function to robustly parse tags
def _parse_tags_from_source(tags_source: Any) -> List[models.Tag]:
    actual_tag_data_list = []
    if isinstance(tags_source, str):
        try:
            parsed_json = json.loads(tags_source)
            if isinstance(parsed_json, list):
                actual_tag_data_list = parsed_json
            else:
                print(f"Warning: Tags source string did not parse to a list: {str(tags_source)[:100]}")
        except json.JSONDecodeError:
            print(f"Warning: JSONDecodeError for tags source string: {str(tags_source)[:100]}")
    elif isinstance(tags_source, list):
        actual_tag_data_list = tags_source
    else:
        if tags_source is not None:
            print(f"Warning: Tags source is neither string nor list: {type(tags_source)}")

    parsed_tags = []
    for item in actual_tag_data_list:
        item_dict = None
        if isinstance(item, dict):
            item_dict = item
        elif isinstance(item, str):
            try:
                loaded_item = json.loads(item)
                if isinstance(loaded_item, dict):
                    item_dict = loaded_item
                else:
                    print(f"Warning: Tag item string did not parse to a dict: {item[:100]}")
            except json.JSONDecodeError:
                print(f"Warning: JSONDecodeError for tag item string: {item[:100]}")

        if item_dict:
            try:
                if 'id' in item_dict and isinstance(item_dict['id'], int) and \
                   'name' in item_dict and isinstance(item_dict['name'], str):
                    parsed_tags.append(models.Tag(**item_dict))
                else:
                    print(f"Warning: Tag item dict is missing fields or has wrong types: {item_dict}")
            except Exception as e:
                print(f"Warning: Failed to create Tag from dict {item_dict}. Error: {e}")
        else:
            if item is not None:
                 print(f"Warning: Item in tags list is not a dict or valid JSON string for a dict: {type(item)} - {str(item)[:100]}")
    return parsed_tags

# Cache constants
POST_CACHE_PREFIX = "post:"
POST_LIST_CACHE_PREFIX = "posts_list:"
POST_COUNT_CACHE_PREFIX = "posts_count:"
CACHE_EXPIRY_SECONDS = 300 # 5 minutes

async def get_or_create_tag(db: asyncpg.Connection, tag_name: str) -> models.Tag:
    tag_name_cleaned = tag_name.strip().lower().replace(' ', '_')
    if not tag_name_cleaned:
        raise ValueError("Tag name cannot be empty.")
    async with db.transaction():
        tag_record = await db.fetchrow("SELECT id, name FROM tags WHERE name = $1", tag_name_cleaned)
        if tag_record:
            return models.Tag(id=tag_record['id'], name=tag_record['name'])
        created_tag_record = await db.fetchrow(
            "INSERT INTO tags (name) VALUES ($1) RETURNING id, name", tag_name_cleaned
        )
        if not created_tag_record:
            raise Exception(f"Failed to create tag: {tag_name_cleaned}")
        return models.Tag(id=created_tag_record['id'], name=created_tag_record['name'])

async def create_post_with_tags(
    db: asyncpg.Connection,
    redis: redis_async.Redis,
    post_data: models.PostCreate,
    filepath_on_disk: str,
    uploader_id: int
) -> models.Post:
    async with db.transaction():
        post_insert_query = """
            INSERT INTO posts (filename, filepath, mimetype, filesize, title, description, uploader_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id, filename, filepath, mimetype, filesize, title, description, uploader_id, uploaded_at
        """
        post_record = await db.fetchrow(
            post_insert_query,
            post_data.filename, filepath_on_disk, post_data.mimetype, post_data.filesize,
            post_data.title, post_data.description, uploader_id
        )
        if not post_record:
            raise Exception("Failed to create post record in database.")

        created_post_id = post_record['id']
        processed_tags: List[models.Tag] = []
        if post_data.tags:
            for tag_name in post_data.tags:
                tag_name_cleaned = tag_name.strip().lower()
                if not tag_name_cleaned: continue
                tag_obj = await get_or_create_tag(db, tag_name_cleaned)
                processed_tags.append(tag_obj)
                await db.execute(
                    "INSERT INTO post_tags (post_id, tag_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                    created_post_id, tag_obj.id
                )

        uploader_info_record = await db.fetchrow("SELECT id, username, role FROM users WHERE id = $1", uploader_id) # Fetch only needed fields for UserPublic
        uploader_public_info = models.UserPublic(**uploader_info_record) if uploader_info_record else None

        response_post = models.Post(
            id=post_record['id'], filename=post_record['filename'], filepath=post_record['filepath'],
            mimetype=post_record['mimetype'], filesize=post_record['filesize'], title=post_record['title'],
            description=post_record['description'], uploader_id=post_record['uploader_id'],
            uploader=uploader_public_info, uploaded_at=post_record['uploaded_at'], tags=processed_tags,
            image_url=None, thumbnail_url=None, comment_count=0, upvotes=0, downvotes=0
        )

        list_cache_keys = [key async for key in redis.scan_iter(match=f"{POST_LIST_CACHE_PREFIX}*")]
        if list_cache_keys: await redis.delete(*list_cache_keys)
        count_cache_keys = [key async for key in redis.scan_iter(match=f"{POST_COUNT_CACHE_PREFIX}*")]
        if count_cache_keys: await redis.delete(*count_cache_keys)
        return response_post

async def get_post(db: asyncpg.Connection, redis: redis_async.Redis, post_id: int) -> Optional[models.Post]:
    cache_key = f"{POST_CACHE_PREFIX}{post_id}"
    cached_post_json = await redis.get(cache_key)
    if cached_post_json:
        try:
            post_dict = json.loads(cached_post_json)
            post_dict['tags'] = _parse_tags_from_source(post_dict.get('tags', []))
            if post_dict.get('uploader') and isinstance(post_dict['uploader'], dict):
                 # Ensure it's parsed as UserPublic if that's what Post expects
                 post_dict['uploader'] = models.UserPublic(**post_dict['uploader'])
            return models.Post(**post_dict)
        except (json.JSONDecodeError, TypeError, KeyError) as e: # Added KeyError for safety
            print(f"Error decoding/parsing cached post for ID: {post_id}. Error: {e}. Fetching from DB.")

    query = """
        SELECT
            p.id, p.filename, p.filepath, p.mimetype, p.filesize, p.title, p.description,
            p.uploaded_at, p.uploader_id,
            u.id AS uploader_user_id, u.username AS uploader_username, u.role AS uploader_role, -- Removed email, added uploader_user_id
            -- u.is_active AS uploader_is_active, u.created_at AS uploader_created_at, -- Not needed for UserPublic
            COALESCE((SELECT json_agg(json_build_object('id', t.id, 'name', t.name) ORDER BY t.name)
                      FROM tags t JOIN post_tags pt ON t.id = pt.tag_id WHERE pt.post_id = p.id), '[]'::json) AS tags,
            (SELECT COUNT(*) FROM comments c WHERE c.post_id = p.id) AS comment_count,
            (SELECT COUNT(*) FROM votes v WHERE v.post_id = p.id AND v.vote_type = 1) AS upvotes,
            (SELECT COUNT(*) FROM votes v WHERE v.post_id = p.id AND v.vote_type = -1) AS downvotes
        FROM posts p
        LEFT JOIN users u ON p.uploader_id = u.id
        WHERE p.id = $1;
    """
    post_record = await db.fetchrow(query, post_id)
    if not post_record: return None

    parsed_db_tags = _parse_tags_from_source(post_record['tags'])
    uploader_public_data = None
    if post_record['uploader_id'] and post_record['uploader_user_id']: # Ensure uploader_user_id is present
        uploader_public_data = models.UserPublic(
            id=post_record['uploader_user_id'], # Use uploader_user_id from query
            username=post_record['uploader_username'],
            role=post_record['uploader_role']
        )
    db_post_model = models.Post(
        id=post_record['id'], filename=post_record['filename'], filepath=post_record['filepath'],
        mimetype=post_record['mimetype'], filesize=post_record['filesize'], title=post_record['title'],
        description=post_record['description'], uploaded_at=post_record['uploaded_at'],
        uploader_id=post_record['uploader_id'], uploader=uploader_public_data, tags=parsed_db_tags,
        image_url=None, thumbnail_url=None, comment_count=post_record['comment_count'],
        upvotes=post_record['upvotes'], downvotes=post_record['downvotes']
    )
    await redis.set(cache_key, db_post_model.model_dump_json(), ex=CACHE_EXPIRY_SECONDS)
    return db_post_model

async def get_posts(
    db: asyncpg.Connection, redis: redis_async.Redis, skip: int = 0, limit: int = 10,
    tags_filter: Optional[List[str]] = None,
    sort_by: Optional[str] = None, order: Optional[str] = "desc",
    advanced_filters: Optional[Dict[str, Any]] = None
) -> List[models.Post]:
    normalized_tags_key_part = "_".join(sorted([tag.strip().lower().replace(' ', '_') for tag in tags_filter])) if tags_filter else "all"
    sort_key_part = f"sort_{sort_by}_order_{order}" if sort_by else "sort_default"
    
    adv_filters_key_parts = []
    if advanced_filters:
        for k, v in sorted(advanced_filters.items()): # Sort for consistent key order
            if v is not None: # Ensure None values don't break the key or are handled consistently
                adv_filters_key_parts.append(f"{k}_{str(v).replace(' ','_')}")
    adv_filters_key = "_".join(adv_filters_key_parts) if adv_filters_key_parts else "no_adv_filters"

    cache_key = f"{POST_LIST_CACHE_PREFIX}skip_{skip}_limit_{limit}_tags_{normalized_tags_key_part}_{sort_key_part}_adv_{adv_filters_key}"
    
    cached_posts_json = await redis.get(cache_key)
    if cached_posts_json:
        try:
            posts_dict_list = json.loads(cached_posts_json)
            response_posts = []
            for post_dict in posts_dict_list:
                post_dict['tags'] = _parse_tags_from_source(post_dict.get('tags', []))
                if post_dict.get('uploader') and isinstance(post_dict['uploader'], dict):
                    # Ensure it's parsed as UserPublic if that's what Post expects
                    post_dict['uploader'] = models.UserPublic(**post_dict['uploader'])
                response_posts.append(models.Post(**post_dict))
            return response_posts
        except (json.JSONDecodeError, TypeError, KeyError) as e: # Added KeyError for safety
            print(f"Error decoding/parsing cached post list for key: {cache_key}. Error: {e}. Fetching from DB.")

    base_query = """
        SELECT
            p.id, p.filename, p.filepath, p.mimetype, p.filesize, p.title, p.description,
            p.uploaded_at, p.uploader_id,
            u.id AS uploader_user_id, u.username AS uploader_username, u.role AS uploader_role, -- Removed email, added uploader_user_id
            -- u.is_active AS uploader_is_active, u.created_at AS uploader_created_at, -- Not needed for UserPublic
            COALESCE((SELECT json_agg(json_build_object('id', t.id, 'name', t.name) ORDER BY t.name)
                      FROM tags t JOIN post_tags pt ON t.id = pt.tag_id WHERE pt.post_id = p.id), '[]'::json) AS tags,
            (SELECT COUNT(*) FROM comments c WHERE c.post_id = p.id) AS comment_count,
            (SELECT COUNT(*) FROM votes v WHERE v.post_id = p.id AND v.vote_type = 1) AS upvotes,
            (SELECT COUNT(*) FROM votes v WHERE v.post_id = p.id AND v.vote_type = -1) AS downvotes,
            ((SELECT COUNT(*) FROM votes v_up WHERE v_up.post_id = p.id AND v_up.vote_type = 1) -
             (SELECT COUNT(*) FROM votes v_down WHERE v_down.post_id = p.id AND v_down.vote_type = -1)) AS score
        FROM posts p
        LEFT JOIN users u ON p.uploader_id = u.id
    """
    conditions = []
    query_params: List[Any] = []
    param_idx = 1

    if tags_filter:
        normalized_tags_filter = [tag.strip().lower().replace(' ', '_') for tag in tags_filter if tag.strip()]
        if normalized_tags_filter:
            tag_placeholders = ', '.join([f'${i+param_idx}' for i in range(len(normalized_tags_filter))])
            conditions.append(f"""
                EXISTS (
                    SELECT 1
                    FROM post_tags pt_filter
                    JOIN tags t_filter ON pt_filter.tag_id = t_filter.id
                    WHERE pt_filter.post_id = p.id AND t_filter.name IN ({tag_placeholders})
                    GROUP BY pt_filter.post_id
                    HAVING COUNT(DISTINCT t_filter.id) = {len(normalized_tags_filter)}
                )
            """)
            query_params.extend(normalized_tags_filter)
            param_idx += len(normalized_tags_filter)

    if advanced_filters:
        if advanced_filters.get("uploaded_after"):
            conditions.append(f"p.uploaded_at >= ${param_idx}")
            query_params.append(advanced_filters["uploaded_after"])
            param_idx += 1
        if advanced_filters.get("uploaded_before"):
            conditions.append(f"p.uploaded_at <= ${param_idx}")
            query_params.append(advanced_filters["uploaded_before"])
            param_idx += 1
        if advanced_filters.get("min_score") is not None: # Check for None explicitly for 0 score
            # Score is calculated, so we need a subquery or HAVING clause.
            # For simplicity in WHERE, let's assume score is positive and filter on upvotes for now,
            # or adjust the base_query to calculate score and use HAVING.
            # Using the calculated 'score' alias directly in WHERE is not standard SQL for all DBs without subqueries.
            # Let's add it to the HAVING clause later if possible, or filter on components.
            # For now, let's add a placeholder condition that will be part of a HAVING clause if score is used in sort_by
            # This part is tricky without modifying the base query structure significantly for WHERE.
            # A common approach is to filter in a subquery or use HAVING.
            # Let's assume for now we will filter on the calculated score in a HAVING clause if `min_score` is present.
            # This will be handled by adding to a `having_conditions` list.
            pass # Will handle min_score with HAVING clause or by adjusting main query structure
        if advanced_filters.get("min_width"):
            # Assuming image_width column exists in posts table
            conditions.append(f"p.image_width >= ${param_idx}") # Placeholder: requires image_width column
            query_params.append(advanced_filters["min_width"])
            param_idx += 1
        if advanced_filters.get("min_height"):
            # Assuming image_height column exists in posts table
            conditions.append(f"p.image_height >= ${param_idx}") # Placeholder: requires image_height column
            query_params.append(advanced_filters["min_height"])
            param_idx += 1
        if advanced_filters.get("uploader_name"):
            conditions.append(f"u.username ILIKE ${param_idx}") # Case-insensitive search for username
            query_params.append(f"%{advanced_filters['uploader_name']}%") # Add wildcards for partial match
            param_idx += 1
            
    if conditions:
        base_query += " WHERE " + " AND ".join(conditions)

    # Handle min_score with a HAVING clause if present
    having_conditions = []
    if advanced_filters and advanced_filters.get("min_score") is not None:
        having_conditions.append(f"score >= ${param_idx}")
        query_params.append(advanced_filters["min_score"])
        param_idx += 1
    
    # Determine ORDER BY clause
    order_clause = "ORDER BY p.uploaded_at DESC, p.id DESC" # Default sort
    if sort_by == "date":
        order_clause = f"ORDER BY p.uploaded_at {order.upper()}, p.id {order.upper()}"
    elif sort_by == "score":
        # Score is calculated in the SELECT, so we can use the alias 'score'
        order_clause = f"ORDER BY score {order.upper()}, p.id {order.upper()}"
    elif sort_by == "id":
        order_clause = f"ORDER BY p.id {order.upper()}"
    elif sort_by == "random":
        order_clause = "ORDER BY RANDOM()" # PostgreSQL specific for random
    
    base_query += f" {order_clause}" # Apply order first

    if having_conditions:
        base_query += " HAVING " + " AND ".join(having_conditions)

    base_query += f" LIMIT ${param_idx} OFFSET ${param_idx + 1}" # Then limit and offset
    query_params.extend([limit, skip])


    post_records = await db.fetch(base_query, *query_params)
    posts_list = []
    for record in post_records:
        parsed_db_tags = _parse_tags_from_source(record['tags'])
        uploader_public_data = None
        if record['uploader_id'] and record['uploader_user_id']: # Ensure uploader_user_id is present
            uploader_public_data = models.UserPublic(
                id=record['uploader_user_id'], # Use uploader_user_id from query
                username=record['uploader_username'],
                role=record['uploader_role']
            )
        posts_list.append(models.Post(
            id=record['id'], filename=record['filename'], filepath=record['filepath'],
            mimetype=record['mimetype'], filesize=record['filesize'], title=record['title'],
            description=record['description'], uploaded_at=record['uploaded_at'],
            uploader_id=record['uploader_id'], uploader=uploader_public_data, tags=parsed_db_tags,
            image_url=None, thumbnail_url=None, comment_count=record['comment_count'],
            upvotes=record['upvotes'], downvotes=record['downvotes']
        ))
    if posts_list:
        try:
            cacheable_data = json_dumps([post.model_dump() for post in posts_list])
            await redis.set(cache_key, cacheable_data, ex=CACHE_EXPIRY_SECONDS)
        except Exception as e:
            print(f"Error caching post list: {e}")
    return posts_list

async def count_posts(
    db: asyncpg.Connection, redis: redis_async.Redis, tags_filter: Optional[List[str]] = None,
    sort_by: Optional[str] = None, # sort_by might be needed if filtering changes based on it
    advanced_filters: Optional[Dict[str, Any]] = None
) -> int:
    normalized_tags_key_part = "_".join(sorted([tag.strip().lower().replace(' ', '_') for tag in tags_filter])) if tags_filter else "all"
    
    adv_filters_key_parts = []
    if advanced_filters:
        for k, v in sorted(advanced_filters.items()):
             if v is not None:
                adv_filters_key_parts.append(f"{k}_{str(v).replace(' ','_')}")
    adv_filters_key = "_".join(adv_filters_key_parts) if adv_filters_key_parts else "no_adv_filters"

    # sort_by is usually not part of count cache key unless it implies different filtering logic for count
    cache_key = f"{POST_COUNT_CACHE_PREFIX}tags_{normalized_tags_key_part}_adv_{adv_filters_key}"
    
    cached_count = await redis.get(cache_key)
    if cached_count is not None:
        try: return int(cached_count)
        except ValueError: print(f"Error decoding cached post count for key: {cache_key}. Fetching from DB.")

    # Base query for counting. We might need to join with users if filtering by uploader_name.
    # Or calculate score if filtering by min_score.
    # This can get complex. A subquery approach is often cleaner for counts with complex filters.
    
    # Start with a subquery that applies all filters, then count from that.
    sub_query_sql = """
        SELECT p.id
        FROM posts p
        LEFT JOIN users u ON p.uploader_id = u.id
        LEFT JOIN (
            SELECT post_id, 
                   (COUNT(CASE WHEN vote_type = 1 THEN 1 END) - COUNT(CASE WHEN vote_type = -1 THEN 1 END)) as calculated_score
            FROM votes
            GROUP BY post_id
        ) v_score ON p.id = v_score.post_id
    """
    conditions = []
    query_params: List[Any] = []
    param_idx = 1

    if tags_filter:
        normalized_tags_filter = [tag.strip().lower().replace(' ', '_') for tag in tags_filter if tag.strip()]
        if normalized_tags_filter:
            tag_placeholders = ', '.join([f'${i+param_idx}' for i in range(len(normalized_tags_filter))])
            conditions.append(f"""
                EXISTS (
                    SELECT 1
                    FROM post_tags pt_filter
                    JOIN tags t_filter ON pt_filter.tag_id = t_filter.id
                    WHERE pt_filter.post_id = p.id AND t_filter.name IN ({tag_placeholders})
                    GROUP BY pt_filter.post_id
                    HAVING COUNT(DISTINCT t_filter.id) = {len(normalized_tags_filter)}
                )
            """)
            query_params.extend(normalized_tags_filter)
            param_idx += len(normalized_tags_filter)

    if advanced_filters:
        if advanced_filters.get("uploaded_after"):
            conditions.append(f"p.uploaded_at >= ${param_idx}")
            query_params.append(advanced_filters["uploaded_after"])
            param_idx += 1
        if advanced_filters.get("uploaded_before"):
            conditions.append(f"p.uploaded_at <= ${param_idx}")
            query_params.append(advanced_filters["uploaded_before"])
            param_idx += 1
        if advanced_filters.get("min_score") is not None:
            conditions.append(f"COALESCE(v_score.calculated_score, 0) >= ${param_idx}")
            query_params.append(advanced_filters["min_score"])
            param_idx += 1
        if advanced_filters.get("min_width"):
            conditions.append(f"p.image_width >= ${param_idx}") # Placeholder: requires image_width column
            query_params.append(advanced_filters["min_width"])
            param_idx += 1
        if advanced_filters.get("min_height"):
            conditions.append(f"p.image_height >= ${param_idx}") # Placeholder: requires image_height column
            query_params.append(advanced_filters["min_height"])
            param_idx += 1
        if advanced_filters.get("uploader_name"):
            conditions.append(f"u.username ILIKE ${param_idx}")
            query_params.append(f"%{advanced_filters['uploader_name']}%")
            param_idx += 1

    if conditions:
        sub_query_sql += " WHERE " + " AND ".join(conditions)
    
    final_count_query = f"SELECT COUNT(*) FROM ({sub_query_sql}) AS filtered_posts"

    count_record = await db.fetchval(final_count_query, *query_params)
    db_count = count_record if count_record is not None else 0
    await redis.set(cache_key, db_count, ex=CACHE_EXPIRY_SECONDS)
    return db_count

# Helper for count_posts query construction (internal)
def conditions_to_str(conditions: List[str]) -> str:
    return " AND ".join(conditions)


# User CRUD operations
async def get_user_by_email(db: asyncpg.Connection, email: str) -> Optional[models.UserInDB]:
    query = "SELECT id, username, email, hashed_password, role, is_active, created_at FROM users WHERE email = $1"
    user_record = await db.fetchrow(query, email)
    if user_record: return models.UserInDB(**user_record)
    return None

async def get_user_by_username(db: asyncpg.Connection, username: str) -> Optional[models.UserInDB]:
    query = "SELECT id, username, email, hashed_password, role, is_active, created_at FROM users WHERE username = $1"
    user_record = await db.fetchrow(query, username)
    if user_record: return models.UserInDB(**user_record)
    return None

async def create_user(db: asyncpg.Connection, user_in: models.UserCreate) -> models.User:
    hashed_password = security.get_password_hash(user_in.password)
    existing_email_user = await get_user_by_email(db, user_in.email)
    if existing_email_user: raise ValueError(f"User with email {user_in.email} already exists.")
    existing_username_user = await get_user_by_username(db, user_in.username)
    if existing_username_user: raise ValueError(f"User with username {user_in.username} already exists.")
    query = """
        INSERT INTO users (username, email, hashed_password, role, is_active)
        VALUES ($1, $2, $3, $4, TRUE)
        RETURNING id, username, email, role, is_active, created_at
    """
    # user_in.is_superuser from UserCreate model is not directly inserted; role defines privileges.
    # The UserCreate model defaults role to 'user' and is_superuser to False.
    user_record = await db.fetchrow(
        query, user_in.username, user_in.email, hashed_password, user_in.role.value
    )
    if not user_record: raise Exception("Failed to create user.")
    # models.User will get 'role' from UserBase. 'is_superuser' in models.User defaults to False.
    # If is_superuser needs to be explicitly set based on role for the response model,
    # it would be: models.User(**user_record, is_superuser=(user_record['role'] in [models.UserRole.admin, models.UserRole.owner]))
    # For now, relying on the model's default for is_superuser and the presence of 'role'.
    return models.User(**user_record)

async def get_user(db: asyncpg.Connection, user_id: int) -> Optional[models.UserInDB]: # Should return UserInDB for internal use
    query = "SELECT id, username, email, hashed_password, role, is_active, created_at FROM users WHERE id = $1"
    user_record = await db.fetchrow(query, user_id)
    if user_record:
        return models.UserInDB(**user_record) # Return UserInDB as it contains hashed_password
    return None

# Comment CRUD operations
COMMENTS_FOR_POST_CACHE_PREFIX = "comments_for_post:"

async def create_comment(db: asyncpg.Connection, redis: redis_async.Redis, comment_data: models.CommentCreate, post_id: int, user_id: int) -> models.Comment:
    async with db.transaction():
        # Insert the comment
        query = """
            INSERT INTO comments (post_id, user_id, parent_comment_id, content)
            VALUES ($1, $2, $3, $4)
            RETURNING id, post_id, user_id, parent_comment_id, content, created_at, updated_at
        """
        comment_record = await db.fetchrow(
            query,
            post_id,
            user_id,
            comment_data.parent_comment_id,
            comment_data.content
        )
        if not comment_record:
            raise Exception("Failed to create comment.")

        # Fetch the user who made the comment (only fields needed for UserPublic)
        commenter_user_record = await db.fetchrow("SELECT id, username, role FROM users WHERE id = $1", user_id)
        if not commenter_user_record:
            raise Exception("Commenter user not found.")

        commenter_public_info = models.UserPublic(**commenter_user_record)

        # Invalidate post cache as comment_count has changed
        await redis.delete(f"{POST_CACHE_PREFIX}{post_id}")
        # Invalidate the comments list cache for this post
        comments_list_cache_keys = [key async for key in redis.scan_iter(match=f"{COMMENTS_FOR_POST_CACHE_PREFIX}{post_id}:*")]
        if comments_list_cache_keys:
            await redis.delete(*comments_list_cache_keys)
            print(f"Invalidated comments list cache for post {post_id} due to new comment.")

        return models.Comment(
            id=comment_record['id'],
            post_id=comment_record['post_id'],
            user_id=comment_record['user_id'],
            user=commenter_public_info, # Use UserPublic
            parent_comment_id=comment_record['parent_comment_id'],
            content=comment_record['content'],
            created_at=comment_record['created_at'],
            updated_at=comment_record['updated_at'],
            replies=[],
            upvotes=0,
            downvotes=0
        )

async def get_comments_for_post(db: asyncpg.Connection, redis: redis_async.Redis, post_id: int, skip: int = 0, limit: int = 10) -> List[models.Comment]:
    cache_key = f"{COMMENTS_FOR_POST_CACHE_PREFIX}{post_id}:skip_{skip}:limit_{limit}"
    cached_comments_json = await redis.get(cache_key)

    if cached_comments_json:
        try:
            comments_dict_list = json.loads(cached_comments_json)
            response_comments = []
            for comm_dict in comments_dict_list:
                if comm_dict.get('user') and isinstance(comm_dict['user'], dict):
                    # Ensure it's parsed as UserPublic
                    comm_dict['user'] = models.UserPublic(**comm_dict['user'])
                comm_dict['replies'] = []
                response_comments.append(models.Comment(**comm_dict))
            print(f"Cache HIT for comments list: {cache_key}")
            return response_comments
        except (json.JSONDecodeError, TypeError, KeyError) as e: # Added KeyError for safety
            print(f"Error decoding/parsing cached comments for post {post_id}. Error: {e}. Fetching from DB.")

    query = """
        SELECT
            c.id, c.post_id, c.user_id, c.parent_comment_id, c.content, c.created_at, c.updated_at,
            u.id AS comment_user_id, u.username AS user_username, u.role AS user_role, -- Removed email, added comment_user_id and role
            (SELECT COUNT(*) FROM votes v WHERE v.comment_id = c.id AND v.vote_type = 1) AS upvotes,
            (SELECT COUNT(*) FROM votes v WHERE v.comment_id = c.id AND v.vote_type = -1) AS downvotes
        FROM comments c
        JOIN users u ON c.user_id = u.id
        WHERE c.post_id = $1 AND c.parent_comment_id IS NULL
        ORDER BY c.created_at ASC
        LIMIT $2 OFFSET $3;
    """
    comment_records = await db.fetch(query, post_id, limit, skip)

    comments_list = []
    for record in comment_records:
        commenter_public_info = models.UserPublic(
            id=record['comment_user_id'], # Use comment_user_id from query
            username=record['user_username'],
            role=record['user_role']
        )
        comments_list.append(models.Comment(
            id=record['id'],
            post_id=record['post_id'],
            user_id=record['user_id'],
            user=commenter_public_info,
            parent_comment_id=record['parent_comment_id'],
            content=record['content'],
            created_at=record['created_at'],
            updated_at=record['updated_at'],
            replies=[], # Populate if fetching replies recursively
            upvotes=record['upvotes'],
            downvotes=record['downvotes']
        ))

    if comments_list:
        try:
            # For caching, ensure UserBase within Comment is also serializable if not default
            cacheable_data = json_dumps([comment.model_dump() for comment in comments_list])
            await redis.set(cache_key, cacheable_data, ex=CACHE_EXPIRY_SECONDS)
        except Exception as e:
            print(f"Error caching comments list for post {post_id}: {e}")

    return comments_list

# Vote CRUD operations
COMMENT_CACHE_PREFIX = "comment:" # For individual comment caching if implemented

async def cast_vote(db: asyncpg.Connection, redis: redis_async.Redis, vote_data: models.VoteCreate, user_id: int) -> Optional[models.Vote]:
    async with db.transaction():
        target_post_id = vote_data.post_id
        target_comment_id = vote_data.comment_id
        new_vote_type = vote_data.vote_type

        # Check for existing vote by this user on this target
        existing_vote_query = """
            SELECT id, vote_type FROM votes
            WHERE user_id = $1 AND post_id = $2 AND comment_id IS NULL
        """
        params = [user_id, target_post_id]
        if target_comment_id:
            existing_vote_query = """
                SELECT id, vote_type FROM votes
                WHERE user_id = $1 AND comment_id = $2 AND post_id IS NULL
            """
            params = [user_id, target_comment_id]

        existing_vote_record = await db.fetchrow(existing_vote_query, *params)

        if existing_vote_record:
            # Vote exists
            existing_vote_id = existing_vote_record['id']
            current_vote_type = existing_vote_record['vote_type']
            if current_vote_type == new_vote_type:
                # User clicked the same vote button again - unvote (delete the vote)
                await db.execute("DELETE FROM votes WHERE id = $1", existing_vote_id)
                created_vote_record = None # Vote removed
            else:
                # User changed their vote (e.g., from up to down) - update
                updated_vote_record = await db.fetchrow(
                    "UPDATE votes SET vote_type = $1, created_at = CURRENT_TIMESTAMP WHERE id = $2 RETURNING *",
                    new_vote_type, existing_vote_id
                )
                created_vote_record = updated_vote_record
        else:
            # New vote - insert
            insert_query = """
                INSERT INTO votes (user_id, post_id, comment_id, vote_type)
                VALUES ($1, $2, $3, $4) RETURNING *
            """
            created_vote_record = await db.fetchrow(
                insert_query, user_id, target_post_id, target_comment_id, new_vote_type
            )

        # Invalidate caches
        if target_post_id:
            await redis.delete(f"{POST_CACHE_PREFIX}{target_post_id}")
            # Also invalidate lists where this post might appear with updated vote counts
            # This is a broad invalidation for simplicity.
            list_cache_keys = [key async for key in redis.scan_iter(match=f"{POST_LIST_CACHE_PREFIX}*")]
            if list_cache_keys: await redis.delete(*list_cache_keys)
            count_cache_keys = [key async for key in redis.scan_iter(match=f"{POST_COUNT_CACHE_PREFIX}*")]
            if count_cache_keys: await redis.delete(*count_cache_keys)

        elif target_comment_id:
            # Invalidate specific comment cache (if we implement it)
            # await redis.delete(f"{COMMENT_CACHE_PREFIX}{target_comment_id}")
            # Invalidate the cache for the post this comment belongs to, as its aggregated view might change
            comment_post_id_record = await db.fetchval("SELECT post_id FROM comments WHERE id = $1", target_comment_id)
            if comment_post_id_record:
                await redis.delete(f"{POST_CACHE_PREFIX}{comment_post_id_record}")
                # Also invalidate comment list for that post
                # A more granular approach would be to update the specific comment in the list cache if possible
                comments_list_cache_keys = [key async for key in redis.scan_iter(match=f"{COMMENTS_FOR_POST_CACHE_PREFIX}{comment_post_id_record}:*")]
                if comments_list_cache_keys: await redis.delete(*comments_list_cache_keys)


        if not created_vote_record: # Case where vote was deleted (unvoted)
            return None

        # Fetch user details for the vote response (only fields needed for UserPublic)
        voter_user_record = await db.fetchrow("SELECT id, username, role FROM users WHERE id = $1", created_vote_record['user_id'])
        voter_public_info = models.UserPublic(**voter_user_record) if voter_user_record else None

        return models.Vote(
            id=created_vote_record['id'],
            user_id=created_vote_record['user_id'],
            post_id=created_vote_record['post_id'],
            comment_id=created_vote_record['comment_id'],
            vote_type=created_vote_record['vote_type'],
            created_at=created_vote_record['created_at'],
            user=voter_public_info # Use UserPublic
        )

async def update_user_role(db: asyncpg.Connection, user_id: int, new_role: models.UserRole) -> Optional[models.User]:
    """
    Update the role of a user.
    """
    async with db.transaction():
        # Fetch the current user data first to ensure it exists and for constructing the response
        current_user_record = await db.fetchrow(
            "SELECT id, username, email, role, is_active, created_at FROM users WHERE id = $1",
            user_id
        )
        if not current_user_record:
            return None

        # Update the role
        updated_record = await db.fetchrow(
            "UPDATE users SET role = $1 WHERE id = $2 RETURNING id, username, email, role, is_active, created_at",
            new_role.value, user_id
        )
        if not updated_record:
            # This case should ideally not be reached if current_user_record was found,
            # but it's a safeguard.
            return None
        
        # Construct the User model for the response.
        # is_superuser can be derived or kept as its current value if not directly managed by role alone.
    # For simplicity, we'll rely on the User model's default or existing logic for is_superuser.
    return models.User(**updated_record)

async def get_all_tags_with_counts(db: asyncpg.Connection, redis: redis_async.Redis) -> List[models.TagWithCount]:
    """
    Retrieves all tags along with the count of posts associated with each tag.
    Results are cached.
    """
    cache_key = "all_tags_with_counts"
    cached_data_json = await redis.get(cache_key)
    if cached_data_json:
        try:
            tags_dict_list = json.loads(cached_data_json)
            return [models.TagWithCount(**tag_dict) for tag_dict in tags_dict_list]
        except (json.JSONDecodeError, TypeError) as e:
            print(f"Error decoding/parsing cached all_tags_with_counts. Error: {e}. Fetching from DB.")

    query = """
        SELECT t.id, t.name, COUNT(pt.post_id) as post_count
        FROM tags t
        LEFT JOIN post_tags pt ON t.id = pt.tag_id
        GROUP BY t.id, t.name
        ORDER BY post_count DESC, t.name ASC;
    """
    tag_records = await db.fetch(query)
    
    tags_with_counts = []
    if tag_records:
        tags_with_counts = [
            models.TagWithCount(id=record['id'], name=record['name'], post_count=record['post_count'])
            for record in tag_records
        ]
        try:
            cacheable_data = json_dumps([tag.model_dump() for tag in tags_with_counts])
            await redis.set(cache_key, cacheable_data, ex=CACHE_EXPIRY_SECONDS * 2) # Longer expiry for general tag list
        except Exception as e:
            print(f"Error caching all_tags_with_counts: {e}")
            
    return tags_with_counts

async def update_tags_for_posts(
    db: asyncpg.Connection,
    redis: redis_async.Redis,
    post_ids: List[int],
    tag_names_to_modify: List[str],
    action: models.BatchTagAction
) -> Dict[str, Any]:
    """
    Batch update tags for multiple posts.
    Actions:
    - ADD: Adds the specified tags to the posts.
    - REMOVE: Removes the specified tags from the posts.
    - SET: Replaces all existing tags on the posts with the specified tags.
    Returns a dictionary with counts of affected posts and tags.
    """
    if not post_ids:
        return {"message": "No post IDs provided.", "updated_posts_count": 0, "affected_tags_count": 0}

    # Ensure all post_ids are valid integers
    valid_post_ids = [int(pid) for pid in post_ids if isinstance(pid, (int, str)) and str(pid).isdigit()]
    if not valid_post_ids:
        return {"message": "No valid post IDs provided.", "updated_posts_count": 0, "affected_tags_count": 0}
    
    # Prepare tag objects (get or create them)
    tag_objects_to_modify: List[models.Tag] = []
    if tag_names_to_modify: # Only process if there are tags to modify
        for tag_name in tag_names_to_modify:
            tag_name_cleaned = tag_name.strip().lower()
            if not tag_name_cleaned:
                continue
            try:
                tag_obj = await get_or_create_tag(db, tag_name_cleaned)
                tag_objects_to_modify.append(tag_obj)
            except ValueError: # Handles empty tag name from get_or_create_tag
                print(f"Skipping empty or invalid tag name: '{tag_name}'")
            except Exception as e:
                print(f"Error processing tag '{tag_name}': {e}")
                # Decide if this should be a hard fail or just skip the tag
    
    tag_ids_to_modify = [tag.id for tag in tag_objects_to_modify]

    updated_posts_count = 0
    
    # Use a transaction for atomicity
    async with db.transaction():
        # Verify existence of posts first to avoid issues later
        # This also helps in confirming which posts were actually targeted
        placeholders = ', '.join(f'${i+1}' for i in range(len(valid_post_ids)))
        existing_posts_records = await db.fetch(f"SELECT id FROM posts WHERE id IN ({placeholders})", *valid_post_ids)
        actual_post_ids_to_update = [record['id'] for record in existing_posts_records]

        if not actual_post_ids_to_update:
            return {"message": "None of the provided post IDs exist.", "updated_posts_count": 0, "affected_tags_count": 0}

        updated_posts_count = len(actual_post_ids_to_update)
        post_id_placeholders = ', '.join(f'${i+1}' for i in range(len(actual_post_ids_to_update)))

        if action == models.BatchTagAction.SET:
            # Delete all existing tags for these posts
            await db.execute(f"DELETE FROM post_tags WHERE post_id IN ({post_id_placeholders})", *actual_post_ids_to_update)
            # Then add the new tags (if any)
            if tag_ids_to_modify:
                # Prepare for bulk insert
                insert_values = []
                for post_id in actual_post_ids_to_update:
                    for tag_id in tag_ids_to_modify:
                        insert_values.append((post_id, tag_id))
                if insert_values:
                    await db.executemany(
                        "INSERT INTO post_tags (post_id, tag_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                        insert_values
                    )
        
        elif action == models.BatchTagAction.ADD:
            if tag_ids_to_modify:
                insert_values = []
                for post_id in actual_post_ids_to_update:
                    for tag_id in tag_ids_to_modify:
                        insert_values.append((post_id, tag_id))
                if insert_values:
                    await db.executemany(
                        "INSERT INTO post_tags (post_id, tag_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                        insert_values
                    )

        elif action == models.BatchTagAction.REMOVE:
            if tag_ids_to_modify:
                tag_id_placeholders = ', '.join(f'${i+1+len(actual_post_ids_to_update)}' for i in range(len(tag_ids_to_modify)))
                query_params = actual_post_ids_to_update + tag_ids_to_modify
                await db.execute(
                    f"DELETE FROM post_tags WHERE post_id IN ({post_id_placeholders}) AND tag_id IN ({tag_id_placeholders})",
                    *query_params
                )
    
    # Invalidate Redis caches for affected posts and lists
    if updated_posts_count > 0:
        for post_id in actual_post_ids_to_update:
            await redis.delete(f"{POST_CACHE_PREFIX}{post_id}")
        
        # Broad invalidation for list caches, as their content might have changed
        list_cache_keys = [key async for key in redis.scan_iter(match=f"{POST_LIST_CACHE_PREFIX}*")]
        if list_cache_keys: await redis.delete(*list_cache_keys)
        
        count_cache_keys = [key async for key in redis.scan_iter(match=f"{POST_COUNT_CACHE_PREFIX}*")]
        if count_cache_keys: await redis.delete(*count_cache_keys)

    return {
        "message": f"Successfully performed '{action.value}' operation.",
        "updated_posts_count": updated_posts_count,
        "processed_tags_count": len(tag_ids_to_modify) if tag_names_to_modify else 0,
        "target_post_ids_found": actual_post_ids_to_update
    }

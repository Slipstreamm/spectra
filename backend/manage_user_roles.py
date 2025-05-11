import argparse
import asyncio
import asyncpg
import sys
import os

# This script does not import app-specific modules at the top level yet.
# They will be imported in the `if __name__ == "__main__":` block
# after sys.path is configured and .env is potentially loaded.

async def run_script_operations(
    cli_args,
    script_settings,
    RoleEnum,
    crud_get_user_by_username,
    crud_get_user_by_email,
    crud_update_user_role
):
    """
    Core logic for the script, accepting necessary dependencies.
    """
    try:
        new_role_enum = RoleEnum(cli_args.role)
    except ValueError:
        print(f"Error: Invalid role '{cli_args.role}'. Valid roles are: {', '.join([r.value for r in RoleEnum])}")
        sys.exit(1)

    conn = None
    try:
        # Check for essential database settings before attempting to connect
        required_db_settings = [
            "POSTGRES_USER",
            "POSTGRES_PASSWORD",
            "POSTGRES_DB",
            "POSTGRES_SERVER",
            "POSTGRES_PORT"
        ]
        missing_settings = [
            attr for attr in required_db_settings if not hasattr(script_settings, attr) or not getattr(script_settings, attr)
        ]

        if missing_settings:
            print(f"Error: Missing essential database configuration: {', '.join(missing_settings)}.")
            print("Please ensure these are set in your .env file, system environment, or a correctly formatted config.toml.")
            # The user's feedback already indicated a TOML loading issue, so this reinforces checking .env.
            sys.exit(1)

        conn = await asyncpg.connect(
            user=script_settings.POSTGRES_USER,
            password=script_settings.POSTGRES_PASSWORD.get_secret_value(),
            database=script_settings.POSTGRES_DB,
            host=script_settings.POSTGRES_SERVER,
            port=script_settings.POSTGRES_PORT
        )

        # user_to_update_record will hold an object compatible with UserInDB
        # (i.e., has .id, .username, .role attributes)
        user_to_update_record = None
        identifier_type = ""
        identifier_value = ""

        if cli_args.username:
            user_to_update_record = await crud_get_user_by_username(conn, cli_args.username)
            identifier_type = "username"
            identifier_value = cli_args.username
        elif cli_args.email:
            user_to_update_record = await crud_get_user_by_email(conn, cli_args.email)
            identifier_type = "email"
            identifier_value = cli_args.email

        if not user_to_update_record:
            print(f"Error: User with {identifier_type} '{identifier_value}' not found.")
            sys.exit(1)

        # user_to_update_record.role is expected to be a UserRole enum instance
        if user_to_update_record.role == new_role_enum:
            print(f"User '{user_to_update_record.username}' (ID: {user_to_update_record.id}) already has the role '{new_role_enum.value}'. No changes made.")
            sys.exit(0)

        updated_user = await crud_update_user_role(conn, user_to_update_record.id, new_role_enum)

        if updated_user: # updated_user is models.User
            print(f"Successfully updated role for user '{updated_user.username}' (ID: {updated_user.id}) to '{updated_user.role.value}'.")
        else:
            # This might happen if update_user_role returns None unexpectedly, though crud.py's version should return the updated user or raise.
            print(f"Error: Failed to update role for user with {identifier_type} '{identifier_value}'. The user might have been deleted concurrently, or an unknown error occurred.")
            sys.exit(1)

    except asyncpg.exceptions.PostgresError as e:
        print(f"Database error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)
    finally:
        if conn:
            await conn.close()


if __name__ == "__main__":
    # Step 1: Adjust sys.path to allow importing the 'app' module
    # Assumes this script is in 'backend/', and 'app/' is a sibling directory.
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # Should be z:/projects_git/spectra
    # If 'app' is inside 'backend', then backend_dir is project_root for app module path.
    backend_dir = os.path.dirname(os.path.abspath(__file__)) # z:/projects_git/spectra/backend
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir) # Add backend/ to path so 'from app...' works

    # Step 2: Attempt to load .env file using python-dotenv
    # This should happen before importing any 'app' modules that rely on settings.
    try:
        from dotenv import load_dotenv
        # Look for .env in backend/ first, then project root
        dotenv_path_backend = os.path.join(backend_dir, '.env')
        # project_root for .env is one level above backend_dir if script is in backend/
        # For this project structure, backend/.env is the primary location.
        # The create_initial_admin.py uses Path(__file__).resolve().parent / ".env"
        
        # Let's assume .env is in the same directory as this script (backend/) or project root
        # The sys.path.append for project_root was for finding the 'app' package if it was at project_root/app
        # Given current structure, app is backend/app. So sys.path.insert(0, backend_dir) is key.

        env_file_loaded = False
        if os.path.exists(dotenv_path_backend):
            load_dotenv(dotenv_path_backend)
            env_file_loaded = True
            # print(f"Loaded .env from: {dotenv_path_backend}") # For debugging
        else:
            # Fallback to project root .env (e.g. z:/projects_git/spectra/.env)
            # This path needs to be relative to where the script thinks project_root is.
            # If backend_dir is z:/projects_git/spectra/backend, then its parent is z:/projects_git/spectra
            project_root_for_env = os.path.dirname(backend_dir)
            dotenv_path_project_root_level = os.path.join(project_root_for_env, '.env')
            if os.path.exists(dotenv_path_project_root_level):
                load_dotenv(dotenv_path_project_root_level)
                env_file_loaded = True
                # print(f"Loaded .env from: {dotenv_path_project_root_level}") # For debugging

        # if not env_file_loaded:
            # print("No .env file found in backend/ or project root.") # For debugging

    except ImportError:
        print("Warning: python-dotenv is not installed. .env file will not be loaded. Ensure environment variables are set manually if needed.")
    except Exception as e:
        print(f"Warning: Could not load .env file. Ensure environment variables are set. Error: {e}")

    # Step 3: Import application-specific modules now that .env may have been loaded.
    # These imports will use the environment variables set by dotenv.
    from app.core.config import settings as app_settings
    from app.models import UserRole as AppUserRole
    # Specific CRUD functions are imported to be passed as dependencies
    from app.crud import get_user_by_username as crud_get_user_by_username_func
    from app.crud import get_user_by_email as crud_get_user_by_email_func
    from app.crud import update_user_role as crud_update_user_role_func

    # Step 4: Setup argparse using the imported AppUserRole for choices
    parser = argparse.ArgumentParser(description="Manage user roles in the Spectra database.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--username", type=str, help="Username of the user to modify.")
    group.add_argument("--email", type=str, help="Email of the user to modify.")
    parser.add_argument(
        "--role",
        type=str,
        required=True,
        choices=[role.value for role in AppUserRole],
        help=f"New role to assign. Choices: {', '.join([role.value for role in AppUserRole])}",
    )
    cli_args_parsed = parser.parse_args()

    # Step 5: Run the main asynchronous logic with injected dependencies
    asyncio.run(run_script_operations(
        cli_args_parsed,
        app_settings,
        AppUserRole,
        crud_get_user_by_username_func,
        crud_get_user_by_email_func,
        crud_update_user_role_func
    ))

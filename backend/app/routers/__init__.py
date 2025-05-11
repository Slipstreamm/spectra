# This file makes the 'routers' directory a Python package.
# It can also be used to conveniently import all routers.

from . import posts
from . import auth
from . import admin
from . import utils
from . import comments # Importing placeholder comments router
from . import votes # Importing placeholder votes router


# You could also define an __all__ variable if you want to control
# what `from .routers import *` imports, e.g.:
# __all__ = ["posts", "auth", "admin", "utils", "comments", "votes"]

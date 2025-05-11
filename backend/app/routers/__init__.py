# This file makes the 'routers' directory a Python package.
# It can also be used to conveniently import all routers.

from . import images
from . import auth
from . import admin

# You could also define an __all__ variable if you want to control
# what `from .routers import *` imports, e.g.:
# __all__ = ["images", "auth", "admin"]

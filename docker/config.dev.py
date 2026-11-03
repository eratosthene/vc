# The settings for the local copy that docker/compose.dev.yml runs, mounted
# there as /app/config.py in place of the live one. Nothing here is secret: it
# only reaches the throwaway database next to it, and has no Discogs token, so
# a sync can't touch a real account.
import os

from flask_appbuilder.security.manager import AUTH_DB

SECRET_KEY = "dev-only-not-a-secret"
SQLALCHEMY_DATABASE_URI = (
    f"mysql+pymysql://vc:{os.environ['VC_DEV_DB_PASSWORD']}@db/vc?charset=utf8mb4"
)
SQLALCHEMY_TRACK_MODIFICATIONS = False
CSRF_ENABLED = True
APP_NAME = "vc (dev)"
AUTH_TYPE = AUTH_DB
BABEL_DEFAULT_LOCALE = "en"
DISCOGS_SETTINGS = {"USER_TOKEN": "", "USER_AGENT": "discogs_exporter/1.0"}

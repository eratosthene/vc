from flask_appbuilder.security.manager import AUTH_DB

# Copy this file to config.py and fill in the values. config.py is
# gitignored, so the real secrets never go into git. The app reads it. In the
# Docker image it isn't copied in; mount it at /app/config.py.

# Your App secret key. Signs the session cookie; set it to a long random
# string, e.g. the output of: python3 -c "import secrets; print(secrets.token_hex())"
SECRET_KEY = "change-me"

# The database connection, as a SQLAlchemy URL. vc has its own `vc` database,
# and a user with rights on that database only, on the MariaDB server. The URL
# below is a placeholder: the real user, password and host go in config.py
# only, never in this file. Keep ?charset=utf8mb4 so artist and title names in
# any script survive. A password with special characters, such as @ or /, has
# to be percent-encoded.
SQLALCHEMY_DATABASE_URI = "mysql+pymysql://vc:change-me@localhost/vc?charset=utf8mb4"
SQLALCHEMY_TRACK_MODIFICATIONS = False

# CSRF protection is on by default (Flask-WTF's WTF_CSRF_ENABLED), so there is
# nothing to set. The old CSRF_ENABLED setting does nothing now.

# ------------------------------
# GLOBALS FOR APP Builder
# ------------------------------
# The name shown in the navbar and page titles
APP_NAME = "vc"

# ----------------------------------------------------
# AUTHENTICATION CONFIG
# ----------------------------------------------------
# The authentication type. AUTH_DB is username/password, with the users kept
# in the database.
AUTH_TYPE = AUTH_DB

# The language of Flask-AppBuilder's own pages (login, menus). vc has no
# translations of its own.
BABEL_DEFAULT_LOCALE = "en"

# How much the app logs: DEBUG, INFO, WARNING, ERROR or CRITICAL. INFO is the
# default. DEBUG adds more from the libraries, and the sync's detail on each
# genre, style and condition it adds. The sync's own log, shown on its progress
# page, always keeps INFO.
LOG_LEVEL = "INFO"

# Theme configuration
# these are located on static/appbuilder/css/themes
# APP_THEME = "bootstrap-theme.css"  # default bootstrap

# discogs settings, used by the index page's Discogs sync (/syncdiscogs and
# /syncdiscogsnotes)
DISCOGS_SETTINGS = {
    # A personal access token (discogs.com > Settings > Developers). It gives
    # full access to the Discogs account, so it only ever goes in config.py.
    "USER_TOKEN": "",
    "USER_AGENT": "discogs_exporter/1.0",
}

# Where the Discogs sync keeps its lock and its background jobs' state and log
# files. The default is a "vc-sync-jobs" folder in the system's temp folder.
# Every gunicorn worker has to see the same folder.
# SYNC_JOB_FOLDER = "/tmp/vc-sync-jobs"

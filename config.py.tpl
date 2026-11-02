from flask_appbuilder.security.manager import AUTH_DB

# Copy this file to config.py and fill in the values. config.py is
# gitignored, so the real secrets never go into git. The app and run.py
# read it.

# Your App secret key. Signs the session cookie; set it to a long random
# string, e.g. the output of: python3 -c "import secrets; print(secrets.token_hex())"
SECRET_KEY = "change-me"

# The MongoDB connection, passed to flask-mongoengine. The database name goes
# at the end of the host URI.
MONGODB_SETTINGS = {
    "host": "mongodb://localhost:27017/vc",
}

# Flask-WTF flag for CSRF
CSRF_ENABLED = True

# ------------------------------
# GLOBALS FOR APP Builder
# ------------------------------
# The name shown in the navbar and page titles
APP_NAME = "vc"

# ----------------------------------------------------
# AUTHENTICATION CONFIG
# ----------------------------------------------------
# The authentication type. AUTH_DB is username/password, with the users kept
# in MongoDB.
AUTH_TYPE = AUTH_DB

# ---------------------------------------------------
# Babel config for translations
# ---------------------------------------------------
# Setup default language
BABEL_DEFAULT_LOCALE = "en"

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

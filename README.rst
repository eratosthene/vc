Base Skeleton to start your application using Flask-AppBuilder and MongoEngine
------------------------------------------------------------------------------

- Install it::

	pip install flask-appbuilder
	git clone https://github.com/dpgaspar/Flask-AppBuilder-Skeleton.git

- Run it::

	fabmanager run


That's it!!


Tests
-----

- Run them (no ``config.py``, database or network needed)::

	pipenv install --dev
	pipenv run pytest

- Report coverage::

	pipenv run pytest --cov=app --cov-report=term-missing

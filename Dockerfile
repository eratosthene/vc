FROM tiangolo/uwsgi-nginx-flask:python3.10

RUN apt-get update \
  && apt-get install -y ca-certificates \
  && rm -rf /var/lib/apt/lists/*

COPY ./requirements.txt /requirements.txt
COPY ./vc.cfg /vc.cfg
COPY ./uwsgi.ini /app/uwsgi.ini
COPY ./app /app/app
RUN pip install --upgrade -r /requirements.txt
RUN sed -i 's/int(pk)/str(pk)/g' /usr/local/lib/python3.10/site-packages/flask_appbuilder/views.py
RUN sed -i 's/int(pk)/str(pk)/g' /usr/local/lib/python3.10/site-packages/flask_appbuilder/security/manager.py

ENV STATIC_PATH /usr/local/lib/python3.10/site-packages/flask_appbuilder/static
ENV VC_SETTINGS=/vc.cfg
ENV LISTEN_PORT=19999
EXPOSE 19999


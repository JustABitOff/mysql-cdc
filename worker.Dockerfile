FROM python:3.10

# copy contents of project into docker
COPY ./ /app/

# We will use internal functions of the API
# So install all dependencies of the API
RUN cd app && pip install -r requirements.txt

WORKDIR /app

ENTRYPOINT celery -A cdc_stream worker --loglevel=INFO
FROM python:3.10-slim as dependency_stage

WORKDIR /code
ENV PATH="/env/bin:$PATH"
RUN python3 -m venv /env

COPY ./requirements.txt /code/requirements.txt

ARG GITLAB_USERNAME
ARG GITLAB_PASSWORD

# echo "machine gitlab.<foo-bar>.de login $GITLAB_USERNAME password $GITLAB_PASSWORD" > ~/.netrc \
# --extra-index-url https://gitlab.<foo-bar>.de/<some-where>/-/packages/pypi/simple
RUN pip install -r /code/requirements.txt
#  && rm -v "$HOME/.netrc"

FROM python:3.10-slim as production_stage
WORKDIR /code
ENV PATH="$WORKDIR/env/bin:$PATH"
COPY --from=dependency_stage /env /env
# <replace-me-by-COPY-from-statements>

# TODO: maybe somewhen in future one could want a prepare stage?
# COPY some_service.py /code/tests/fastapi_service_for_testing/some_service.py
# COPY prepare_service.py /code/prepare_service.py
# RUN python /code/prepare_service.py
# TODO: prepare and production stage are essentially one! otherwise I would have to copy everything twice
#COPY --from=prepare_stage /cache /cache


COPY ./app /code/app
# <replace-me-by-CMD-statement>

FROM python:3.10
LABEL authors="Florian Finkeldei <florian.finkeldei@tum.de>, Boran Sivrikaya <boran.sivrikaya@tum.de>"

RUN pip install poetry

COPY . .

RUN apt-get update && apt-get install -y --no-install-recommends git wget unzip bzip2 sudo build-essential ca-certificates && \
    apt-get install -y sumo && apt-get install -y osmium-tool && \
    apt-get install -y libxext-dev libxrender-dev libsm-dev libgl-dev

RUN poetry install

ENV SUMO_HOME="/usr/share/sumo"


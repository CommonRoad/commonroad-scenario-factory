FROM python:3.10
LABEL authors="Florian Finkeldei <florian.finkeldei@tum.de>, Boran Sivrikaya <boran.sivrikaya@tum.de>"

RUN pip install poetry

COPY . .

RUN mkdir -p -m 0600 /root/.ssh

COPY id_rsa /root/.ssh/id_rsa
COPY id_rsa.pub /root/.ssh/id_rsa.pub

RUN chmod 700 /root/.ssh && \
    chmod 600 /root/.ssh/id_rsa && \
    chmod 644 /root/.ssh/id_rsa.pub

RUN ssh-keyscan gitlab.lrz.de >> /root/.ssh/known_hosts

RUN apt-get update && apt-get install -y --no-install-recommends git wget unzip bzip2 sudo build-essential ca-certificates && \
    apt-get install -y sumo && apt-get install -y osmium-tool && \
    apt-get install -y libxext-dev libxrender-dev libsm-dev libgl-dev

RUN poetry install

ENV SUMO_HOME="/usr/share/sumo"

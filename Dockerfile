FROM python:3.10
LABEL authors="Florian Finkeldei <florian.finkeldei@tum.de>"

RUN pip install poetry

COPY pyproject.toml /app/pyproject.toml

ENTRYPOINT ["top", "-b"]
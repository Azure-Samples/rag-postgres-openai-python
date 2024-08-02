FROM python:3.12-bullseye

RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install --no-install-recommends postgresql-client \
    && apt-get update && apt-get install -y xdg-utils \
    && apt-get clean -y && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade pip

WORKDIR /demo-code

COPY requirements.txt .
RUN python -m pip install -r requirements.txt

COPY . .
RUN python -m pip install .

RUN chmod +x entrypoint.sh
EXPOSE 8000
CMD ["bash", "-c", ". entrypoint.sh"]

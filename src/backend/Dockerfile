FROM python:3.12-bullseye

# Removed postgresql-client and xdg-utils packages as they are not used by the backend
# The backend uses SQLAlchemy/asyncpg for PostgreSQL connections, not CLI tools

RUN python -m pip install --upgrade pip

WORKDIR /demo-code

COPY requirements.txt .
RUN python -m pip install -r requirements.txt

COPY . .
RUN python -m pip install .

RUN chmod +x entrypoint.sh
EXPOSE 8000
CMD ["bash", "-c", ". entrypoint.sh"]

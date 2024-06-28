import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from fastapi_app import create_app
from fastapi_app.postgres_models import Base

POSTGRESQL_DATABASE_URL = "postgresql://admin:postgres@localhost:5432/postgres"


# Create a SQLAlchemy engine
engine = create_engine(
    POSTGRESQL_DATABASE_URL,
    poolclass=StaticPool,
)

# Create a sessionmaker to manage sessions
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session")
def setup_database():
    """Create tables in the database for all tests."""
    try:
        Base.metadata.create_all(bind=engine)
        yield
        Base.metadata.drop_all(bind=engine)
    except Exception as e:
        pytest.skip(f"Unable to connect to the database: {e}")


@pytest.fixture(scope="function")
def db_session(setup_database):
    """Create a new database session with a rollback at the end of the test."""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def test_db_client(db_session):
    """Create a test client that uses the override_get_db fixture to return a session."""

    def override_db_session():
        try:
            yield db_session
        finally:
            db_session.close()

    app = create_app()
    app.router.lifespan = override_db_session
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="function")
def test_client():
    """Create a test client."""
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client

from __future__ import annotations

from pgvector.sqlalchemy import Vector
from sqlalchemy import Index, ARRAY, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


# Define the models
class Base(DeclarativeBase):
    pass


class Item(Base):
    __tablename__ = "sessions"
    # An ID column should always be defined, but it can be int or string
    id: Mapped[str] = mapped_column(primary_key=True)
    # Schema specific:
    title: Mapped[str] = mapped_column()
    description: Mapped[str] = mapped_column()
    speakers: Mapped[list[str]] = mapped_column(ARRAY(String))
    tracks: Mapped[list[str]] = mapped_column(ARRAY(String))
    day: Mapped[str] = mapped_column()
    time: Mapped[str] = mapped_column()
    mode: Mapped[str] = mapped_column()
    # Embeddings for different models:
    embedding_ada002: Mapped[Vector] = mapped_column(Vector(1536), nullable=True)  # ada-002
    embedding_nomic: Mapped[Vector] = mapped_column(Vector(768), nullable=True)  # nomic-embed-text

    def to_dict(self, include_embedding: bool = False):
        model_dict = {column.name: getattr(self, column.name) for column in self.__table__.columns}
        if include_embedding:
            model_dict["embedding_ada002"] = model_dict.get("embedding_ada002", [])
            model_dict["embedding_nomic"] = model_dict.get("embedding_nomic", [])
        else:
            del model_dict["embedding_ada002"]
            del model_dict["embedding_nomic"]
        return model_dict

    def to_str_for_rag(self):
        return f"Title:{self.title} Description:{self.description} Speakers:{self.speakers} Tracks:{self.tracks} Day:{self.day} Time:{self.time} Mode:{self.mode}"  # noqa

    def to_str_for_embedding(self):
        return f"Name: {self.title} Description: {self.description} Tracks: {self.tracks} Day: {self.day} Mode: {self.mode}"  # noqa


# Define HNSW index to support vector similarity search
# Use vector_cosine_ops operator since that works for both normalized and non-normalized embeddings
# and matches the operator used in postgres_searcher.py

table_name = Item.__tablename__

index_ada002 = Index(
    f"hnsw_index_for_innerproduct_{table_name}_embedding_ada002",
    Item.embedding_ada002,
    postgresql_using="hnsw",
    postgresql_with={"m": 16, "ef_construction": 64},
    postgresql_ops={"embedding_ada002": "vector_cosine_ops"},
)

index_nomic = Index(
    f"hnsw_index_for_innerproduct_{table_name}_embedding_nomic",
    Item.embedding_nomic,
    postgresql_using="hnsw",
    postgresql_with={"m": 16, "ef_construction": 64},
    postgresql_ops={"embedding_nomic": "vector_cosine_ops"},
)

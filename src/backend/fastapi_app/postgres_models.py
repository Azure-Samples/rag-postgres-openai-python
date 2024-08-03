from __future__ import annotations

from dataclasses import asdict

from pgvector.sqlalchemy import Vector
from sqlalchemy import Index
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, mapped_column


# Define the models
class Base(DeclarativeBase, MappedAsDataclass):
    pass


class Item(Base):
    __tablename__ = "items"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column()
    brand: Mapped[str] = mapped_column()
    name: Mapped[str] = mapped_column()
    description: Mapped[str] = mapped_column()
    price: Mapped[float] = mapped_column()
    embedding_ada002: Mapped[Vector] = mapped_column(Vector(1536))  # ada-002
    embedding_nomic: Mapped[Vector] = mapped_column(Vector(768))  # nomic-embed-text

    def to_dict(self, include_embedding: bool = False):
        model_dict = asdict(self)
        if include_embedding:
            model_dict["embedding_ada002"] = model_dict.get("embedding_ada002", [])
            model_dict["embedding_nomic"] = model_dict.get("embedding_nomic", [])
        else:
            del model_dict["embedding_ada002"]
            del model_dict["embedding_nomic"]
        return model_dict

    def to_str_for_rag(self):
        return f"Name:{self.name} Description:{self.description} Price:{self.price} Brand:{self.brand} Type:{self.type}"

    def to_str_for_embedding(self):
        return f"Name: {self.name} Description: {self.description} Type: {self.type}"


# Define HNSW index to support vector similarity search through the vector_cosine_ops access method (cosine distance).
index_ada002 = Index(
    "hnsw_index_for_innerproduct_item_embedding_ada002",
    Item.embedding_ada002,
    postgresql_using="hnsw",
    postgresql_with={"m": 16, "ef_construction": 64},
    postgresql_ops={"embedding_ada002": "vector_ip_ops"},
)

index_nomic = Index(
    "hnsw_index_for_innerproduct_item_embedding_nomic",
    Item.embedding_nomic,
    postgresql_using="hnsw",
    postgresql_with={"m": 16, "ef_construction": 64},
    postgresql_ops={"embedding_nomic": "vector_ip_ops"},
)

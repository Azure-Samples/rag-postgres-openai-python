from __future__ import annotations

from pgvector.sqlalchemy import Vector
from sqlalchemy import VARCHAR, Index
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


# Define the models
class Base(DeclarativeBase):
    pass


class Item(Base):
    __tablename__ = "items"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column()
    location: Mapped[str] = mapped_column()
    cuisine: Mapped[str] = mapped_column()
    rating: Mapped[int] = mapped_column()
    price_level: Mapped[int] = mapped_column()
    review_count: Mapped[int] = mapped_column()
    hours: Mapped[str] = mapped_column()
    tags: Mapped[list[str]] = mapped_column(postgresql.ARRAY(VARCHAR))  # Array of strings
    description: Mapped[str] = mapped_column()
    menu_summary: Mapped[str] = mapped_column()
    top_reviews: Mapped[str] = mapped_column()
    vibe: Mapped[str] = mapped_column()

    # Embeddings for different models:
    embedding_3l: Mapped[Vector] = mapped_column(Vector(1024), nullable=True)  # text-embedding-3-large
    embedding_nomic: Mapped[Vector] = mapped_column(Vector(768), nullable=True)  # nomic-embed-text

    def to_dict(self, include_embedding: bool = False):
        model_dict = {column.name: getattr(self, column.name) for column in self.__table__.columns}
        if include_embedding:
            model_dict["embedding_3l"] = model_dict.get("embedding_3l", [])
            model_dict["embedding_nomic"] = model_dict.get("embedding_nomic", [])
        else:
            del model_dict["embedding_3l"]
            del model_dict["embedding_nomic"]
        return model_dict

    def to_str_for_rag(self):
        return f"Name:{self.name} Description:{self.description} Location:{self.location} Cuisine:{self.cuisine} Rating:{self.rating} Price Level:{self.price_level} Review Count:{self.review_count} Hours:{self.hours} Tags:{self.tags} Menu Summary:{self.menu_summary} Top Reviews:{self.top_reviews} Vibe:{self.vibe}"  # noqa: E501

    def to_str_for_embedding(self):
        return f"Name: {self.name} Description: {self.description} Cuisine: {self.cuisine} Tags: {self.tags} Menu Summary: {self.menu_summary} Top Reviews: {self.top_reviews} Vibe: {self.vibe}"  # noqa: E501


"""
**Define HNSW index to support vector similarity search**

We use the vector_cosine_ops access method (cosine distance)
 since it works for both normalized and non-normalized vector embeddings
If you know your embeddings are normalized,
 you can switch to inner product for potentially better performance.
The index operator should match the operator used in queries.
"""

table_name = Item.__tablename__

index_3l = Index(
    f"hnsw_index_for_cosine_{table_name}_embedding_3l",
    Item.embedding_3l,
    postgresql_using="hnsw",
    postgresql_with={"m": 16, "ef_construction": 64},
    postgresql_ops={"embedding_3l": "vector_cosine_ops"},
)

index_nomic = Index(
    f"hnsw_index_for_cosine_{table_name}_embedding_nomic",
    Item.embedding_nomic,
    postgresql_using="hnsw",
    postgresql_with={"m": 16, "ef_construction": 64},
    postgresql_ops={"embedding_nomic": "vector_cosine_ops"},
)

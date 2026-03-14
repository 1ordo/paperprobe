import logging
import uuid
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    VectorParams,
    Filter,
    FieldCondition,
    MatchValue,
)

from app.config import settings

logger = logging.getLogger(__name__)


class VectorStore:
    def __init__(self):
        self.client = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
        )
        self.collection_name = settings.qdrant_collection
        self.dimension = settings.embedding_dimension

    def ensure_collection(self):
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)
        if not exists:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.dimension,
                    distance=Distance.COSINE,
                ),
            )
            logger.info(f"Created Qdrant collection: {self.collection_name}")

    def upsert_chunks(
        self,
        chunks: list[dict],
        embeddings: list[list[float]],
        paper_id: str,
    ) -> list[str]:
        self.ensure_collection()
        points = []
        point_ids = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            point_id = str(uuid.uuid4())
            point_ids.append(point_id)
            points.append(
                PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload={
                        "paper_id": paper_id,
                        "chunk_text": chunk["text"],
                        "chunk_index": chunk.get("chunk_index", i),
                        "page_number": chunk.get("page_number"),
                        "char_start": chunk.get("char_start"),
                        "char_end": chunk.get("char_end"),
                        "section_type": chunk.get("section_type"),
                    },
                )
            )

        # Upsert in batches of 100
        batch_size = 100
        for j in range(0, len(points), batch_size):
            batch = points[j : j + batch_size]
            self.client.upsert(collection_name=self.collection_name, points=batch)

        logger.info(f"Upserted {len(points)} chunks for paper {paper_id}")
        return point_ids

    def search(
        self,
        query_embedding: list[float],
        paper_id: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        self.ensure_collection()
        filter_condition = None
        if paper_id:
            filter_condition = Filter(
                must=[
                    FieldCondition(
                        key="paper_id",
                        match=MatchValue(value=paper_id),
                    )
                ]
            )

        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_embedding,
            query_filter=filter_condition,
            limit=limit,
        )

        return [
            {
                "id": str(hit.id),
                "score": hit.score,
                "text": hit.payload.get("chunk_text", ""),
                "page_number": hit.payload.get("page_number"),
                "char_start": hit.payload.get("char_start"),
                "char_end": hit.payload.get("char_end"),
                "section_type": hit.payload.get("section_type"),
                "chunk_index": hit.payload.get("chunk_index"),
            }
            for hit in response.points
        ]

    def delete_by_paper(self, paper_id: str):
        self.ensure_collection()
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="paper_id",
                        match=MatchValue(value=paper_id),
                    )
                ]
            ),
        )
        logger.info(f"Deleted vectors for paper {paper_id}")

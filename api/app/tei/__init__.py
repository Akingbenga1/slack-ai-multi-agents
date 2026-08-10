"""TEI (Text Embeddings Inference) HTTP client."""

from api.app.tei.client import TeiClient, TeiError, embed_texts

__all__ = ["TeiClient", "TeiError", "embed_texts"]

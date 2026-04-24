"""
RAG (Retrieval-Augmented Generation) module for FinCLI.

Architecture:
  embedder.py   — converts text → vector (the "understanding" step)
  vector_store.py — stores & searches vectors by similarity
  retriever.py  — hybrid retrieval: SQL pre-filter + vector similarity
  indexer.py    — offline pipeline: new transactions → embeddings
"""

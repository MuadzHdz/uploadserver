"""
Advanced search engine for UploadServer Pro
"""

import os
import hashlib
import mimetypes
from datetime import datetime
from whoosh import fields, index
from whoosh.analysis import StandardAnalyzer, StemmingAnalyzer
from whoosh.filedb.filestore import FileStorage
from whoosh.qparser import QueryParser, MultifieldParser
from whoosh.query import And, Or, Term, Prefix, Wildcard
import magic
import json

from .models import File, User


class SearchEngine:
    def __init__(self, index_dir="search_index"):
        self.index_dir = index_dir
        self.analyzer = StemmingAnalyzer()
        self.ensure_index_directory()

    def ensure_index_directory(self):
        """Create index directory if it doesn't exist"""
        if not os.path.exists(self.index_dir):
            os.makedirs(self.index_dir)

    def create_schema(self):
        """Create Whoosh schema for file indexing"""
        return fields.Schema(
            id=fields.ID(unique=True, stored=True),
            filename=fields.TEXT(stored=True, analyzer=self.analyzer),
            content=fields.TEXT(stored=True, analyzer=self.analyzer),
            original_filename=fields.TEXT(stored=True, analyzer=self.analyzer),
            mime_type=fields.ID(stored=True),
            file_size=fields.NUMERIC(stored=True),
            owner_id=fields.ID(stored=True),
            owner_username=fields.TEXT(stored=True, analyzer=self.analyzer),
            parent_directory=fields.ID(stored=True),
            tags=fields.KEYWORD(stored=True, commas=True),
            is_public=fields.BOOLEAN(stored=True),
            created_at=fields.DATETIME(stored=True),
            updated_at=fields.DATETIME(stored=True),
            file_hash=fields.ID(stored=True),
            metadata=fields.TEXT(stored=True, analyzer=self.analyzer),
        )

    def get_index(self):
        """Get or create search index"""
        storage = FileStorage(self.index_dir)
        if index.exists_in(self.index_dir):
            return index.open_dir(self.index_dir)
        else:
            schema = self.create_schema()
            return index.create_in(self.index_dir, schema)

    def extract_file_content(self, file_path, mime_type):
        """Extract text content from various file types"""
        try:
            if mime_type and mime_type.startswith("text/"):
                # Text files
                encodings = ["utf-8", "latin-1", "cp1252"]
                for encoding in encodings:
                    try:
                        with open(file_path, "r", encoding=encoding) as f:
                            return f.read()[:10000]  # Limit content size
                    except UnicodeDecodeError:
                        continue

            elif mime_type == "application/pdf":
                # PDF files (requires PyPDF2)
                try:
                    import PyPDF2

                    with open(file_path, "rb") as f:
                        reader = PyPDF2.PdfReader(f)
                        content = ""
                        for page in reader.pages[:10]:  # Limit to first 10 pages
                            content += page.extract_text() + "\n"
                        return content[:10000]
                except ImportError:
                    return None

            elif mime_type in [
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ]:
                # Microsoft Office documents (requires python-docx)
                try:
                    if mime_type.endswith(".wordprocessingml.document"):
                        import docx

                        doc = docx.Document(file_path)
                        content = "\n".join(
                            [paragraph.text for paragraph in doc.paragraphs]
                        )
                        return content[:10000]
                    # Add Excel and PowerPoint extraction if needed
                except ImportError:
                    return None

            elif mime_type in [
                "application/zip",
                "application/x-tar",
                "application/gzip",
            ]:
                # Archive files - list contents
                try:
                    import zipfile
                    import tarfile

                    if mime_type == "application/zip":
                        with zipfile.ZipFile(file_path, "r") as zf:
                            return "\n".join(zf.namelist())
                    else:
                        with tarfile.open(file_path, "r:*") as tf:
                            return "\n".join(tf.getnames())
                except:
                    return None

            return None
        except Exception:
            return None

    def index_file(self, file_obj):
        """Index a single file"""
        try:
            idx = self.get_index()
            writer = idx.writer()

            # Extract content for indexing
            content = ""
            if not file_obj.is_directory:
                content = (
                    self.extract_file_content(file_obj.file_path, file_obj.mime_type)
                    or ""
                )

            # Prepare metadata
            metadata_text = ""
            if file_obj.file_metadata:
                metadata_text = " ".join(
                    [str(v) for v in file_obj.file_metadata.values() if isinstance(v, str)]
                )

            tags_text = " ".join(file_obj.tags) if file_obj.tags else ""

            writer.add_document(
                id=file_obj.id,
                filename=file_obj.filename,
                content=content,
                original_filename=file_obj.original_filename,
                mime_type=file_obj.mime_type or "",
                file_size=file_obj.file_size,
                owner_id=file_obj.owner_id,
                owner_username=file_obj.owner.username
                if hasattr(file_obj, "owner")
                else "",
                parent_directory=file_obj.parent_directory,
                tags=tags_text,
                is_public=file_obj.is_public,
                created_at=file_obj.created_at,
                updated_at=file_obj.updated_at,
                file_hash=file_obj.file_hash,
                metadata=metadata_text,
            )
            writer.commit()

        except Exception as e:
            print(f"Error indexing file {file_obj.filename}: {e}")

    def index_directory(self, directory_path, user_id=None):
        """Index all files in a directory"""
        try:
            from .models import db, File

            # Query files from database
            query = File.query
            if user_id:
                query = query.filter_by(owner_id=user_id)
            else:
                query = query.filter_by(is_public=True)

            files = query.all()

            idx = self.get_index()
            writer = idx.writer()

            for file_obj in files:
                try:
                    # Extract content
                    content = ""
                    if not file_obj.is_directory:
                        full_path = os.path.join(directory_path, file_obj.file_path)
                        if os.path.exists(full_path):
                            content = (
                                self.extract_file_content(full_path, file_obj.mime_type)
                                or ""
                            )

                    # Prepare metadata
                    metadata_text = ""
                    if file_obj.file_metadata:
                        metadata_text = " ".join(
                            [
                                str(v)
                                for v in file_obj.file_metadata.values()
                                if isinstance(v, str)
                            ]
                        )

                    tags_text = " ".join(file_obj.tags) if file_obj.tags else ""

                    writer.add_document(
                        id=file_obj.id,
                        filename=file_obj.filename,
                        content=content,
                        original_filename=file_obj.original_filename,
                        mime_type=file_obj.mime_type or "",
                        file_size=file_obj.file_size,
                        owner_id=file_obj.owner_id,
                        owner_username=file_obj.owner.username
                        if hasattr(file_obj, "owner")
                        else "",
                        parent_directory=file_obj.parent_directory,
                        tags=tags_text,
                        is_public=file_obj.is_public,
                        created_at=file_obj.created_at,
                        updated_at=file_obj.updated_at,
                        file_hash=file_obj.file_hash,
                        metadata=metadata_text,
                    )
                except Exception as e:
                    print(f"Error indexing file {file_obj.filename}: {e}")

            writer.commit()
            return True

        except Exception as e:
            print(f"Error indexing directory: {e}")
            return False

    def search(self, query_string, user_id=None, filters=None, limit=50, offset=0):
        """Perform search with filters"""
        try:
            idx = self.get_index()
            searcher = idx.searcher()

            # Build query parser for multi-field search
            parser = MultifieldParser(
                [
                    "filename",
                    "content",
                    "original_filename",
                    "tags",
                    "metadata",
                    "owner_username",
                ],
                idx.schema,
            )

            query = parser.parse(query_string)

            # Apply filters
            if user_id:
                query = And([query, Term("owner_id", user_id)])
            elif filters and filters.get("public_only"):
                query = And([query, Term("is_public", True)])

            # Additional filters
            if filters:
                if filters.get("mime_type"):
                    query = And([query, Term("mime_type", filters["mime_type"])])

                if filters.get("size_min"):
                    query = And(
                        [
                            query,
                            fields.RangeFilter("file_size", filters["size_min"], None),
                        ]
                    )

                if filters.get("size_max"):
                    query = And(
                        [
                            query,
                            fields.RangeFilter("file_size", None, filters["size_max"]),
                        ]
                    )

                if filters.get("date_from"):
                    query = And(
                        [
                            query,
                            fields.DateRangeFilter(
                                "created_at", filters["date_from"], None
                            ),
                        ]
                    )

                if filters.get("date_to"):
                    query = And(
                        [
                            query,
                            fields.DateRangeFilter(
                                "created_at", None, filters["date_to"]
                            ),
                        ]
                    )

            # Execute search
            results = searcher.search(query, limit=limit, offset=offset)

            # Format results
            formatted_results = []
            for hit in results:
                result = {
                    "id": hit["id"],
                    "filename": hit["filename"],
                    "original_filename": hit["original_filename"],
                    "mime_type": hit["mime_type"],
                    "file_size": hit["file_size"],
                    "owner_id": hit["owner_id"],
                    "owner_username": hit["owner_username"],
                    "parent_directory": hit["parent_directory"],
                    "tags": hit.get("tags", ""),
                    "is_public": hit["is_public"],
                    "created_at": hit["created_at"],
                    "updated_at": hit["updated_at"],
                    "file_hash": hit["file_hash"],
                    "score": hit.score,
                    "highlights": [],
                }

                # Add highlights
                if hasattr(hit, "highlights"):
                    for field in ["filename", "content", "original_filename"]:
                        if field in hit.highlights:
                            result["highlights"].extend(hit.highlights[field])

                formatted_results.append(result)

            return {
                "results": formatted_results,
                "total": len(results),
                "limit": limit,
                "offset": offset,
                "query": query_string,
                "filters": filters or {},
            }

        except Exception as e:
            print(f"Search error: {e}")
            return {
                "results": [],
                "total": 0,
                "limit": limit,
                "offset": offset,
                "query": query_string,
                "filters": filters or {},
                "error": str(e),
            }

    def get_suggestions(self, query_string, field="filename", limit=10):
        """Get autocomplete suggestions"""
        try:
            idx = self.get_index()
            searcher = idx.searcher()

            # Create prefix query for autocomplete
            query = Prefix(field, query_string)
            results = searcher.search(query, limit=limit)

            suggestions = []
            seen_terms = set()

            for hit in results:
                term = hit[field]
                if term and term not in seen_terms:
                    suggestions.append(term)
                    seen_terms.add(term)

            return suggestions

        except Exception as e:
            print(f"Suggestion error: {e}")
            return []

    def get_popular_files(self, limit=10, user_id=None):
        """Get most accessed/downloaded files"""
        try:
            idx = self.get_index()
            searcher = idx.searcher()

            # Sort by download count or file size
            query = Every()
            if user_id:
                query = Term("owner_id", user_id)

            results = searcher.search(
                query, sortedby="file_size", reverse=True, limit=limit
            )

            return [hit.fields() for hit in results]

        except Exception as e:
            print(f"Popular files error: {e}")
            return []

    def update_file(self, file_obj):
        """Update file index entry"""
        try:
            idx = self.get_index()
            writer = idx.writer()

            # Delete existing document
            writer.delete_by_term("id", file_obj.id)

            # Add updated document
            content = ""
            if not file_obj.is_directory:
                content = (
                    self.extract_file_content(file_obj.file_path, file_obj.mime_type)
                    or ""
                )

            metadata_text = ""
            if file_obj.file_metadata:
                metadata_text = " ".join(
                    [str(v) for v in file_obj.file_metadata.values() if isinstance(v, str)]
                )

            tags_text = " ".join(file_obj.tags) if file_obj.tags else ""

            writer.add_document(
                id=file_obj.id,
                filename=file_obj.filename,
                content=content,
                original_filename=file_obj.original_filename,
                mime_type=file_obj.mime_type or "",
                file_size=file_obj.file_size,
                owner_id=file_obj.owner_id,
                owner_username=file_obj.owner.username
                if hasattr(file_obj, "owner")
                else "",
                parent_directory=file_obj.parent_directory,
                tags=tags_text,
                is_public=file_obj.is_public,
                created_at=file_obj.created_at,
                updated_at=file_obj.updated_at,
                file_hash=file_obj.file_hash,
                metadata=metadata_text,
            )

            writer.commit()

        except Exception as e:
            print(f"Error updating file index: {e}")

    def delete_file(self, file_id):
        """Remove file from index"""
        try:
            idx = self.get_index()
            writer = idx.writer()
            writer.delete_by_term("id", file_id)
            writer.commit()
        except Exception as e:
            print(f"Error deleting from index: {e}")

    def optimize_index(self):
        """Optimize search index for better performance"""
        try:
            idx = self.get_index()
            writer = idx.writer()
            writer.commit(optimize=True)
        except Exception as e:
            print(f"Error optimizing index: {e}")


SEARCH_ENGINE = SearchEngine()

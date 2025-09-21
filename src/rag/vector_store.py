from typing import List, Tuple, Dict, Any
import numpy as np
import os
import gc
import time
import traceback
from sentence_transformers import SentenceTransformer

os.environ["OMP_NUM_THREADS"] = "1"  # Quan trọng để tránh xung đột FAISS
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import faiss

faiss.omp_set_num_threads(1)  # Giới hạn thread cho FAISS

from src.utils.logger import setup_logger

logger = setup_logger()
try:
    from config import USE_MOCK_EMBEDDING, MEMORY_THRESHOLD_MB, LOG_LEVEL
except ImportError:
    USE_MOCK_EMBEDDING = False
    MEMORY_THRESHOLD_MB = 1000
    LOG_LEVEL = "INFO"
# Buộc sử dụng CPU để tránh vấn đề với GPU
os.environ["CUDA_VISIBLE_DEVICES"] = ""


class Document:
    """Lớp Document đại diện cho một đoạn văn bản đã xử lý với metadata"""

    def __init__(self, content: str, metadata: Dict[str, str]):
        self.content = content
        self.metadata = metadata

    def __str__(self) -> str:
        return f"Document(content={self.content[:50]}..., metadata={self.metadata})"


class VectorStore:
    def __init__(
        self, dimension: int = 768, use_mock_embedding: bool = False
    ):  # Sử dụng 768 dims và real embedding
        self.dimension = dimension
        self.index = faiss.IndexFlatL2(dimension)
        self.documents = []
        self.use_mock_embedding = use_mock_embedding
        self._model = None
        self._embeddings_cache = {}
        self._memory_threshold_mb = 1000  # Ngưỡng RAM (MB) để tự động chuyển sang mock
        logger.info(
            f"Initialized VectorStore with dimension {dimension}, mock={use_mock_embedding}"
        )

    def _check_memory_usage(self):
        """Kiểm tra sử dụng RAM và tự động chuyển sang mock nếu quá cao"""
        try:
            import psutil

            memory_usage = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
            logger.debug(f"Current memory usage: {memory_usage:.2f}MB")
            if memory_usage > self._memory_threshold_mb and not self.use_mock_embedding:
                logger.warning(
                    f"Memory threshold exceeded ({memory_usage:.2f}MB > {self._memory_threshold_mb}MB). Switching to mock embeddings."
                )
                self.use_mock_embedding = True
                # Giải phóng mô hình nếu đã tải
                if self._model is not None:
                    self._model = None
                    gc.collect()
                return True
            return False
        except:
            return False

    @property
    def model(self):
        """Lazy loading và tự động giải phóng mô hình"""
        if self._check_memory_usage():
            return None

        if self._model is None and not self.use_mock_embedding:
            try:
                # Sử dụng model 768 dimensions như config
                self._model = SentenceTransformer(
                    "paraphrase-multilingual-mpnet-base-v2", device="cpu"
                )
                # Tắt đa luồng và giảm batch
                self._model.max_seq_length = 128  # Giảm độ dài tối đa
            except Exception as e:
                logger.error(f"Error loading model: {e}")
                self.use_mock_embedding = True

        return self._model

    def _get_mock_embedding(self, content: str) -> np.ndarray:
        """Tạo mock embedding từ hash nội dung"""
        import hashlib

        content_hash = hashlib.md5(content.encode()).hexdigest()
        seed = int(content_hash, 16) % (2**32)
        rng = np.random.RandomState(seed)
        mock_embedding = rng.rand(self.dimension).astype(np.float32) - 0.5
        norm = np.linalg.norm(mock_embedding)
        if norm > 0:
            mock_embedding /= norm
        return mock_embedding

    def add_documents(self, documents: List[Document]):
        """Thêm documents an toàn với cơ chế tự phục hồi khi lỗi"""
        if not documents:
            logger.warning("No documents to add")
            return

        if self.use_mock_embedding:
            self._add_documents_mock(documents)
        else:
            try:
                self._add_documents_real(documents)
            except Exception as e:
                logger.error(f"Error using real embeddings: {e}. Falling back to mock.")
                self.use_mock_embedding = True
                self._add_documents_mock(documents)

    def _add_documents_mock(self, documents: List[Document]):
        """Thêm documents với mock embeddings - nhanh và tiết kiệm RAM"""
        start_time = time.time()
        try:
            logger.info(f"Adding {len(documents)} documents with mock embeddings")

            embeddings = np.zeros((len(documents), self.dimension), dtype=np.float32)
            for i, doc in enumerate(documents):
                embeddings[i] = self._get_mock_embedding(doc.content)

                # Định kỳ báo cáo
                if i % 5 == 0 or i == len(documents) - 1:
                    print(f"Mock embedded {i+1}/{len(documents)} documents")

            # Thêm vào index và documents
            faiss.normalize_L2(embeddings)
            self.index.add(embeddings)
            self.documents.extend(documents)

            elapsed = time.time() - start_time
            logger.info(
                f"Added {len(documents)} documents to vector store in {elapsed:.2f}s (mock)"
            )
            return True

        except Exception as e:
            logger.error(f"Error adding documents with mock: {e}")
            logger.error(traceback.format_exc())
            return False

    def _add_documents_real(self, documents: List[Document]):
        """Thêm documents với real embeddings - nhưng có cơ chế bảo vệ RAM"""
        start_time = time.time()
        processed = 0
        batch_size = 1  # Encode 1 document/lần để giảm sử dụng RAM
        all_embeddings = []
        force_gc_every = 2  # Force GC sau mỗi 2 documents

        try:
            print(
                f"Adding {len(documents)} documents with real embeddings, batch_size={batch_size}"
            )

            # Xử lý từng batch nhỏ
            for i in range(0, len(documents), batch_size):
                # Kiểm tra RAM
                self._check_memory_usage()
                if self.use_mock_embedding:
                    # Chuyển sang mock nếu RAM quá cao
                    remaining = documents[i:]
                    logger.warning(
                        f"Switching to mock embeddings for remaining {len(remaining)} documents"
                    )
                    self._add_documents_mock(remaining)
                    break

                batch_docs = documents[i : i + batch_size]
                batch_contents = [doc.content for doc in batch_docs]

                # Encode batch
                print(
                    f"Encoding batch {i//batch_size + 1}/{(len(documents) + batch_size - 1)//batch_size}..."
                )

                try:
                    # Ưu tiên dùng cache
                    batch_embeddings = []
                    for content in batch_contents:
                        cache_key = hash(content)
                        if cache_key in self._embeddings_cache:
                            embedding = self._embeddings_cache[cache_key]
                        else:
                            if self.model is None:
                                embedding = self._get_mock_embedding(content)
                            else:
                                embedding = self.model.encode(
                                    [content],
                                    show_progress_bar=False,
                                    convert_to_numpy=True,
                                    device="cpu",
                                )[0]
                            self._embeddings_cache[cache_key] = embedding
                        batch_embeddings.append(embedding)

                    all_embeddings.extend(batch_embeddings)
                    processed += len(batch_docs)

                except Exception as e:
                    logger.error(f"Error encoding batch {i//batch_size + 1}: {e}")
                    # Dùng mock cho batch này
                    for doc in batch_docs:
                        all_embeddings.append(self._get_mock_embedding(doc.content))

                # Giải phóng bộ nhớ thường xuyên
                if (i // batch_size) % force_gc_every == 0:
                    gc.collect()

                print(f"Processed {processed}/{len(documents)} documents")

            # Kết thúc xử lý - thêm tất cả vào index
            if all_embeddings:
                embeddings_array = np.array(all_embeddings, dtype=np.float32)
                faiss.normalize_L2(embeddings_array)
                self.index.add(embeddings_array)
                self.documents.extend(documents[:processed])

                elapsed = time.time() - start_time
                print(f"Successfully added {processed} documents in {elapsed:.2f}s")
                logger.info(f"Added {processed} documents to vector store")

            # Giải phóng bộ nhớ
            all_embeddings = None
            gc.collect()

            return True

        except Exception as e:
            logger.error(f"Error in _add_documents_real: {e}")
            logger.error(traceback.format_exc())
            # Try to add processed documents
            if all_embeddings and processed > 0:
                try:
                    embeddings_array = np.array(all_embeddings, dtype=np.float32)
                    faiss.normalize_L2(embeddings_array)
                    self.index.add(embeddings_array)
                    self.documents.extend(documents[:processed])
                    logger.info(
                        f"Partially added {processed} documents to vector store"
                    )
                except:
                    pass
            return False

    def search_with_scores(
        self, query: str, documents: List[Document] = None, top_k: int = 3
    ) -> Tuple[List[Document], List[float]]:
        """Tìm kiếm kết hợp từ khóa và vector (nếu khả dụng)"""
        # Ưu tiên tìm kiếm từ khóa nếu dùng mock hoặc model lỗi
        if self.use_mock_embedding or self.model is None:
            return self._search_with_keywords(query, documents, top_k)

        # Thử tìm kiếm vector, fallback sang keyword nếu lỗi
        try:
            results, scores = self._search_with_vectors(query, documents, top_k)
            if not results:  # Nếu không tìm thấy kết quả
                logger.info("No vector results, trying keyword search")
                return self._search_with_keywords(query, documents, top_k)
            return results, scores
        except Exception as e:
            logger.error(f"Vector search failed: {e}, falling back to keyword search")
            return self._search_with_keywords(query, documents, top_k)

    def _search_with_keywords(
        self, query: str, documents: List[Document] = None, top_k: int = 3
    ) -> Tuple[List[Document], List[float]]:
        """Tìm kiếm từ khóa cải tiến - dùng bộ lọc stopwords và trọng số TF-IDF"""
        if documents is None:
            documents = self.documents
        if not documents:
            logger.warning("No documents available for search")
            return [], []

        # Tiền xử lý query
        query_terms = query.lower().split()

        # Bỏ qua stopwords tiếng Việt phổ biến
        stopwords = {
            "của",
            "và",
            "các",
            "là",
            "để",
            "trong",
            "với",
            "những",
            "được",
            "không",
            "cho",
            "một",
            "có",
            "này",
            "đã",
            "từ",
            "về",
        }
        filtered_terms = [term for term in query_terms if term not in stopwords]
        if not filtered_terms:  # Nếu tất cả là stopwords
            filtered_terms = query_terms

        results, scores = [], []
        for doc in documents:
            content_lower = doc.content.lower()

            # Tính điểm với trọng số term frequency
            score = 0
            for term in filtered_terms:
                # Đếm số lần xuất hiện của term
                count = content_lower.count(term)
                if count > 0:
                    # Trọng số TF-IDF đơn giản (không nhân 100 như trước)
                    score += count / len(content_lower)

            # Thêm vào kết quả nếu phù hợp
            if score > 0:
                results.append(doc)
                scores.append(score)

        # Chuẩn hóa điểm số về khoảng 0-1
        if scores:
            max_score = max(scores)
            if max_score > 0:
                scores = [score / max_score for score in scores]

        # Sắp xếp kết quả
        if not results:
            return [], []

        sorted_pairs = sorted(zip(scores, results), key=lambda x: x[0], reverse=True)
        sorted_scores = [score for score, _ in sorted_pairs]
        sorted_results = [doc for _, doc in sorted_pairs]

        return sorted_results[:top_k], sorted_scores[:top_k]

    def _search_with_vectors(
        self, query: str, documents: List[Document] = None, top_k: int = 3
    ) -> Tuple[List[Document], List[float]]:
        """Tìm kiếm vector với nhiều cải tiến"""
        if documents is None:
            if not self.index or len(self.documents) == 0:
                logger.warning("Vector store is empty, cannot search")
                return [], []
            search_docs = self.documents
            search_index = self.index
        else:
            # Tạo index tạm thời
            if not documents:
                logger.warning("Empty documents list provided for search")
                return [], []

            search_docs = documents

            try:
                # Encode các documents được cung cấp
                contents = [doc.content for doc in documents]
                embeddings = []

                # Ưu tiên sử dụng cache
                for content in contents:
                    cache_key = hash(content)
                    if cache_key in self._embeddings_cache:
                        embedding = self._embeddings_cache[cache_key]
                    else:
                        embedding = self.model.encode([content], device="cpu")[0]
                        self._embeddings_cache[cache_key] = embedding
                    embeddings.append(embedding)

                embeddings = np.array(embeddings)
                temp_index = faiss.IndexFlatL2(self.dimension)
                faiss.normalize_L2(embeddings)
                temp_index.add(embeddings)
                search_index = temp_index

            except Exception as e:
                logger.error(f"Error creating temporary index: {e}")
                return [], []

        try:
            # Encode query
            logger.info(f"Searching for: {query}")
            query_embedding = self.model.encode([query], device="cpu")[0]
            query_embedding = query_embedding.reshape(1, -1)
            faiss.normalize_L2(query_embedding)

            # Tìm kiếm với k phù hợp
            actual_k = min(top_k, len(search_docs))
            distances, indices = search_index.search(query_embedding, actual_k)

            # Kiểm tra kết quả
            if indices.size == 0 or indices[0][0] == -1:
                logger.warning("No vector search results found")
                return [], []

            # Tính điểm tương đồng từ khoảng cách
            similarities = [1.0 / (1.0 + float(dist)) for dist in distances[0]]

            # Lấy document tương ứng
            results = [search_docs[idx] for idx in indices[0]]

            # Log kết quả tìm kiếm
            for i, (doc, score) in enumerate(zip(results, similarities)):
                content_preview = (
                    doc.content[:50] + "..." if len(doc.content) > 50 else doc.content
                )
                logger.debug(
                    f"Result {i+1}: Score {score:.4f}, Document: {content_preview}"
                )

            return results, similarities

        except Exception as e:
            logger.error(f"Search error: {e}")
            return [], []

    def clear(self):
        """Xóa tất cả documents và reset index"""
        self.documents = []
        self._embeddings_cache = {}
        if hasattr(self, "index"):
            del self.index
        self.index = faiss.IndexFlatL2(self.dimension)
        gc.collect()  # Force garbage collection
        logger.info("Cleared vector store")


# # Ver3
# from typing import List, Tuple, Dict, Any
# import numpy as np
# import os
# import gc
# import time
# from sentence_transformers import SentenceTransformer
# try:
#     import faiss
# except ImportError:
#     raise ImportError("FAISS not installed. Run: pip install faiss-cpu")
# from src.utils.logger import setup_logger
# logger = setup_logger()

# # Buộc sử dụng CPU để tránh vấn đề với GPU
# os.environ['CUDA_VISIBLE_DEVICES'] = ""

# class Document:
#     """Lớp Document đại diện cho một đoạn văn bản đã xử lý với metadata"""
#     def __init__(self, content: str, metadata: Dict[str, str]):
#         self.content = content
#         self.metadata = metadata

#     def __str__(self) -> str:
#         return f"Document(content={self.content[:50]}..., metadata={self.metadata})"

# class VectorStore:
#     def __init__(self, dimension: int = 384, use_mock_embedding: bool = False):
#         self.dimension = dimension
#         self.index = faiss.IndexFlatL2(dimension)
#         self.documents = []
#         self.use_mock_embedding = use_mock_embedding
#         self._model = None
#         self._embeddings_cache = {}
#         logger.info(f"Initialized VectorStore with dimension {dimension}")

#     @property
#     def model(self):
#         if self._model is None and not self.use_mock_embedding:
#             # Dùng mô hình nhẹ nhất, không dùng đa luồng để tránh overload CPU
#             self._model = SentenceTransformer("paraphrase-MiniLM-L3-v2", device="cpu")
#         return self._model

#     def _get_mock_embedding(self, content: str) -> np.ndarray:
#         import hashlib
#         content_hash = hashlib.md5(content.encode()).hexdigest()
#         seed = int(content_hash, 16) % (2**32)
#         rng = np.random.RandomState(seed)
#         mock_embedding = rng.rand(self.dimension).astype(np.float32) - 0.5
#         norm = np.linalg.norm(mock_embedding)
#         if norm > 0:
#             mock_embedding /= norm
#         return mock_embedding

#     def add_documents(self, documents: List[Document]):
#         if not documents:
#             logger.warning("No documents to add")
#             return

#         start_time = gc_start = None
#         try:
#             print(f"Thêm {len(documents)} documents vào vector store")
#             start_time = time.time()
#             embeddings = []

#             # Encode từng document một, tránh batch lớn
#             for i, doc in enumerate(documents):
#                 content = doc.content
#                 cache_key = hash(content)
#                 if cache_key in self._embeddings_cache:
#                     embedding = self._embeddings_cache[cache_key]
#                 else:
#                     if self.use_mock_embedding:
#                         embedding = self._get_mock_embedding(content)
#                     else:
#                         try:
#                             # Encode từng document, không batch, không show_progress_bar
#                             embedding = self.model.encode([content], show_progress_bar=False, device="cpu")[0]
#                         except Exception as e:
#                             logger.error(f"Lỗi encoding document {i+1}: {str(e)}")
#                             embedding = self._get_mock_embedding(content)
#                     self._embeddings_cache[cache_key] = embedding
#                 embeddings.append(embedding)
#                 if (i + 1) % 2 == 0:
#                     gc.collect()
#                 print(f"Đã encode document {i+1}/{len(documents)}")

#             embeddings = np.array(embeddings, dtype=np.float32)
#             faiss.normalize_L2(embeddings)
#             self.index.add(embeddings)
#             self.documents.extend(documents)
#             logger.info(f"Added {len(documents)} documents to vector store")
#             gc.collect()
#             elapsed = time.time() - start_time
#             print(f"Đã tạo {len(embeddings)} embeddings với shape {embeddings.shape}")
#             print(f"Thời gian xử lý: {elapsed:.2f} giây")
#         except Exception as e:
#             import traceback
#             logger.error(f"Error during encoding: {str(e)}")
#             logger.error(traceback.format_exc())

#     def search_with_scores(self, query: str, documents: List[Document] = None, top_k: int = 3) -> Tuple[List[Document], List[float]]:
#         if self.use_mock_embedding or (self.model is None):
#             return self._search_with_keywords(query, documents, top_k)
#         else:
#             return self._search_with_vectors(query, documents, top_k)

#     def _search_with_keywords(self, query: str, documents: List[Document] = None, top_k: int = 3) -> Tuple[List[Document], List[float]]:
#         if documents is None:
#             documents = self.documents
#         if not documents:
#             logger.warning("No documents available for search")
#             return [], []
#         query_terms = query.lower().split()
#         results, scores = [], []
#         for doc in documents:
#             content_lower = doc.content.lower()
#             matches = sum(1 for term in query_terms if term in content_lower)
#             if matches > 0:
#                 score = matches / len(query_terms)
#                 results.append(doc)
#                 scores.append(score)
#         sorted_pairs = sorted(zip(scores, results), key=lambda x: x[0], reverse=True)
#         sorted_scores = [score for score, _ in sorted_pairs]
#         sorted_results = [doc for _, doc in sorted_pairs]
#         return sorted_results[:top_k], sorted_scores[:top_k]

#     def _search_with_vectors(self, query: str, documents: List[Document] = None, top_k: int = 3) -> Tuple[List[Document], List[float]]:
#         if documents is None:
#             if not self.index or len(self.documents) == 0:
#                 logger.warning("Vector store is empty, cannot search")
#                 return [], []
#             search_docs = self.documents
#             search_index = self.index
#         else:
#             if not documents:
#                 logger.warning("Empty documents list provided for search")
#                 return [], []
#             search_docs = documents
#             try:
#                 contents = [doc.content for doc in documents]
#                 embeddings = []
#                 for content in contents:
#                     cache_key = hash(content)
#                     if cache_key in self._embeddings_cache:
#                         embedding = self._embeddings_cache[cache_key]
#                     else:
#                         embedding = self.model.encode([content], show_progress_bar=False, device="cpu")[0]
#                         self._embeddings_cache[cache_key] = embedding
#                     embeddings.append(embedding)
#                 embeddings = np.array(embeddings)
#                 temp_index = faiss.IndexFlatL2(self.dimension)
#                 faiss.normalize_L2(embeddings)
#                 temp_index.add(embeddings)
#                 search_index = temp_index
#             except Exception as e:
#                 logger.error(f"Error creating temporary index: {str(e)}")
#                 return self._search_with_keywords(query, documents, top_k)
#         try:
#             logger.info(f"Searching for: {query}")
#             query_embedding = self.model.encode([query], show_progress_bar=False, device="cpu")[0]
#             query_embedding = query_embedding.reshape(1, -1)
#             faiss.normalize_L2(query_embedding)
#             actual_k = min(top_k, len(search_docs))
#             distances, indices = search_index.search(query_embedding, actual_k)
#             if indices.size == 0 or indices[0][0] == -1:
#                 logger.warning("No search results found")
#                 return [], []
#             similarities = [1.0 / (1.0 + float(dist)) for dist in distances[0]]
#             results = [search_docs[idx] for idx in indices[0]]
#             for i, (doc, score) in enumerate(zip(results, similarities)):
#                 logger.debug(f"Result {i+1}: Score {score:.4f}, Document: {doc.content[:50]}...")
#             return results, similarities
#         except Exception as e:
#             import traceback
#             logger.error(f"Search error: {str(e)}")
#             logger.error(traceback.format_exc())
#             return self._search_with_keywords(query, documents, top_k)

#     def clear(self):
#         self.documents = []
#         self._embeddings_cache = {}
#         if hasattr(self, 'index'):
#             del self.index
#         self.index = faiss.IndexFlatL2(self.dimension)
#         logger.info("Cleared vector store")

#     def __del__(self):
#         if hasattr(self, 'index'):
#             del self.index

# Ver2
# from typing import List, Tuple, Dict, Any
# import numpy as np
# from sentence_transformers import SentenceTransformer
# try:
#     import faiss
# except ImportError:
#     raise ImportError("FAISS not installed. Run: pip install faiss-cpu")
# from src.utils.logger import setup_logger
# logger = setup_logger()
# import os
# import time
# import threading
# from queue import Queue
# import gc

# # Buộc sử dụng CPU để tránh vấn đề với GPU
# os.environ['CUDA_VISIBLE_DEVICES'] = ""

# class Document:
#     """Lớp Document đại diện cho một đoạn văn bản đã xử lý với metadata"""
#     def __init__(self, content: str, metadata: Dict[str, str]):
#         self.content = content
#         self.metadata = metadata

#     def __str__(self) -> str:
#         """String representation để debug"""
#         return f"Document(content={self.content[:50]}..., metadata={self.metadata})"

# class VectorStore:
#     def __init__(self, dimension: int = 384, use_mock_embedding: bool = False):
#         """
#         Khởi tạo VectorStore

#         Args:
#             dimension: Dimension của vectors
#             use_mock_embedding: Nếu True, sẽ dùng mock embeddings thay vì gọi mô hình thật
#         """
#         self.dimension = dimension
#         self.index = faiss.IndexFlatL2(dimension)
#         self.documents = []
#         self.use_mock_embedding = use_mock_embedding
#         self._model = None  # Lazy loading
#         self._embeddings_cache = {}  # Cache để tránh encode lại
#         logger.info(f"Initialized VectorStore with dimension {dimension}")

#     @property
#     def model(self):
#         """Lazy loading model để giảm tải khi khởi tạo"""
#         if self._model is None and not self.use_mock_embedding:
#             # Sử dụng mô hình siêu nhẹ
#             self._model = SentenceTransformer("paraphrase-MiniLM-L3-v2")
#         return self._model

#     def _get_mock_embedding(self, content: str) -> np.ndarray:
#         """Tạo mock embedding từ nội dung văn bản"""
#         # Dùng hash để tạo embedding giả có tính nhất quán
#         import hashlib
#         # Tạo seed từ hash của content để có kết quả nhất quán
#         content_hash = hashlib.md5(content.encode()).hexdigest()
#         seed = int(content_hash, 16) % (2**32)
#         np.random.seed(seed)

#         # Tạo vector ngẫu nhiên nhưng nhất quán
#         mock_embedding = np.random.rand(self.dimension).astype(np.float32) - 0.5

#         # Normalize vector để giống với thực tế
#         norm = np.linalg.norm(mock_embedding)
#         if norm > 0:
#             mock_embedding /= norm

#         return mock_embedding

#     def add_documents(self, documents: List[Document]):
#         """Thêm documents vào vector store với xử lý tối ưu cho MacOS"""
#         if not documents:
#             logger.warning("No documents to add")
#             return

#         start_time = time.time()

#         try:
#             # Hiển thị thông tin cơ bản
#             print(f"Thêm {len(documents)} documents vào vector store")

#             # 1. Sử dụng mock embedding nếu được chỉ định
#             if self.use_mock_embedding:
#                 embeddings = np.zeros((len(documents), self.dimension), dtype=np.float32)
#                 for i, doc in enumerate(documents):
#                     print(f"Tạo mock embedding cho document {i+1}/{len(documents)}")
#                     embeddings[i] = self._get_mock_embedding(doc.content)

#             # 2. Hoặc encode thật nhưng với batch size nhỏ và hiển thị tiến trình
#             else:
#                 # Xử lý từng document một để tránh memory issues
#                 embeddings = []
#                 for i, doc in enumerate(documents):
#                     content = doc.content

#                     # Check cache để tránh encode lại
#                     cache_key = hash(content)
#                     if cache_key in self._embeddings_cache:
#                         print(f"Dùng cache cho document {i+1}/{len(documents)}")
#                         embedding = self._embeddings_cache[cache_key]
#                     else:
#                         print(f"Encoding document {i+1}/{len(documents)}")
#                         try:
#                             # Encode với batch_size=1
#                             embedding = self.model.encode([content], show_progress_bar=False)[0]
#                             # Lưu vào cache
#                             self._embeddings_cache[cache_key] = embedding
#                             print(f"Hoàn thành embedding cho document {i+1}")
#                         except Exception as e:
#                             logger.error(f"Lỗi encoding document {i+1}: {str(e)}")
#                             # Dùng mock embedding thay thế nếu thất bại
#                             embedding = self._get_mock_embedding(content)
#                             print(f"Dùng mock embedding thay thế cho document {i+1}")

#                     embeddings.append(embedding)

#                     # Giải phóng bộ nhớ sau mỗi document
#                     if i % 2 == 1:  # Cứ 2 documents thì clear một lần
#                         gc.collect()

#                 # Chuyển list thành numpy array
#                 embeddings = np.array(embeddings, dtype=np.float32)

#             print(f"Đã tạo {len(embeddings)} embeddings với shape {embeddings.shape}")

#             # 3. Thêm vào FAISS index
#             # Chuẩn hóa vectors để cải thiện kết quả tìm kiếm
#             faiss.normalize_L2(embeddings)
#             self.index.add(embeddings)

#             # 4. Lưu documents
#             self.documents.extend(documents)
#             logger.info(f"Added {len(documents)} documents to vector store")

#             # 5. Giải phóng bộ nhớ
#             gc.collect()

#             # Báo cáo thời gian
#             elapsed = time.time() - start_time
#             print(f"Thời gian xử lý: {elapsed:.2f} giây")

#         except Exception as e:
#             import traceback
#             logger.error(f"Error during encoding: {str(e)}")
#             logger.error(traceback.format_exc())

#     def search_with_scores(self, query: str, documents: List[Document] = None, top_k: int = 3) -> Tuple[List[Document], List[float]]:
#         """Tìm kiếm documents liên quan và trả về kèm điểm tương đồng"""

#         # Lựa chọn giữa tìm kiếm vector và tìm kiếm từ khóa đơn giản dựa trên context
#         if self.use_mock_embedding or (self.model is None):
#             return self._search_with_keywords(query, documents, top_k)
#         else:
#             return self._search_with_vectors(query, documents, top_k)

#     def _search_with_keywords(self, query: str, documents: List[Document] = None, top_k: int = 3) -> Tuple[List[Document], List[float]]:
#         """Tìm kiếm đơn giản dựa trên từ khóa"""
#         if documents is None:
#             documents = self.documents

#         if not documents:
#             logger.warning("No documents available for search")
#             return [], []

#         # Tiền xử lý truy vấn
#         query_terms = query.lower().split()

#         # Tính điểm tương đồng
#         results = []
#         scores = []

#         for doc in documents:
#             content_lower = doc.content.lower()
#             # Tính điểm dựa trên số từ khóa xuất hiện
#             matches = sum(1 for term in query_terms if term in content_lower)
#             if matches > 0:
#                 # Tính điểm tương đồng dựa trên số từ khóa trùng khớp
#                 # và độ dài của văn bản (ưu tiên văn bản ngắn hơn)
#                 score = matches / len(query_terms) * (1 - 0.1 * min(9, len(content_lower) / 500))
#                 results.append(doc)
#                 scores.append(score)

#         # Sắp xếp kết quả
#         sorted_pairs = sorted(zip(scores, results), key=lambda x: x[0], reverse=True)
#         sorted_scores = [score for score, _ in sorted_pairs]
#         sorted_results = [doc for _, doc in sorted_pairs]

#         # Giới hạn số lượng kết quả
#         return sorted_results[:top_k], sorted_scores[:top_k]

#     def _search_with_vectors(self, query: str, documents: List[Document] = None, top_k: int = 3) -> Tuple[List[Document], List[float]]:
#         """Tìm kiếm dựa trên embedding vectors"""
#         # Kiểm tra xem có documents để tìm kiếm không
#         if documents is None:
#             if not self.index or len(self.documents) == 0:
#                 logger.warning("Vector store is empty, cannot search")
#                 return [], []
#             search_docs = self.documents
#             search_index = self.index
#         else:
#             # Tạo index tạm thời cho documents được cung cấp
#             if not documents:
#                 logger.warning("Empty documents list provided for search")
#                 return [], []

#             search_docs = documents

#             try:
#                 # Encode documents
#                 contents = [doc.content for doc in documents]
#                 embeddings = []

#                 # Encode từng document một
#                 for content in contents:
#                     cache_key = hash(content)
#                     if cache_key in self._embeddings_cache:
#                         embedding = self._embeddings_cache[cache_key]
#                     else:
#                         embedding = self.model.encode([content], show_progress_bar=False)[0]
#                         self._embeddings_cache[cache_key] = embedding
#                     embeddings.append(embedding)

#                 embeddings = np.array(embeddings)

#                 # Tạo index tạm thời
#                 temp_index = faiss.IndexFlatL2(self.dimension)
#                 faiss.normalize_L2(embeddings)  # Chuẩn hóa vectors
#                 temp_index.add(embeddings)
#                 search_index = temp_index
#             except Exception as e:
#                 logger.error(f"Error creating temporary index: {str(e)}")
#                 return self._search_with_keywords(query, documents, top_k)  # Fallback to keyword search

#         try:
#             # Encode query
#             logger.info(f"Searching for: {query}")
#             query_embedding = self.model.encode([query])[0]
#             query_embedding = query_embedding.reshape(1, -1)
#             faiss.normalize_L2(query_embedding)

#             # Tìm kiếm top_k documents
#             actual_k = min(top_k, len(search_docs))
#             distances, indices = search_index.search(query_embedding, actual_k)

#             # Kiểm tra kết quả tìm kiếm
#             if indices.size == 0 or indices[0][0] == -1:
#                 logger.warning("No search results found")
#                 return [], []

#             # Chuyển đổi khoảng cách L2 sang điểm tương đồng (similarity)
#             # Khoảng cách L2 nhỏ = similarity cao
#             # Formula: similarity = 1 / (1 + distance)
#             similarities = [1.0 / (1.0 + float(dist)) for dist in distances[0]]

#             # Lấy documents theo indices
#             results = [search_docs[idx] for idx in indices[0]]

#             # Log kết quả
#             for i, (doc, score) in enumerate(zip(results, similarities)):
#                 logger.debug(f"Result {i+1}: Score {score:.4f}, Document: {doc.content[:50]}...")

#             return results, similarities

#         except Exception as e:
#             import traceback
#             logger.error(f"Search error: {str(e)}")
#             logger.error(traceback.format_exc())
#             # Fallback to keyword search if vector search fails
#             return self._search_with_keywords(query, documents, top_k)

#     def clear(self):
#         """Xóa tất cả documents và reset index"""
#         self.documents = []
#         self._embeddings_cache = {}
#         if hasattr(self, 'index'):
#             del self.index
#         self.index = faiss.IndexFlatL2(self.dimension)
#         logger.info("Cleared vector store")

#     def __del__(self):
#         """Destructor để giải phóng tài nguyên"""
#         if hasattr(self, 'index'):
#             del self.index
# from typing import List, Tuple, Dict, Any
# import numpy as np
# from sentence_transformers import SentenceTransformer
# try:
#     import faiss
# except ImportError:
#     raise ImportError("FAISS not installed. Run: pip install faiss-cpu")
# from src.utils.logger import setup_logger
# logger = setup_logger()
# import os
# # Buộc sử dụng CPU để tránh vấn đề với GPU
# os.environ['CUDA_VISIBLE_DEVICES'] = ""

# class Document:
#     """Lớp Document đại diện cho một đoạn văn bản đã xử lý với metadata"""
#     def __init__(self, content: str, metadata: Dict[str, str]):
#         self.content = content
#         self.metadata = metadata

#     def __str__(self) -> str:
#         """String representation để debug"""
#         return f"Document(content={self.content[:50]}..., metadata={self.metadata})"

# class VectorStore:
#     def __init__(self, dimension: int = 384):
#         # Sử dụng mô hình nhẹ hơn để tránh vấn đề bộ nhớ
#         self.model = SentenceTransformer("paraphrase-MiniLM-L3-v2")
#         self.dimension = dimension
#         self.index = faiss.IndexFlatL2(dimension)
#         self.documents = []
#         logger.info(f"Initialized VectorStore with dimension {dimension}")

#     # def add_documents(self, documents: List[Document]):
#     #     """Thêm documents vào vector store"""
#     #     if not documents:
#     #         logger.warning("No documents to add")
#     #         return

#     #     try:
#     #         # Tách nội dung để encode
#     #         contents = [doc.content for doc in documents]
#     #         logger.info(f"Encoding {len(contents)} documents")

#     #         # Giảm batch_size để tránh memory issues
#     #         embeddings = self.model.encode(contents, batch_size=2, show_progress_bar=False)
#     #         logger.info(f"Successfully created {len(embeddings)} embeddings")

#     #         # Kiểm tra shape của embeddings
#     #         if embeddings.shape[1] != self.dimension:
#     #             logger.error(f"Embedding dimension mismatch: expected {self.dimension}, got {embeddings.shape[1]}")
#     #             embeddings = np.resize(embeddings, (embeddings.shape[0], self.dimension))

#     #         # Thêm vào index
#     #         faiss.normalize_L2(embeddings)  # Chuẩn hóa vectors để cải thiện tìm kiếm
#     #         self.index.add(embeddings)

#     #         # Lưu documents
#     #         self.documents.extend(documents)
#     #         logger.info(f"Added {len(documents)} documents to vector store")

#     #         # Giải phóng bộ nhớ
#     #         import gc
#     #         gc.collect()

#     #     except Exception as e:
#     #         import traceback
#     #         logger.error(f"Error during encoding: {str(e)}")
#     #         logger.error(traceback.format_exc())
#     def add_documents(self, documents: List[Document]):
#         if not documents:
#          return

#         try:
#             # Tách nội dung để encode
#             contents = [doc.content for doc in documents]
#             print(f"Bắt đầu encoding {len(contents)} documents với batch_size=1")

#             # Giảm batch_size xuống 1 để tránh memory issues
#             print("Encoding document 1...")
#             embeddings = []
#             for i, content in enumerate(contents):
#                 print(f"Encoding document {i+1}/{len(contents)}...")
#                 # Encode từng document một
#                 embedding = self.model.encode([content], show_progress_bar=False)[0]
#                 embeddings.append(embedding)
#                 print(f"Đã encode document {i+1}")

#             # Chuyển đổi list embeddings thành numpy array
#             embeddings = np.array(embeddings)
#             print(f"Successfully created {len(embeddings)} embeddings với shape {embeddings.shape}")

#             # Thêm vào index
#             faiss.normalize_L2(embeddings)
#             self.index.add(embeddings)

#             # Lưu documents
#             self.documents.extend(documents)
#             logger.info(f"Added {len(documents)} documents to vector store")

#             # Giải phóng bộ nhớ
#             import gc
#             gc.collect()

#         except Exception as e:
#             import traceback
#             print(f"Error during encoding: {str(e)}")
#             print(traceback.format_exc())

#     def search_with_scores(self, query: str, documents: List[Document] = None, top_k: int = 3) -> Tuple[List[Document], List[float]]:
#         """Tìm kiếm documents liên quan và trả về kèm điểm tương đồng"""
#         # Kiểm tra xem có documents để tìm kiếm không
#         if documents is None:
#             if not self.index or len(self.documents) == 0:
#                 logger.warning("Vector store is empty, cannot search")
#                 return [], []
#             search_docs = self.documents
#             search_index = self.index
#         else:
#             # Tạo index tạm thời cho documents được cung cấp
#             if not documents:
#                 logger.warning("Empty documents list provided for search")
#                 return [], []

#             search_docs = documents

#             try:
#                 # Encode documents
#                 contents = [doc.content for doc in documents]
#                 embeddings = self.model.encode(contents, batch_size=2, show_progress_bar=False)

#                 # Tạo index tạm thời
#                 temp_index = faiss.IndexFlatL2(self.dimension)
#                 faiss.normalize_L2(embeddings)  # Chuẩn hóa vectors
#                 temp_index.add(embeddings)
#                 search_index = temp_index
#             except Exception as e:
#                 logger.error(f"Error creating temporary index: {str(e)}")
#                 return [], []

#         try:
#             # Encode query
#             logger.info(f"Searching for: {query}")
#             query_embedding = self.model.encode([query])[0]
#             query_embedding = query_embedding.reshape(1, -1)
#             faiss.normalize_L2(query_embedding)

#             # Tìm kiếm top_k documents
#             actual_k = min(top_k, len(search_docs))
#             distances, indices = search_index.search(query_embedding, actual_k)

#             # Kiểm tra kết quả tìm kiếm
#             if indices.size == 0 or indices[0][0] == -1:
#                 logger.warning("No search results found")
#                 return [], []

#             # Chuyển đổi khoảng cách L2 sang điểm tương đồng (similarity)
#             # Khoảng cách L2 nhỏ = similarity cao
#             # Formula: similarity = 1 / (1 + distance)
#             similarities = [1.0 / (1.0 + float(dist)) for dist in distances[0]]

#             # Lấy documents theo indices
#             results = [search_docs[idx] for idx in indices[0]]

#             # Log kết quả
#             for i, (doc, score) in enumerate(zip(results, similarities)):
#                 logger.debug(f"Result {i+1}: Score {score:.4f}, Document: {doc.content[:50]}...")

#             return results, similarities

#         except Exception as e:
#             import traceback
#             logger.error(f"Search error: {str(e)}")
#             logger.error(traceback.format_exc())
#             return [], []

#     def clear(self):
#         """Xóa tất cả documents và reset index"""
#         self.documents = []
#         if hasattr(self, 'index'):
#             del self.index
#         self.index = faiss.IndexFlatL2(self.dimension)
#         logger.info("Cleared vector store")

#     def __del__(self):
#         """Destructor để giải phóng tài nguyên"""
#         if hasattr(self, 'index'):
#             del self.index

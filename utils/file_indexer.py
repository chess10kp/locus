# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false
# pyright: reportUntypedBaseClass=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnusedCallResult=false
# pyright: reportUnknownVariableType=false
# pyright: reportMissingImports=false
# ruff: ignore

"""
File indexing service with SQLite FTS5 for fast full-text search.
Runs in a background thread for non-blocking file operations.
"""

import os
import sqlite3
import threading
import time
import fnmatch
import logging
from pathlib import Path
from typing import List, Optional, Dict, Tuple
from queue import Queue, Empty
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("FileIndexer")


class ScanType(Enum):
    """Type of scan operation."""
    FULL = 0
    INCREMENTAL = 1
    WATCHER = 2


class ScanStatus(Enum):
    """Status of a scan operation."""
    PENDING = 0
    RUNNING = 1
    SUCCEEDED = 2
    FAILED = 3
    INTERRUPTED = 4


@dataclass
class FileResult:
    """Search result for a file."""
    path: str
    name: str
    parent_path: str
    size: int
    file_type: str
    relevancy_score: float
    last_modified_at: int


@dataclass
class IndexEvent:
    """Event for the indexer to process."""
    event_type: str  # 'full_scan', 'incremental_scan', 'file_created', 'file_deleted', 'file_modified'
    path: str
    timestamp: float = 0.0


class FileIndexer:
    """
    File indexing service running in a background thread.

    Thread-safe singleton pattern with deferred initialization.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # Prevent re-initialization
        if hasattr(self, '_initialized'):
            return

        self._initialized = True
        self.db_path = os.path.expanduser("~/.cache/locus/file_index.db")
        self.home_dir = os.path.expanduser("~")

        # Threading
        self.indexer_thread: Optional[threading.Thread] = None
        self.event_queue: Queue = Queue()
        self.running = False
        self.ready = False
        self.db_lock = threading.Lock()  # Protects SQLite access

        # Statistics
        self.file_count = 0
        self.last_scan_time = 0.0
        self.last_scan_duration = 0

        # Configuration
        self.excluded_dirs = [
            '.cache', '.local', '.config', '.npm', '.node_modules',
            '.git', '.venv', 'venv', '__pycache__', '.mypy_cache',
            'target', 'build', 'dist', '.cargo', '.rustup',
            '.thumbnails', '.local/share/Trash', '.virtualenv',
            'site-packages', '.pytest_cache', '.idea', '.vscode',
            '.emacs.d', '.vim', '.cargo', 'debug', 'cmake-build-',
        ]

        self.excluded_patterns = [
            '*.o', '*.a', '*.so', '*.dylib', '*.dll', '*.exe',
            '*.pyc', '*.pyo', '*.pyd', '*.log', '*.log.*',
            '*.swp', '*.swo', '*~', '.DS_Store', 'Thumbs.db',
            'desktop.ini', '*.part', '*.crdownload', '*.tmp',
            '*.temp', '*.class', '*.jar', '*.war',
        ]

        # Minimum file size to index (100 bytes)
        self.min_file_size = 100

        # File type mappings
        self.file_type_map = {
            '.txt': 'text/plain',
            '.md': 'text/markdown',
            '.py': 'text/x-python',
            '.js': 'text/javascript',
            '.ts': 'text/typescript',
            '.json': 'application/json',
            '.yaml': 'application/x-yaml',
            '.yml': 'application/x-yaml',
            '.xml': 'application/xml',
            '.html': 'text/html',
            '.css': 'text/css',
            '.pdf': 'application/pdf',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.svg': 'image/svg+xml',
            '.webp': 'image/webp',
            '.mp3': 'audio/mpeg',
            '.mp4': 'video/mp4',
            '.wav': 'audio/wav',
            '.flac': 'audio/flac',
            '.ogg': 'audio/ogg',
            '.webm': 'video/webm',
            '.zip': 'application/zip',
            '.tar': 'application/x-tar',
            '.gz': 'application/gzip',
            '.xz': 'application/x-xz',
            '.7z': 'application/x-7z',
            '.rar': 'application/x-rar-compressed',
            '.deb': 'application/vnd.debian.binary-package',
            '.rpm': 'application/x-rpm',
        }

    def _init_database(self):
        """Initialize database with schema."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            # Configure for performance
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.execute("PRAGMA temp_store = MEMORY")
            conn.execute("PRAGMA busy_timeout = 1000")
            conn.execute("PRAGMA page_size = 4096")
            conn.execute("PRAGMA mmap_size = 30000000000")

            # Create main table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS indexed_file (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT UNIQUE NOT NULL,
                    parent_path TEXT NOT NULL,
                    name TEXT NOT NULL,
                    last_modified_at INTEGER,
                    size INTEGER DEFAULT 0,
                    file_type TEXT,
                    relevancy_score REAL DEFAULT 1.0
                )
            """)

            # Create FTS5 virtual table
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS unicode_idx USING fts5(
                    name,
                    content='indexed_file',
                    tokenize='unicode61',
                    prefix='1 2 3 4 5 6'
                )
            """)

            # Create triggers for FTS synchronization
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS unicode_idx_ai
                AFTER INSERT ON indexed_file BEGIN
                    INSERT INTO unicode_idx(rowid, name) VALUES (new.id, new.name);
                END
            """)

            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS unicode_idx_ad
                AFTER DELETE ON indexed_file BEGIN
                    INSERT INTO unicode_idx(unicode_idx, rowid, name)
                    VALUES('delete', old.id, old.name);
                END
            """)

            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS unicode_idx_au
                AFTER UPDATE ON indexed_file BEGIN
                    UPDATE unicode_idx SET name = new.name WHERE rowid = new.id;
                END
            """)

            # Create indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_parent_path ON indexed_file(parent_path)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_path ON indexed_file(path)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_covering ON indexed_file(id, relevancy_score DESC, path)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_last_modified ON indexed_file(last_modified_at)")

            # Create scan history table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scan_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    status INTEGER NOT NULL,
                    created_at INTEGER DEFAULT (unixepoch()),
                    entrypoint TEXT NOT NULL,
                    error TEXT,
                    type INTEGER NOT NULL,
                    indexed_file_count INTEGER DEFAULT 0,
                    duration_ms INTEGER DEFAULT 0
                )
            """)

            conn.commit()

    def start(self):
        """Start the indexer in background thread."""
        if self.running:
            logger.debug("File indexer already running")
            return

        logger.info("Starting file indexer...")
        self.running = True

        # Initialize database
        self._init_database()

        # Start worker thread
        self.indexer_thread = threading.Thread(target=self._indexer_loop, daemon=True)
        self.indexer_thread.start()

        # Queue initial full scan
        self.event_queue.put(IndexEvent('full_scan', self.home_dir))

        logger.info("File indexer started, initial scan queued")

    def stop(self):
        """Stop the indexer."""
        if not self.running:
            return

        logger.info("Stopping file indexer...")
        self.running = False

        if self.indexer_thread:
            self.indexer_thread.join(timeout=5)

        logger.info("File indexer stopped")

    def search_files(self, query: str, limit: int = 50) -> List[FileResult]:
        """
        Search files using FTS5 with relevancy scoring.
        Thread-safe call from main thread.

        Args:
            query: Search query
            limit: Maximum number of results

        Returns:
            List of FileResult objects
        """
        if not self.ready or not query:
            return []

        with self.db_lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    # Use faster settings for searches
                    conn.execute("PRAGMA synchronous = OFF")
                    conn.execute("PRAGMA journal_mode = MEMORY")

                    # FTS5 search with BM25 ranking + relevancy_score
                    cursor = conn.execute("""
                        SELECT
                            f.path, f.name, f.parent_path, f.size,
                            f.file_type, f.relevancy_score, f.last_modified_at
                        FROM indexed_file f
                        INNER JOIN unicode_idx u ON f.id = u.rowid
                        WHERE unicode_idx MATCH ?
                        ORDER BY
                            (bm25(unicode_idx) * -1.0) + f.relevancy_score DESC
                        LIMIT ?
                    """, (self._prepare_fts_query(query), limit))

                    results = []
                    for row in cursor:
                        results.append(FileResult(
                            path=row[0],
                            name=row[1],
                            parent_path=row[2],
                            size=row[3],
                            file_type=row[4] or '',
                            relevancy_score=row[5],
                            last_modified_at=row[6]
                        ))

                    return results
            except Exception as e:
                logger.error(f"Search error: {e}")
                return []

    def _prepare_fts_query(self, query: str) -> str:
        """Prepare query for FTS5 (handle multi-word, quotes, etc.)."""
        # Simple word-based search with prefix matching
        words = query.strip().split()
        if not words:
            return "*"

        # Quote each word and add wildcard for prefix matching
        terms = [f'"{word}"*' for word in words]
        return " ".join(terms)

    def is_excluded(self, path: str) -> bool:
        """Check if path should be excluded from indexing."""
        path_obj = Path(path)

        # Check excluded directories
        for part in path_obj.parts:
            if part in self.excluded_dirs:
                return True

        # Check excluded patterns
        for pattern in self.excluded_patterns:
            if fnmatch.fnmatch(path_obj.name, pattern):
                return True

        # Skip hidden files/dirs (except some explicitly allowed)
        for part in path_obj.parts:
            if part.startswith('.') and part not in {'.git', '.local'}:
                return True

        return False

    def _is_excluded_dir(self, dirpath: str) -> bool:
        """Check if directory should be excluded."""
        dirname = os.path.basename(dirpath)
        return dirname in self.excluded_dirs

    def _indexer_loop(self):
        """Main indexer loop running in background thread."""
        logger.info("File indexer thread started")

        while self.running:
            try:
                # Get event with timeout to allow checking self.running
                event = self.event_queue.get(timeout=1.0)

                if event.event_type == 'full_scan':
                    self._run_full_scan(event.path)
                elif event.event_type == 'incremental_scan':
                    self._run_incremental_scan(event.path)
                elif event.event_type == 'file_created':
                    self._index_single_file(event.path)
                elif event.event_type == 'file_deleted':
                    self._remove_file(event.path)
                elif event.event_type == 'file_modified':
                    self._update_file(event.path)

            except Empty:
                continue
            except Exception as e:
                logger.error(f"Indexer loop error: {e}")

        logger.info("File indexer thread stopped")

    def _run_full_scan(self, root_path: str):
        """Run full scan of directory tree."""
        start_time = time.time()
        logger.info(f"Starting full scan: {root_path}")

        scan_id = self._create_scan_record(root_path, ScanType.FULL)

        try:
            with self.db_lock:
                # Clear existing index for this root
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("DELETE FROM indexed_file WHERE path LIKE ?", (f"{root_path}%",))
                    conn.commit()

            file_count = 0
            batch_count = 0
            batch_size = 1000

            # Batch insert for performance
            batch_data = []

            # Walk directory tree
            for root, dirs, files in os.walk(root_path):
                # Filter out excluded directories in-place
                dirs[:] = [d for d in dirs if not self._is_excluded_dir(os.path.join(root, d))]

                for filename in files:
                    filepath = os.path.join(root, filename)

                    if self.is_excluded(filepath):
                        continue

                    try:
                        stat = os.stat(filepath)
                        if stat.st_size < self.min_file_size:
                            continue

                        path_obj = Path(filepath)
                        parent_path = str(path_obj.parent)
                        name = path_obj.name
                        file_type = self._get_file_type(filepath)

                        batch_data.append((
                            filepath, parent_path, name,
                            int(stat.st_mtime), stat.st_size, file_type
                        ))

                        file_count += 1
                        batch_count += 1

                        # Batch commit
                        if batch_count >= batch_size:
                            self._batch_insert(batch_data)
                            batch_count = 0
                            batch_data = []
                            # Small yield to prevent blocking
                            time.sleep(0.001)

                    except (OSError, PermissionError):
                        continue

            # Insert remaining files
            if batch_data:
                self._batch_insert(batch_data)

            duration_ms = int((time.time() - start_time) * 1000)
            self._update_scan_record(scan_id, ScanStatus.SUCCEEDED, file_count, duration_ms)

            self.file_count = self._get_total_file_count()
            self.last_scan_time = time.time()
            self.last_scan_duration = duration_ms
            self.ready = True

            logger.info(f"Full scan complete: {file_count} files in {duration_ms}ms")

        except Exception as e:
            logger.error(f"Full scan failed: {e}")
            self._update_scan_record(scan_id, ScanStatus.FAILED, 0, 0, str(e))

    def _batch_insert(self, batch_data: List[Tuple]):
        """Batch insert files into database."""
        with self.db_lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.executemany("""
                        INSERT OR REPLACE INTO indexed_file
                        (path, parent_path, name, last_modified_at, size, file_type, relevancy_score)
                        VALUES (?, ?, ?, ?, ?, ?, 1.0)
                    """, batch_data)
                    conn.commit()
            except sqlite3.IntegrityError:
                pass  # Files already exist

    def _run_incremental_scan(self, root_path: str):
        """Run incremental scan checking mtime."""
        start_time = time.time()
        logger.info(f"Starting incremental scan: {root_path}")

        scan_id = self._create_scan_record(root_path, ScanType.INCREMENTAL)

        try:
            updated_count = 0
            deleted_count = 0

            # Check for deleted files
            with self.db_lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.execute(
                        "SELECT path FROM indexed_file WHERE path LIKE ?",
                        (f"{root_path}%",)
                    )
                    for row in cursor:
                        path = row[0]
                        if not os.path.exists(path):
                            conn.execute("DELETE FROM indexed_file WHERE path = ?", (path,))
                            deleted_count += 1
                    conn.commit()

            # Check for updated/new files
            for root, dirs, files in os.walk(root_path):
                dirs[:] = [d for d in dirs if not self._is_excluded_dir(os.path.join(root, d))]

                for filename in files:
                    filepath = os.path.join(root, filename)

                    if self.is_excluded(filepath):
                        continue

                    try:
                        stat = os.stat(filepath)
                        if stat.st_size < self.min_file_size:
                            continue

                        # Check if file needs update
                        if self._file_needs_update(filepath, stat.st_mtime):
                            self._index_file_locked(filepath, stat)
                            updated_count += 1

                    except (OSError, PermissionError):
                        continue

            duration_ms = int((time.time() - start_time) * 1000)
            self._update_scan_record(scan_id, ScanStatus.SUCCEEDED, updated_count, duration_ms)

            self.file_count = self._get_total_file_count()
            self.last_scan_time = time.time()

            logger.info(f"Incremental scan complete: {updated_count} updated, {deleted_count} deleted in {duration_ms}ms")

        except Exception as e:
            logger.error(f"Incremental scan failed: {e}")
            self._update_scan_record(scan_id, ScanStatus.FAILED, 0, 0, str(e))

    def _index_single_file(self, filepath: str):
        """Index a single file."""
        try:
            stat = os.stat(filepath)
            self._index_file_locked(filepath, stat)
        except (OSError, PermissionError):
            pass

    def _index_file_locked(self, filepath: str, stat: os.stat_result):
        """Index a file (must be called with db_lock held)."""
        path_obj = Path(filepath)
        parent_path = str(path_obj.parent)
        name = path_obj.name
        file_type = self._get_file_type(filepath)

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO indexed_file
                    (path, parent_path, name, last_modified_at, size, file_type, relevancy_score)
                    VALUES (?, ?, ?, ?, ?, ?, 1.0)
                """, (filepath, parent_path, name, int(stat.st_mtime), stat.st_size, file_type))
                conn.commit()
        except sqlite3.IntegrityError:
            pass  # File already exists

    def _remove_file(self, filepath: str):
        """Remove file from index."""
        with self.db_lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("DELETE FROM indexed_file WHERE path = ?", (filepath,))
                    conn.commit()
            except Exception as e:
                logger.error(f"Error removing file: {e}")

    def _update_file(self, filepath: str):
        """Update file in index."""
        try:
            stat = os.stat(filepath)
            self._index_file_locked(filepath, stat)
        except (OSError, PermissionError):
            self._remove_file(filepath)

    def _file_needs_update(self, filepath: str, mtime: float) -> bool:
        """Check if file needs to be re-indexed."""
        with self.db_lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.execute(
                        "SELECT last_modified_at FROM indexed_file WHERE path = ?",
                        (filepath,)
                    )
                    row = cursor.fetchone()
                    if not row:
                        return True  # New file
                    return row[0] != int(mtime)  # Modified
            except Exception:
                return True

    def _get_file_type(self, filepath: str) -> str:
        """Get file type from extension."""
        ext = Path(filepath).suffix.lower()
        return self.file_type_map.get(ext, 'application/octet-stream')

    def _get_total_file_count(self) -> int:
        """Get total number of indexed files."""
        with self.db_lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.execute("SELECT COUNT(*) FROM indexed_file")
                    return cursor.fetchone()[0]
            except Exception:
                return 0

    def _create_scan_record(self, entrypoint: str, scan_type: ScanType) -> int:
        """Create a scan history record."""
        with self.db_lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.execute("""
                        INSERT INTO scan_history (entrypoint, type, status)
                        VALUES (?, ?, ?)
                        RETURNING id
                    """, (entrypoint, scan_type.value, ScanStatus.RUNNING.value))
                    return cursor.fetchone()[0]
            except Exception:
                return -1

    def _update_scan_record(self, scan_id: int, status: ScanStatus,
                           file_count: int, duration_ms: int, error: str = ""):
        """Update scan history record."""
        with self.db_lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("""
                        UPDATE scan_history
                        SET status = ?, indexed_file_count = ?, duration_ms = ?, error = ?
                        WHERE id = ?
                    """, (status.value, file_count, duration_ms, error, scan_id))
                    conn.commit()
            except Exception as e:
                logger.error(f"Error updating scan record: {e}")

    # Public API methods

    def get_file_count(self) -> int:
        """Get total number of indexed files."""
        return self.file_count

    def is_ready(self) -> bool:
        """Check if indexer is ready for searches."""
        return self.ready

    def get_last_scan_info(self) -> Dict[str, any]:
        """Get information about last scan."""
        return {
            'time': self.last_scan_time,
            'duration_ms': self.last_scan_duration,
            'file_count': self.file_count
        }

    def force_reindex(self):
        """Force a full re-scan."""
        self.ready = False
        self.event_queue.put(IndexEvent('full_scan', self.home_dir))


# Singleton accessor
def get_file_indexer() -> FileIndexer:
    """Get the singleton file indexer instance."""
    return FileIndexer()

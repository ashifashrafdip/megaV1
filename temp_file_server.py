from __future__ import annotations

import contextlib
import shutil
import socket
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import BinaryIO
from urllib.parse import quote


class TemporaryFileServer:
    """Serve files from a temporary directory and return accessible URLs."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0):
        self.host = host
        self.port = port
        self.temp_dir: tempfile.TemporaryDirectory[str] | None = None
        self.directory: Path | None = None
        self.httpd: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None

    @property
    def base_url(self) -> str:
        if not self.httpd:
            raise RuntimeError("Server is not running. Call start() first.")
        return f"http://{self.host}:{self.httpd.server_port}"

    def start(self) -> str:
        """Start the server and return its base URL."""
        if self.httpd:
            return self.base_url

        self.temp_dir = tempfile.TemporaryDirectory(prefix="py-file-server-")
        self.directory = Path(self.temp_dir.name)

        handler = self._make_handler(self.directory)
        self.httpd = ThreadingHTTPServer((self.host, self.port), handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        return self.base_url

    def stop(self):
        """Stop the server and remove the temporary directory."""
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None

        if self.thread:
            self.thread.join(timeout=2)
            self.thread = None

        if self.temp_dir:
            self.temp_dir.cleanup()
            self.temp_dir = None
            self.directory = None

    def write_text(self, filename: str, content: str, encoding: str = "utf-8") -> str:
        """Write text into the temp directory and return the file URL."""
        path = self._safe_path(filename)
        path.write_text(content, encoding=encoding)
        return self.url_for(filename)

    def write_bytes(self, filename: str, content: bytes) -> str:
        """Write bytes into the temp directory and return the file URL."""
        path = self._safe_path(filename)
        path.write_bytes(content)
        return self.url_for(filename)

    def copy_file(self, source: str | Path, filename: str | None = None) -> str:
        """Copy an existing file into the temp directory and return its URL."""
        source_path = Path(source)
        if not source_path.is_file():
            raise FileNotFoundError(source_path)

        target_name = filename or source_path.name
        target_path = self._safe_path(target_name)
        shutil.copy2(source_path, target_path)
        return self.url_for(target_name)

    def copy_directory(self, source_dir: str | Path, target_subpath: str = "") -> str:
        """Copy an entire directory recursively into the server root and return its URL."""
        src = Path(source_dir).resolve()
        if not src.is_dir():
            raise NotADirectoryError(src)
        self._require_started()
        assert self.directory is not None
        dest = (self.directory / target_subpath).resolve() if target_subpath else self.directory
        shutil.copytree(src, dest, dirs_exist_ok=True)
        return self.url_for(target_subpath or "")

    def save_upload(self, filename: str, stream: BinaryIO) -> str:
        """Save a binary stream into the temp directory and return its URL."""
        path = self._safe_path(filename)
        with path.open("wb") as output:
            shutil.copyfileobj(stream, output)
        return self.url_for(filename)

    def url_for(self, filename: str) -> str:
        """Return the URL for a file in the temporary directory."""
        self._require_started()
        normalized = Path(filename).as_posix().lstrip("/")
        return f"{self.base_url}/{quote(normalized)}"

    def __enter__(self) -> "TemporaryFileServer":
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop()

    def _safe_path(self, filename: str) -> Path:
        self._require_started()
        assert self.directory is not None

        target = (self.directory / filename).resolve()
        root = self.directory.resolve()
        if root != target and root not in target.parents:
            raise ValueError(f"Unsafe filename outside server directory: {filename}")

        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    def _require_started(self):
        if not self.httpd or not self.directory:
            raise RuntimeError("Server is not running. Call start() first.")

    @staticmethod
    def _make_handler(directory: Path):
        class QuietHandler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(directory), **kwargs)

            def end_headers(self):
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "*")
                super().end_headers()

            def do_OPTIONS(self):
                self.send_response(204)
                self.end_headers()

            def copyfile(self, source, outputfile):
                try:
                    shutil.copyfileobj(source, outputfile, length=1024 * 1024)
                except (ConnectionResetError, BrokenPipeError, OSError):
                    return

            def log_message(self, format: str, *args):
                return

        return QuietHandler


def find_free_port(host: str = "127.0.0.1") -> int:
    """Return an available TCP port for callers that need to reserve one."""
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind((host, 0))
        return sock.getsockname()[1]


if __name__ == "__main__":
    with TemporaryFileServer() as server:
        url = server.write_text("hello.txt", "Hello from a temporary HTTP server.\n")
        print(url)
        input("Press Enter to stop the server...")

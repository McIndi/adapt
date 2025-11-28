from pathlib import Path
import logging

from uvicorn import Config, Server

from ..config import AdaptConfig
from ..app import create_app

logger = logging.getLogger(__name__)


def run_serve(root: Path, host: str, port: int, tls_cert: str | None, tls_key: str | None, reload: bool, readonly: bool) -> None:
    """Start the Adapt server.

    Args:
        root: The root directory path for the Adapt configuration.
        host: The host address to bind the server to.
        port: The port number to bind the server to.
        tls_cert: Path to the TLS certificate file. Optional.
        tls_key: Path to the TLS key file. Optional.
        reload: Whether to enable auto-reload for development.
        readonly: Whether to run the server in read-only mode.

    Returns:
        None

    Raises:
        None
    """
    config = AdaptConfig(root=root, readonly=readonly)
    if tls_cert:
        config.tls_cert = Path(tls_cert)
    if tls_key:
        config.tls_key = Path(tls_key)

    use_tls = bool(config.tls_cert and config.tls_key)
    config.secure_cookies = use_tls  # Set secure cookies when using TLS
    logger.info("Starting server on %s:%d with TLS=%s, reload=%s, readonly=%s", host, port, use_tls, reload, readonly)
    app = create_app(config)
    server_config = Config(
        app=app,
        host=host,
        port=port,
        reload=reload,
        ssl_certfile=str(config.tls_cert) if use_tls else None,
        ssl_keyfile=str(config.tls_key) if use_tls else None,
        log_level="info",
    )
    Server(config=server_config).run()
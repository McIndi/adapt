from pathlib import Path
import logging

from uvicorn import Config, Server

from ..config import AdaptConfig
from ..app import create_app

logger = logging.getLogger(__name__)


def run_serve(
    root: Path,
    host: str | None,
    port: int | None,
    tls_cert: str | None,
    tls_key: str | None,
    reload: bool,
    readonly: bool | None,
    debug: bool | None,
) -> None:
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
    config = AdaptConfig(root=root)
    config.load_from_file()
    if host is not None:
        config.host = host
    if port is not None:
        config.port = port
    if readonly is not None:
        config.readonly = readonly
    if debug is not None:
        config.debug = debug
    if (tls_cert and not tls_key) or (tls_key and not tls_cert):
        raise ValueError("Both --tls-cert and --tls-key must be provided together")

    if tls_cert:
        config.tls_cert = Path(tls_cert)
    if tls_key:
        config.tls_key = Path(tls_key)

    if config.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    use_tls = bool(config.tls_cert and config.tls_key)
    config.secure_cookies = use_tls  # Set secure cookies when using TLS
    logger.info(
        "Starting server on %s:%d with TLS=%s, reload=%s, readonly=%s, debug=%s",
        config.host,
        config.port,
        use_tls,
        reload,
        config.readonly,
        config.debug,
    )
    app = create_app(config)
    server_config = Config(
        app=app,
        host=config.host,
        port=config.port,
        reload=reload,
        ssl_certfile=str(config.tls_cert) if use_tls else None,
        ssl_keyfile=str(config.tls_key) if use_tls else None,
        log_level="debug" if config.debug else "info",
    )
    Server(config=server_config).run()
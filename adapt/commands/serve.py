from pathlib import Path

from uvicorn import Config, Server

from ..config import AdaptConfig
from ..app import create_app


def run_serve(root: Path, host: str, port: int, tls_cert: str | None, tls_key: str | None, reload: bool, readonly: bool) -> None:
    config = AdaptConfig(root=root, readonly=readonly)
    if tls_cert:
        config.tls_cert = Path(tls_cert)
    if tls_key:
        config.tls_key = Path(tls_key)

    use_tls = bool(config.tls_cert and config.tls_key)
    config.secure_cookies = use_tls  # Set secure cookies when using TLS
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
from __future__ import annotations

import hashlib
import logging
import mimetypes
import threading
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from sqlmodel import Session, select

from .. import cache, search
from ..audit import log_action
from ..auth.dependencies import check_permission, require_auth
from ..discovery import discover_resource
from ..locks import LockConflictError, LockTimeoutError
from ..routes import build_resource_registry, generate_routes
from ..storage import Action, Group, GroupPermission, Permission, UserGroup, get_db_session
from ..plugins.base import atomic_write


router = APIRouter(tags=["uploads"])


logger = logging.getLogger(__name__)

UPLOAD_ROOT_RESOURCE = ""
_CHUNK_SIZE = 1024 * 1024
_MIME_SNIFF_BYTES = 4096
_refresh_lock = threading.Lock()


def _strip_mime_params(mime_type: str | None) -> str:
    if not mime_type:
        return ""
    return mime_type.split(";", 1)[0].strip().lower()


def _extension_expected_mime(filename: str) -> str:
    mime_type, _ = mimetypes.guess_type(filename)
    return _strip_mime_params(mime_type)


def _sniff_mime(header: bytes, filename: str) -> str:
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if header.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if header.startswith(b"RIFF") and len(header) >= 12 and header[8:12] == b"WEBP":
        return "image/webp"
    if header.startswith(b"%PDF"):
        return "application/pdf"
    if header.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
        suffix = Path(filename).suffix.lower()
        if suffix in {".xlsx", ".xlsm", ".xltx", ".xltm"}:
            return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        return "application/zip"

    if b"\x00" in header:
        return "application/octet-stream"

    text = header.decode("utf-8", errors="ignore").lstrip()
    if text.startswith("{") or text.startswith("["):
        return "application/json"
    lowered = text[:128].lower()
    if lowered.startswith("<svg") or "<svg" in lowered:
        return "image/svg+xml"
    if lowered.startswith("<?xml"):
        return "application/xml"
    if lowered.startswith("<!doctype html") or lowered.startswith("<html"):
        return "text/html"
    return "text/plain"


def _mime_compatible(expected: str, actual: str) -> bool:
    if not expected:
        return True
    if expected == actual:
        return True
    if expected.startswith("text/") and actual.startswith("text/"):
        return True
    return False


def _is_valid_filename(filename: str) -> bool:
    path = Path(filename)
    if not filename or path.is_absolute():
        return False
    if any(separator in filename for separator in ("/", "\\")):
        return False
    if ".." in path.parts:
        return False
    return path.name == filename


def _resolve_target_path(root: Path, filename: str) -> Path:
    target = (root / filename).resolve(strict=False)
    if target.parent != root.resolve():
        raise HTTPException(status_code=400, detail="Filename must stay at the document root")
    return target


def _normalize_allowed_ext(value: str) -> str:
    return value.lower() if value.startswith(".") else f".{value.lower()}"


def _validate_extension_policy(config_upload: dict, filename: str) -> None:
    suffix = Path(filename).suffix.lower()
    allowed = {_normalize_allowed_ext(ext) for ext in config_upload.get("allowed_extensions", [])}
    denied = {_normalize_allowed_ext(ext) for ext in config_upload.get("denied_extensions", [])}

    if suffix in denied:
        raise HTTPException(status_code=400, detail=f"File extension '{suffix}' is not allowed")
    if allowed and suffix not in allowed:
        raise HTTPException(status_code=400, detail=f"File extension '{suffix}' is not allowed")


def _validate_mime_policy(config_upload: dict, filename: str, sniffed_mime: str, provided_mime: str) -> None:
    strict = bool(config_upload.get("strict_mime_sniffing", False))
    allowed_mime_types = {
        _strip_mime_params(item)
        for item in config_upload.get("allowed_mime_types", [])
        if _strip_mime_params(item)
    }

    if strict and allowed_mime_types and sniffed_mime not in allowed_mime_types:
        raise HTTPException(status_code=400, detail=f"Detected MIME type '{sniffed_mime}' is not allowed")

    if strict:
        expected_mime = _extension_expected_mime(filename)
        if expected_mime and not _mime_compatible(expected_mime, sniffed_mime):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Detected MIME type '{sniffed_mime}' does not match the filename extension "
                    f"(expected '{expected_mime}')"
                ),
            )
        normalized_provided = _strip_mime_params(provided_mime)
        if normalized_provided and normalized_provided != "application/octet-stream":
            if not _mime_compatible(normalized_provided, sniffed_mime):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Detected MIME type '{sniffed_mime}' does not match the provided content type "
                        f"'{normalized_provided}'"
                    ),
                )


def _log_upload(request: Request, action: str, filename: str, details: str, user_id: int) -> None:
    log_action(request, action, filename, details, user_id)


def _grant_owner_access(
    db: Session,
    user_id: int,
    username: str,
    resource_namespaces: list[str],
    resource_label: str,
) -> None:
    group_name = f"upload_owner_{resource_label.replace('.', '_').replace('/', '_')}"
    group = db.exec(select(Group).where(Group.name == group_name)).first()
    if group is None:
        group = Group(name=group_name, description=f"Owner access for {resource_label}")
        db.add(group)
        db.commit()
        db.refresh(group)

    if not db.get(UserGroup, (user_id, group.id)):
        db.add(UserGroup(user_id=user_id, group_id=group.id))

    for namespace in resource_namespaces:
        for action in (Action.read, Action.write):
            perm = db.exec(select(Permission).where(Permission.resource == namespace, Permission.action == action)).first()
            if perm is None:
                perm = Permission(resource=namespace, action=action, description=f"{action.value.capitalize()} access to {namespace}")
                db.add(perm)
                db.commit()
                db.refresh(perm)
            if not db.get(GroupPermission, (group.id, perm.id)):
                db.add(GroupPermission(group_id=group.id, permission_id=perm.id))

    db.commit()
    logger.debug("Granted owner access to %s for user %s", resource_label, username)


def _refresh_upload_resources(request: Request, target: Path) -> list[str]:
    config = request.app.state.config
    with _refresh_lock:
        discovered = discover_resource(target, config)
        if not discovered:
            return []

        existing_by_path = {resource.path.resolve(): resource for resource in request.app.state.resources}
        for resource in discovered:
            current = existing_by_path.get(resource.path.resolve())
            if current is None:
                request.app.state.resources.append(resource)
            else:
                current.__dict__.update(resource.__dict__)

        new_resources = [resource for resource in discovered if resource.path.resolve() not in existing_by_path]
        if new_resources:
            registry = build_resource_registry(new_resources, config)
            for namespace, entry in registry.items():
                if namespace in request.app.state.resource_registry:
                    continue
                request.app.state.resource_registry[namespace] = entry
            generate_routes(request.app, registry)

    return [resource.relative_path.with_suffix("").as_posix() if "sub_namespace" not in resource.metadata else f"{resource.relative_path.with_suffix('').as_posix()}/{resource.metadata['sub_namespace']}" for resource in discovered]


@router.post("/api/uploads", status_code=201)
async def upload_file(
    request: Request,
    db: Session = Depends(get_db_session),
    user=Depends(require_auth),
):
    """Upload a new file into the document root."""
    request.state.user = user
    form = await request.form()
    filename = str(form.get("filename") or "").strip()
    upload = form.get("file")

    if request.app.state.config.readonly:
        _log_upload(request, "upload_denied", filename or "<missing>", "Uploads are disabled in read-only mode", user.id)
        raise HTTPException(status_code=405, detail="Server is in read-only mode")

    config_upload = request.app.state.config.upload
    if not config_upload.get("enabled", False):
        _log_upload(request, "upload_denied", filename or "<missing>", "Uploads are disabled", user.id)
        raise HTTPException(status_code=403, detail="Uploads are disabled")

    if not check_permission(user, db, "write", UPLOAD_ROOT_RESOURCE):
        _log_upload(request, "upload_denied", filename or "<missing>", "Permission denied for document root", user.id)
        raise HTTPException(status_code=403, detail="Permission denied: write on document root")

    if not _is_valid_filename(filename):
        _log_upload(request, "upload_failed", filename or "<missing>", "Invalid filename", user.id)
        raise HTTPException(status_code=400, detail="Filename must be a basename without path separators")

    if upload is None or not hasattr(upload, "filename"):
        _log_upload(request, "upload_failed", filename, "Missing file payload", user.id)
        raise HTTPException(status_code=400, detail="Missing file payload")

    root = request.app.state.config.root.resolve()
    target = _resolve_target_path(root, filename)

    if target.is_dir() or target.name.startswith("."):
        _log_upload(request, "upload_failed", filename, "Hidden files and directories are not allowed", user.id)
        raise HTTPException(status_code=400, detail="Filename is not allowed")

    if target.exists() and target.is_dir():
        _log_upload(request, "upload_failed", filename, "Target path is a directory", user.id)
        raise HTTPException(status_code=400, detail="Target path is a directory")

    if target.exists() or target.is_symlink():
        try:
            resolved_target = target.resolve(strict=False)
        except OSError as exc:
            _log_upload(request, "upload_failed", filename, f"Path resolution failed: {exc}", user.id)
            raise HTTPException(status_code=400, detail="Unable to resolve upload target") from exc
        if resolved_target.parent != root:
            _log_upload(request, "upload_failed", filename, "Symlink escape rejected", user.id)
            raise HTTPException(status_code=400, detail="Upload target must stay inside the document root")

    _validate_extension_policy(config_upload, filename)

    collision_policy = str(config_upload.get("collision_policy", "overwrite")).strip().lower()
    checksum = hashlib.sha256()
    size = 0
    sniffed_mime = "application/octet-stream"
    provided_mime = getattr(upload, "content_type", None) or "application/octet-stream"
    outcome = "created"

    owner_name = getattr(user, "username", "anonymous")
    try:
        with request.app.state.lock_manager.lock(target.as_posix(), owner_name, reason="upload"):
            existed = target.exists() or target.is_symlink()
            if existed and collision_policy == "reject":
                raise HTTPException(status_code=409, detail="Target file already exists and overwrite is disabled")

            await upload.seek(0)

            def _write_file(tmp_path: Path) -> None:
                nonlocal size, sniffed_mime
                header = bytearray()
                with tmp_path.open("wb") as destination:
                    while True:
                        chunk = upload.file.read(_CHUNK_SIZE)
                        if not chunk:
                            break
                        if len(header) < _MIME_SNIFF_BYTES:
                            needed = _MIME_SNIFF_BYTES - len(header)
                            header.extend(chunk[:needed])
                        size += len(chunk)
                        if size > int(config_upload["max_size_bytes"]):
                            raise HTTPException(status_code=413, detail="Upload exceeds the configured size limit")
                        checksum.update(chunk)
                        destination.write(chunk)
                sniffed_mime = _sniff_mime(bytes(header), filename)
                _validate_mime_policy(config_upload, filename, sniffed_mime, provided_mime)

            await run_in_threadpool(atomic_write, target, target.suffix, _write_file)

            cache.invalidate_cache(str(target))

            namespaces = _refresh_upload_resources(request, target)
            if not existed:
                _grant_owner_access(db, user.id, user.username, namespaces, target.name)

            for namespace in namespaces:
                entry = request.app.state.resource_registry.get(namespace)
                if entry is None:
                    continue
                search.index_resource(entry.plugin, entry.descriptor, namespace)

            action = "upload_success"
            outcome = "overwritten" if existed else "created"
            _log_upload(request, action, filename, f"{outcome} {target.name}", user.id)
    except HTTPException:
        _log_upload(request, "upload_failed", filename, "Upload rejected during validation or write", user.id)
        raise
    except (LockConflictError, LockTimeoutError) as exc:
        _log_upload(request, "upload_failed", filename, f"Upload lock failed: {exc}", user.id)
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        _log_upload(request, "upload_failed", filename, f"Upload failed: {exc}", user.id)
        raise HTTPException(status_code=500, detail="Upload failed") from exc

    return {
        "path": target.relative_to(root).as_posix(),
        "size": size,
        "mime_type": sniffed_mime,
        "checksum": checksum.hexdigest(),
        "operation": outcome,
    }
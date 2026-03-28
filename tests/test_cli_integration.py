from adapt.commands.admin import run_create_permissions
from adapt.commands.check import run_check
from adapt.commands.list_endpoints import run_list_endpoints


def _seed_workspace(root):
    # Include a media extension to exercise MediaPlugin cache reads during discovery.
    (root / "data.csv").write_text("name,age\nAlice,30\nBob,25\n")
    (root / "clip.mp3").write_bytes(b"not-a-real-mp3")


def test_run_check_discovers_media_without_cache_table_error(tmp_path, capsys):
    _seed_workspace(tmp_path)

    run_check(tmp_path)

    output = capsys.readouterr().out
    assert "Document root:" in output
    assert "Discovered" in output


def test_run_list_endpoints_discovers_media_without_cache_table_error(tmp_path, capsys):
    _seed_workspace(tmp_path)

    run_list_endpoints(tmp_path)

    output = capsys.readouterr().out
    assert "/api/data" in output


def test_run_create_permissions_all_with_media_does_not_crash(tmp_path, capsys):
    _seed_workspace(tmp_path)

    run_create_permissions(
        root=tmp_path,
        resources=["__all__"],
        all_group_name="all-rw",
        read_group_name="all-ro",
    )

    output = capsys.readouterr().out
    assert "Using all" in output
    assert "Permissions and groups created successfully." in output

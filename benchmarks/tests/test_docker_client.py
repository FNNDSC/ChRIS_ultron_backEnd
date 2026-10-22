"""
Tests for benchmarks.docker_client — the image record of a workload plugin.
"""

from types import SimpleNamespace

from benchmarks.docker_client import DockerClient, image_record


def _client(docker):
    client = DockerClient.__new__(DockerClient)          # no Docker connection needed
    client._docker = docker
    return client


def _missing(ref):
    raise LookupError(ref)                               # what images.get does, roughly


def test_image_record_sorts_the_digests_and_keeps_the_architecture():
    image = SimpleNamespace(id="sha256:1c45", attrs={
        "RepoDigests": ["localhost/x@sha256:bb", "fnndsc/x@sha256:aa"],
        "Architecture": "amd64"})

    assert image_record(image) == {  # nosec B101 - pytest assertion
        "image_id": "sha256:1c45",
        "repo_digests": ["fnndsc/x@sha256:aa", "localhost/x@sha256:bb"],
        "architecture": "amd64"}


def test_image_record_of_an_image_without_digests():
    # a local build on overlay2 (on containerd it has a digest of its own)
    record = image_record(SimpleNamespace(id="sha256:e2f4", attrs={}))

    assert record["repo_digests"] == []  # nosec B101 - pytest assertion
    assert record["architecture"] is None  # nosec B101 - pytest assertion


def test_image_info_is_none_without_docker_a_reference_or_the_image():
    client = _client(SimpleNamespace(images=SimpleNamespace(get=_missing)))

    assert _client(None).image_info("fnndsc/x") is None  # nosec B101 - pytest assertion
    assert client.image_info(None) is None  # nosec B101 - pytest assertion
    assert client.image_info("fnndsc/x") is None  # nosec B101 - pytest assertion


def test_image_info_records_the_image_a_reference_resolves_to():
    image = SimpleNamespace(id="sha256:3329", attrs={"RepoDigests": ["fnndsc/x@sha256:35"]})
    client = _client(SimpleNamespace(images=SimpleNamespace(get={"fnndsc/x@sha256:35": image}.get)))

    assert client.image_info("fnndsc/x@sha256:35")["image_id"] == "sha256:3329"  # nosec B101 - pytest assertion

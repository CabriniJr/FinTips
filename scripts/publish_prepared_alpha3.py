"""Publish the already signed alpha via the runner's repository token.

The manifest references public release files stored as Git blobs. No signing
key, personal data, or new build is transferred. Restrict this workflow to its
dedicated publication branch; verify every byte before making the draft public.
"""

import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import urllib.error
import urllib.request


REPO = "CabriniJr/FinTips"
TAG = "android-v0.6.0-alpha.3"
SOURCE = "2aca938cb4316c0e7caa76de4e6c3254973a45ea"
RELEASE_ID = 413204503
EXPECTED_NAMES = {
    "FinTips-Android-v0.6.0-alpha.3.apk",
    "FinTips-Android-v0.6.0-alpha.3-source.zip",
    "SHA256SUMS.txt", "build-info.json", "hoje.png", "leitura.png",
}


def api(path):
    request = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/{path}",
        headers={"Authorization": f"Bearer {os.environ['GH_TOKEN']}",
                 "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def gh(*args):
    subprocess.run(["gh", *args, "--repo", REPO], check=True)


def assert_asset(path, asset):
    data = path.read_bytes()
    assert len(data) == asset["size"], f"Size mismatch: {path.name}"
    assert hashlib.sha256(data).hexdigest() == asset["sha256"], path.name


def tag_commit():
    try:
        reference = api(f"git/ref/tags/{TAG}")["object"]
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise
    while reference["type"] == "tag":
        reference = api(f"git/tags/{reference['sha']}")["object"]
    assert reference["type"] == "commit"
    return reference["sha"]


def main():
    manifest = json.loads(Path(".github/release-transfer.json").read_text())
    assert manifest["repository"] == REPO and manifest["tag"] == TAG
    assert manifest["source_commit"] == SOURCE
    assert manifest["release_id"] == RELEASE_ID
    assets = manifest["assets"]
    assert {asset["name"] for asset in assets} == EXPECTED_NAMES
    assert len(assets) == len(EXPECTED_NAMES)
    release = api(f"releases/{RELEASE_ID}")
    assert release["tag_name"] == TAG
    assert release["target_commitish"] == SOURCE
    assert release["prerelease"]
    existing_tag = tag_commit()
    assert existing_tag in (None, SOURCE), "Tag points to another source"
    assert api(f"commits/{SOURCE}")["sha"] == SOURCE

    prepared = Path(".release-assets")
    prepared.mkdir()
    for asset in assets:
        assert 0 < asset["size"] < 20_000_000
        blob = api(f"git/blobs/{asset['blob_sha']}")
        assert blob["sha"] == asset["blob_sha"] and blob["encoding"] == "base64"
        assert blob["size"] == asset["size"]
        data = base64.b64decode(blob["content"])
        path = prepared / asset["name"]
        path.write_bytes(data)
        assert_asset(path, asset)
        print(f"Verified prepared asset: {path.name}", flush=True)

    info = json.loads((prepared / "build-info.json").read_text())
    assert info["source_commit"] == SOURCE and info["tag"] == TAG
    assert info["version_code"] == 3 and info["application_id"] == "com.fintips.app.ui"
    assert info["apk_sha256"] == hashlib.sha256(
        (prepared / "FinTips-Android-v0.6.0-alpha.3.apk").read_bytes()
    ).hexdigest()

    existing = {asset["name"] for asset in release["assets"]}
    assert existing <= EXPECTED_NAMES, "Unexpected assets in release"
    pending = [str(prepared / asset["name"]) for asset in assets
               if asset["name"] not in existing]
    if pending:
        assert release["draft"], "Refusing to add files to a published release"
        gh("release", "upload", TAG, *pending)

    uploaded = api(f"releases/{RELEASE_ID}")["assets"]
    assert {asset["name"] for asset in uploaded} == EXPECTED_NAMES
    assert all(asset["state"] == "uploaded" for asset in uploaded)
    verified = Path(".release-downloads")
    gh("release", "download", TAG, "--dir", str(verified))
    for asset in assets:
        assert_asset(verified / asset["name"], asset)
    subprocess.run(["sha256sum", "-c", "SHA256SUMS.txt"], cwd=verified, check=True)
    print("All release downloads match the prepared files.", flush=True)

    gh("release", "edit", TAG, "--draft=false", "--prerelease")
    published = api(f"releases/{RELEASE_ID}")
    assert not published["draft"] and published["prerelease"]
    assert tag_commit() == SOURCE
    print(f"Published and verified: {published['html_url']}", flush=True)
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as summary:
        summary.write(f"Published [{TAG}]({published['html_url']}).\n\n"
                      "All six assets were downloaded and verified before publication.\n")


if __name__ == "__main__":
    main()

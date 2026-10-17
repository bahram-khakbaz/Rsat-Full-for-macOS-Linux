# Integrated File Transfer (1.3.0)

The File Transfer tab is an SFTP client inside RSAT. It uses the existing saved
SSH inventory, encrypted password storage and approved host fingerprints. It
does not invoke a shell, install FileZilla, or expose the Mac filesystem through
an HTTP path-reading endpoint. The local pane shows files/folders explicitly
chosen by the operator, not unrestricted backend access to the Mac.

## Connect

1. In **Linux Servers**, add the host, SSH port, username and password. Switches
   can also be selected if they actually offer an SFTP subsystem.
2. Inspect the host key and compare its SHA256 fingerprint with a trusted source
   before approving it. Changed keys block password transmission.
3. Click **FILES / SFTP**, or choose the host in **File Transfer** and click
   **CONNECT SFTP**. OpenSSH normally provides SFTP with its SSH server; other
   servers may disable it even when their interactive terminal works.

Panel `admin` and `network` roles have `sftp.read`/`sftp.write`. Inventory is
per-operator, and Linux/switch IDs occupy separate namespaces. All filesystem
operations are additionally subject to the remote SSH user's permissions. An
SSH login failure does not invalidate the separate RSAT panel session.

## Local and remote workflows

- Choose several files or a folder, navigate within that local selection, select
  items and upload. Selecting a folder for upload preserves its subfolders;
  required remote parent directories are created. Empty local directories have
  no browser File entry and are not automatically uploaded; use **NEW FOLDER**.
- Drop individual files into the local pane to stage them, or onto a connected
  remote pane to queue upload. Use **CHOOSE FOLDER** for nested directories.
- Browse the remote path bar or click directory names. Listings show size,
  modification time and Unix permissions, with a 10,000-entry display limit.
- Download selected files directly. Selected folders become ZIP downloads;
  symlinks, devices and other special files are skipped and counted. ZIPs are
  prepared before progress bytes appear. This is not a consistent filesystem
  snapshot if another application changes the folder concurrently.
- Rename never overwrites another destination. Deletion removes one file/link
  or an empty directory, with an explicit confirmation; it never recursively
  deletes a directory tree. The remote server has no RSAT trash/recycle bin.
- **EDIT TEXT** opens UTF-8 regular files up to 512 KiB. Saving uses the same
  upload queue. Changed size or modification timestamp blocks saving until
  reloaded. This is not a distributed lock and cannot detect every same-size,
  same-timestamp concurrent edit. Binary files should be downloaded instead.
- **PERMISSIONS** accepts Unix octal modes. Whether a change is allowed depends
  on the SSH account and filesystem, not the panel administrator role alone.

## Transfer integrity and limits

Transfers are sequential. Upload progress first measures browser-to-backend
bytes; **COMMITTING** continues until the remote write/verification finishes.
Uploads use an exclusive random `.rsat-upload-*.part` file, set to `0600` before
content is written. The backend verifies remote size before committing the
destination. The returned SHA256 is the source-byte digest, not a separate
server-side full-file checksum. SSH provides transport integrity.

Existing files require explicit overwrite. Atomic replacement requires the
server's POSIX rename extension. If unsupported, upload under a new name;
RSAT never deletes the old file as a fallback. Ordinary existing permissions
are retained; setuid/setgid bits are not copied to new contents. Normal errors
and cancellations remove the temporary file where possible. A server outage or
backend crash can leave a `.part` file; inspect it before manual cleanup.

Cancellation may race with the last commit. Refresh the remote directory before
retrying. There is no automatic replay, persistent queue or resume after the
page/app closes. Queue **DONE** on download means the data was received and
offered for saving; check the browser/native save location. Native downloads
use a temporary local file and replace a chosen existing destination only after
the download finishes.

Current limits:

| Operation | Limit |
| --- | --- |
| One uploaded/downloaded file | 512 MiB |
| UTF-8 editor | 512 KiB |
| Folder ZIP | 512 MiB uncompressed data, 10,000 entries, depth 32 |
| ZIP preparation | 180 seconds, plus an in-flight read timeout |
| Remote channel inactivity | 30 seconds |

Downloads are buffered into a browser Blob before saving, which uses local
memory. Larger files, FTP/FTPS, private-key authentication and resumable transfers
are not implemented. Native macOS file pickers/save dialogs are included in the
updated RSAT.app; rebuild/reinstall older launchers after updating source.

Uploads and mutations are audited without file content or passwords. File
download audit events are marked `requested`; they do not prove the user saved
the file. A completed archive preparation likewise does not prove local saving.

## Validation

The backend suite includes a temporary real Paramiko SSH/SFTP server, isolated
SQLite inventory and synthetic accounts. Tests exercise binary upload/download,
host-key rejection before authentication, account/role isolation, explicit
overwrite, size/mtime conflicts, private permissions, upload-limit cleanup,
cancelled-upload preservation, management operations and ZIP hierarchy/link
handling. No production server or domain account is needed for these tests.

Run `PYTHONPATH=backend pytest -q backend/tests` with backend dependencies
installed. Frontend helper tests run with
`node --test frontend/src/api-errors.test.mjs frontend/src/file-transfer.test.mjs`.
Build with `docker compose build backend web`; the frontend context excludes
host `node_modules` so native dependency binaries do not cross platforms.

Manual acceptance used a separate disposable backend/database and SFTP server:
the actual interface uploaded/downloaded a synthetic file and saved/re-read an
edit. The native macOS app selected that file, blocked an unapproved overwrite,
and saved a download whose bytes matched the fixture. Production credentials,
inventory and corporate servers were not used for those acceptance tests.

Local validation on 2026-10-17: **70 backend tests, 4 frontend helper tests and
4 launcher tests passed**. Backend/Windows Python syntax checks, the production
frontend build, native macOS compilation/signature verification and Nginx syntax
checks also passed. Native acceptance found and fixed missing Edit shortcuts;
the installed app's healthy-service fast startup path was observed afterward.
These are local results, not a claim that every server or remote CI run passed.

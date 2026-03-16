# Updatr - Centralized Patch Management

Updatr is a web-based patch management system for Windows and Linux hosts. It provides a single UI to manage host inventory, store credentials securely, trigger patching via Ansible, and monitor compliance status.

## Features

- **Host Management** - Add, tag, and organize Windows/Linux hosts
- **Credential Vault** - AES-256-GCM encrypted storage for SSH keys, passwords, and WinRM credentials
- **Ansible Patching** - Agentless patching via SSH (Linux) and WinRM (Windows)
- **Job Tracking** - Trigger patch jobs, monitor progress, view history
- **Scheduling** - Cron-based recurring patch schedules with pause/resume
- **Compliance Dashboard** - At-a-glance view of patch compliance across all hosts
- **Nightly Scans** - Automated compliance scans via Celery Beat

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│   Next.js   │────▶│   FastAPI    │────▶│  PostgreSQL  │
│  Frontend   │     │   Backend    │     │              │
│  :3000      │     │  :8000       │     │  :5432       │
└─────────────┘     └──────┬───────┘     └──────────────┘
                           │
                    ┌──────┴───────┐     ┌──────────────┐
                    │Celery Worker │────▶│    Redis      │
                    │+ Beat        │     │   :6379       │
                    └──────┬───────┘     └──────────────┘
                           │
                    ┌──────┴───────┐
                    │   Ansible    │───▶ SSH / WinRM
                    │  (via runner)│     to hosts
                    └──────────────┘
```

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Git

### Setup

```bash
git clone <repo-url> updatr && cd updatr

# Configure environment
cp .env.example .env
# Edit .env: set POSTGRES_PASSWORD, SECRET_KEY, ENCRYPTION_KEY

# Start all services
docker compose up -d

# Run database migrations
docker compose exec backend alembic upgrade head
```

Navigate to `http://localhost:3000` and create your admin account.

## Target Hosts Setup

### Linux (SSH)

Ensure SSH is enabled and the user has sudo privileges:

```bash
sudo systemctl enable --now sshd
```

### Windows (WinRM)

Enable WinRM with a self-signed certificate:

```powershell
# Run as Administrator
Enable-PSRemoting -Force
winrm set winrm/config/service '@{AllowUnencrypted="false"}'
winrm set winrm/config/service/auth '@{Basic="true"}'

# Create self-signed cert for HTTPS listener
$cert = New-SelfSignedCertificate -DnsName $env:COMPUTERNAME -CertStoreLocation Cert:\LocalMachine\My
New-Item -Path WSMan:\Localhost\Listener -Transport HTTPS -Address * -CertificateThumbprint $cert.Thumbprint -Force

# Open firewall port
New-NetFirewallRule -Name "WinRM HTTPS" -DisplayName "WinRM HTTPS" -Protocol TCP -LocalPort 5986 -Action Allow
```

## Development

### Running Services Separately

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev

# Celery Worker
cd backend
celery -A app.tasks.celery_app worker --loglevel=info

# Celery Beat
cd backend
celery -A app.tasks.celery_app beat --loglevel=info
```

### Running Tests

```bash
cd backend
python -m pytest tests/ -v
```

### Database Migrations

```bash
cd backend
alembic revision --autogenerate -m "description"
alembic upgrade head
```

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `POSTGRES_DB` | Database name | `updatr` |
| `POSTGRES_USER` | Database user | `updatr` |
| `POSTGRES_PASSWORD` | Database password | `updatr_dev` |
| `SECRET_KEY` | JWT signing key | `dev-secret-...` |
| `ENCRYPTION_KEY` | AES key for credentials | `dev-encryption-...` |
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` |

## Security Notes

- **ENCRYPTION_KEY**: Back this up. Lost key = lost credentials. Use a 64-char hex string in production.
- **SECRET_KEY**: Use a random 64-char string in production.
- Credentials are encrypted at rest with AES-256-GCM.
- JWT tokens expire after 1 hour (access) / 7 days (refresh).
- WinRM cert validation is set to `ignore` by default for self-signed certs.

## License

MIT

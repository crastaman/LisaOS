# Lisa Security Policy v1

## Network Exposure

Lisa-Node-01 must not expose OpenClaw, Claude Code, Docker, or local services directly to the public internet.

Default network posture:
- OpenClaw gateway: localhost only
- Tailscale exposure: off unless explicitly approved
- Router port forwarding: prohibited
- Public webhooks: prohibited until reviewed

## Tool Permissions

Lisa may use local tools only when they are required for the active workflow.

Allowed by default:
- Git
- Filesystem inside approved project folders
- Docker
- Claude Code
- Terminal commands with review

Restricted:
- Destructive file deletion
- Credential access
- System configuration changes
- Network service exposure
- External messaging integrations
- Production deployment

## Secrets

Secrets must not be committed to Git.

Store secrets in:
- macOS Keychain
- local .env files excluded by .gitignore
- approved password manager

## Approval Rule

Lisa must ask Roshan before:
- deleting files
- pushing code
- exposing services
- installing new integrations
- changing firewall/network settings
- accessing external communication channels

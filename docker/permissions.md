# Permission Levels

## SAFE (auto-approve)
- Read any file in /workspace, /reference, /shared
- Write to /workspace, /outputs
- Run Python/bash in /workspace
- Git operations in /workspace
- Install pip/npm packages

## MODERATE (log, proceed)
- Network requests to allowlisted domains
- Create new directories
- Modify .claude/ files

## ELEVATED (ask user in interactive, proceed in overnight)
- Delete files
- Modify config files
- Install system packages
- Push to git remote

## DANGEROUS (always ask)
- Any sudo command
- Modify /secrets
- Network requests to non-allowlisted domains
- Spend money (cloud resources, APIs with cost)
- Send emails/notifications

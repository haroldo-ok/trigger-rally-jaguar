#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Fetch the pinned, unmodified ORIGINAL inputs for asset regeneration.

Content rights are separate from the GPL source-code license. Fetching does
not grant redistribution/modification rights: read licenses/TriggerRally-terms.md.
"""
from pathlib import Path
import subprocess
R=Path(__file__).resolve().parents[1]
PIN='079ac53216b74598b652ce3bf11478beb5c6832b'
p=R/'.cache/TriggerRally'
if not p.exists():
    p.parent.mkdir(exist_ok=True)
    subprocess.run(['git','clone','--no-checkout','https://github.com/CodeArtemis/TriggerRally.git',str(p)],check=True)
    subprocess.run(['git','-C',str(p),'checkout','--detach',PIN],check=True)
head=subprocess.check_output(['git','-C',str(p),'rev-parse','HEAD'],text=True).strip()
if head!=PIN:raise SystemExit('Refusing to change an existing checkout at a different revision: '+head)
print('Original asset inputs: '+str(p/'server/public'))
print('Rights warning: content is NOT GPL. Read licenses/TriggerRally-terms.md.')
print('Regenerate with: make regenerate-assets TR_PUBLIC='+str(p/'server/public'))

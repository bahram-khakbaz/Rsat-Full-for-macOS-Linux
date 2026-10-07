#!/usr/bin/env python3
"""Build a local RSAT.app without embedding credentials or machine-specific source paths."""
import argparse
import json
import platform
import plistlib
import shutil
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, default=Path('.macos-build/RSAT.app'))
args = parser.parse_args()
if platform.system() != 'Darwin':
    parser.error('Building the native app requires macOS and Xcode Command Line Tools.')
repo = Path(__file__).resolve().parents[1]
output = args.output.expanduser().resolve()
if output.exists():
    parser.error(f'{output} already exists. Choose a new output path or remove the old generated app.')
arch = {'arm64': 'arm64', 'x86_64': 'x86_64'}.get(platform.machine())
if not arch:
    parser.error('Unsupported Mac architecture')
contents = output/'Contents'
(contents/'MacOS').mkdir(parents=True)
(contents/'Resources').mkdir()
cache = repo/'.macos-build/module-cache'
cache.mkdir(parents=True, exist_ok=True)
subprocess.run(['xcrun', 'swiftc', '-target', f'{arch}-apple-macosx13.0',
                '-module-cache-path', str(cache), str(repo/'macos/RSATLauncher.swift'),
                '-o', str(contents/'MacOS/RSATLauncher')], check=True)
logdir = Path.home()/'Library/Logs/RSAT'
(contents/'Resources/launcher.json').write_text(json.dumps({
    'repository': str(repo), 'log': str(logdir/'RSAT-startup.log')})+'\n')
shutil.copyfile(repo/'macos/start-rsat.sh', contents/'Resources/start-rsat.sh')
with (contents/'Info.plist').open('wb') as handle:
    plistlib.dump({'CFBundleExecutable':'RSATLauncher', 'CFBundleIdentifier':'com.bahram.rsat.mac',
                  'CFBundleName':'RSAT', 'CFBundlePackageType':'APPL', 'CFBundleVersion':'1',
                  'CFBundleShortVersionString':'1.0', 'LSMinimumSystemVersion':'13.0',
                  'NSHighResolutionCapable':True,
                  'NSAppTransportSecurity':{'NSAllowsLocalNetworking':True}}, handle)
subprocess.run(['codesign', '--force', '--sign', '-', str(output)], check=True)
subprocess.run(['codesign', '--verify', '--strict', str(output)], check=True)
print(f'Built {output}. Move it to Applications and choose Keep in Dock.')

# -*- coding: utf-8 -*-
#
# Remote channel stream converter - online update from GitHub - https://www.youtube.com/@SetTvBox4U
# Copyright (C) 2026 Mardo22 (SetTvBox4U)
#
# This program is free software: you can redistribute it and/or modify it under the terms of
# the GNU General Public License as published by the Free Software Foundation, version 3.
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details: https://www.gnu.org/licenses/gpl-3.0.html
#
# Same file for DreamOS (Python 2.7, .deb) and open-source images (Python 3, .ipk).
# No enigma calls - checkLatest() and downloadAndInstall() run in a thread (twisted deferToThread).
# Only published releases count: GitHub "releases/latest" never returns drafts or pre-releases.
import os
import re
import json
import hashlib
import subprocess

try:
	from urllib2 import Request, urlopen	# Python 2 (DreamOS)
except ImportError:
	from urllib.request import Request, urlopen	# Python 3

API = "https://api.github.com/repos/%s/releases/latest"
HEADERS = {"User-Agent": "Enigma2 RCSC updater", "Accept": "application/vnd.github+json"}
TMP_DIR = "/tmp/rcsc-update/"


def native(x):
	"""Python 2: unicode from json -> UTF-8 str (enigma texts); Python 3: str"""
	if not isinstance(x, str) and not isinstance(x, bytes):
		try:
			return x.encode("utf-8")
		except AttributeError:
			return x
	return x


def versionTuple(text):
	"""'v2.0.4' / '2.0.4' -> (2, 0, 4)"""
	nums = re.findall(r"\d+", text or "")
	return tuple([int(x) for x in nums[:4]])


def isNewer(remote, local):
	r, l = versionTuple(remote), versionTuple(local)
	return bool(r) and r > l


def notesText(body, maxlen=700):
	"""first part of the release notes (English, up to the first '---'), without Markdown signs"""
	text = (body or "").replace("\r", "")
	text = text.split("\n---")[0]
	text = text.split("```")[0]	# no install commands in the message box
	out = []
	for line in text.split("\n"):
		line = re.sub(r"^#+\s*", "", line)
		line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)
		line = line.replace("**", "").replace("`", "").strip()
		low = line.lower()
		if low.rstrip(":") in ("install", "installation", "update", "how to install", "how to update") or low.startswith(("install:", "update:")):
			break	# the install part is not needed in the message box
		if line.lower().startswith("copy the"):
			continue
		if line or (out and out[-1]):
			out.append(line)
	text = "\n".join(out).strip()
	if len(text) > maxlen:
		text = text[:maxlen].rsplit(" ", 1)[0] + " ..."
	return text


def checkLatest(repo, local_version, suffix):
	"""-> dict(version, notes, url, name, size, digest) when GitHub has a newer published release, else None"""
	data = urlopen(Request(API % repo, headers=HEADERS), timeout=15).read()
	if not isinstance(data, str):
		data = data.decode("utf-8", "replace")
	rel = json.loads(data)
	if rel.get("draft") or rel.get("prerelease"):
		return None
	tag = rel.get("tag_name") or ""
	if not isNewer(tag, local_version):
		return None
	for a in rel.get("assets") or []:
		if (a.get("name") or "").endswith(suffix):
			return {"version": native(tag.lstrip("vV")), "notes": native(notesText(rel.get("body"))), "url": native(a.get("browser_download_url")),
				"name": native(a.get("name")), "size": a.get("size") or 0, "digest": native(a.get("digest") or "")}
	return None


def downloadAndInstall(info, command):
	"""downloads the package, checks size and sha256, installs it with command (e.g. ['dpkg', '-i'])
	-> (ok, text of the installer)"""
	name = os.path.basename(info["name"])
	if not re.match(r"^[A-Za-z0-9._+-]+$", name):
		return False, "bad file name"
	if not os.path.isdir(TMP_DIR):
		os.makedirs(TMP_DIR)
	path = TMP_DIR + name
	req = Request(info["url"], headers={"User-Agent": HEADERS["User-Agent"], "Accept": "application/octet-stream"})
	data = urlopen(req, timeout=60).read()
	if info.get("size") and len(data) != info["size"]:
		return False, "download incomplete (%d of %d bytes)" % (len(data), info["size"])
	digest = info.get("digest") or ""
	if digest.startswith("sha256:") and hashlib.sha256(data).hexdigest() != digest[7:]:
		return False, "download damaged (sha256 does not match)"
	f = open(path, "wb")
	try:
		f.write(data)
	finally:
		f.close()
	try:
		p = subprocess.Popen(command + [path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
		out = p.communicate()[0]
		if not isinstance(out, str):
			out = out.decode("utf-8", "replace")
		ok = p.returncode == 0
	finally:
		try:
			os.remove(path)
		except OSError:
			pass
	return ok, out.strip()[-600:]

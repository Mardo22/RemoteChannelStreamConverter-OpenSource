# -*- coding: utf-8 -*-
#
# Remote channel stream converter for open-source Enigma2 images (OpenATV) - https://www.youtube.com/@SetTvBox4U
# Copyright (C) 2026 Mardo22 (SetTvBox4U) - GPL-3.0, see LICENSE
#
# 2.0: EPG for the stream channels of RCSC without changing their references or numbers.
#
# (C) EPG the Dreambox already has: EPGImport imports rytec / other XMLTV sources for the normal satellite references
#     (namespace shortened, e.g. ...:820000:...). The stream channels of RCSC keep the full reference of the server
#     (e.g. ...:823082:...), so this EPG did not fit them. RCSC writes its own block into
#     /etc/epgimport/custom.channels.xml (EPGImport adds this file to every source): XMLTV id -> RCSC reference.
#     The next EPGImport run (automatic or by hand) stores the EPG for the RCSC channels too. Other lines of the
#     file stay untouched; the block is renewed on every conversion and removed with the last RCSC bouquet.
#
# (A) EPG of the server (supplement): for RCSC channels that got no id in (C), the EPG of the server is taken from
#     OpenWebif (/api/epgmulti per bouquet) and written as a local XMLTV source "RCSC - EPG from server"
#     (/etc/epgimport/rcsc.sources.xml + rcsc.channels.xml + data file). When the server has no EPG (e.g. other
#     image booted on the server) nothing is changed - the old data stay.
#
# Python 3 (OpenATV 8.0.1, Python 3.14), no enigma calls (runs in a thread). Port of the DreamOS version 2.0.2.
import os
import re
import time
import json
import gzip
import pickle
import subprocess
from urllib.parse import quote
from xml.sax.saxutils import escape

EPGIMPORT_DIR = "/etc/epgimport/"
CUSTOM_CHANNELS = EPGIMPORT_DIR + "custom.channels.xml"
EPGIMPORT_CONF = ["/etc/epgimport/epgimport.conf", "/etc/enigma2/epgimport.conf"]
SERVER_SOURCES = EPGIMPORT_DIR + "rcsc.sources.xml"
SERVER_CHANNELS = EPGIMPORT_DIR + "rcsc.channels.xml"
SERVER_SOURCE_NAME = "RCSC - EPG from server"
CACHE_DIR = "/tmp/rcsc-epg/"
CACHE_MAX_AGE = 12 * 3600
BLOCK_BEGIN = "<!-- RCSC begin (Remote channel stream converter - do not edit, renewed automatically) -->"
BLOCK_END = "<!-- RCSC end -->"


def readFile(path):
	f = open(path, encoding="utf-8", errors="surrogateescape")
	try:
		return f.read()
	finally:
		f.close()


def writeAtomic(path, data):
	tmp = path + ".rcsc_tmp"
	if isinstance(data, bytes):
		f = open(tmp, "wb")
	else:
		f = open(tmp, "w", encoding="utf-8", errors="surrogateescape")
	try:
		f.write(data)
	finally:
		f.close()
	os.rename(tmp, path)


def epgimportInstalled():
	return os.path.isdir("/usr/lib/enigma2/python/Plugins/Extensions/EPGImport") and os.path.isdir(EPGIMPORT_DIR)


def key4(fields):
	"""(sid, tsid, onid, namespace & 0xFFFF0000) of a reference - the identity EPG sources use"""
	try:
		return (int(fields[3], 16), int(fields[4], 16), int(fields[5], 16), int(fields[6], 16) & 0xFFFF0000)
	except (ValueError, IndexError):
		return None


# ---------------------------------------------------------------- (C) map XMLTV ids of the enabled EPGImport sources
def enabledSources():
	for path in EPGIMPORT_CONF:
		try:
			f = open(path, "rb")
			try:
				data = pickle.load(f)
			finally:
				f.close()
			if isinstance(data, dict):
				return set(data.get("sources", []))
		except Exception:
			pass
	return set()


def channelFilesOfEnabledSources():
	"""names / paths / urls of the channels files used by the enabled sources, with the urls of named channel files"""
	enabled = enabledSources()
	used = set()
	named = {}
	for fn in os.listdir(EPGIMPORT_DIR):
		if not fn.endswith(".sources.xml"):
			continue
		try:
			data = readFile(EPGIMPORT_DIR + fn)
		except Exception:
			continue
		for m in re.finditer(r'<channel\s+name="([^"]+)"\s*>(.*?)</channel>', data, re.S):
			named.setdefault(m.group(1), re.findall(r"<url>\s*([^<\s]+)\s*</url>", m.group(2)))
		for m in re.finditer(r'<source\b([^>]*)>(.*?)</source>', data, re.S):
			ch = re.search(r'channels="([^"]+)"', m.group(1))
			desc = re.search(r"<description>([^<]*)</description>", m.group(2))
			if ch and desc and desc.group(1).strip() in enabled and fn != os.path.basename(SERVER_SOURCES):
				used.add(ch.group(1))
	result = []
	for name in sorted(used):
		if name.startswith("/"):
			result.append((name, [name]))
		elif name.startswith("http"):
			result.append((name, [name]))
		elif name in named:
			result.append((name, named[name]))
	return result


def fetchChannelFile(name, urls, opener):
	"""local path of the (decompressed) channels file - downloads are cached for 12 hours"""
	if urls and urls[0].startswith("/"):
		path = urls[0]
		if not os.path.exists(path):
			return None
	else:
		if not os.path.isdir(CACHE_DIR):
			os.makedirs(CACHE_DIR)
		path = CACHE_DIR + re.sub(r"[^A-Za-z0-9._-]", "_", name)
		if not (os.path.exists(path) and time.time() - os.path.getmtime(path) < CACHE_MAX_AGE):
			for url in urls:
				try:
					data = opener(url)
					if data:
						writeAtomic(path, data)
						break
				except Exception as e:
					print("[RCSC] EPG channels download failed:", url, e)
			if not os.path.exists(path):
				return None
	low = path.lower()
	if low.endswith(".xz") or low.endswith(".lzma"):
		out = CACHE_DIR + os.path.basename(path) + ".xml"
		if not (os.path.exists(out) and os.path.getmtime(out) >= os.path.getmtime(path)):
			f = open(out + ".rcsc_tmp", "wb")
			try:
				rc = subprocess.call(["xz", "-dc", path], stdout=f)
			finally:
				f.close()
			if rc != 0:
				return None
			os.rename(out + ".rcsc_tmp", out)
		return out
	if low.endswith(".gz"):
		out = CACHE_DIR + os.path.basename(path) + ".xml"
		if not (os.path.exists(out) and os.path.getmtime(out) >= os.path.getmtime(path)):
			g = gzip.open(path, "rb")
			try:
				writeAtomic(out, g.read())
			finally:
				g.close()
		return out
	return path


def readChannelIds(path, wanted):
	"""XMLTV ids of the services in `wanted` (set of key4) from one channels file -> {key4: set(ids)}"""
	result = {}
	try:
		data = readFile(path)
	except Exception:
		return result
	for m in re.finditer(r'<channel\s+id="([^"]+)"\s*>\s*([^<]+?)\s*</channel>', data):
		k = key4(m.group(2).split(":"))
		if k is not None and k in wanted:
			result.setdefault(k, set()).add(m.group(1))
	return result


def writeCustomBlock(lines):
	"""own block in /etc/epgimport/custom.channels.xml - everything outside the block is kept"""
	block = ""
	if lines:
		block = BLOCK_BEGIN + "\n" + "\n".join(lines) + "\n" + BLOCK_END + "\n"
	old = ""
	if os.path.exists(CUSTOM_CHANNELS):
		old = readFile(CUSTOM_CHANNELS)
	if old:
		new = re.sub(re.escape(BLOCK_BEGIN) + r".*?" + re.escape(BLOCK_END) + r"\n?", "", old, flags=re.S)
		if block:
			if "</channels>" in new:
				i = new.rfind("</channels>")
				new = new[:i] + block + new[i:]
			else:
				new = new + block
		# the file was created by RCSC alone and is empty now -> remove it
		if not block and re.sub(r"\s+", "", re.sub(r"<\?xml[^>]*\?>", "", new)) in ("<channels></channels>", ""):
			os.remove(CUSTOM_CHANNELS)
			return
	elif block:
		new = '<?xml version="1.0" encoding="utf-8"?>\n<channels>\n' + block + "</channels>\n"
	else:
		return
	if new != old:
		writeAtomic(CUSTOM_CHANNELS, new)


def mapEpg(services, opener):
	"""services: {reference (10 fields): fields} of the RCSC stream channels.
	Returns {"channels", "mapped", "ids", "files", "unmapped": set(reference)}"""
	result = {"channels": len(services), "mapped": 0, "ids": 0, "files": 0, "unmapped": set(services.keys())}
	if not epgimportInstalled():
		result["error"] = "EPGImport"
		return result
	wanted = {}
	for ref, fields in services.items():
		k = key4(fields)
		if k is not None:
			wanted.setdefault(k, []).append(ref)
	ids = {}
	if wanted:
		for name, urls in channelFilesOfEnabledSources():
			path = fetchChannelFile(name, urls, opener)
			if not path:
				continue
			result["files"] += 1
			for k, s in readChannelIds(path, set(wanted.keys())).items():
				ids.setdefault(k, set()).update(s)
	lines = []
	for k in sorted(ids.keys()):
		for ref in sorted(wanted[k]):
			result["unmapped"].discard(ref)
			result["mapped"] += 1
			for i in sorted(ids[k]):
				lines.append('<channel id="%s">%s:</channel>' % (escape(i, {'"': "&quot;"}), ref))
	result["ids"] = len(lines)
	writeCustomBlock(lines)
	return result


# ---------------------------------------------------------------- (A) EPG of the server as a local XMLTV source
def xmltvTime(ts):
	return time.strftime("%Y%m%d%H%M%S +0000", time.gmtime(ts))


def serverEpg(web, bouquets, refs, datafile):
	"""bouquets: list of bouquet references of the server; refs: {server ref key (10 fields upper): our reference}
	for the channels without EPG mapping. Writes the XMLTV data file + rcsc.channels.xml + rcsc.sources.xml.
	Returns {"channels": n, "events": n} - with no events nothing is written (old data stay)."""
	result = {"channels": 0, "events": 0}
	if not refs or not epgimportInstalled():
		return result
	programmes = []
	seen = set()
	for bref in bouquets:
		try:
			data = json.loads(web._open("/api/epgmulti?bRef=%s&endTime=10080" % quote(bref), timeout=60))
		except Exception as e:
			print("[RCSC] EPG of the server failed:", bref, e)
			continue
		for e in data.get("events", []):
			sref = str(e.get("sref") or "")
			k = ":".join(sref.split(":")[:10]).upper()
			if k not in refs:
				continue
			try:
				begin = int(e.get("begin_timestamp"))
				dur = int(e.get("duration_sec"))
			except (TypeError, ValueError):
				continue
			if (k, begin) in seen:
				continue
			seen.add((k, begin))
			programmes.append((k, begin, dur, e.get("title") or "", e.get("shortdesc") or "", e.get("longdesc") or ""))
	if not programmes:
		return result
	chans = sorted(set([p[0] for p in programmes]))
	cid = dict([(k, "rcsc." + k.replace(":", "_")) for k in chans])
	out = ['<?xml version="1.0" encoding="utf-8"?>', '<tv generator-info-name="RCSC">']
	for k in chans:
		out.append('<channel id="%s"><display-name>%s</display-name></channel>' % (cid[k], cid[k]))
	for k, begin, dur, title, short, long_ in programmes:
		desc = long_ or short
		out.append('<programme start="%s" stop="%s" channel="%s"><title>%s</title>%s%s</programme>' % (
			xmltvTime(begin), xmltvTime(begin + dur), cid[k], escape(u8(title)),
			short and "<sub-title>%s</sub-title>" % escape(u8(short)) or "",
			desc and "<desc>%s</desc>" % escape(u8(desc)) or ""))
	out.append("</tv>")
	g = gzip.open(datafile + ".rcsc_tmp", "wb")
	try:
		g.write(("\n".join(out) + "\n").encode("utf-8"))
	finally:
		g.close()
	os.rename(datafile + ".rcsc_tmp", datafile)
	writeAtomic(SERVER_CHANNELS, '<?xml version="1.0" encoding="utf-8"?>\n<channels>\n' + "\n".join(
		['<channel id="%s">%s:</channel>' % (cid[k], refs[k]) for k in chans]) + "\n</channels>\n")
	writeAtomic(SERVER_SOURCES, '<?xml version="1.0" encoding="utf-8"?>\n<sources>\n'
		'  <sourcecat sourcecatname="RCSC - Remote channel stream converter">\n'
		'    <source type="gen_xmltv" nocheck="1" channels="%s">\n'
		'      <description>%s</description>\n'
		'      <url>%s</url>\n'
		'    </source>\n'
		'  </sourcecat>\n</sources>\n' % (SERVER_CHANNELS, SERVER_SOURCE_NAME, datafile))
	result["channels"] = len(chans)
	result["events"] = len(programmes)
	return result


def removeServerEpg(datafile):
	for path in (SERVER_SOURCES, SERVER_CHANNELS, datafile):
		try:
			if os.path.exists(path):
				os.remove(path)
		except OSError:
			pass


def u8(x):
	if isinstance(x, bytes):
		return x.decode("utf-8", "replace")
	return str(x)

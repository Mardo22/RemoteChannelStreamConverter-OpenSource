# -*- coding: utf-8 -*-
#
# Remote channel stream converter for open-source Enigma2 images (OpenATV) - https://www.youtube.com/@SetTvBox4U
# Copyright (C) the original authors of the Enigma2 plugin "Remote channel stream converter"
#   (OpenPLi / E2OpenPlugins / OE-Alliance contributors)
# Modifications for DreamOS 4.5 / 5.0 (versions 1.1 - 2.0.2, since 21.10.2026) and open-source images (2.1.0, since 11.11.2026):
#   Copyright (C) 2026 Mardo22 (SetTvBox4U)
#
# This program is free software: you can redistribute it and/or modify it under the terms of
# the GNU General Public License as published by the Free Software Foundation, version 3.
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details: https://www.gnu.org/licenses/gpl-3.0.html
#
# Remote channel stream converter 2.1.0 for open-source Enigma2 images (OpenATV 8.0.1, Python 3)
# 2.1.0 (11.11.2026): port of the DreamOS version 2.0.2 to Python 3 for OpenATV 8.0.1 on the Dreambox Two -
#      bytes/str, urllib.request, print(); screens designed in Full HD and scaled to the GUI resolution (OpenATV on the
#      Dreambox runs MetrixHD in 1280x720), color keys at the bottom as big colored tiles, numbered MENU options (1-9), image name from
#      /etc/image-version, state of the OpenATV "Fallback remote receiver" in the server panel, EPGImport of OpenATV.
# 2.1.1 (22.11.2026): online update from GitHub - when the plugin is opened it asks GitHub for the latest
#      published release; if it is newer, OK downloads and installs it (opkg install) and offers a GUI restart.
#      Option "Check for updates when opening" and MENU "Check for updates now".
# 2.1.2 (27.11.2026): the EPG of the server is imported about 1 minute after Convert / Update all (timer in the
#      main thread, also when the window is closed) and never while enigma2 is still saving its EPG or EPGImport
#      is running (then 30 s later, max. 10 times) - before EPGImport started at once and could hang enigma2.
#      No import of only the server EPG when EPGImport is set to clear the whole EPG before each import.
# Earlier versions (DreamOS 4.5 and 5.0, one package, the system was detected at runtime):
# Based on the OpenPLi plugin "Remote channel stream converter" (GPL).
# 1.1: Full HD screen in the style of the DreamOS skin, menu in Service Searching (like "Tuners & Scanning"
#      on OpenPLi/OE-A), OpenWebif download without password or FTP with password, update/delete of converted
#      bouquets, bouquet with the same name is replaced (others stay), lamedb merge without duplicates,
#      optional backup, server status (standby / busy tuners), channel count and satellites per bouquet, en/sk/cs.
# 1.2 (22.10.2026): list via template - converted bouquets green, divider between channels and satellites,
#      yellow summary and key hint, About with "Updated by Mardo22 since 21.10.2026" and version + date.
# 1.3 (22.10.2026): IPTV channels of the server copied with their internet links (option), "converted" moved left,
#      About with the YouTube channel SetTvBox4U.
# 1.4 (22.10.2026): QR code of the YouTube channel SetTvBox4U in the bottom bar and in an own About screen.
# 1.5 (22.10.2026): one package for DreamOS 4.5 and 5.0 - system detected from the enigma2 package version (title, About).
# 1.6 (22.10.2026): StreamRelay - channels in the whitelist_streamrelay of the server (OE-A) are streamed on port 17999
#      (decrypted by the server), option in the settings. Public release under GPL-3.0.
# 1.7 (23.10.2026): bouquet counter fixed (same names counted once), no crash by late callbacks after closing.
# 1.8 (05.11.2026): picon links - after every conversion, "Update all" and delete the plugin creates symlinks in the
#      picon directory: <service of the stream>.png -> existing picon of the channel (server namespace, shortened
#      namespace ns & 0xFFFF0000, service types 1/19/16/1F/D), so that the channels of the server have logos.
# 1.9 (05.11.2026): missing picons are downloaded from the server (OpenWebif /api/getservices&picon=1, option),
#      optional entries in the plugin browser, the extensions menu (blue button) and the main menu.
# 2.0.2 (09.11.2026): short tip in the server panel (the long one was cut off at the bottom), message "Deleting ..."
#   while the bouquets, picon links and EPG mapping are removed (before, the window did not change for ~45 s).
# 2.0.1 (05.11.2026): EPG of the server only with Update all / MENU (Convert stays light), one settings window at the
#   first start, "1 bouquet" singular. Found in the test on DreamOS 5.0 (Slot 0).
# 2.0 (05.11.2026): EPG without changing references or channel numbers - (1) EPG the Dreambox already has: own block
#      in /etc/epgimport/custom.channels.xml maps the XMLTV ids of the enabled EPGImport sources to the RCSC channels
#      (EPGImport fills them at its next run, no dependence on the server); (2) EPG of the server (OpenWebif) only on
#      demand (MENU "Update EPG from server", option) for the channels without (1), imported at once by EPGImport
#      (only the RCSC source). See epgmap.py.
import os
import re
import time
import json
import base64
import tarfile
from collections import OrderedDict
from urllib.parse import quote
import urllib.request

from enigma import getDesktop, eDVBDB, eServiceReference, eListboxPythonMultiContent, gFont, \
	RT_HALIGN_LEFT, RT_HALIGN_RIGHT, RT_VALIGN_CENTER, BT_SCALE
from Components.ActionMap import ActionMap
from Components.ConfigList import ConfigListScreen
from Components.MenuList import MenuList
from Components.MultiContent import MultiContentEntryText, MultiContentEntryPixmapAlphaBlend
from Components.Sources.StaticText import StaticText
from Components.config import config, configfile, ConfigSubsection, ConfigText, ConfigPassword, ConfigInteger, \
	ConfigYesNo, ConfigIP, ConfigSelection, getConfigListEntry
from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Screens.ChoiceBox import ChoiceBox
from Tools.Directories import resolveFilename, SCOPE_CURRENT_SKIN
from Tools.LoadPixmap import LoadPixmap
from twisted.internet import threads

from . import _
from .FTPDownloader import FTPDownloader
from . import epgmap
from . import updater

VERSION = "2.1.2"
VERSION_DATE = "27.11.2026"
UPDATED_SINCE = "21.10.2026"
UPDATED_BY = "Mardo22"
YOUTUBE = "youtube.com/@SetTvBox4U"
GITHUB_REPO = "Mardo22/RemoteChannelStreamConverter-OpenSource"
UPDATE_SUFFIX = ".ipk"
UPDATE_COMMAND = ["opkg", "install"]
PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
QR_SMALL = os.path.join(PLUGIN_DIR, "qr_youtube_small.png")
QR_BIG = os.path.join(PLUGIN_DIR, "qr_youtube_big.png")
LOGO = os.path.join(PLUGIN_DIR, "logo_rcsc.png")	# 2.1.0: our logo (shamrock, same as plugin.png of DreamOS 2.0) in the main window and About


def detectImage():
	"""2.1.0: name and version of the image (e.g. "OpenATV 8.0.1") from /etc/image-version (OE-Alliance),
	otherwise from BoxInfo"""
	name = ver = ""
	try:
		for line in open("/etc/image-version", encoding="utf-8", errors="replace"):
			key, sep, value = line.strip().partition("=")
			if key == "creator" and not name:
				name = value.strip()
			elif key == "comment" and value.strip():
				name = value.strip()
			elif key == "version":
				ver = value.strip()
	except Exception:
		pass
	if not name:
		try:
			from Components.SystemInfo import BoxInfo
			name = BoxInfo.getItem("displaydistro") or BoxInfo.getItem("distro") or ""
			ver = ver or BoxInfo.getItem("imageversion") or ""
		except Exception:
			pass
	return ("%s %s" % (name, ver)).strip() or "Enigma2"

IMAGE_NAME = detectImage()
DIR_ENIGMA2 = "/etc/enigma2/"
REMOTE_DIR = "/etc/enigma2/"
DIR_WORK = "/tmp/rcsc/"
RCSC_PREFIX = "userbouquet.rcsc."
BACKUP_DIR = "/media/hdd/rcsc-backup/"
BACKUP_KEEP = 3
# 1.8: picon links
PICON_LIST = DIR_ENIGMA2 + "rcsc_picon_links"  # links created by RCSC (only these are ever removed)
PICON_FILES = DIR_ENIGMA2 + "rcsc_picon_files"  # 1.9: picons downloaded from the server by RCSC
PICON_DIRS = ["/data/picon/", "/usr/share/enigma2/picon/", "/media/hdd/picon/", "/media/usb/picon/", "/media/mmc/picon/", "/media/cf/picon/", "/picon/"]
PICON_SERVICE_TYPES = ("1", "19", "16", "1F", "D")

FLAG_MUST_DESCENT = 2
FLAG_MARKER = 64
FLAG_GROUP = 128
try:
	FLAG_MUST_DESCENT = eServiceReference.mustDescent
	FLAG_MARKER = eServiceReference.isMarker
	FLAG_GROUP = eServiceReference.isGroup
except Exception:
	pass

# ---------------------------------------------------------------- config (keys of 1.0 kept: ip, username, password, port, passive)
config.plugins.RemoteStreamConverter = ConfigSubsection()
cfg = config.plugins.RemoteStreamConverter
cfg.language = ConfigSelection(default="auto", choices=[("auto", "auto"), ("en", "English"), ("sk", "Slovenčina"), ("cs", "Čeština")])
cfg.address = ConfigText(default="", fixed_size=False)
cfg.ip = ConfigIP(default=[0, 0, 0, 0])
cfg.mode = ConfigSelection(default="webif", choices=[("webif", "OpenWebif"), ("ftp", "FTP")])
cfg.webif_port = ConfigInteger(80, (1, 65535))
cfg.webif_user = ConfigText(default="", fixed_size=False)
cfg.webif_password = ConfigPassword(default="", fixed_size=False)
cfg.username = ConfigText(default="root", fixed_size=False)
cfg.password = ConfigPassword(default="", fixed_size=False)
cfg.port = ConfigInteger(21, (0, 65535))
cfg.passive = ConfigYesNo(False)
cfg.telnetport = ConfigInteger(23, (0, 65535))
cfg.stream_port = ConfigInteger(8001, (1, 65535))
cfg.backup = ConfigYesNo(False)
cfg.merge_lamedb = ConfigYesNo(True)
cfg.copy_iptv = ConfigYesNo(True)
cfg.streamrelay = ConfigYesNo(True)
cfg.streamrelay_port = ConfigInteger(17999, (1, 65535))
cfg.picon_links = ConfigYesNo(True)
cfg.picon_download = ConfigYesNo(True)
cfg.epg_map = ConfigYesNo(True)
cfg.epg_server = ConfigYesNo(True)
cfg.show_pluginbrowser = ConfigYesNo(False)
cfg.show_extensions = ConfigYesNo(False)
cfg.show_mainmenu = ConfigYesNo(False)
cfg.check_update = ConfigYesNo(True)
cfg.picon_dir = ConfigSelection(default="auto", choices=[("auto", "auto")] + [(x, x) for x in PICON_DIRS])



def loadCross():
	# 2.1.0: the icon is in the skin (MetrixHD: skin_default/icons) or in the default skin of the image
	for path in (resolveFilename(SCOPE_CURRENT_SKIN, "skin_default/icons/selectioncross.png"),
			"/usr/share/enigma2/skin_default/icons/selectioncross.png", "/usr/share/enigma2/skin_default/icons/lock_on.png"):
		if os.path.exists(path):
			return LoadPixmap(cached=True, path=path)
	return None


CROSS_PNG = loadCross()


# ---------------------------------------------------------------- 2.1.0: screens are designed in Full HD and scaled to the GUI
def guiScale():
	"""factor GUI width / 1920 (OpenATV with MetrixHD on the Dreambox: 1280 -> 2/3)"""
	try:
		w = getDesktop(0).size().width()
		if w > 0:
			return w / 1920.0
	except Exception:
		pass
	return 1.0


def S(v):
	return int(round(v * guiScale()))


def scaleSkin(skin):
	"""positions, sizes and font sizes of a Full HD skin -> GUI resolution ("center" etc. stay)"""
	f = guiScale()
	if abs(f - 1.0) < 0.01:
		return skin

	def num(x):
		x = x.strip()
		try:
			return str(int(round(int(x) * f)))
		except ValueError:
			return x
	skin = re.sub(r'\b(position|size|shadowOffset|itemHeight)="([^"]+)"', lambda m: '%s="%s"' % (m.group(1), ",".join([num(x) for x in m.group(2).split(",")])), skin)
	skin = re.sub(r'font="([^";]+);(\d+)"', lambda m: 'font="%s;%s"' % (m.group(1), num(m.group(2))), skin)
	return skin


# ---------------------------------------------------------------- helpers (no enigma calls - also used in threads)
def utf8(x):
	"""Python 3: text of a value (bytes decoded as UTF-8)"""
	if isinstance(x, bytes):
		return x.decode("utf-8", "replace")
	return str(x)


def serverAddress():
	if cfg.address.value.strip():
		return cfg.address.value.strip()
	return "%d.%d.%d.%d" % tuple(cfg.ip.value)


def isServerSet():
	return serverAddress() not in ("", "0.0.0.0")


def localPrefix(address):
	return "%s%s." % (RCSC_PREFIX, address.replace(".", "_"))


def readLines(path):
	# surrogateescape: names in other code pages (lamedb) are written back unchanged
	f = open(path, encoding="utf-8", errors="surrogateescape")
	try:
		return f.read().replace("\r", "").split("\n")
	finally:
		f.close()


def writeFileAtomic(path, data):
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


def readBouquetName(path):
	try:
		for line in readLines(path):
			if line.startswith("#NAME "):
				return line[6:].strip()
	except Exception:
		pass
	return ""


def stripRemoteSuffix(name):
	return re.sub(r"\s*\(remote of [^)]*\)\s*$", "", name).strip()


def satName(pos):
	if pos == -1:
		return "IPTV"
	if pos == 0xeeee:
		return "DVB-T"
	if pos == 0xffff:
		return "DVB-C"
	if pos > 1800:
		return "%.1f°W" % ((3600 - pos) / 10.0)
	return "%.1f°E" % (pos / 10.0)


def parseRef(line):
	"""'#SERVICE x:y:...' -> list of fields or None"""
	ref = line[9:].strip()
	fields = ref.split(":")
	if len(fields) < 10:
		return None
	try:
		int(fields[1])
	except ValueError:
		return None
	return fields


def analyseBouquet(path):
	count = 0
	sats = {}
	try:
		lines = readLines(path)
	except Exception:
		return 0, []
	for line in lines:
		if not line.startswith("#SERVICE "):
			continue
		f = parseRef(line)
		if f is None:
			continue
		flags = int(f[1])
		if flags & FLAG_MARKER:
			continue
		if "http" in line or f[0] != "1":  # IPTV / media (4097, 5001, 5002 ...)
			count += 1
			sats[-1] = sats.get(-1, 0) + 1
			continue
		count += 1
		if flags & FLAG_MUST_DESCENT:
			continue
		try:
			pos = (int(f[6], 16) >> 16) & 0xffff
		except ValueError:
			continue
		sats[pos] = sats.get(pos, 0) + 1
	return count, sorted(sats.items(), key=lambda x: -x[1])


def satsText(sats, maxitems=2):
	if not sats:
		return ""
	txt = ", ".join([satName(p) for p, c in sats[:maxitems]])
	if len(sats) > maxitems:
		txt += " +%d" % (len(sats) - maxitems)
	return txt


def parseBouquetsIndex(path):
	"""bouquets.tv/radio -> list of bouquet file names"""
	result = []
	try:
		lines = readLines(path)
	except Exception:
		return result
	for line in lines:
		m = re.search(r'FROM BOUQUET "([^"]+)"', line)
		if m and line.startswith("#SERVICE"):
			f = parseRef(line)
			if f and (int(f[1]) & 512):  # isInvisible
				continue
			name = m.group(1)
			if name not in result:
				result.append(name)
	return result


def findAlternativeFiles(path):
	result = []
	try:
		lines = readLines(path)
	except Exception:
		return result
	for line in lines:
		if line.startswith("#SERVICE "):
			f = parseRef(line)
			if f and int(f[1]) & FLAG_MUST_DESCENT and not int(f[1]) & FLAG_MARKER:
				m = re.search(r'FROM BOUQUET "([^"]+)"', line)
				if m:
					result.append(m.group(1))
	return result


# ---------------------------------------------------------------- lamedb (format /4/)
def lamedbKey4(key):
	parts = key.split(":")
	try:
		return tuple([int(x, 16) for x in parts[:4]])
	except ValueError:
		return key.lower()


def readLamedb(path):
	lines = readLines(path)
	if not lines or not lines[0].startswith("eDVB services /4/"):
		return None
	transponders = OrderedDict()
	services = OrderedDict()
	i = 1
	n = len(lines)
	while i < n and lines[i] != "transponders":
		i += 1
	i += 1
	while i < n and lines[i] != "end":
		key = lines[i]
		data = []
		i += 1
		while i < n and lines[i] != "/" and lines[i] != "end":
			data.append(lines[i])
			i += 1
		if i < n and lines[i] == "/":
			i += 1
		k = lamedbKey4(key)
		if k not in transponders:
			transponders[k] = (key, data)
	i += 1
	while i < n and lines[i] != "services":
		i += 1
	i += 1
	while i + 2 < n and lines[i] != "end":
		k = lamedbKey4(lines[i])
		if k not in services:
			services[k] = (lines[i], lines[i + 1], lines[i + 2])
		i += 3
	tail = [x for x in lines[i + 1:] if x != ""]
	return lines[0], transponders, services, tail


def writeLamedb(path, db):
	header, transponders, services, tail = db
	out = [header, "transponders"]
	for key, data in transponders.values():
		out.append(key)
		out.extend(data)
		out.append("/")
	out.append("end")
	out.append("services")
	for entry in services.values():
		out.extend(entry)
	out.append("end")
	out.extend(tail)
	writeFileAtomic(path, "\n".join(out) + "\n")


def serviceNames(db):
	"""(sid, ns, tsid, onid) -> name"""
	names = {}
	if db:
		for k, entry in db[2].items():
			if isinstance(k, tuple):
				names[k] = entry[1]
	return names


# ---------------------------------------------------------------- downloads
LOAD_TIMEOUT = 25	# s - connecting to the server (until bouquets.tv is read)

class WebifFetcher(object):
	def __init__(self, address):
		self.address = address

	def _open(self, path, timeout=20):
		url = "http://%s:%d%s" % (self.address, cfg.webif_port.value, path)
		req = urllib.request.Request(url, headers={"User-Agent": "Enigma2 RCSC"})
		if cfg.webif_user.value:
			auth = base64.b64encode(("%s:%s" % (cfg.webif_user.value, cfg.webif_password.value)).encode("utf-8")).decode("ascii")
			req.add_header("Authorization", "Basic %s" % auth)
		return urllib.request.urlopen(req, timeout=timeout).read()	# bytes

	def _get(self, remote, local):
		data = self._open("/file?file=%s" % quote(REMOTE_DIR + remote))
		head = data[:300].decode("utf-8", "replace")
		if head.startswith("File '") and "not found" in head:
			raise IOError("not found: %s" % remote)
		if remote == "lamedb":
			if not head.startswith("eDVB services"):
				raise IOError("invalid lamedb")
		elif head.lstrip().startswith("<"):
			raise IOError("invalid answer for %s" % remote)
		f = open(local, "wb")
		try:
			f.write(data)
		finally:
			f.close()
		return remote

	def get(self, remote, local):
		return threads.deferToThread(self._get, remote, local)

	def _json(self, path):
		return json.loads(self._open(path, timeout=6))

	def status(self):
		def work():
			info = {}
			try:
				info["status"] = self._json("/api/statusinfo")
			except Exception:
				pass
			try:
				info["device"] = self._json("/api/deviceinfo")
			except Exception:
				pass
			return info
		return threads.deferToThread(work)


class FtpFetcher(WebifFetcher):
	def get(self, remote, local):
		return FTPDownloader(self.address, cfg.port.value, REMOTE_DIR + remote, local,
			cfg.username.value, cfg.password.value, cfg.passive.value).deferred


def makeFetcher():
	if cfg.mode.value == "ftp":
		return FtpFetcher(serverAddress())
	return WebifFetcher(serverAddress())


# ---------------------------------------------------------------- conversion worker (runs in a thread)
def makeBackup():
	if not os.path.isdir("/media/hdd"):
		raise IOError("/media/hdd")
	if not os.path.isdir(BACKUP_DIR):
		os.makedirs(BACKUP_DIR)
	name = BACKUP_DIR + "enigma2_" + time.strftime("%Y-%m-%d_%H%M%S") + ".tar.gz"
	tar = tarfile.open(name, "w:gz")
	try:
		tar.add("/etc/enigma2", arcname="enigma2")
	finally:
		tar.close()
	old = sorted([x for x in os.listdir(BACKUP_DIR) if x.startswith("enigma2_") and x.endswith(".tar.gz")])
	for x in old[:-BACKUP_KEEP]:
		try:
			os.remove(BACKUP_DIR + x)
		except OSError:
			pass
	return name


def refKey(fields):
	"""first 10 fields of a service reference -> comparable key (hex, case and leading zeros ignored)"""
	try:
		return tuple([int(x, 16) for x in fields[:10]])
	except ValueError:
		return tuple([x.lower() for x in fields[:10]])


def readStreamRelay():
	"""1.6: /etc/enigma2/whitelist_streamrelay of the server (OE-A StreamRelay) - these channels are decrypted
	by the server and streamed on the StreamRelay port (17999) instead of the normal stream port"""
	relay = set()
	if not cfg.streamrelay.value or not os.path.exists(DIR_WORK + "whitelist_streamrelay"):
		return relay
	try:
		for line in readLines(DIR_WORK + "whitelist_streamrelay"):
			fields = line.strip().split(":")
			if len(fields) >= 10:
				relay.add(refKey(fields))
	except Exception:
		pass
	return relay


def convertLine(line, address, names, alternatives, relay=None):
	"""one #SERVICE line of the server bouquet -> local line, or None to skip"""
	f = parseRef(line)
	if f is None:
		return line
	flags = int(f[1])
	if flags & FLAG_MARKER:
		return line
	if "http" in line or f[0] != "1":  # IPTV / media (4097, 5001, 5002 ...)
		# IPTV of the server: internet link copied unchanged (1.3), or skipped when the option is off
		if not cfg.copy_iptv.value:
			return None
		# a proxy on the server itself (127.0.0.1 / localhost) is reached via the server address
		return re.sub(r"(?i)(%3a//|://)(127\.0\.0\.1|localhost)(?=[%:/])", r"\g<1>" + address, line)
	if flags & FLAG_MUST_DESCENT:
		m = re.search(r'FROM BOUQUET "([^"]+)"', line)
		alt = m and alternatives.get(m.group(1))
		if not alt:
			return None
		return convertLine(alt, address, names, {}, relay)
	base = ":".join(f[:10])
	name = ""
	try:
		name = names.get((int(f[3], 16), int(f[6], 16), int(f[4], 16), int(f[5], 16)), "")
	except ValueError:
		pass
	if not name and len(f) > 11:
		name = ":".join(f[11:]).strip()
	port = cfg.stream_port.value
	if relay and refKey(f) in relay:
		port = cfg.streamrelay_port.value
	url = "http://%s:%d/%s" % (address, port, base)
	return "#SERVICE %s:%s:%s" % (base, quote(url), name)



def readAlternatives():
	alternatives = {}
	if os.path.isdir(DIR_WORK):
		for fn in os.listdir(DIR_WORK):
			if fn.startswith("alternatives."):
				try:
					for line in readLines(DIR_WORK + fn):
						if line.startswith("#SERVICE "):
							alternatives[fn] = line
							break
				except Exception:
					pass
	return alternatives


def updateIndex(btype, add, remove):
	path = DIR_ENIGMA2 + "bouquets." + btype
	try:
		lines = readLines(path)
	except Exception:
		lines = ["#NAME User - Bouquets (%s)" % ("TV" if btype == "tv" else "Radio")]
	while lines and lines[-1] == "":
		lines.pop()
	out = []
	present = []
	for line in lines:
		m = re.search(r'FROM BOUQUET "([^"]+)"', line)
		if m and m.group(1) in remove:
			continue
		if m:
			present.append(m.group(1))
		out.append(line)
	t = "1" if btype == "tv" else "2"
	for fn in add:
		if fn not in present:
			out.append('#SERVICE 1:7:%s:0:0:0:0:0:0:0:FROM BOUQUET "%s" ORDER BY bouquet' % (t, fn))
	writeFileAtomic(path, "\n".join(out) + "\n")


def localConverted(address):
	"""list of (local file, name without suffix) of converted bouquets of this server"""
	prefix = localPrefix(address)
	result = []
	for fn in sorted(os.listdir(DIR_ENIGMA2)):
		if fn.startswith(prefix) and (fn.endswith(".tv") or fn.endswith(".radio")):
			result.append((fn, stripRemoteSuffix(readBouquetName(DIR_ENIGMA2 + fn))))
	return result


def convertWorker(items, address, merge, server_epg=False):
	result = {"bouquets": 0, "channels": 0, "backup": None, "relay": 0}
	relay = readStreamRelay()
	relay_port = ":%d/" % cfg.streamrelay_port.value
	remote_db = None
	if os.path.exists(DIR_WORK + "lamedb"):
		try:
			remote_db = readLamedb(DIR_WORK + "lamedb")
		except Exception:
			remote_db = None
	names = serviceNames(remote_db)
	alternatives = readAlternatives()
	existing = localConverted(address)
	add = {"tv": [], "radio": []}
	remove = {"tv": [], "radio": []}
	for item in items:
		lines = readLines(DIR_WORK + item["remote"])
		out = []
		skip_desc = False
		for line in lines:
			if skip_desc and line.startswith("#DESCRIPTION"):
				skip_desc = False
				continue
			skip_desc = False
			if line.startswith("#NAME "):
				out.append("#NAME %s (remote of %s)" % (line[6:].strip(), address))
			elif line.startswith("#SERVICE "):
				new = convertLine(line, address, names, alternatives, relay)
				if new is None:
					skip_desc = True
					continue
				nf = parseRef(new)
				if nf and not int(nf[1]) & FLAG_MARKER:
					result["channels"] += 1
					if relay and quote(relay_port) in new:
						result["relay"] += 1
				out.append(new)
			elif line != "":
				out.append(line)
		writeFileAtomic(DIR_ENIGMA2 + item["local"], "\n".join(out) + "\n")
		result["bouquets"] += 1
		btype = item["type"]
		add[btype].append(item["local"])
		# bouquet with the same name (other file of this server) is replaced
		for fn, name in existing:
			if fn != item["local"] and name == item["name"] and fn.endswith("." + btype):
				try:
					os.remove(DIR_ENIGMA2 + fn)
				except OSError:
					pass
				remove[btype].append(fn)
	for btype in ("tv", "radio"):
		if add[btype] or remove[btype]:
			updateIndex(btype, add[btype], remove[btype])
	if merge and remote_db:
		try:
			local_db = readLamedb(DIR_ENIGMA2 + "lamedb")
			if local_db:
				for k, v in remote_db[1].items():
					if k not in local_db[1]:
						local_db[1][k] = v
				for k, v in remote_db[2].items():
					if k not in local_db[2]:
						local_db[2][k] = v
				writeLamedb(DIR_ENIGMA2 + "lamedb", local_db)
				result["lamedb"] = True
		except Exception as e:
			result["lamedb_error"] = str(e)
	result["picons"] = safeSyncPicons(download=True)
	# 2.0.1: EPG of the server only with Update all / MENU (not with every Convert - heavy EPG save, GUI waits)
	result["epg"] = safeEpgWorker(server=server_epg and cfg.epg_server.value)
	return result


def deleteWorker(files):
	remove = {"tv": [], "radio": []}
	for fn in files:
		try:
			os.remove(DIR_ENIGMA2 + fn)
		except OSError:
			pass
		remove["radio" if fn.endswith(".radio") else "tv"].append(fn)
	for btype in ("tv", "radio"):
		if remove[btype]:
			updateIndex(btype, [], remove[btype])
	# 1.8: links of channels that are no longer in any RCSC bouquet are removed
	return len(files), safeSyncPicons(), safeEpgWorker(server=False)


# ---------------------------------------------------------------- 1.8: picon links (run in a thread, no enigma calls)
def piconDirs():
	"""picon directories: the one chosen in the settings, or (auto) the picon paths from /etc/enigma2/settings
	(skins, picon plugins) and the usual paths - only existing directories with picons, each real directory once"""
	if cfg.picon_dir.value != "auto":
		cands = [cfg.picon_dir.value]
	else:
		cands = []
		try:
			for line in readLines(DIR_ENIGMA2 + "settings"):
				key, sep, value = line.partition("=")
				value = value.strip()
				if sep and "picon" in key.lower() and value.startswith("/") and os.path.basename(value.rstrip("/")) == "picon":
					cands.append(value)
		except Exception:
			pass
		cands += PICON_DIRS
	result = []
	seen = set()
	for d in cands:
		d = d.rstrip("/") + "/"
		if not os.path.isdir(d):
			continue
		real = os.path.realpath(d).rstrip("/") + "/"
		if real in seen:
			continue
		if cfg.picon_dir.value == "auto":
			try:
				if not [x for x in os.listdir(real)[:200] if x.endswith(".png")]:
					continue
			except OSError:
				continue
		seen.add(real)
		result.append(real)
	return result


def piconName(fields):
	"""name of the picon the enigma2 Picon renderer looks for (first 10 fields, flags 0; the TSi image writes the
	namespace in upper case, stock DreamOS 4.5 / 5.0 keeps it as it is - both names are linked, see rcscPiconServices)"""
	x = list(fields[:10])
	x[1] = "0"
	x[6] = x[6].upper()
	return "_".join(x)


def piconCandidates(fields):
	"""existing picons that fit the service: own service type first, then 1/19/16/1F/D; for each the namespace
	of the server and the shortened namespace (ns & 0xFFFF0000) that picon packs use"""
	x = [v.upper() for v in fields[:10]]
	x[1] = "0"
	try:
		ns = int(x[6], 16)
	except ValueError:
		return []
	namespaces = [x[6]]
	short = "%X" % (ns & 0xFFFF0000)
	if short not in namespaces:
		namespaces.append(short)
	stype = x[2].lstrip("0") or "0"
	types = [stype] + [t for t in PICON_SERVICE_TYPES if t != stype]
	result = []
	for t in types:
		for n in namespaces:
			y = list(x)
			y[2] = t
			y[6] = n
			name = "_".join(y)
			if name not in result:
				result.append(name)
	return result


def rcscFiles():
	"""all RCSC bouquets (of every server)"""
	try:
		return [fn for fn in os.listdir(DIR_ENIGMA2) if fn.startswith(RCSC_PREFIX) and (fn.endswith(".tv") or fn.endswith(".radio"))]
	except OSError:
		return []


def rcscPiconServices():
	"""picon name -> fields of every stream service (type 1 with a link to the server) in the RCSC bouquets"""
	services = {}
	for fn in rcscFiles():
		try:
			lines = readLines(DIR_ENIGMA2 + fn)
		except Exception:
			continue
		for line in lines:
			if not line.startswith("#SERVICE ") or "http" not in line:
				continue
			f = parseRef(line)
			if f is None or f[0] != "1" or int(f[1]) & (FLAG_MARKER | FLAG_MUST_DESCENT):
				continue
			services[piconName(f)] = f
			# stock DreamOS 4.5 / 5.0 PiconResolver keeps the case of the namespace (TSi writes it in upper case)
			raw = list(f[:10])
			raw[1] = "0"
			services["_".join(raw)] = f
	return services


def readPiconList(path):
	try:
		return set([x for x in readLines(path) if x.startswith("/")])
	except Exception:
		return set()


def syncPicons(download=False):
	"""creates the missing links, renews broken ones and removes own links that are not needed any more.
	Real picon files are never touched; only links listed in PICON_LIST are removed.
	1.9: download=True - picons still missing are downloaded from the server (option), listed in PICON_FILES."""
	result = {"links": 0, "new": 0, "own": 0, "missing": 0, "removed": 0, "dirs": [], "server": 0, "server_new": 0}
	wanted = rcscPiconServices() if cfg.picon_links.value else {}
	known = readPiconList(PICON_LIST)
	files_known = readPiconList(PICON_FILES)
	keep = set()
	keep_files = set()
	missing = []
	dirs = piconDirs() if wanted else []
	result["dirs"] = dirs
	for d in dirs:
		try:
			files = os.listdir(d)
		except OSError:
			continue
		byname = {}
		for fn in files:
			if fn.endswith(".png"):
				byname.setdefault(fn[:-4].upper(), fn)
		for name, fields in wanted.items():
			link = d + name + ".png"
			islink = os.path.islink(link)
			if not islink and os.path.exists(link):
				if link in files_known:
					keep_files.add(link)  # downloaded from the server before
					result["server"] += 1
				else:
					result["own"] += 1  # the channel has its own picon
				continue
			if islink and link not in known and os.path.exists(link):
				# a working link made by hand (or by RCSC in another slot) - adopted, left as it is
				keep.add(link)
				result["links"] += 1
				continue
			target = None
			for cand in piconCandidates(fields):
				real = byname.get(cand)
				if not real or real == name + ".png":
					continue
				if os.path.islink(d + real) and (real[:-4] in wanted or d + real in known):
					continue  # never a link to another RCSC link (no chains)
				target = real
				break
			if target is None:
				if d == dirs[0]:
					missing.append((link, fields))
				else:
					result["missing"] += 1
				continue
			if islink:
				try:
					if os.readlink(link) == target and os.path.exists(link):
						keep.add(link)
						result["links"] += 1
						continue
				except OSError:
					pass
			tmp = link + ".rcsc_tmp"
			try:
				if os.path.lexists(tmp):
					os.remove(tmp)
				os.symlink(target, tmp)
				os.rename(tmp, link)
			except OSError as e:
				print("[RCSC] picon link failed:", link, e)
				continue
			keep.add(link)
			result["links"] += 1
			result["new"] += 1
	# 1.9: picons still missing are downloaded from the server
	if missing and download and cfg.picon_download.value and isServerSet():
		got = downloadServerPicons(missing)
		for link in got:
			keep_files.add(link)
		result["server"] += len(got)
		result["server_new"] = len(got)
		result["missing"] += len(missing) - len(got)
	else:
		result["missing"] += len(missing)
	for link in known - keep:
		if os.path.islink(link):
			try:
				os.remove(link)
				result["removed"] += 1
			except OSError:
				pass
	for path in files_known - keep_files:
		if os.path.exists(path) and not os.path.islink(path):
			try:
				os.remove(path)
				result["removed"] += 1
			except OSError:
				pass
	for path, data, old in ((PICON_LIST, keep, known), (PICON_FILES, keep_files, files_known)):
		if data or old:
			try:
				writeFileAtomic(path, "\n".join(sorted(data)) + "\n")
			except Exception:
				pass
	return result


def serviceKey(fields):
	"""first 10 fields of a reference, flags ignored -> comparable key"""
	x = list(fields[:10])
	x[1] = "0"
	return refKey(x)


def serverPiconMap(web, address):
	"""service key -> picon path on the server, from OpenWebif /api/getservices?picon=1 of the server bouquets
	that belong to the RCSC bouquets of this server (one request per bouquet)"""
	prefix = localPrefix(address)
	result = {}
	for fn in rcscFiles():
		if not fn.startswith(prefix):
			continue
		remote = fn[len(prefix):]
		btype = "2" if fn.endswith(".radio") else "1"
		bref = '1:7:%s:0:0:0:0:0:0:0:FROM BOUQUET "%s" ORDER BY bouquet' % (btype, remote)
		try:
			data = json.loads(web._open("/api/getservices?sRef=%s&picon=1" % quote(bref), timeout=10))
		except Exception as e:
			print("[RCSC] picon list of the server failed:", remote, e)
			continue
		for svc in data.get("services", []):
			path = utf8(svc.get("picon") or "")
			fields = utf8(svc.get("servicereference") or "").split(":")
			if not path.startswith("/") or "default_picon" in path or len(fields) < 10:
				continue
			result[serviceKey(fields)] = path
	return result


def downloadServerPicons(missing):
	"""missing: list of (local picon path, fields) -> list of the paths saved from the server"""
	address = serverAddress()
	web = WebifFetcher(address)
	pmap = serverPiconMap(web, address)
	saved = []
	cache = {}
	for link, fields in missing:
		path = pmap.get(serviceKey(fields))
		if not path:
			continue
		data = cache.get(path)
		if data is None:
			try:
				data = web._open(quote(path), timeout=10)
			except Exception:
				data = ""
			cache[path] = data
		if not data.startswith("\x89PNG"):
			continue
		try:
			writeFileAtomic(link, data)
			saved.append(link)
		except Exception as e:
			print("[RCSC] picon save failed:", link, e)
	return saved


def safeSyncPicons(download=False):
	try:
		return syncPicons(download)
	except Exception as e:
		print("[RCSC] picon links failed:", e)
		return {"error": str(e)}


def piconText(p, short=False):
	"""summary of syncPicons() for the message (short=True: for the status line)"""
	if not p:
		return ""
	if p.get("error"):
		return _("Picon links failed: %s") % p["error"]
	removed = p.get("removed") and (_("Picon links removed: %d") % p["removed"]) or ""
	if not cfg.picon_links.value or not p.get("dirs"):
		return removed
	if short:
		return _("Picons: %d (server %d), without: %d") % (p["links"] + p["own"], p.get("server", 0), p["missing"])
	txt = _("Picons: %d links (%d new), %d own, %d without picon") % (p["links"], p["new"], p["own"], p["missing"])
	if p.get("server"):
		txt += ", " + _("from server: %d (%d new)") % (p["server"], p.get("server_new", 0))
	if removed:
		txt += ", " + removed
	return txt


# ---------------------------------------------------------------- 2.0: EPG (runs in a thread, no enigma calls)
SERVER_EPG_FILE = "/etc/enigma2/rcsc_server_epg.xml.gz"


def rcscEpgServices():
	"""reference (10 fields) -> fields of every stream channel in the RCSC bouquets"""
	services = {}
	for fn in rcscFiles():
		try:
			lines = readLines(DIR_ENIGMA2 + fn)
		except Exception:
			continue
		for line in lines:
			if not line.startswith("#SERVICE ") or "http" not in line:
				continue
			f = parseRef(line)
			if f is None or f[0] != "1" or int(f[1]) & (FLAG_MARKER | FLAG_MUST_DESCENT):
				continue
			services[":".join(f[:10])] = f
	return services


def httpGet(url):
	return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Enigma2 RCSC"}), timeout=30).read()


def epgWorker(server=False):
	"""(1) EPG mapping for EPGImport, (2) with server=True the EPG of the server for the channels without mapping"""
	result = {"map": None, "server": None}
	services = rcscEpgServices()
	unmapped = set(services.keys())
	if True:  # also removes the block when the option is off
		result["map"] = epgmap.mapEpg(services if cfg.epg_map.value else {}, httpGet)
		if cfg.epg_map.value:
			unmapped = result["map"]["unmapped"]
	if not services:
		epgmap.removeServerEpg(SERVER_EPG_FILE)
	elif server and cfg.epg_server.value and isServerSet():
		address = serverAddress()
		prefix = localPrefix(address)
		bouquets = []
		for fn in rcscFiles():
			if fn.startswith(prefix):
				btype = "2" if fn.endswith(".radio") else "1"
				bouquets.append('1:7:%s:0:0:0:0:0:0:0:FROM BOUQUET "%s" ORDER BY bouquet' % (btype, fn[len(prefix):]))
		refs = dict([(r.upper(), r) for r in unmapped])
		result["server"] = epgmap.serverEpg(WebifFetcher(address), bouquets, refs, SERVER_EPG_FILE)
	return result


def safeEpgWorker(server=False):
	try:
		return epgWorker(server)
	except Exception as e:
		print("[RCSC] EPG failed:", e)
		return {"error": str(e)}


def epgText(e):
	"""summary of epgWorker() for the message"""
	if not e:
		return ""
	if e.get("error"):
		return _("EPG failed: %s") % e["error"]
	lines = []
	m = e.get("map")
	if m and m.get("error") == "EPGImport":
		lines.append(_("EPG: EPGImport is not installed."))
	elif m and cfg.epg_map.value and m.get("channels"):
		lines.append(_("EPG of the Dreambox: %d of %d channels mapped (after the next EPGImport run)") % (m["mapped"], m["channels"]))
	srv = e.get("server")
	if srv is not None:
		if srv.get("events"):
			lines.append(_("EPG from server: %d events for %d channels") % (srv["events"], srv["channels"]))
		else:
			lines.append(_("EPG from server: no new EPG (old data kept)"))
	return "\n".join(lines)


def startEpgImportAll():
	"""starts EPGImport with all its enabled sources (like "Manual import" in EPGImport) - main thread"""
	try:
		from Plugins.Extensions.EPGImport import plugin as epi
		if not getattr(epi, "ensure_runtime_modules", lambda: True)() or epi.epgimport.isImportRunning():
			return False
		epi.EPGConfig.channelCache = {}
		conf = epi.EPGConfig.loadUserSettings()
		sources = [x for x in epi.EPGConfig.enumSources(epi.CONFIG_PATH, filter=conf["sources"])]
		if not sources:
			return False
		sources.reverse()
		epi.epgimport.sources = sources
		epi.startImport()
		return True
	except Exception as e:
		print("[RCSC] EPGImport start failed:", e)
		return False


def epgImportClearsAll():
	"""EPGImport option "Clearing current EPG before import": every import starts with an empty EPG"""
	try:
		return bool(config.plugins.epgimport.clear_oldepg.value)
	except Exception:
		return False


def startEpgImportOfServer():
	"""imports only the source "RCSC - EPG from server" with EPGImport (like its own import) - main thread"""
	if not os.path.exists(epgmap.SERVER_SOURCES):
		return False
	if epgImportClearsAll():
		print("[RCSC] EPG of the server not imported - EPGImport clears the whole EPG before each import")
		return False
	try:
		from Plugins.Extensions.EPGImport import plugin as epi
		if not getattr(epi, "ensure_runtime_modules", lambda: True)() or epi.epgimport.isImportRunning():
			return False
		epi.EPGConfig.channelCache = {}
		sources = [x for x in epi.EPGConfig.enumSourcesFile(epgmap.SERVER_SOURCES)]
		if not sources:
			return False
		epi.epgimport.sources = sources
		epi.startImport()
		return True
	except Exception as e:
		print("[RCSC] EPGImport start failed:", e)
		return False


# ---- 2.0.5 / 2.1.2: EPGImport later, in the main thread, never while enigma2 saves its EPG
EPG_IMPORT_DELAY = 60	# seconds after Convert / Update all
EPG_RETRY_DELAY = 30	# seconds between the checks while the EPG is being saved
EPG_RETRY_MAX = 10
EPG_SAVE_QUIET = 20	# the EPG file of enigma2 must be unchanged for so many seconds
_epgTimer = {}


def epgCacheFiles():
	files = []
	try:
		fn = config.misc.epgcache_filename.value
		if fn:
			files.append(fn)
	except Exception:
		pass
	for fn in ("/etc/enigma2/epg.db", "/data/epg/epg.db", "/media/hdd/epg.db", "/etc/enigma2/epg.dat",
			"/media/hdd/epg.dat", "/media/usb/epg.dat"):
		if fn not in files:
			files.append(fn)
	return files


def epgSaving():
	"""True while enigma2 still writes its EPG file (changed less than EPG_SAVE_QUIET seconds ago)"""
	now = time.time()
	for fn in epgCacheFiles():
		for f in (fn, fn + "-journal", fn + "-wal"):
			try:
				if 0 <= now - os.path.getmtime(f) < EPG_SAVE_QUIET:
					return True
			except OSError:
				pass
	return False


def epgImportRunning():
	try:
		from Plugins.Extensions.EPGImport import plugin as epi
		return bool(epi.epgimport.isImportRunning())
	except Exception:
		return False


def epgImportBusy():
	return epgImportRunning() or epgSaving()


def scheduleEpgImport(func, delay, name="server"):
	"""runs func (startEpgImportOfServer / startEpgImportAll) after delay seconds in the main thread (reactor timer,
	also when the plugin window is closed); while the EPG is saved or EPGImport runs: again EPG_RETRY_DELAY later"""
	from twisted.internet import reactor
	old = _epgTimer.get(name)
	if old is not None and old.active():
		old.cancel()
	_epgTimer[name] = reactor.callLater(delay, _epgImportTry, func, name, 1)


def _epgImportTry(func, name, attempt):
	from twisted.internet import reactor
	_epgTimer.pop(name, None)
	if epgImportBusy():
		if attempt >= EPG_RETRY_MAX:
			print("[RCSC] EPGImport (%s) not started - enigma2 still saves the EPG or EPGImport is running" % name)
			return
		print("[RCSC] EPG is being saved or imported - EPGImport (%s) in %d s (try %d)" % (name, EPG_RETRY_DELAY, attempt))
		_epgTimer[name] = reactor.callLater(EPG_RETRY_DELAY, _epgImportTry, func, name, attempt + 1)
		return
	if func():
		print("[RCSC] EPGImport (%s) started" % name)
	else:
		print("[RCSC] EPGImport (%s) could not be started" % name)


def reloadEnigmaLists(services=True):
	db = eDVBDB.getInstance()
	if services:
		db.reloadServicelist()
	db.reloadBouquets()


# ---------------------------------------------------------------- list
# DreamOS 4.5 and 5.0: colors in a MultiContent list only via a template (like the skins do) - a color directly in a row
# entry is taken as a template index and crashes enigma2 (1.1 test 2026-10-21).
# row: (item, name, name_converted_green, count, satellites, status_green, cross_png)
def listTemplate():
	return [
	MultiContentEntryPixmapAlphaBlend(pos=(S(8), S(13)), size=(S(30), S(30)), png=6, flags=BT_SCALE),
	MultiContentEntryText(pos=(S(50), 0), size=(S(540), S(56)), font=0, flags=RT_HALIGN_LEFT | RT_VALIGN_CENTER, text=1),
	MultiContentEntryText(pos=(S(50), 0), size=(S(540), S(56)), font=0, flags=RT_HALIGN_LEFT | RT_VALIGN_CENTER, text=2, color=0x4fc02a, color_sel=0x9be87a),
	MultiContentEntryText(pos=(S(600), 0), size=(S(140), S(56)), font=1, flags=RT_HALIGN_RIGHT | RT_VALIGN_CENTER, text=3),
	MultiContentEntryText(pos=(S(758), S(8)), size=(max(1, S(2)), S(40)), font=1, flags=RT_VALIGN_CENTER, backcolor=0xaaaaaa, backcolor_sel=0xaaaaaa),
	MultiContentEntryText(pos=(S(778), 0), size=(S(232), S(56)), font=1, flags=RT_HALIGN_LEFT | RT_VALIGN_CENTER, text=4),
	MultiContentEntryText(pos=(S(1020), 0), size=(S(220), S(56)), font=1, flags=RT_HALIGN_LEFT | RT_VALIGN_CENTER, text=5, color=0x4fc02a, color_sel=0x9be87a),
	]


def fallbackText():
	"""2.1.0: state of the OpenATV "Fallback remote receiver" (config.usage.remote_fallback*) - only shown,
	RCSC does not need it and does not change it"""
	try:
		enabled = config.usage.remote_fallback_enabled.value
		url = config.usage.remote_fallback.value
	except Exception:
		return ""
	# 2.1.0: name of the image instead of a fixed "OpenATV" (PurE2 test 11.11.2026)
	img = IMAGE_NAME.split(" ")[0] if IMAGE_NAME else "Enigma2"
	if not enabled:
		return _("Fallback tuner (%s): off") % img
	host = re.sub(r"^[a-z]+://", "", url or "").split("/")[0].split(":")[0]
	return _("Fallback tuner (%s): on - %s") % (img, host or "?")


class RCSCList(MenuList):
	def __init__(self):
		MenuList.__init__(self, [], enableWrapAround=True, content=eListboxPythonMultiContent)
		self.l.setFont(0, gFont("Regular", S(30)))
		self.l.setFont(1, gFont("Regular", S(26)))
		self.l.setTemplate(listTemplate())
		self.l.setItemHeight(S(56))


def listEntry(item):
	name = " ".join(item["name"].split())
	if item["type"] == "radio":
		name += " (Radio)"
	conv = item["converted"]
	return (item,
		"" if conv else name,
		name if conv else "",
		"%d" % item["count"],
		satsText(item["sats"]),
		_("converted") if conv else "",
		CROSS_PNG if item["selected"] else None)


def buttons(y, n=4, width=445, x0=20, height=56):
	"""2.1.0: color keys at the bottom as big colored tiles with white text (wish of 11.11.2026), Full HD coordinates"""
	colors = [("key_red", "#b81c1c"), ("key_green", "#2e8b22"), ("key_yellow", "#b89a00"), ("key_blue", "#1d5fb8")]
	if n == 3:
		colors = [colors[0], colors[1], colors[3]]
	out = []
	for k, (name, color) in enumerate(colors):
		x = x0 + k * width
		out.append('<eLabel position="%d,%d" size="%d,%d" backgroundColor="%s" zPosition="1"/>' % (x, y, width - 16, height, color))
		out.append('<widget source="%s" render="Label" position="%d,%d" size="%d,%d" font="Regular;32" valign="center" halign="center" foregroundColor="#ffffff" backgroundColor="%s" transparent="1" zPosition="2"/>' % (name, x, y, width - 16, height, color))
	return "\n\t\t".join(out)


CLOCK = """<widget source="global.CurrentTime" render="Label" position="%(x)d,10" size="150,70" font="Regular;50" halign="right" valign="center" backgroundColor="#101010" transparent="1">
			<convert type="ClockToText">Default</convert>
		</widget>"""


# ---------------------------------------------------------------- main screen
class RCSCMain(Screen):
	SKIN_FHD = """
	<screen name="RCSCMain" position="center,center" size="1800,960" flags="wfNoBorder" backgroundColor="#101010" title="Remote channel stream converter">
		<ePixmap pixmap="%(logo)s" position="18,9" size="68,68" alphatest="blend" scale="1"/>
		<widget source="Title" render="Label" position="100,15" size="1180,60" font="Regular;40" valign="center" backgroundColor="#101010" transparent="1"/>
		<widget source="global.CurrentTime" render="Label" position="1300,12" size="310,32" font="Regular;26" halign="right" valign="center" backgroundColor="#101010" transparent="1">
			<convert type="ClockToText">Format:%%A</convert>
		</widget>
		<widget source="global.CurrentTime" render="Label" position="1300,46" size="310,32" font="Regular;26" halign="right" valign="center" backgroundColor="#101010" transparent="1">
			<convert type="ClockToText">Format:%%d. %%B</convert>
		</widget>
		%(clock)s
		<eLabel backgroundColor="#555555" position="10,85" size="1780,1"/>
		<widget name="list" position="10,95" size="1260,672" scrollbarMode="showOnDemand" enableWrapAround="1" backgroundColor="#101010" transparent="1"/>
		<eLabel backgroundColor="#555555" position="1285,85" size="1,700"/>
		<widget source="server_title" render="Label" position="1300,95" size="480,40" font="Regular;30" foregroundColor="#e6bd00" backgroundColor="#101010" transparent="1"/>
		<widget source="server_info" render="Label" position="1300,140" size="480,330" font="Regular;26" backgroundColor="#101010" transparent="1"/>
		<widget source="detail_title" render="Label" position="1300,480" size="480,40" font="Regular;30" foregroundColor="#e6bd00" backgroundColor="#101010" transparent="1"/>
		<widget source="detail" render="Label" position="1300,525" size="480,250" font="Regular;26" foregroundColor="#aaaaaa" backgroundColor="#101010" transparent="1"/>
		<eLabel backgroundColor="#555555" position="10,790" size="1780,1"/>
		<widget source="status" render="Label" position="10,793" size="680,96" font="Regular;26" valign="center" foregroundColor="#e6bd00" backgroundColor="#101010" transparent="1"/>
		<ePixmap pixmap="%(qr_small)s" position="700,798" size="99,99" alphatest="off" scale="1"/>
		<widget source="youtube" render="Label" position="815,795" size="400,105" font="Regular;26" valign="center" backgroundColor="#101010" transparent="1"/>
		<widget source="hint" render="Label" position="1290,795" size="490,105" font="Regular;26" halign="right" valign="center" foregroundColor="#e6bd00" backgroundColor="#101010" transparent="1"/>
		<eLabel backgroundColor="#555555" position="10,890" size="1780,1"/>
		%(buttons)s
	</screen>""" % {"buttons": buttons(898), "qr_small": QR_SMALL, "logo": LOGO, "clock": CLOCK % {"x": 1630}}

	def __init__(self, session):
		self.skin = scaleSkin(self.SKIN_FHD)
		Screen.__init__(self, session)
		self.setTitle("%s %s  ·  %s" % (_("Remote channel stream converter"), VERSION, IMAGE_NAME))
		self["key_red"] = StaticText(_("Close"))
		self["key_green"] = StaticText("")
		self["key_yellow"] = StaticText(_("Settings"))
		self["key_blue"] = StaticText("")
		self["list"] = RCSCList()
		self["server_title"] = StaticText(_("Server"))
		self["server_info"] = StaticText("")
		self["detail_title"] = StaticText(_("Selected bouquet"))
		self["detail"] = StaticText("")
		self["status"] = StaticText("")
		self["hint"] = StaticText(_("OK = select   MENU = options"))
		self["youtube"] = StaticText("YouTube  SetTvBox4U\n" + YOUTUBE)
		self["actions"] = ActionMap(["OkCancelActions", "ColorActions", "MenuActions"], {
			"ok": self.keyOk,
			"cancel": self.keyClose,
			"red": self.keyClose,
			"green": self.keyGreen,
			"yellow": self.keySettings,
			"blue": self.keyBlue,
			"menu": self.keyMenu,
		}, -1)
		self.entries = []
		self.working = False
		self.closing = False
		self.fetcher = None
		self.serverText = ""
		self["list"].onSelectionChanged.append(self.updateDetail)
		self.onLayoutFinish.append(self.start)

	# ---- start / loading
	def start(self):
		if cfg.check_update.value and isServerSet():
			from twisted.internet import reactor
			reactor.callLater(2, self.checkUpdate, False)
		if not isServerSet():
			self["status"].setText(_("Set the server IP first (yellow button)."))
			# 2.0.1 fix (09.11.2026): open the settings only after this window is shown. Opened from onLayoutFinish,
			# the settings stayed hidden behind the main window, yellow did nothing and red showed them.
			from twisted.internet import reactor
			reactor.callLater(0.3, self.openFirstSettings)
			return
		self.loadRemote()

	def openFirstSettings(self):
		if self.alive() and not self.closing:
			self.keySettings()

	def prepareWorkDir(self):
		if not os.path.isdir(DIR_WORK):
			os.makedirs(DIR_WORK)
		for fn in os.listdir(DIR_WORK):
			try:
				os.remove(DIR_WORK + fn)
			except OSError:
				pass

	def loadRemote(self):
		# 2.0.1 fix (09.11.2026): every load has its own number - answers of an older (cancelled) load are ignored,
		# yellow can cancel the connecting, and connecting gives up after LOAD_TIMEOUT s (wrong IP never answered).
		self.loadGen = self.__dict__.get("loadGen", 0) + 1
		self.loading = True
		self.connected = False
		self.working = True
		self.entries = []
		self["list"].setList([])
		self["key_green"].setText("")
		self["key_blue"].setText("")
		self.address = serverAddress()
		self.fetcher = makeFetcher()
		self.prepareWorkDir()
		self.updateServerInfo(None)
		self["status"].setText(_("Connecting to %s ...") % self.address)
		WebifFetcher(self.address).status().addCallback(self.statusReceived, self.loadGen).addErrback(lambda e: None)
		self.fetchSeq(["bouquets.tv", "bouquets.radio"], None, self.indexFetched)
		from twisted.internet import reactor
		reactor.callLater(LOAD_TIMEOUT, self._loadTimeout, self.loadGen)

	def _loadTimeout(self, gen):
		if not self.alive() or gen != self.loadGen or not self.loading or self.connected:
			return
		self.cancelLoad()
		self["status"].setText(_("Could not connect to %s - check the server IP (yellow button).") % self.address)

	def cancelLoad(self):
		self.loadGen += 1
		self.loading = False
		self.working = False

	def fetchSeq(self, names, fmt, done):
		self._queue = list(names)
		self._qi = 0
		self._qfmt = fmt
		self._qdone = done
		self._failed = []
		self._fetchNext()

	def _fetchNext(self, *args):
		if not self.alive():
			return
		if self._qi >= len(self._queue):
			self._qdone(self._failed)
			return
		name = self._queue[self._qi]
		self._qi += 1
		if self._qfmt:
			self["status"].setText(self._qfmt % (self._qi, len(self._queue)))
		gen = self.loadGen
		d = self.fetcher.get(name, DIR_WORK + name)
		d.addCallback(self._fetchDone, gen)
		d.addErrback(self._fetchFailed, name, gen)

	def _fetchDone(self, result, gen):
		if self.alive() and gen == self.loadGen:
			self._fetchNext()

	def _fetchFailed(self, failure, name, gen=None):
		print("[RCSC] download failed:", name, failure)
		if not self.alive() or gen != self.loadGen:
			return
		self._failed.append(name)
		self._fetchNext()

	def indexFetched(self, failed):
		if "bouquets.tv" in failed:
			self.loading = False
			self.working = False
			self["status"].setText(_("Could not connect to %s") % self.address)
			return
		self.connected = True
		self.remoteIndex = []
		for btype in ("tv", "radio"):
			for fn in parseBouquetsIndex(DIR_WORK + "bouquets." + btype):
				if not fn.startswith(RCSC_PREFIX):
					self.remoteIndex.append((fn, btype))
		self.fetchSeq([x[0] for x in self.remoteIndex] + ["lamedb", "whitelist_streamrelay"], _("Reading bouquets %d of %d"), self.bouquetsFetched)

	def bouquetsFetched(self, failed):
		alternatives = []
		for fn, btype in self.remoteIndex:
			if fn not in failed:
				for alt in findAlternativeFiles(DIR_WORK + fn):
					if alt not in alternatives:
						alternatives.append(alt)
		self._bouquetFailed = failed
		if alternatives:
			self.fetchSeq(alternatives, _("Reading alternatives %d of %d"), self.allFetched)
		else:
			self.allFetched([])

	def allFetched(self, failed):
		self.loading = False
		self.working = False
		self.buildItems()
		if not self.entries:
			self["status"].setText(_("Download from server failed"))
			return
		self["key_green"].setText(_("Convert"))
		self["key_blue"].setText(_("Invert"))
		self.showSummary()

	def buildItems(self):
		prefix = localPrefix(self.address)
		converted = localConverted(self.address)
		# 1.7: every local bouquet counts for one server bouquet only (same names like "Others" were counted twice)
		claimed = set()
		rows = []
		for fn, btype in self.remoteIndex:
			if fn in self._bouquetFailed:
				continue
			local = prefix + fn
			exact = os.path.exists(DIR_ENIGMA2 + local)
			if exact:
				claimed.add(local)
			rows.append((fn, btype, local, exact))
		self.entries = []
		for fn, btype, local, exact in rows:
			count, sats = analyseBouquet(DIR_WORK + fn)
			name = readBouquetName(DIR_WORK + fn) or fn
			isConv = exact
			if not isConv:
				for lfn, lname in converted:
					if lname == name and lfn not in claimed:
						claimed.add(lfn)
						isConv = True
						break
			self.entries.append({"remote": fn, "type": btype, "name": name, "count": count, "sats": sats,
				"local": local, "converted": isConv, "selected": False})
		self.refreshList()

	def refreshList(self):
		idx = self["list"].getSelectionIndex() if self.entries else 0
		self["list"].setList([listEntry(x) for x in self.entries])
		if self.entries:
			self["list"].moveToIndex(min(idx, len(self.entries) - 1))
		self.updateDetail()

	def showSummary(self, extra=""):
		conv = len([x for x in self.entries if x["converted"]])
		txt = _("%d bouquets on server, %d converted") % (len(self.entries), conv)
		if extra:
			txt = extra + "   " + txt
		self["status"].setText(txt)

	# ---- server info
	def statusReceived(self, info, gen=None):
		if self.alive() and (gen is None or gen == self.loadGen):
			self.updateServerInfo(info)

	def updateServerInfo(self, info):
		mode = _("OpenWebif (no password)") if cfg.mode.value == "webif" else _("FTP (with password)")
		lines = ["%s  ·  %s" % (serverAddress(), mode)]
		if info is None:
			pass
		elif not info:
			lines.append(_("Server status unknown (OpenWebif not reachable)."))
		else:
			dev = info.get("device") or {}
			if dev:
				lines.append("%s %s  ·  %s %s" % (utf8(dev.get("brand", "")), utf8(dev.get("model", "")),
					utf8(dev.get("friendlyimagedistro", dev.get("imagedistro", ""))), utf8(dev.get("imagever", ""))))
			st = info.get("status") or {}
			standby = utf8(st.get("inStandby", "")).lower() == "true"
			if standby:
				lines.append(_("Server is in standby - tuner is free."))
			elif st.get("currservice_name"):
				lines.append(_("Server is watching: %s") % utf8(st.get("currservice_name")))
			busy = []
			for t in dev.get("tuners", []):
				use = [x for x in ("live", "rec", "stream") if t.get(x)]
				if use:
					busy.append("%s (%s)" % (utf8(t.get("name", "")).replace("Tuner ", ""), "/".join(use)))
			if busy:
				lines.append(_("Server busy tuners: %s") % ", ".join(busy))
		fb = fallbackText()
		if fb:
			lines.append(fb)
			lines.append("")
			lines.append(_("Tip: one tuner on the server = channels of one transponder only (all in standby)."))
		self["server_info"].setText("\n".join([utf8(x) for x in lines]))

	def updateDetail(self):
		item = self.currentItem()
		if not item:
			self["detail"].setText("")
			return
		sats = ", ".join(["%s (%d)" % (satName(p), c) for p, c in item["sats"][:5]])
		lines = [" ".join(item["name"].split()),
			"%d %s" % (item["count"], _("channels")),
			"%s: %s" % (_("Satellites"), sats or "-"),
			"%s: %s" % (_("Status"), _("converted") if item["converted"] else _("not converted")),
			"%s: %s" % (_("File"), item["remote"]),
			_("Bouquet with the same name is replaced, other bouquets stay.")]	# 2.1.0: no empty line - the last line was cut in Full HD MetrixHD
		self["detail"].setText("\n".join(lines))

	def currentItem(self):
		cur = self["list"].getCurrent()
		if isinstance(cur, dict):
			return cur
		if isinstance(cur, (list, tuple)) and cur and isinstance(cur[0], dict):
			return cur[0]
		return None

	# ---- keys
	def alive(self):
		# 1.7: enigma clears __dict__ of a closed Screen - late callbacks must not touch it
		return not self.__dict__.get("closing", True)

	def keyClose(self):
		self.closing = True
		self.close()

	def keyOk(self):
		item = self.currentItem()
		if self.working or not item:
			return
		item["selected"] = not item["selected"]
		self.refreshList()

	def keyBlue(self):
		if self.working or not self.entries:
			return
		for x in self.entries:
			x["selected"] = not x["selected"]
		self.refreshList()

	def keySettings(self):
		# 2.0.1: only one settings window (at the first start it opens by itself - yellow must not open a second one)
		if self.__dict__.get("settingsOpen"):
			return
		if self.working:
			if not self.__dict__.get("loading"):
				return
			self.cancelLoad()		# 2.0.1 fix: yellow while connecting/reading - stop it and open the settings
			self["status"].setText(_("Connecting cancelled."))
		self.settingsOpen = True
		self.session.openWithCallback(self.settingsClosed, RCSCSetup)

	def settingsClosed(self, changed=False):
		self.__dict__["settingsOpen"] = False
		if not self.alive():
			return
		if changed or (isServerSet() and not self.entries):
			if isServerSet():
				self.loadRemote()

	def keyGreen(self):
		if self.working or not self.entries:
			return
		selected = [x for x in self.entries if x["selected"]]
		if not selected:
			self["status"].setText(_("No bouquets selected"))
			return
		self.convert(selected)

	def keyMenu(self):
		if self.working:
			return
		conv = [x for x in self.entries if x["converted"]]
		local = localConverted(serverAddress()) if isServerSet() else []
		menu = []
		if self.entries:
			menu.append((_("Update all converted bouquets (%d)") % len(conv), "update"))
			menu.append((_("Delete selected converted bouquets"), "delete_sel"))
		menu.append((_("Delete all converted bouquets of this server (%d)") % len(local), "delete_all"))
		menu.append((_("Update picon links of the channels"), "picons"))
		menu.append((_("Update EPG from server"), "epg"))
		menu.append((_("Start EPGImport now (all sources)"), "epgimport"))
		menu.append((_("Reload list from server"), "reload"))
		menu.append((_("Server settings"), "settings"))
		menu.append((_("Check for updates now"), "update_check"))
		menu.append((_("About"), "about"))
		# 2.1.0: numbered options (wish of 11.11.2026) - the number key on the remote starts the option directly
		keys = [str(n + 1) for n in range(len(menu))][:9]
		keys += [""] * (len(menu) - len(keys))
		# the skins of the images draw the number of the key in front of the option (no number in the text - test 11.11.)
		self.session.openWithCallback(self.menuCallback, ChoiceBox, title=_("Options"), list=menu, keys=keys)

	def menuCallback(self, choice):
		if not choice or not self.alive():
			return
		action = choice[1]
		if action == "update":
			conv = [x for x in self.entries if x["converted"]]
			if not conv:
				self["status"].setText(_("No converted bouquets."))
				return
			missing = len(localConverted(self.address)) - len(conv)
			self.convert(conv, missing > 0 and (_("Not found on server: %d") % missing) or "", server_epg=True)
		elif action == "delete_sel":
			files = [x["local"] for x in self.entries if x["selected"] and x["converted"] and os.path.exists(DIR_ENIGMA2 + x["local"])]
			self.askDelete(files)
		elif action == "delete_all":
			self.askDelete([fn for fn, name in localConverted(serverAddress())])
		elif action == "picons":
			self.startPicons()
		elif action == "epg":
			self.startEpg()
		elif action == "epgimport":
			if epgImportBusy():
				scheduleEpgImport(startEpgImportAll, EPG_RETRY_DELAY, "all")
				self["status"].setText(_("The EPG is being saved now - EPGImport starts as soon as it is finished."))
			elif startEpgImportAll():
				self["status"].setText(_("EPGImport is running - EPG comes in a few minutes."))
			else:
				self["status"].setText(_("EPGImport could not be started (not installed or already running)."))
		elif action == "reload":
			if isServerSet():
				self.loadRemote()
		elif action == "settings":
			self.keySettings()
		elif action == "update_check":
			self.checkUpdate(True)
		elif action == "about":
			self.session.open(RCSCAbout)

	# ---- online update from GitHub (2.0.4 DreamOS / 2.1.1 open source)
	def checkUpdate(self, manual=False):
		if not self.alive():
			return
		if manual:
			self["status"].setText(_("Checking for updates ..."))
		threads.deferToThread(updater.checkLatest, GITHUB_REPO, VERSION, UPDATE_SUFFIX) \
			.addCallback(self.updateChecked, manual).addErrback(self.updateCheckFailed, manual)

	def updateCheckFailed(self, failure, manual):
		print("[RCSC] update check failed: %s" % failure.getErrorMessage())
		if manual and self.alive():
			self["status"].setText(_("Could not check for updates (no internet connection?)."))

	def updateChecked(self, info, manual):
		if not self.alive():
			return
		if not info:
			if manual:
				self["status"].setText(_("You have the latest version (%s).") % VERSION)
			return
		self._updateInfo = info
		self.offerUpdate()

	def offerUpdate(self):
		if not self.alive():
			return
		if self.working:	# never install while bouquets are loaded or converted - ask when it is finished
			from twisted.internet import reactor
			reactor.callLater(1, self.offerUpdate)
			return
		info = self._updateInfo
		text = _("A new version %s is available (installed: %s).") % (info["version"], VERSION)
		if info.get("notes"):
			text += "\n\n" + info["notes"]
		text += "\n\n" + _("Download and install it now?")
		self.session.openWithCallback(self.updateAnswer, MessageBox, text, MessageBox.TYPE_YESNO, default=True)

	def updateAnswer(self, answer):
		if not answer or not self.alive():
			return
		self.working = True
		self["status"].setText(_("Downloading and installing version %s ...") % self._updateInfo["version"])
		threads.deferToThread(updater.downloadAndInstall, self._updateInfo, UPDATE_COMMAND) \
			.addCallback(self.updateInstalled).addErrback(self.updateInstallFailed)

	def updateInstallFailed(self, failure):
		self.updateInstalled((False, failure.getErrorMessage()))

	def updateInstalled(self, result):
		ok, out = result
		print("[RCSC] update %s: %s" % (ok and "installed" or "failed", out))
		if not self.alive():
			return
		self.working = False
		if not ok:
			self["status"].setText(_("Update failed."))
			self.session.open(MessageBox, _("The update could not be installed:") + "\n" + out, MessageBox.TYPE_ERROR)
			return
		self["status"].setText(_("Version %s installed - active after a GUI restart.") % self._updateInfo["version"])
		self.session.openWithCallback(self.restartAnswer, MessageBox, _("Version %s is installed. Restart the GUI now?") % self._updateInfo["version"], MessageBox.TYPE_YESNO, default=True)

	def restartAnswer(self, answer):
		if answer and self.alive():
			from Screens.Standby import TryQuitMainloop
			self.session.open(TryQuitMainloop, 3)

	# ---- delete
	def askDelete(self, files):
		if not files:
			self["status"].setText(_("No converted bouquets."))
			return
		self._deleteFiles = files
		self.session.openWithCallback(self.deleteConfirmed, MessageBox, (len(files) == 1 and _("Really delete 1 converted bouquet?") or _("Really delete %d converted bouquets?") % len(files)), MessageBox.TYPE_YESNO, default=False)

	def deleteConfirmed(self, answer):
		if not answer or not self.alive():
			return
		self.working = True
		# 2.0.2: message while deleting (picon links + EPG mapping take a while, the window did not change)
		n = len(self._deleteFiles)
		self["status"].setText((n == 1 and _("Deleting 1 bouquet ...") or _("Deleting %d bouquets ...") % n) + "\n" + _("Updating picon links and EPG mapping - please wait."))
		threads.deferToThread(deleteWorker, self._deleteFiles).addCallback(self.deleteDone).addErrback(self.workerFailed)

	def deleteDone(self, res):
		reloadEnigmaLists(services=False)
		if not self.alive():
			return
		count, picons = res[0], res[1]
		self.working = False
		if self.entries:
			self.buildItems()
		self.showSummary(count == 1 and _("Deleted 1 bouquet.") or _("Deleted %d bouquets.") % count)
		ptxt = piconText(picons, short=True)
		if ptxt:
			self["status"].setText(self["status"].getText() + "\n" + ptxt)

	# ---- 2.0: EPG on demand (MENU)
	def startEpg(self):
		self.working = True
		self["status"].setText(_("Updating EPG ..."))
		threads.deferToThread(safeEpgWorker, True).addCallback(self.epgDone).addErrback(self.workerFailed)

	def epgDone(self, epg):
		if not self.alive():
			return
		self.working = False
		text = epgText(epg)
		if (epg.get("server") or {}).get("events"):
			if epgImportClearsAll():
				text += "\n" + _("EPG of the server not imported: EPGImport is set to clear the whole EPG before each import (EPGImport settings).")
			elif epgImportBusy():
				scheduleEpgImport(startEpgImportOfServer, EPG_RETRY_DELAY)
				text += "\n" + _("The EPG is being saved now - EPGImport imports the EPG of the server as soon as it is finished.")
			elif startEpgImportOfServer():
				text += "\n" + _("EPGImport is importing the EPG of the server now.")
		self["status"].setText(_("EPG updated."))
		self.session.open(MessageBox, text or _("EPG options are off (settings)."), MessageBox.TYPE_INFO, timeout=10)

	# ---- 1.8: picon links only (without converting)
	def startPicons(self):
		self.working = True
		self["status"].setText(_("Creating picon links ..."))
		threads.deferToThread(safeSyncPicons, True).addCallback(self.piconsDone).addErrback(self.workerFailed)

	def piconsDone(self, picons):
		if not self.alive():
			return
		self.working = False
		self["status"].setText(piconText(picons) or _("Picon links are off (settings)."))

	# ---- convert
	def convert(self, items, extra="", server_epg=False):
		self.working = True
		self._serverEpg = server_epg
		self._convertItems = items
		self._convertExtra = extra
		self._backupName = None
		if cfg.backup.value:
			self["status"].setText(_("Creating backup ..."))
			threads.deferToThread(makeBackup).addCallback(self.backupDone).addErrback(self.backupFailed)
		else:
			self.startConvert()

	def backupDone(self, name):
		if not self.alive():
			return
		self._backupName = name
		self.startConvert()

	def backupFailed(self, failure):
		if not self.alive():
			return
		self.working = False
		self.session.open(MessageBox, _("Backup failed: %s") % failure.getErrorMessage(), MessageBox.TYPE_ERROR)
		self.showSummary()

	def startConvert(self):
		n = len(self._convertItems)
		self["status"].setText(n == 1 and _("Converting 1 bouquet ...") or _("Converting %d bouquets ...") % n)
		threads.deferToThread(convertWorker, self._convertItems, self.address, cfg.merge_lamedb.value, self._serverEpg) \
			.addCallback(self.convertDone).addErrback(self.workerFailed)

	def convertDone(self, result):
		reloadEnigmaLists(services=True)
		if not self.alive():
			return
		self.working = False
		for x in self.entries:
			x["selected"] = False
		self.buildItems()
		if result["bouquets"] == 1:
			msg = _("Done: 1 bouquet, %d channels converted.") % result["channels"]
		else:
			msg = _("Done: %d bouquets, %d channels converted.") % (result["bouquets"], result["channels"])
		if result.get("relay"):
			msg += "  " + _("StreamRelay: %d channels") % result["relay"]
		if self._convertExtra:
			msg += "  " + self._convertExtra
		ptxt = piconText(result.get("picons"))
		pshort = piconText(result.get("picons"), short=True)
		self.showSummary()
		self["status"].setText(msg + (pshort and "\n" + pshort or ""))
		text = msg + (ptxt and "\n" + ptxt or "")
		etxt = epgText(result.get("epg"))
		if etxt:
			text += "\n" + etxt
		if (result.get("epg") or {}).get("server", {}) and result["epg"]["server"].get("events"):
			if epgImportClearsAll():
				text += "\n" + _("EPG of the server not imported: EPGImport is set to clear the whole EPG before each import (EPGImport settings).")
			else:
				scheduleEpgImport(startEpgImportOfServer, EPG_IMPORT_DELAY)
				text += "\n" + _("The EPG of the server will be imported in about 1 minute.")
		elif cfg.epg_server.value and not self._serverEpg:
			text += "\n" + _("EPG from server: MENU - Update EPG from server")
		if self._backupName:
			text += "\n" + _("Backup: %s") % self._backupName
		self.session.open(MessageBox, text, MessageBox.TYPE_INFO, timeout=8)

	def workerFailed(self, failure):
		print("[RCSC] worker failed:", failure)
		if not self.alive():
			return
		self.working = False
		self["status"].setText("%s: %s" % (_("Conversion failed"), failure.getErrorMessage()))


# ---------------------------------------------------------------- about (1.4: own screen with the QR code of the YouTube channel)
class RCSCAbout(Screen):
	SKIN_FHD = """
	<screen name="RCSCAbout" position="center,center" size="1500,620" flags="wfNoBorder" backgroundColor="#101010" title="About">
		<eLabel backgroundColor="#555555" position="0,0" size="1500,2"/>
		<ePixmap pixmap="%(logo)s" position="30,40" size="160,160" alphatest="blend" scale="1"/>
		<widget source="text" render="Label" position="215,30" size="870,560" font="Regular;29" valign="center" backgroundColor="#101010" transparent="1"/>
		<ePixmap pixmap="%(qr_big)s" position="1130,110" size="330,330" alphatest="off" scale="1"/>
		<widget source="qr_label" render="Label" position="1100,450" size="390,110" font="Regular;26" halign="center" valign="top" foregroundColor="#e6bd00" backgroundColor="#101010" transparent="1"/>
		<eLabel backgroundColor="#555555" position="0,618" size="1500,2"/>
	</screen>""" % {"qr_big": QR_BIG, "logo": LOGO}

	def __init__(self, session):
		self.skin = scaleSkin(self.SKIN_FHD)
		Screen.__init__(self, session)
		self.setTitle(_("About"))
		self["text"] = StaticText("\n".join([
			_("Remote channel stream converter for %s") % IMAGE_NAME,
			_("Updated by %s since %s") % (UPDATED_BY, UPDATED_SINCE),
			"YouTube: SetTvBox4U  -  %s" % YOUTUBE,
			"",
			_("Updated and extended version of the open-source Enigma2 plugin \"Remote channel stream converter\" for open-source Enigma2 images."),
			_("Original plugin published by: OpenPLi, E2OpenPlugins, OE-Alliance"),
			_("Converts bouquets of another Enigma2 receiver (server) into stream bouquets, so that the Dreambox uses the tuners of the server."),
			"",
			_("Version %s  ·  updated %s") % (VERSION, VERSION_DATE) + "  ·  " + _("License: GPL-3.0")]))
		self["qr_label"] = StaticText("YouTube  SetTvBox4U\n" + YOUTUBE)
		self["actions"] = ActionMap(["OkCancelActions"], {"ok": self.close, "cancel": self.close}, -1)


# ---------------------------------------------------------------- settings
class RCSCSetup(ConfigListScreen, Screen):
	SKIN_FHD = """
	<screen name="RCSCSetup" position="center,center" size="1200,900" flags="wfNoBorder" backgroundColor="#101010" title="Server settings">
		<widget source="Title" render="Label" position="30,15" size="950,60" font="Regular;40" valign="center" backgroundColor="#101010" transparent="1"/>
		%(clock)s
		<eLabel backgroundColor="#555555" position="10,85" size="1180,1"/>
		<widget enableWrapAround="1" name="config" position="10,95" scrollbarMode="showOnDemand" size="1180,600" itemHeight="50" font="Regular;30" backgroundColor="#101010" transparent="1"/>
		<eLabel backgroundColor="#555555" position="10,705" size="1180,1"/>
		<widget source="description" render="Label" position="10,712" size="1180,120" font="Regular;28" halign="center" valign="center" foregroundColor="#aaaaaa" backgroundColor="#101010" transparent="1"/>
		<eLabel backgroundColor="#555555" position="10,840" size="1180,1"/>
		%(buttons)s
	</screen>""" % {"buttons": buttons(842, n=3, width=390), "clock": CLOCK % {"x": 1030}}

	def __init__(self, session):
		self.skin = scaleSkin(self.SKIN_FHD)
		Screen.__init__(self, session)
		self.setTitle(_("Server settings"))
		self["key_red"] = StaticText(_("Cancel"))
		self["key_green"] = StaticText(_("Save"))
		self["key_blue"] = StaticText(_("Keyboard"))
		self["description"] = StaticText("")
		self.list = []
		ConfigListScreen.__init__(self, self.list, session=session, on_change=self.changed)
		self["actions"] = ActionMap(["SetupActions", "ColorActions"], {
			"save": self.keySave,
			"green": self.keySave,
			"cancel": self.keyCancel,
			"red": self.keyCancel,
			"blue": self.keyKeyboard,
		}, -2)
		self.createSetup()
		self["config"].onSelectionChanged.append(self.updateDescription)
		self.onLayoutFinish.append(self.updateDescription)

	def createSetup(self):
		lst = []
		lst.append(getConfigListEntry(_("Connection"), cfg.mode, cfg.mode.value == "webif" and _("OpenWebif needs no password if web authentication on the server is off.") or _("FTP needs the root password of the server.")))
		lst.append(getConfigListEntry(_("Server IP address"), cfg.ip, ""))
		if cfg.mode.value == "webif":
			lst.append(getConfigListEntry(_("OpenWebif port"), cfg.webif_port, ""))
			lst.append(getConfigListEntry(_("OpenWebif user (optional)"), cfg.webif_user, _("OpenWebif needs no password if web authentication on the server is off.")))
			lst.append(getConfigListEntry(_("OpenWebif password (optional)"), cfg.webif_password, _("OpenWebif needs no password if web authentication on the server is off.")))
		else:
			lst.append(getConfigListEntry(_("FTP user"), cfg.username, _("FTP needs the root password of the server.")))
			lst.append(getConfigListEntry(_("FTP password"), cfg.password, _("FTP needs the root password of the server.")))
			lst.append(getConfigListEntry(_("FTP port"), cfg.port, ""))
			lst.append(getConfigListEntry(_("FTP passive mode"), cfg.passive, ""))
		lst.append(getConfigListEntry(_("Stream port"), cfg.stream_port, _("Port of the server's stream (OpenWebif/streamserver), usually 8001.")))
		lst.append(getConfigListEntry(_("Use StreamRelay of the server"), cfg.streamrelay, _("Channels in the StreamRelay list of the server (whitelist_streamrelay) are decrypted by the server and streamed on its StreamRelay port.")))
		if cfg.streamrelay.value:
			lst.append(getConfigListEntry(_("StreamRelay port"), cfg.streamrelay_port, _("StreamRelay port of the server, usually 17999.")))
		lst.append(getConfigListEntry(_("Merge server lamedb (names, providers)"), cfg.merge_lamedb, _("Adds the server's services to the local lamedb without duplicates.")))
		lst.append(getConfigListEntry(_("Copy IPTV channels (internet links)"), cfg.copy_iptv, _("IPTV channels of the server are copied with their original internet links - the Dreambox plays them directly from the internet.")))
		lst.append(getConfigListEntry(_("EPG of the Dreambox for the channels (EPGImport)"), cfg.epg_map, _("The XMLTV ids of your EPGImport sources are assigned to the channels of the server (own block in /etc/epgimport/custom.channels.xml). Channel references and numbers do not change. EPG after the next EPGImport run.")))
		lst.append(getConfigListEntry(_("EPG from server (only on demand)"), cfg.epg_server, _("With Update all / MENU 'Update EPG from server' the EPG of the server is taken for channels without EPG of the Dreambox. Nothing runs automatically; without EPG on the server old data stay.")))
		lst.append(getConfigListEntry(_("Create picon links for the channels"), cfg.picon_links, _("After every conversion the plugin links the picons of the channels to the stream services, so that the channels of the server have logos. Own picon files are not changed.")))
		if cfg.picon_links.value:
			lst.append(getConfigListEntry(_("Import missing picons from server"), cfg.picon_download, _("Channels without a picon on the Dreambox get the picon of the server (OpenWebif). Existing picons are never replaced.")))
			lst.append(getConfigListEntry(_("Picon directory"), cfg.picon_dir, _("auto = picon directory of the skin / picon plugins (e.g. /data/picon, /media/hdd/picon, /usr/share/enigma2/picon).")))
		lst.append(getConfigListEntry(_("Backup /etc/enigma2 before converting"), cfg.backup, _("Backup to /media/hdd/rcsc-backup (last 3 are kept).")))
		lst.append(getConfigListEntry(_("Show in plugin browser"), cfg.show_pluginbrowser, _("Entry in the plugin browser (after GUI restart). Always in: Menu > Setup > Tuners, Scanning & Reception.")))
		lst.append(getConfigListEntry(_("Show in extensions menu (blue button)"), cfg.show_extensions, _("Quick start with the blue button in TV mode (after GUI restart).")))
		lst.append(getConfigListEntry(_("Show in main menu"), cfg.show_mainmenu, _("Entry in the main menu (after GUI restart).")))
		lst.append(getConfigListEntry(_("Check for updates when opening"), cfg.check_update, _("When the plugin is opened it asks GitHub (internet) for a new version. You decide with OK or EXIT - nothing is installed without asking.")))
		lst.append(getConfigListEntry(_("Plugin language"), cfg.language, ""))
		self.list = lst
		self["config"].list = lst
		self["config"].l.setList(lst)

	def changed(self):
		cur = self["config"].getCurrent()
		if cur and cur[1] in (cfg.mode, cfg.language, cfg.streamrelay, cfg.picon_links):
			self.createSetup()

	def updateDescription(self):
		cur = self["config"].getCurrent()
		self["description"].setText(cur and len(cur) > 2 and cur[2] or "")

	def keyKeyboard(self):
		cur = self["config"].getCurrent()
		if cur and isinstance(cur[1], ConfigText):
			self.KeyText()

	def keySave(self):
		changed = self["config"].isChanged()
		entries = (cfg.show_pluginbrowser, cfg.show_extensions, cfg.show_mainmenu)
		restart = [x for x in entries if x.isChanged()]
		self.saveAll()
		cfg.mode.save()
		configfile.save()
		if restart:
			self.session.openWithCallback(lambda *a: self.close(True if changed else False), MessageBox,
				_("The menu entries change after a GUI restart."), MessageBox.TYPE_INFO, timeout=6)
			return
		self.close(True if changed else False)

	def keyCancel(self):
		for x in self["config"].list:
			x[1].cancel()
		self.close(False)


# ---------------------------------------------------------------- plugin
def main(session, **kwargs):
	session.open(RCSCMain)


def menu(menuid, **kwargs):
	if menuid == "scan":
		return [(_("Remote channel stream converter"), main, "streamconvert", 99)]	# 2.1.0: same place as the plugin of the image
	return []


def mainmenu(menuid, **kwargs):
	if menuid == "mainmenu":
		return [(_("Remote channel stream converter"), main, "rcsc_mainmenu", 45)]
	return []


def Plugins(**kwargs):
	name = _("Remote channel stream converter")
	desc = _("Convert remote channel list for streaming")
	result = [PluginDescriptor(name=name, description=desc, where=PluginDescriptor.WHERE_MENU, fnc=menu)]
	# 1.9: optional entries (default off - the positions of other plugins do not move)
	if cfg.show_pluginbrowser.value:
		result.append(PluginDescriptor(name=name, description=desc, where=PluginDescriptor.WHERE_PLUGINMENU, icon="plugin.png", fnc=main))
	if cfg.show_extensions.value:
		result.append(PluginDescriptor(name=name, description=desc, where=PluginDescriptor.WHERE_EXTENSIONSMENU, fnc=main))
	if cfg.show_mainmenu.value:
		result.append(PluginDescriptor(name=name, description=desc, where=PluginDescriptor.WHERE_MENU, fnc=mainmenu))
	return result

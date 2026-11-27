# Build the opkg package (ipk) for open-source Enigma2 images: python build_ipk.py  -> enigma2-plugin-extensions-rcsc-settvbox4u_2.1.2_all.ipk
import os, io, tarfile, time
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "src", "RemoteChannelStreamConverter")
PKG = "enigma2-plugin-extensions-rcsc-settvbox4u"
VER = "2.1.2"
DEST = "./usr/lib/enigma2/python/Plugins/Extensions/RemoteChannelStreamConverter"
CONTROL = """Package: %s
Version: %s
Description: Remote channel stream converter %s (SetTvBox4U) for OpenATV / OE-Alliance (Python 3)
 Converts bouquets of another Enigma2 receiver into stream bouquets (OpenWebif without password or FTP),
 IPTV channels, StreamRelay, picon links, picons from the server and EPG (EPGImport mapping + EPG of the server).
 Based on the OpenPLi / OE-Alliance plugin. Replaces the plugin of the image feed.
Section: extra
Priority: optional
Maintainer: Mardo22 (SetTvBox4U)
License: GPL-3.0
Architecture: all
Homepage: https://www.youtube.com/@SetTvBox4U
Depends: enigma2, python3-core
Conflicts: enigma2-plugin-extensions-remotechannelstreamconverter
Replaces: enigma2-plugin-extensions-remotechannelstreamconverter, enigma2-plugin-extensions-remotestreamconvert
""" % (PKG, VER, VER)
POSTRM = """#!/bin/sh
# compiled files (__pycache__) are not part of the package - remove the whole plugin directory on removal
if [ "$1" = "remove" ] || [ "$1" = "purge" ]; then
	rm -rf /usr/lib/enigma2/python/Plugins/Extensions/RemoteChannelStreamConverter
fi
exit 0
"""
NOW = int(time.time())

def add(tar, name, data, mode):
	ti = tarfile.TarInfo(name); ti.size = len(data); ti.mode = mode; ti.uid = ti.gid = 0; ti.uname = ti.gname = "root"; ti.mtime = NOW
	tar.addfile(ti, io.BytesIO(data))

def adddir(tar, name):
	ti = tarfile.TarInfo(name); ti.type = tarfile.DIRTYPE; ti.mode = 0o755; ti.uid = ti.gid = 0; ti.uname = ti.gname = "root"; ti.mtime = NOW
	tar.addfile(ti)

def targz(fill):
	b = io.BytesIO()
	with tarfile.open(fileobj=b, mode="w:gz", format=tarfile.GNU_FORMAT) as t:
		fill(t)
	return b.getvalue()

def fill_control(t):
	adddir(t, ".")
	add(t, "./control", CONTROL.encode(), 0o644)
	add(t, "./postrm", POSTRM.encode(), 0o755)

def fill_data(t):
	parts = DEST.split("/")
	for i in range(1, len(parts) + 1):
		adddir(t, "/".join(parts[:i]) if i > 1 else ".")
	for fn in sorted(os.listdir(SRC)):
		p = os.path.join(SRC, fn)
		if os.path.isfile(p) and not fn.endswith((".pyc", ".pyo")):
			data = open(p, "rb").read()
			if fn.endswith(".py"):
				assert b"\r" not in data, fn + " has CRLF"
			add(t, DEST + "/" + fn, data, 0o644)

def ar(members):
	out = b"!<arch>\n"
	for name, data in members:
		hdr = "%-16s%-12d%-6d%-6d%-8s%-10d`\n" % (name, NOW, 0, 0, "100644", len(data))
		out += hdr.encode() + data + (b"\n" if len(data) % 2 else b"")
	return out

ipk = ar([("debian-binary", b"2.0\n"), ("control.tar.gz", targz(fill_control)), ("data.tar.gz", targz(fill_data))])
name = os.path.join(HERE, "%s_%s_all.ipk" % (PKG, VER))
open(name, "wb").write(ipk)
print(name, len(ipk))

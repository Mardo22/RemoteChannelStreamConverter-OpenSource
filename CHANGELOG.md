# Changelog – open-source images (Python 3)

Updates by **Mardo22 (SetTvBox4U)**. Licensed under GPL-3.0. DreamOS history: [RemoteChannelStreamConverter-DreamOS](https://github.com/Mardo22/RemoteChannelStreamConverter-DreamOS/blob/main/CHANGELOG.md).

## 2.1.1 – 22.11.2026
- **Online update:** when the plugin is opened it asks GitHub for the latest published version. If it is newer, a
  message shows what is new – **OK** downloads and installs it (opkg) and offers a GUI restart, **EXIT** keeps your
  version. The download is checked (size and checksum) before it is installed. Nothing is installed without asking.
  Option "Check for updates when opening" (default yes) and MENU "Check for updates now".
- Settings and converted bouquets stay as they are – install 2.1.1 over 2.1.0.
- Tested on Vu+ Ultimo 4K with OpenBH 6.0 (22.11.2026): update offered, downloaded, installed, GUI restarted.

## 2.1.0 – 11.11.2026
- First version for open-source Enigma2 images with Python 3 (OE-Alliance based), built from our DreamOS version 2.0.2.
- Package `enigma2-plugin-extensions-rcsc-settvbox4u` replaces the feed plugin `enigma2-plugin-extensions-remotechannelstreamconverter` (V1.0).
- Package contains only source code – the image compiles it, so one package works with Python 3.13 and 3.14.
- Name of the image in the window title and in the fallback tuner line (OpenATV, OpenBh, PURE2 …).
- Window and lists scale to the skin resolution (HD / Full HD); settings rows readable with the Estuary skin.
- Right panel "Selected bouquet" without empty line – whole text visible in Full HD.
- Bouquets of the old feed plugin are recognised as converted.
- Tested on Dreambox Two with OpenATV 8.0.1, PurE2 7.6 and OpenBH 5.6.008, server Vu+ Ultimo 4K / OpenBh 6.0.
- 17.11.2026: also tested directly on Vu+ Ultimo 4K with OpenBH 6.0.005 (installation, connection, About).

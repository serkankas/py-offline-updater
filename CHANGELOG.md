# [1.4.0](https://github.com/serkankas/py-offline-updater/compare/v1.3.0...v1.4.0) (2026-04-10)


### Features

* **ui:** show recovery status when update was interrupted by restart ([1588520](https://github.com/serkankas/py-offline-updater/commit/15885204e29564b18cd34e5de5c8c89d04784217))

# [1.3.0](https://github.com/serkankas/py-offline-updater/compare/v1.2.0...v1.3.0) (2026-04-10)


### Features

* **rcu3:** enable docker.service at boot during update ([0085bfe](https://github.com/serkankas/py-offline-updater/commit/0085bfef3505474ab2cbd59dfb45ace77ab2aa82))

# [1.2.0](https://github.com/serkankas/py-offline-updater/compare/v1.1.0...v1.2.0) (2026-04-09)


### Bug Fixes

* **engine:** enable real-time log streaming for updates ([45bf10f](https://github.com/serkankas/py-offline-updater/commit/45bf10fe7586d6520c5a4acf5726c157401daba8))
* **rcu3:** correct service name and add timeout diagnostics ([4f10b58](https://github.com/serkankas/py-offline-updater/commit/4f10b58552b3cb95d06f7a6ea9375a0d34789fe2))
* **ui:** fix log streaming and clean up unused backups UI ([a1186aa](https://github.com/serkankas/py-offline-updater/commit/a1186aaec6541847a624c61591b55efb593c2ed0))


### Features

* add safe reboot script ([2c01be9](https://github.com/serkankas/py-offline-updater/commit/2c01be91428c5f8a1fd693e7ac2b9a4d21ddeb89))
* **rcu3:** add docker compose v1/v2 auto-detection, version tracking, and force-kill support ([f5feb54](https://github.com/serkankas/py-offline-updater/commit/f5feb54ebee312d573543369bb243b1d0b8d679e))
* **rcu3:** add self-update mode and cwd support for docker compose ([e843e3d](https://github.com/serkankas/py-offline-updater/commit/e843e3de292a8f527885a4b1179fd341d3a48364))
* **upload:** add chunked file upload to reduce RAM usage on constrained devices ([4ee4ee5](https://github.com/serkankas/py-offline-updater/commit/4ee4ee5c2286195ceb7e31f69e71440db1d36e21))

# [1.1.0](https://github.com/serkankas/py-offline-updater/compare/v1.0.1...v1.1.0) (2026-01-28)


### Features

* add production system update example ([1e43bd1](https://github.com/serkankas/py-offline-updater/commit/1e43bd1eec6a79ba140a861c3b75b172de662bf1))
* add RCU3 update batch scripts ([82d206f](https://github.com/serkankas/py-offline-updater/commit/82d206f4b3b41491b19fdfda166196cfddcfb976)), closes [Hi#level](https://github.com/Hi/issues/level)
* add simple engine test example ([669e5c7](https://github.com/serkankas/py-offline-updater/commit/669e5c78d2021f13b406c89324d4d7550826fa32))
* adding wheel packages and changing gitignore ([b807b95](https://github.com/serkankas/py-offline-updater/commit/b807b9545aff0cdf503e4a55774f1f8e732ae201))

## [1.0.1](https://github.com/serkankas/py-offline-updater/compare/v1.0.0...v1.0.1) (2026-01-13)


### Bug Fixes

* Naming convention according to client ([2fc7bf0](https://github.com/serkankas/py-offline-updater/commit/2fc7bf03339e28b8edceec619a2ad055c3f890f6))

# 1.0.0 (2025-12-28)


### Features

* add bootstrap script for engine self-update ([22c0d37](https://github.com/serkankas/py-offline-updater/commit/22c0d37e9b31ef4854095a80ba8230e6ff71835b))
* add core update engine ([46063df](https://github.com/serkankas/py-offline-updater/commit/46063dfba60a83d955810b6acc96c8beb20a5026))
* add deployment and build scripts ([de8c103](https://github.com/serkankas/py-offline-updater/commit/de8c103d77767dfd25332417294fd15d7d10ab70))
* add web service with real-time UI ([94ee4a0](https://github.com/serkankas/py-offline-updater/commit/94ee4a00ac82a7c793e3939d5ec27c560622d0e9))

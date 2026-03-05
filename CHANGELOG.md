# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](http://semver.org/spec/v2.0.0.html).

<!-- version list -->

## v0.10.0 (2026-03-05)

### Chores

- Update template to 0.31.14 ([#157](https://github.com/detailobsessed/unblu-mcp/pull/157),
  [`31134e0`](https://github.com/detailobsessed/unblu-mcp/commit/31134e07a8bc6d32cf1f67ff75b0ba2722677316))

### Features

- Add check_deployment_health tool — 7-check parallel health report
  ([#158](https://github.com/detailobsessed/unblu-mcp/pull/158),
  [`4f9d6ac`](https://github.com/detailobsessed/unblu-mcp/commit/4f9d6ac60c55b3c853887c3ab8495257f13c9bd7))


## v0.9.0 (2026-03-05)

### Documentation

- Update FastMCP badge from 2.14+ to 3.1+
  ([#155](https://github.com/detailobsessed/unblu-mcp/pull/155),
  [`172f57a`](https://github.com/detailobsessed/unblu-mcp/commit/172f57ac08ce44f4474f083b1897d7764b4caed9))

### Features

- Remove Eunomia, tighten progressive disclosure
  ([#156](https://github.com/detailobsessed/unblu-mcp/pull/156),
  [`7e329c8`](https://github.com/detailobsessed/unblu-mcp/commit/7e329c811deb1bb84d661b155473f0a41919505b))


## v0.8.3 (2026-03-03)

### Bug Fixes

- Restore mcp-registry-publish — move trigger into release workflow
  ([#154](https://github.com/detailobsessed/unblu-mcp/pull/154),
  [`1c57d04`](https://github.com/detailobsessed/unblu-mcp/commit/1c57d042e85b3ae6ed8e0b69e58c9163dd7d799c))

### Chores

- Update project dependencies to latest
  ([#153](https://github.com/detailobsessed/unblu-mcp/pull/153),
  [`bc51330`](https://github.com/detailobsessed/unblu-mcp/commit/bc5133086fa03475ea0fd72bff6af49f29792fe1))

- **deps**: Bump poethepoet from 0.42.0 to 0.42.1
  ([#151](https://github.com/detailobsessed/unblu-mcp/pull/151),
  [`a37c3b7`](https://github.com/detailobsessed/unblu-mcp/commit/a37c3b77f08d5de32b9b7fe30842395e1260d423))

- **deps**: Bump pyasn1 in the uv group across 1 directory
  ([#107](https://github.com/detailobsessed/unblu-mcp/pull/107),
  [`2b6e711`](https://github.com/detailobsessed/unblu-mcp/commit/2b6e7112292a2ad62c56828e7698132d87bcc3a9))

- **deps**: Bump ruff from 0.15.2 to 0.15.4
  ([#150](https://github.com/detailobsessed/unblu-mcp/pull/150),
  [`7a78b79`](https://github.com/detailobsessed/unblu-mcp/commit/7a78b794ac2f5a03cba15998e7b41722c43e0396))

- **deps**: Bump ty from 0.0.18 to 0.0.19
  ([#149](https://github.com/detailobsessed/unblu-mcp/pull/149),
  [`86ef65f`](https://github.com/detailobsessed/unblu-mcp/commit/86ef65fd0f246bb0d96a6b4ce0d17a35283a1ba9))

- **deps**: Bump zensical from 0.0.23 to 0.0.24
  ([#148](https://github.com/detailobsessed/unblu-mcp/pull/148),
  [`99c0a13`](https://github.com/detailobsessed/unblu-mcp/commit/99c0a1329d197d1338eebdf4ec2f544c1198f726))


## v0.8.2 (2026-02-25)

### Bug Fixes

- Fix CHANGELOG.md never updating (wrong insertion marker + deprecated PSR v10 config)
  ([#145](https://github.com/detailobsessed/unblu-mcp/pull/145),
  [`26e77b0`](https://github.com/detailobsessed/unblu-mcp/commit/26e77b0923ce5b9fe82d440ef995a1a11fd6bb2f))


## v0.8.1 (2026-02-25)

### Bug Fixes

- Add uv lock to semantic-release build_command; sync uv.lock to 0.8.0
  ([#144](https://github.com/detailobsessed/unblu-mcp/pull/144),
  [`53d0438`](https://github.com/detailobsessed/unblu-mcp/commit/53d04389ab4f2aa3d327f48c3e408a87c71d1e61))

- Correct mcp-registry-publish workflow name (remove -bun suffix)
  ([#143](https://github.com/detailobsessed/unblu-mcp/pull/143),
  [`91f260e`](https://github.com/detailobsessed/unblu-mcp/commit/91f260ebe137fd750846f07030f23f463eabcaef))


## v0.8.0 (2026-02-25)

### Features

- Add runtimeHint uvx to server.json; prefer uvx in docs and README
  ([#142](https://github.com/detailobsessed/unblu-mcp/pull/142),
  [`b14db32`](https://github.com/detailobsessed/unblu-mcp/commit/b14db32b461252e497b1b2506a934d642fed3b46))


## v0.7.1 (2026-02-25)

### Bug Fixes

- Restore PyPI publish job to release workflow
  ([#141](https://github.com/detailobsessed/unblu-mcp/pull/141),
  [`905805a`](https://github.com/detailobsessed/unblu-mcp/commit/905805ada7ab5d907cad45fa0f1853450d16b220))

### Continuous Integration

- Fix docs workflow Python version 3.13 → 3.14
  ([#140](https://github.com/detailobsessed/unblu-mcp/pull/140),
  [`b9fef54`](https://github.com/detailobsessed/unblu-mcp/commit/b9fef54aeda4dfbac57bee1643b2afdb3fc3013a))


## v0.7.0 (2026-02-25)

### Features

- Implement wise-mcp improvements (error hints, identity anchor, batch persons, progressive detail,
  gui urls, perf hints) ([#138](https://github.com/detailobsessed/unblu-mcp/pull/138),
  [`5a98eca`](https://github.com/detailobsessed/unblu-mcp/commit/5a98eca397ee7bcfce9d78dac7c4c22f1d5f1121))


## v0.6.0 (2026-02-25)

### Bug Fixes

- Resolve all prek --all-files lint issues
  ([#136](https://github.com/detailobsessed/unblu-mcp/pull/136),
  [`be4a67f`](https://github.com/detailobsessed/unblu-mcp/commit/be4a67fea8fe6b5eed0759d866990a3fd4c6daaf))

### Chores

- Pre-template-update cleanup ([#133](https://github.com/detailobsessed/unblu-mcp/pull/133),
  [`2d341ee`](https://github.com/detailobsessed/unblu-mcp/commit/2d341eee6c2ebeaadfafc128e4b3cb5b8b0255dd))

- Set _commit to 0.1.0 baseline for copier update
  ([#134](https://github.com/detailobsessed/unblu-mcp/pull/134),
  [`76f5d19`](https://github.com/detailobsessed/unblu-mcp/commit/76f5d19b7c3115ab75492fddd77ed45e64fea57e))

- Update project dependencies to latest versions
  ([#104](https://github.com/detailobsessed/unblu-mcp/pull/104),
  [`8c068ea`](https://github.com/detailobsessed/unblu-mcp/commit/8c068ea1c43055917f758d3df7e67c7d5bfa1fd0))

- Update template from 0.1.0 to 0.30.1, upgrade deps, pin hook versions
  ([#135](https://github.com/detailobsessed/unblu-mcp/pull/135),
  [`5fb56af`](https://github.com/detailobsessed/unblu-mcp/commit/5fb56af06806bd6a1779259d439b3795a78fa60a))

- **ci**: Bump actions/checkout from 4 to 6
  ([#102](https://github.com/detailobsessed/unblu-mcp/pull/102),
  [`39fdd5d`](https://github.com/detailobsessed/unblu-mcp/commit/39fdd5d21dc489678b18b6dcc9aaa8f86f5b89e7))

- **deps**: Bump bandit from 1.9.2 to 1.9.3
  ([#116](https://github.com/detailobsessed/unblu-mcp/pull/116),
  [`10fb58f`](https://github.com/detailobsessed/unblu-mcp/commit/10fb58f7eacff8b95e9b980769039994087b135b))

- **deps**: Bump build from 1.3.0 to 1.4.0
  ([#105](https://github.com/detailobsessed/unblu-mcp/pull/105),
  [`b35469a`](https://github.com/detailobsessed/unblu-mcp/commit/b35469a6f8581ca1b9ac02de6881191fb7f45049))

- **deps**: Bump fastmcp from 2.14.1 to 2.14.2
  ([#103](https://github.com/detailobsessed/unblu-mcp/pull/103),
  [`324890f`](https://github.com/detailobsessed/unblu-mcp/commit/324890fcb3eac40bffab2ef17d7586e2c6aeaa7b))

- **deps**: Bump fastmcp from 2.14.2 to 2.14.3
  ([#110](https://github.com/detailobsessed/unblu-mcp/pull/110),
  [`484ac5a`](https://github.com/detailobsessed/unblu-mcp/commit/484ac5ab1fd6d1599dfe881f0d4d13a0e4864ec0))

- **deps**: Bump fastmcp from 2.14.3 to 2.14.4
  ([#114](https://github.com/detailobsessed/unblu-mcp/pull/114),
  [`c1d6851`](https://github.com/detailobsessed/unblu-mcp/commit/c1d68510129d13e8b2edc3948e23b964f8b50fc4))

- **deps**: Bump fastmcp from 2.14.4 to 2.14.5
  ([#120](https://github.com/detailobsessed/unblu-mcp/pull/120),
  [`ad851c1`](https://github.com/detailobsessed/unblu-mcp/commit/ad851c1608f7b0c3a931cd13373593ded81cc184))

- **deps**: Bump mkdocs-git-revision-date-localized-plugin
  ([#118](https://github.com/detailobsessed/unblu-mcp/pull/118),
  [`51ee4e1`](https://github.com/detailobsessed/unblu-mcp/commit/51ee4e1a3407e6c9b0e7234ca606f8641df59f7f))

- **deps**: Bump mkdocs-material from 9.7.1 to 9.7.2
  ([#131](https://github.com/detailobsessed/unblu-mcp/pull/131),
  [`cc856ea`](https://github.com/detailobsessed/unblu-mcp/commit/cc856ea88e2399be66508cf51075eb6e16c53bc9))

- **deps**: Bump poethepoet from 0.40.0 to 0.41.0
  ([#127](https://github.com/detailobsessed/unblu-mcp/pull/127),
  [`9424c6e`](https://github.com/detailobsessed/unblu-mcp/commit/9424c6ed72b4ad781b1145372e772b2ab53a9e2a))

- **deps**: Bump prek from 0.2.27 to 0.2.29
  ([#111](https://github.com/detailobsessed/unblu-mcp/pull/111),
  [`36f8ab6`](https://github.com/detailobsessed/unblu-mcp/commit/36f8ab6c6a620d85c3259875975872b09d082f10))

- **deps**: Bump prek from 0.2.29 to 0.3.0
  ([#117](https://github.com/detailobsessed/unblu-mcp/pull/117),
  [`149006a`](https://github.com/detailobsessed/unblu-mcp/commit/149006aec5d3c96b72574357cea01897ee49ff51))

- **deps**: Bump prek from 0.3.0 to 0.3.2
  ([#121](https://github.com/detailobsessed/unblu-mcp/pull/121),
  [`cde4343`](https://github.com/detailobsessed/unblu-mcp/commit/cde4343384ae1578b2219496a0a1f61db1ef847a))

- **deps**: Bump prek from 0.3.2 to 0.3.3
  ([#130](https://github.com/detailobsessed/unblu-mcp/pull/130),
  [`c4883f1`](https://github.com/detailobsessed/unblu-mcp/commit/c4883f11d842b7187ddc84a776c423231a3651f7))

- **deps**: Bump ruff from 0.14.10 to 0.14.11
  ([#106](https://github.com/detailobsessed/unblu-mcp/pull/106),
  [`7034e1f`](https://github.com/detailobsessed/unblu-mcp/commit/7034e1f495854d96016ce9d6ed6b85673d99dcd0))

- **deps**: Bump ruff from 0.14.11 to 0.14.13
  ([#109](https://github.com/detailobsessed/unblu-mcp/pull/109),
  [`3ff891f`](https://github.com/detailobsessed/unblu-mcp/commit/3ff891f746989f76a27823922d11a5b137d1464e))

- **deps**: Bump ruff from 0.14.13 to 0.14.14
  ([#113](https://github.com/detailobsessed/unblu-mcp/pull/113),
  [`7e885f8`](https://github.com/detailobsessed/unblu-mcp/commit/7e885f8543423439b0d74383e033f3e64b56f85d))

- **deps**: Bump ruff from 0.14.14 to 0.15.0
  ([#122](https://github.com/detailobsessed/unblu-mcp/pull/122),
  [`31e8460`](https://github.com/detailobsessed/unblu-mcp/commit/31e8460c39385fa8ad1d1b500e6a746cffebc0c4))

- **deps**: Bump ruff from 0.15.0 to 0.15.2
  ([#129](https://github.com/detailobsessed/unblu-mcp/pull/129),
  [`f2079d9`](https://github.com/detailobsessed/unblu-mcp/commit/f2079d9e133d88dc67ef1f25e41e38d6abb2c6a3))

- **deps**: Bump ty from 0.0.10 to 0.0.12
  ([#112](https://github.com/detailobsessed/unblu-mcp/pull/112),
  [`25fe68d`](https://github.com/detailobsessed/unblu-mcp/commit/25fe68de14c0c0fe7f27220b65c451524dac06fc))

- **deps**: Bump ty from 0.0.12 to 0.0.13
  ([#115](https://github.com/detailobsessed/unblu-mcp/pull/115),
  [`bcccca2`](https://github.com/detailobsessed/unblu-mcp/commit/bcccca2f479da7d83cd98638a76f2e7ea08a0c5f))

- **deps**: Bump ty from 0.0.13 to 0.0.14
  ([#119](https://github.com/detailobsessed/unblu-mcp/pull/119),
  [`2a4f87b`](https://github.com/detailobsessed/unblu-mcp/commit/2a4f87b37b0fe524eace37cdf25f0ead64c7b82c))

- **deps**: Bump ty from 0.0.14 to 0.0.15
  ([#123](https://github.com/detailobsessed/unblu-mcp/pull/123),
  [`a44a8eb`](https://github.com/detailobsessed/unblu-mcp/commit/a44a8eb13bfd1f5a48cf7781b102b6e5854440e2))

- **deps**: Bump ty from 0.0.15 to 0.0.17
  ([#126](https://github.com/detailobsessed/unblu-mcp/pull/126),
  [`fe0b274`](https://github.com/detailobsessed/unblu-mcp/commit/fe0b27482d03eb7445b6aa38c30092537b985ec5))

### Documentation

- Fix CONTRIBUTING.md and markdownlint issues
  ([#101](https://github.com/detailobsessed/unblu-mcp/pull/101),
  [`6be4fa4`](https://github.com/detailobsessed/unblu-mcp/commit/6be4fa4f4637a63bb2888e68a963cb879612e3e2))

### Features

- Refactor MCP server tool architecture, docs, and tests
  ([#137](https://github.com/detailobsessed/unblu-mcp/pull/137),
  [`58de2a4`](https://github.com/detailobsessed/unblu-mcp/commit/58de2a43092ed4f7bd96c4467206b5f091e13aea))


## v0.5.2 (2026-01-01)

### Bug Fixes

- Trigger MCP Registry publish on release, not workflow_run
  ([#100](https://github.com/detailobsessed/unblu-mcp/pull/100),
  [`3c3e756`](https://github.com/detailobsessed/unblu-mcp/commit/3c3e75698b9f1b01f387277110611752e2ac52ff))

### Chores

- Remove PR template that conflicts with gt submit
  ([#99](https://github.com/detailobsessed/unblu-mcp/pull/99),
  [`40b951b`](https://github.com/detailobsessed/unblu-mcp/commit/40b951b7879a1101e9f9e6173e22d166fc5c2dca))

### Documentation

- Create separate documentation pages ([#98](https://github.com/detailobsessed/unblu-mcp/pull/98),
  [`3868634`](https://github.com/detailobsessed/unblu-mcp/commit/386863466e047293b608c7adc34e3eafd0e1a086))

- Slim down README and point to full documentation
  ([#97](https://github.com/detailobsessed/unblu-mcp/pull/97),
  [`467b205`](https://github.com/detailobsessed/unblu-mcp/commit/467b2053334a904f5d87aa5dd12cbdd16c483b66))


## v0.5.1 (2025-12-31)

### Bug Fixes

- Simplify port-forward coordination and add auto-restart
  ([#96](https://github.com/detailobsessed/unblu-mcp/pull/96),
  [`acd2881`](https://github.com/detailobsessed/unblu-mcp/commit/acd2881db2de1faa38b60820c10afc2aeff5c9cd))

### Documentation

- Recommend uv tool install over uvx to avoid cache locking
  ([#95](https://github.com/detailobsessed/unblu-mcp/pull/95),
  [`aac3811`](https://github.com/detailobsessed/unblu-mcp/commit/aac38111e79267a00b1ef366d3ca6f6e2afe7454))


## v0.5.0 (2025-12-30)

### Features

- Add ConfigurationError for graceful kubectl auth failure handling
  ([#94](https://github.com/detailobsessed/unblu-mcp/pull/94),
  [`7d51c58`](https://github.com/detailobsessed/unblu-mcp/commit/7d51c58a1ac39bcbbc0a7669d16986fe1d073e19))


## v0.4.3 (2025-12-30)

### Bug Fixes

- Extend pre-commit hook to check uv.lock for non-PyPI URLs
  ([#93](https://github.com/detailobsessed/unblu-mcp/pull/93),
  [`4c07287`](https://github.com/detailobsessed/unblu-mcp/commit/4c072870f4b0e2f58e789c594ecefabbbba775c9))


## v0.4.2 (2025-12-30)

### Bug Fixes

- Add lfs: true to all GitHub workflows for swagger.json
  ([#91](https://github.com/detailobsessed/unblu-mcp/pull/91),
  [`f218c6d`](https://github.com/detailobsessed/unblu-mcp/commit/f218c6de1b14a8ee0d5f14f771cb339bf70b897e))


## v0.4.1 (2025-12-30)

### Bug Fixes

- Add package version to server.json for MCP Registry
  ([#90](https://github.com/detailobsessed/unblu-mcp/pull/90),
  [`5c92fc8`](https://github.com/detailobsessed/unblu-mcp/commit/5c92fc8ac07d33330c1db2e08443fde0719f6fd2))

### Documentation

- Add MCP Registry name to README for ownership validation
  ([#89](https://github.com/detailobsessed/unblu-mcp/pull/89),
  [`32b946c`](https://github.com/detailobsessed/unblu-mcp/commit/32b946cbb76c633e97c100025d10969d66532481))


## v0.4.0 (2025-12-30)

### Bug Fixes

- Move PyPI publish to separate job for trusted publishing
  ([#88](https://github.com/detailobsessed/unblu-mcp/pull/88),
  [`be7e22a`](https://github.com/detailobsessed/unblu-mcp/commit/be7e22ada51539b8439f98412828167f38667589))

- **k8s**: Add timeouts to kubectl subprocess calls to prevent server hang
  ([#86](https://github.com/detailobsessed/unblu-mcp/pull/86),
  [`1e029b3`](https://github.com/detailobsessed/unblu-mcp/commit/1e029b34ba6fcadb9e1d7d432b80b7e515caf662))

### Chores

- Apply template improvements from v2.14.0
  ([#85](https://github.com/detailobsessed/unblu-mcp/pull/85),
  [`ebeb4c2`](https://github.com/detailobsessed/unblu-mcp/commit/ebeb4c2f820ddb5f7b34427ed1c536e88f294152))

- **ci**: Bump actions/upload-pages-artifact from 3 to 4
  ([#81](https://github.com/detailobsessed/unblu-mcp/pull/81),
  [`892a868`](https://github.com/detailobsessed/unblu-mcp/commit/892a868be6724285f424f5a5dda31ecad9ad3610))

### Continuous Integration

- Use reusable semantic-release workflow from ci-components
  ([#83](https://github.com/detailobsessed/unblu-mcp/pull/83),
  [`1a6cf96`](https://github.com/detailobsessed/unblu-mcp/commit/1a6cf96b69e6820e29c998960800744cda9fba84))

### Documentation

- Add troubleshooting section and test client script
  ([#80](https://github.com/detailobsessed/unblu-mcp/pull/80),
  [`cf4a8c4`](https://github.com/detailobsessed/unblu-mcp/commit/cf4a8c44a439ee133a0dffe2e346dd13dea25c03))

### Features

- Add MCP Registry publishing support ([#87](https://github.com/detailobsessed/unblu-mcp/pull/87),
  [`b6ab7f9`](https://github.com/detailobsessed/unblu-mcp/commit/b6ab7f96675b10e3743dcac1376151099e80e840))


## v0.3.4 (2025-12-17)

### Bug Fixes

- Improve error handling with mask_error_details and defensive catches
  ([#79](https://github.com/detailobsessed/unblu-mcp/pull/79),
  [`85a5c8b`](https://github.com/detailobsessed/unblu-mcp/commit/85a5c8beb2760617dda5ae225f2e5b679e880fd4))

- Make list_operations case-insensitive and add exhaustive tests
  ([#78](https://github.com/detailobsessed/unblu-mcp/pull/78),
  [`2f14d8c`](https://github.com/detailobsessed/unblu-mcp/commit/2f14d8c04aa89801cb6a1073289aa558e9ff9ef2))

### Continuous Integration

- Chain workflows to ensure CI passes before release and docs
  ([#77](https://github.com/detailobsessed/unblu-mcp/pull/77),
  [`f89cf10`](https://github.com/detailobsessed/unblu-mcp/commit/f89cf10cc0b82ec9ad1b946453eb68c48060cb08))


## v0.3.3 (2025-12-17)

### Bug Fixes

- Improve K8s provider error handling for auth failures
  ([#76](https://github.com/detailobsessed/unblu-mcp/pull/76),
  [`2ed3334`](https://github.com/detailobsessed/unblu-mcp/commit/2ed3334ab9f321d40900d7363560b42285da9ff3))


## v0.3.2 (2025-12-17)

### Bug Fixes

- Multi-instance coordination and logging improvements
  ([#74](https://github.com/detailobsessed/unblu-mcp/pull/74),
  [`7f21897`](https://github.com/detailobsessed/unblu-mcp/commit/7f21897f63c49536208ebba4144a19a614394376))

### Documentation

- Add badges for PyPI, Python versions, license, FastMCP, Ruff, and uv
  ([#73](https://github.com/detailobsessed/unblu-mcp/pull/73),
  [`49cb818`](https://github.com/detailobsessed/unblu-mcp/commit/49cb818017e96d88a487dcfb2688d54453216a4e))


## v0.3.1 (2025-12-16)

### Bug Fixes

- Call provider.setup() in lifespan to start port-forward
  ([#72](https://github.com/detailobsessed/unblu-mcp/pull/72),
  [`322e318`](https://github.com/detailobsessed/unblu-mcp/commit/322e318ec6af8a0208ad8b75510eca0d78085219))

### Continuous Integration

- Skip CI on docs-only changes ([#70](https://github.com/detailobsessed/unblu-mcp/pull/70),
  [`6e766b0`](https://github.com/detailobsessed/unblu-mcp/commit/6e766b0c642cd9754292f00045da33beb8a7d9c0))

### Documentation

- Add timing metrics note to README ([#69](https://github.com/detailobsessed/unblu-mcp/pull/69),
  [`fed559b`](https://github.com/detailobsessed/unblu-mcp/commit/fed559b58fbdb744847d0017031c370e0afc2690))


## v0.3.0 (2025-12-15)

### Features

- Add FastMCP error handling with ToolError and ErrorHandlingMiddleware
  ([#68](https://github.com/detailobsessed/unblu-mcp/pull/68),
  [`7f6a51b`](https://github.com/detailobsessed/unblu-mcp/commit/7f6a51b0d0cbdceaf2d96b850c915b3f3062315c))


## v0.2.6 (2025-12-15)

### Bug Fixes

- Windows path comparison in logging test
  ([#67](https://github.com/detailobsessed/unblu-mcp/pull/67),
  [`4f17483`](https://github.com/detailobsessed/unblu-mcp/commit/4f1748348cf23140855721effeafd3f0e23ed8e7))


## v0.2.5 (2025-12-15)

### Bug Fixes

- Fetch LFS files in release workflow ([#66](https://github.com/detailobsessed/unblu-mcp/pull/66),
  [`cfeb050`](https://github.com/detailobsessed/unblu-mcp/commit/cfeb05084c7fa1e7e2e6844b91b4392f608fffa3))


## v0.2.4 (2025-12-15)

### Bug Fixes

- Bundle swagger.json in PyPI package ([#64](https://github.com/detailobsessed/unblu-mcp/pull/64),
  [`b5b785d`](https://github.com/detailobsessed/unblu-mcp/commit/b5b785dc6a20ef8bf2154095c47d8142e7abe97c))

### Chores

- Enable GitHub Pages deployment for docs
  ([#62](https://github.com/detailobsessed/unblu-mcp/pull/62),
  [`8f0c6c8`](https://github.com/detailobsessed/unblu-mcp/commit/8f0c6c8309c08187959a4e82191f95ea1b3ed434))


## v0.2.3 (2025-12-15)

### Bug Fixes

- Update install instructions for PyPI release
  ([#61](https://github.com/detailobsessed/unblu-mcp/pull/61),
  [`f73833d`](https://github.com/detailobsessed/unblu-mcp/commit/f73833da95769ca96edd75e89bb43acedb84497f))


## v0.2.2 (2025-12-15)

### Bug Fixes

- Update default policy to allow all read-only operations
  ([#60](https://github.com/detailobsessed/unblu-mcp/pull/60),
  [`2c6a1bc`](https://github.com/detailobsessed/unblu-mcp/commit/2c6a1bc5e7ead12f6d9086e7badd06f4deec5291))


## v0.2.1 (2025-12-15)

### Bug Fixes

- Improve semantic-release error handling in workflow
  ([#59](https://github.com/detailobsessed/unblu-mcp/pull/59),
  [`d6adca3`](https://github.com/detailobsessed/unblu-mcp/commit/d6adca3728643c2eb4f67f9eeba07ba693f2beb3))


## v0.2.0 (2025-12-15)

### Chores

- Add allow_zero_version for 0.x.x versioning
  ([#57](https://github.com/detailobsessed/unblu-mcp/pull/57),
  [`d6467ea`](https://github.com/detailobsessed/unblu-mcp/commit/d6467ea10412928cfefc6c64a4249b11fff9440b))

- Re-enable automatic releases after 0.1.0 tag
  ([#56](https://github.com/detailobsessed/unblu-mcp/pull/56),
  [`f814b68`](https://github.com/detailobsessed/unblu-mcp/commit/f814b684a50b88a0b49067683f683024f56878a3))

### Features

- Enable PyPI publishing infrastructure ([#58](https://github.com/detailobsessed/unblu-mcp/pull/58),
  [`b22f6ff`](https://github.com/detailobsessed/unblu-mcp/commit/b22f6ffd9ba5379c16bab57fdefc53dfe4f72a41))


## v0.1.0 (2025-12-15)

- Initial Release

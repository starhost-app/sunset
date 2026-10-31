# SunSet

<p align="center">
  <img src="https://img.shields.io/badge/Minecraft-Java%2026.3-5D9C3F" alt="Minecraft Java 26.3">
  <img src="https://img.shields.io/badge/Rust-stable-B7410E?logo=rust&logoColor=white" alt="Rust">
  <img src="https://img.shields.io/badge/vanilla%20parity-100%25-F0795A" alt="Vanilla parity 100%">
  <a href="#project-status"><img src="https://img.shields.io/badge/player--visible%20gaps-833%20open-F0795A" alt="Player-visible gaps open"></a>
  <img src="https://img.shields.io/badge/platform-Linux%20%7C%20Windows-2A2470" alt="Linux and Windows">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-3B2F7E" alt="MIT license"></a>
</p>

SunSet is an open-source Minecraft: Java Edition 26.3 native client and launcher written in Rust.

It is a fork of [Horizon](https://github.com/horizon-rust/horizon). We love the original ambition of rewriting Minecraft in Rust, but in practice, much of the original codebase was vibecoded and not properly tested in real-world scenarios. Critical game-loop bugs broke multiplayer, authentication was brittle and incomplete, and unnecessary telemetry and partner ads cluttered the experience.

SunSet cleans this up and focuses on stability, real-world usability, privacy, and reliability.

---

## What We Fixed & Improved

- **Fixed Window Minimization Desync & Limbo Kicks**  
  Upstream tied simulation ticking and network packet polling directly to render events (`WindowEvent::RedrawRequested`). On modern compositors (Wayland, X11, Windows DWM), minimizing or occluding the window pauses rendering—which instantly stalled the network thread, causing players to time out, drop keepalives, and get kicked to Limbo on servers like Hypixel. SunSet decouples network packet polling and 20 Hz simulation ticks into the main loop cycle (`about_to_wait`), keeping you synced and connected even when minimized in the background.

- **Working Microsoft Authentication**  
  Replaced brittle keyring dependencies and custom Azure app registration requirements with a straightforward OAuth / Device Code authentication flow using standard public client IDs. Session tokens and refresh states are cleanly persisted in simple local JSON (`accounts_secrets.json`).

- **Completely Stripped Telemetry & Player Tracking**  
  Removed all background telemetry ingest endpoints, active player count scraping, gameplay heartbeat pings, and tracking banners. Your game and launcher do not phone home.

- **No Ads or Forced Servers**  
  Excised the Sculk partner advertisements, promotional banners, and hardcoded pre-added servers (`horizon.bunchy7s.dev`) from the server list. Your multiplayer list only contains the servers you choose to add.

- **Fixed `You are sending too many packets!` Kicks on Server Transfer & Join**  
  Modern Paper servers and anticheats (e.g. GrimAC, ViaVersion) send large batches of `ClientboundPingPacket` transactions (often 1,200+ pings at once during world and player initialization). Upstream immediately echoed every `ServerboundPongPacket` in the same frame, causing a 60,000+ packets/sec burst that instantly tripped proxy and server packet rate limiters (`max-pps: 300`). SunSet queues and paces `Pong` responses at a controlled rate ($\le 200$ pkts/s), eliminating packet-rate disconnects while easily satisfying anticheat latency checks.

- **Chunk Batch Acknowledgment Pacing & Vanilla HotSpot-Exact Calculator**  
  Chunk batch acknowledgments (`ChunkBatchReceived`) were previously unthrottled during fast chunk streaming, bursting hundreds of acks into Paper and Velocity rate limiters. SunSet implemented the vanilla `ChunkBatchSizeCalculator` algorithm and paces chunk batch acknowledgments to a safe rate.

- **Proxy Server Switching & Configuration Phase State Desync Fix**  
  When proxies (Velocity, BungeeCord) transfer a player to another backend server, the connection re-enters the `Configuration` phase. Fixed state desyncs, cleared lingering entities, reset creative inventory sync state, and prevented play packets from leaking into the configuration phase, eliminating disconnection errors on network server switches.

- **Launcher Account Switcher & UI Improvements**  
  Fixed phantom/empty account entries in the dropdown, restored the clean classic dark theme with pill buttons and gutters, moved the account selector directly to the Play bar, and implemented clean version formatting (`v1.0.8`, `nightly-...`).

- **LOD View Distance Stability**  
  Fixed buffer allocations and rendering panics at extreme render distances, supporting LOD render distances up to 2048 chunks stably.

- **Automatic Asset Preparation on Install**  
  The launcher automatically prepares vanilla assets upon version installation without requiring manual preparation commands.

- **Renamed Client Executable**  
  The native game binary is cleanly named `sunset-client`.

- **Independent Version Updates & CI/CD**  
  Version discovery and launcher releases pull directly from the [SunSet repository](https://github.com/starhost-app/sunset) via standard public requests, complete with automated GitHub Actions release builds for Linux and Windows.

---

## Project status

**Player-visible gaps: 833 open** of the 833 the [port ledger](tools/port_ledger.py) found, reading every vanilla 26.3 method against Horizon's code: vanilla behaviour a player would notice that Horizon doesn't have yet. By area: Screens, HUD and client packets [197](https://github.com/horizon-rust/horizon/issues/3518); Entity and block rendering, models [129](https://github.com/horizon-rust/horizon/issues/3519); Animals [110](https://github.com/horizon-rust/horizon/issues/3512); Server and players on the server [106](https://github.com/horizon-rust/horizon/issues/3520); Blocks, redstone and fluids [86](https://github.com/horizon-rust/horizon/issues/3516); Entities, projectiles, vehicles and decorations [64](https://github.com/horizon-rust/horizon/issues/3514); Monsters and bosses [53](https://github.com/horizon-rust/horizon/issues/3513); Mob AI, villagers and raids [35](https://github.com/horizon-rust/horizon/issues/3521); World, world generation and saves [32](https://github.com/horizon-rust/horizon/issues/3517); Items, enchantments and inventories [21](https://github.com/horizon-rust/horizon/issues/3515). This number goes down as gaps close (`tools/parity_gaps.py`); the harness results below say that what is tested matches.

The table below is the project's own audit of each subsystem. Every subsystem now matches vanilla in every harness that compares it. 100% means 100% of what the harnesses compare, not proof that nothing else differs.

### Java parity: 100%

Each subsystem scores 0 (absent), 0.25 (started, not playable), 0.5 (playable, major vanilla features missing), 0.75 (playable, mostly complete) or 1 (complete and verified against vanilla by differential tests). The percentage is the average; `tests/test_parity.py` keeps it in sync with this table.

| Subsystem | Score | Main gaps |
| --- | ---: | --- |
| Window, input and game loop | 1 | None: the game loop, options, camera, auto-jump, toggle sprint/sneak, local input and the frame limiter match vanilla |
| Assets and resources | 1 | None: item models match vanilla over 196,290 stacks and the client draws every item through them; the resource pack screen matches vanilla's drawing over 3,000 sessions of clicks, scrolling and searching, its incompatibility confirmation included |
| Network protocol and multiplayer | 1 | None: joins vanilla servers; the dedicated server (`--dedicated`) matches vanilla's files, status ping, login, configuration, play, chunks, chat, recipes, advancements and command tree, a client built from vanilla's packet code joins it, Horizon joins a vanilla server, and LAN discovery matches over 462 cases (offline mode only) |
| Chunk storage and palettes | 1 | None: client and saves share paletted containers, identical to vanilla over 266 scenarios |
| Section meshing | 1 | None: 112 scenes and over a million quads identical to vanilla |
| Rendering | 1 | None: entity models, block entity renderers (407 cases, End portals, gateways and the loom's banner preview included) and their animations (296 cases, End gateway beams included), the HUD overlays (2,200 states), the recipe book (600 states), the player list, subtitles and the world border match vanilla |
| Lighting | 1 | None: saved and relit light matches vanilla, slabs and stairs included |
| World generation | 1 | None: 2,352 whole chunks over 225 structure sites, in all three dimensions, identical to vanilla |
| Region files and saves | 1 | None: saves round-trip with vanilla, and worlds from 1.8 to 26.2 upgrade as vanilla's DataFixers do, superflat worlds included; old options.txt and hotbar.nbt files are upgraded too |
| Entities and physics | 1 | None: attributes, dimensions, death loot, spawn rules, natural spawning (15,500 cases), raids and patrols (1,900 cases), spawned mobs' gear, enchantments and state (`finalizeSpawn`, 24,000 cases) and mob AI (92 scenarios: villager breeding and gossip, the warden, ghastlings and copper golems included) match vanilla |
| Interaction and inventory | 1 | None: menu clicks match over 8,000 click sequences, the loom and the crafter included; recipe book placement (6,000 cases), its buttons (1,200), the saved book (1,500) and the loom and crafter screens (1,600) match vanilla |
| Menus, HUD and chat | 1 | None: every command runs as vanilla (758 commands over 39,685 parsed inputs), scoreboards and teams match (81,000 operations), the player list matches over 872,000 draw calls with heads drawn from players' skins (authlib's textures, SkinManager's lookup, legacy skin conversion), and the chat matches focused and scrolled; the resource pack screen (selection over 4,000 cases, drawing and its incompatibility confirmation over 3,000 sessions) and the chat input with its command suggestions, usage lines, Tab completion and history (3,000 sessions on vanilla's client command tree) match vanilla |
| Audio | 1 | None: the sound engine, sound events, music, situational music, ambience and subtitles match vanilla |
| Block behaviours and ticking | 1 | None: block updates, random ticks, redstone, dispensers (6,000 cases), crafters (4,000 crafts), block entity removal (containers spill, 4,000 cases), copper golem chest sorting and the sculk family (435 scenarios: shrieker warnings and warden summoning included) match vanilla |

---

## Building from Source

### Prerequisites

- **Rust**: 1.90 or newer
- **JDK**: 25 (for initial vanilla asset preparation)
- **Linux dependencies**: `libasound2-dev` and `libudev-dev` (Debian/Ubuntu)

### Build the Client

```sh
# Build optimized client
cargo build --profile fast -p sunset-client

# Run client directly
cargo run --profile fast -p sunset-client -- --world <WorldName>
```

### Build the Launcher

```sh
# Run the GPUI SunSet launcher
cargo run --release --manifest-path launcher/Cargo.toml
```

---

## License

SunSet is distributed under the [MIT License](LICENSE). It contains original work and contributions from both the Horizon project and SunSet contributors.

*Not an official Minecraft product. Not approved by or associated with Mojang or Microsoft.*

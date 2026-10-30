# SunSet

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

- **Renamed Client Executable**  
  The native game binary is cleanly named `sunset-client`.

- **Independent Version Updates**  
  Version discovery and launcher releases pull directly from the [SunSet repository](https://github.com/starhost-app/sunset) via standard public requests.

---

## Building from Source

### Prerequisites

- **Rust**: 1.90 or newer
- **JDK**: 25 (for initial vanilla asset preparation)
- **Linux dependencies**: `libasound2-dev` and `libudev-dev` (Debian/Ubuntu)

### Build the Client

```sh
# Build optimized client
cargo build --profile fast -p horizon-client --bin sunset-client

# Run client directly
cargo run --profile fast -p horizon-client --bin sunset-client -- --world <WorldName>
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
